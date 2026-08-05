import os
from pathlib import Path

from playwright.sync_api import sync_playwright


class BrowserManager:
    """
    Shared Playwright browser manager.

    LOCAL:
        Uses persistent browser profiles by default so existing
        authenticated sessions can be reused.

        LinkedIn -> browser-data/
        Naukri   -> browser-data-naukri/

    APIFY / CLOUD:
        Set BROWSER_PERSISTENT=false.

        This launches a fresh browser context and does not depend
        on browser-data directories from the local machine.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        profile_name: str = "browser-data",
        persistent: bool | None = None,
    ):
        self.profile_name = profile_name

        # Keep existing local behaviour by default.
        #
        # Local:
        #   BROWSER_PERSISTENT is normally not set
        #   -> persistent=True
        #
        # Apify:
        #   Dockerfile sets BROWSER_PERSISTENT=false
        #   -> persistent=False
        if persistent is None:
            value = os.getenv(
                "BROWSER_PERSISTENT",
                "true",
            ).strip().lower()

            persistent = value not in {
                "false",
                "0",
                "no",
            }

        self.persistent = persistent

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def launch(
        self,
        headless: bool = True,
        block_resources: bool = True,
        proxy_url: str | None = None,
    ):
        self.playwright = sync_playwright().start()

        context_options = {
            "viewport": {
                "width": 1440,
                "height": 900,
            },
            "locale": "en-US",
            "timezone_id": "Asia/Kolkata",
            "user_agent": self.USER_AGENT,
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        if self.persistent:
            self._launch_persistent(
                headless=headless,
                context_options=context_options,
                proxy_url=proxy_url,
            )
        else:
            self._launch_ephemeral(
                headless=headless,
                context_options=context_options,
                proxy_url=proxy_url,
            )

        # Keep the existing resource-blocking behaviour.
        #
        # Naukri currently calls launch(block_resources=False),
        # so its stylesheets/fonts/images are still allowed.
        if block_resources:
            self.context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in {
                        "image",
                        "font",
                        "media",
                        "stylesheet",
                    }
                    else route.continue_()
                ),
            )

        self.page = (
            self.context.pages[0]
            if self.context.pages
            else self.context.new_page()
        )

        self.page.set_default_timeout(10000)
        self.page.set_default_navigation_timeout(20000)

        return self.page

    def _launch_persistent(
        self,
        headless: bool,
        context_options: dict,
        proxy_url: str | None = None,
    ):
        """
        Persistent local browser profile.

        This preserves the current local login/session behaviour.
        """

        profile = (
            Path(__file__)
            .resolve()
            .parents[3]
            / self.profile_name
        )

        launch_options = {
            "user_data_dir": str(profile),
            "headless": headless,
            "slow_mo": 0,
            **context_options,
        }

        if proxy_url:
            launch_options["proxy"] = {
                "server": proxy_url,
            }

        try:
            self.context = (
                self.playwright.chromium.launch_persistent_context(
                    channel="chrome",
                    **launch_options,
                )
            )

        except Exception as exc:
            print(
                "System Chrome unavailable; "
                "falling back to Playwright Chromium:",
                exc,
            )

            self.context = (
                self.playwright.chromium.launch_persistent_context(
                    **launch_options,
                )
            )

    def _launch_ephemeral(
        self,
        headless: bool,
        context_options: dict,
        proxy_url: str | None = None,
    ):
        """
        Fresh browser session.

        Used by the Apify Actor for anonymous/public Naukri access.

        No browser-data or browser-data-naukri directory is required.
        """

        launch_options = {
            "headless": headless,
        }

        if proxy_url:
            launch_options["proxy"] = {
                "server": proxy_url,
            }

        try:
            self.browser = self.playwright.chromium.launch(
                channel="chrome",
                **launch_options,
            )

        except Exception as exc:
            print(
                "System Chrome unavailable; "
                "falling back to Playwright Chromium:",
                exc,
            )

            self.browser = self.playwright.chromium.launch(
                **launch_options,
            )

        self.context = self.browser.new_context(
            **context_options,
        )

    def close(self):
        """
        Close Playwright resources safely.

        Persistent mode:
            context -> playwright

        Ephemeral mode:
            context -> browser -> playwright
        """

        if self.context:
            try:
                self.context.close()
            except Exception:
                pass

        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

