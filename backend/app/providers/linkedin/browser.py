from pathlib import Path
from playwright.sync_api import sync_playwright


class BrowserManager:

    def __init__(self):
        self.playwright = None
        self.context = None
        self.page = None

    def launch(self):

        profile = (
            Path(__file__)
            .resolve()
            .parents[3]
            / "browser-data"
        )

        self.playwright = sync_playwright().start()

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=True,          # Faster
            slow_mo=0,              # Remove artificial delay
            viewport={
                "width": 1440,
                "height": 900,
            },
        )

        # Block unnecessary resources
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

        # Disable animations
        # Faster page loading
        self.page.set_default_timeout(10000)
        self.page.set_default_navigation_timeout(20000)

        return self.page

    def close(self):

        if self.context:
            self.context.close()

        if self.playwright:
            self.playwright.stop()