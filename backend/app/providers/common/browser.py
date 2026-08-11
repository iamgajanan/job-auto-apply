import platform
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright


class BrowserManager:
    """
    Thin wrapper around a Playwright persistent context.

    profile_name controls WHICH on-disk browser-data folder is used.
    Each site that needs its own logged-in session (LinkedIn, Naukri, ...)
    should use its own profile_name so their cookies/session never mix.

    headless=False is only needed for one-time interactive login scripts.
    Regular scraping runs headless=True by default.

    On Linux/ARM devices such as Raspberry Pi, Playwright's bundled Chrome
    channel may not exist. In that case we automatically use an installed
    system Chromium (for example /usr/bin/chromium).
    """

    def __init__(self, profile_name: str = "browser-data"):
        self.profile_name = profile_name
        self.playwright = None
        self.context = None
        self.page = None

    @staticmethod
    def _parse_proxy(proxy_url: str) -> dict:
        """
        Turn 'http://user:pass@host:port' into Playwright's proxy config.
        """
        import re

        m = re.match(r"^(https?)://([^:]+):([^@]+)@(.+)$", proxy_url)
        if m:
            scheme, user, pwd, host_port = m.groups()
            return {
                "server": f"{scheme}://{host_port}",
                "username": user,
                "password": pwd,
            }
        return {"server": proxy_url}

    @staticmethod
    def _system_chromium() -> str | None:
        """Return an installed Chromium executable on Linux, if available."""
        if platform.system().lower() != "linux":
            return None

        for executable in (
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
        ):
            if executable and Path(executable).is_file():
                return executable
        return None

    def launch(
        self,
        headless: bool = True,
        block_resources: bool = True,
        proxy_url: str = None,
    ):
        profile = (
            Path(__file__).resolve().parents[3] / self.profile_name
        )

        self.playwright = sync_playwright().start()

        is_linux = platform.system().lower() == "linux"
        system_chromium = self._system_chromium()

        if is_linux and system_chromium:
            user_agent = (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        else:
            user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

        launch_kwargs = dict(
            user_data_dir=str(profile),
            headless=headless,
            slow_mo=0,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            user_agent=user_agent,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )

        if proxy_url:
            launch_kwargs["proxy"] = self._parse_proxy(proxy_url)

        if system_chromium:
            app_logger_message = f"Using system Chromium: {system_chromium}"
            print(app_logger_message)
            launch_kwargs["executable_path"] = system_chromium
            self.context = self.playwright.chromium.launch_persistent_context(
                **launch_kwargs
            )
        else:
            try:
                self.context = self.playwright.chromium.launch_persistent_context(
                    channel="chrome",
                    **launch_kwargs,
                )
                print("Using installed Chrome channel")
            except Exception as e:
                print("Chrome channel unavailable, falling back to Playwright Chromium:", e)
                self.context = self.playwright.chromium.launch_persistent_context(
                    **launch_kwargs
                )

        if block_resources:
            self.context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in [
                        "image",
                        "font",
                        "media",
                        "stylesheet",
                    ]
                    else route.continue_()
                ),
            )

        self.page = (
            self.context.pages[0]
            if self.context.pages
            else self.context.new_page()
        )

        self.page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        self.page.set_default_timeout(10000)
        self.page.set_default_navigation_timeout(20000)

        return self.page

    def close(self):
        if self.context:
            self.context.close()

        if self.playwright:
            self.playwright.stop()
