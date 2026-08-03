from pathlib import Path
from playwright.sync_api import sync_playwright


class BrowserManager:
    """
    Thin wrapper around a Playwright persistent context.

    profile_name controls WHICH on-disk browser-data folder is used.
    Each site that needs its own logged-in session (LinkedIn, Naukri, ...)
    should use its own profile_name so:
      - their cookies/session never mix
      - two providers can safely launch a browser in parallel
        (e.g. two Celery workers running at once) without fighting
        over the same locked profile directory.

    headless=False is only needed for the one-time interactive login
    scripts (login_once.py / login_naukri_once.py) where a human has
    to actually see the page and type credentials/OTP. Regular scraping
    runs headless=True by default.

    block_resources=True (the LinkedIn-tuned default) aborts
    images/fonts/media/stylesheets for speed. Some sites sit behind
    bot-management edges (Akamai, Cloudflare, etc.) that treat a page
    that never requests a stylesheet or a font as a strong bot signal
    -- for those, pass block_resources=False so the page loads like a
    normal browser would, at the cost of being slower.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, profile_name: str = "browser-data"):
        self.profile_name = profile_name
        self.playwright = None
        self.context = None
        self.page = None

    def launch(self, headless: bool = True, block_resources: bool = True):

        profile = (
            Path(__file__)
            .resolve()
            .parents[3]
            / self.profile_name
        )

        self.playwright = sync_playwright().start()

        launch_kwargs = dict(
            user_data_dir=str(profile),
            headless=headless,
            slow_mo=0,
            viewport={
                "width": 1440,
                "height": 900,
            },
            locale="en-US",
            timezone_id="Asia/Kolkata",
            user_agent=self.USER_AGENT,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        try:
            # Prefer the real, installed Chrome build over bundled
            # Chromium -- it presents a normal Chrome fingerprint
            # (build id, plugin list, etc.) instead of the generic
            # headless-Chromium one that bot-management products
            # specifically look for.
            self.context = self.playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs,
            )
        except Exception as e:
            print("No system Chrome found, falling back to bundled Chromium:", e)
            self.context = self.playwright.chromium.launch_persistent_context(
                **launch_kwargs,
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

        # Best-effort: patch the single most commonly checked automation
        # flag. This alone will NOT get past serious bot-management (they
        # fingerprint far more than this), but it's free and harmless.
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
