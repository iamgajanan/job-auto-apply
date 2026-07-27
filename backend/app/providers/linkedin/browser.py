from playwright.sync_api import sync_playwright


class BrowserManager:

    def launch(self):

        playwright = sync_playwright().start()

        browser = playwright.chromium.launch(
            headless=False,
            slow_mo=300,
        )

        page = browser.new_page()

        return playwright, browser, page