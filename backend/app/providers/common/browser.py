import os
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


class BrowserManager:
    """
    Shared Playwright browser manager.

    Local/default mode:
        Uses a persistent browser profile so existing authenticated
        sessions can be reused.

        LinkedIn -> browser-data/
        Naukri   -> browser-data-naukri/

    Cloud/Apify mode:
        Set BROWSER_PERSISTENT=false.

        A fresh Chromium browser/context is created and no local
        browser profile is required.
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

    def _build_proxy_config(
        self,
        proxy_url: str | None,
    ) -> dict | None:
        """
        Convert an authenticated proxy URL such as:

        http://username:password@host:port

        into the proxy configuration expected by Playwright.

        Credentials are never logged.
        """

        if not proxy_url:
            return None

        match = re.match(
            r"^(https?://)([^:]+):([^@]+)@(.+)$",
            proxy_url,
        )

        if match:
            return {
                "server": f"{match.group(1)}{match.group(4)}",
                "username": match.group(2),
                "password": match.group(3),
            }

        return {
            "server": proxy_url,
        }

    def _context_options(self) -> dict:
        return {
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

    def launch(
        self,
        headless: bool = True,
        block_resources: bool = True,
        proxy_url: str | None = None,
    ):
        self.playwright = sync_playwright().start()

        context_options = self._context_options()
        proxy_config = self._build_proxy_config(proxy_url)

        if self.persistent:
            self._launch_persistent(
                headless=headless,
                context_options=context_options,
                proxy_config=proxy_config,
            )
        else:
            self._launch_ephemeral(
                headless=headless,
                context_options=context_options,
                proxy_config=proxy_config,
            )

        if block_resources:
            self.context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type
                    in {
                        "image",
                        "font",
                        "media",
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
        self.page.set_default_navigation_timeout(30000)

        return self.page

    def _launch_persistent(
        self,
        headless: bool,
        context_options: dict,
        proxy_config: dict | None,
    ):
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

        if proxy_config:
            launch_options["proxy"] = proxy_config

        try:
            self.context = (
                self.playwright.chromium
                .launch_persistent_context(
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
                self.playwright.chromium
                .launch_persistent_context(
                    **launch_options,
                )
            )

    def _launch_ephemeral(
        self,
        headless: bool,
        context_options: dict,
        proxy_config: dict | None,
    ):
        launch_options = {
            "headless": headless,
        }

        if proxy_config:
            launch_options["proxy"] = proxy_config

        try:
            self.browser = (
                self.playwright.chromium.launch(
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

            self.browser = (
                self.playwright.chromium.launch(
                    **launch_options,
                )
            )

        self.context = self.browser.new_context(
            **context_options,
        )

    def close(self):
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