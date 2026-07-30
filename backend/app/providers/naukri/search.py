from urllib.parse import quote

from app.providers.linkedin.browser import BrowserManager


from app.providers.base import BaseProvider, ProviderCapabilities


class NaukriSearch(BaseProvider):
    name = "naukri"

    capabilities = ProviderCapabilities(
        easy_apply=False,
        remote=True,
        salary=True,
        login=False,
    )

    def search(self, request):

        browser = BrowserManager()
        page = browser.launch()

        keyword = quote(request.job_title or "")
        location = quote(request.location or "")

        url = (
            f"https://www.naukri.com/{keyword.replace('%20','-')}"
            f"-jobs-in-{location.replace('%20','-')}"
        )

        print("=" * 80)
        print(url)
        print("=" * 80)

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(3000)

        page.screenshot(path="naukri.png", full_page=True)

        with open("naukri.html", "w", encoding="utf-8") as f:
            f.write(page.content())

        browser.close()

        return []