from app.providers.linkedin.browser import BrowserManager


class LinkedInLogin:

    def login(self):

        browser = BrowserManager()

        # headed -- a human needs to actually see this page to type
        # credentials / solve any checkpoint.
        page = browser.launch(headless=False)

        page.goto(
            "https://www.linkedin.com/login",
            wait_until="domcontentloaded",
        )

        return browser, page