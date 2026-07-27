from pathlib import Path

from playwright.sync_api import sync_playwright


class BrowserManager:

    def __init__(self):
        self.playwright = None
        self.browser = None
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

        self.context = (
            self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=False,
                slow_mo=150,
                viewport={
                    "width": 1440,
                    "height": 900,
                },
            )
        )

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

        return self.page

    def close(self):

        if self.context:
            self.context.close()

        if self.playwright:
            self.playwright.stop()