from app.providers.linkedin.browser import BrowserManager


class LinkedInLogin:

    def login(self):

        browser = BrowserManager()

        page = browser.launch()

        page.goto(
            "https://www.linkedin.com/login",
            wait_until="networkidle",
        )

        return browser, page