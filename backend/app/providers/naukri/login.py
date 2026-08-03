from app.providers.common.browser import BrowserManager

NAUKRI_PROFILE = "browser-data-naukri"


class NaukriLogin:

    def login(self):

        browser = BrowserManager(profile_name=NAUKRI_PROFILE)

        # headed -- a human needs to actually see this page to type
        # credentials / solve any OTP or captcha.
        page = browser.launch(headless=False)

        page.goto(
            "https://www.naukri.com/nlogin/login",
            wait_until="domcontentloaded",
        )

        return browser, page