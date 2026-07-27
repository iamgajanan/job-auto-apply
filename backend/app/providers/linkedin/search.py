from urllib.parse import quote

from app.providers.linkedin.browser import BrowserManager


class LinkedInSearch:

    def search(self, request):

        browser = BrowserManager()
        page = browser.launch()

        keyword = quote(request.job_title)
        location = quote(request.location)

        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={keyword}"
            f"&location={location}"
        )

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(8000)

        cards = page.locator(".job-card-container")

        jobs = []

        for i in range(cards.count()):

            card = cards.nth(i)

            text = card.inner_text()

            try:
                title = card.locator("strong").first.inner_text().strip()
            except:
                title = ""

            try:
                company = card.locator(
                    ".artdeco-entity-lockup__subtitle"
                ).first.inner_text().strip()
            except:
                company = ""

            try:
                location = card.locator(
                    ".artdeco-entity-lockup__caption"
                ).first.inner_text().strip()
            except:
                location = ""

            try:
                logo = card.locator("img").first.get_attribute("src")
            except:
                logo = ""

            try:
                link = card.locator("a").first.get_attribute("href")

                if link and link.startswith("/"):
                    link = "https://www.linkedin.com" + link

            except:
                link = ""

            job_id = ""

            if "/jobs/view/" in link:
                try:
                    job_id = (
                        link.split("/jobs/view/")[1]
                        .split("/")[0]
                        .split("?")[0]
                    )
                except:
                    job_id = ""

            easy_apply = "easy apply" in text.lower()

            work_mode = "Unknown"

            if "remote" in text.lower():
                work_mode = "Remote"
            elif "hybrid" in text.lower():
                work_mode = "Hybrid"
            elif "on-site" in text.lower():
                work_mode = "On-site"

            jobs.append(
                {
                    "platform": "linkedin",
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "salary": "Not Disclosed",
                    "experience": request.experience or "Not Mentioned",
                    "work_mode": work_mode,
                    "easy_apply": easy_apply,
                    "job_url": link,
                    "apply_url": "",
                    "description": "",
                    "company_logo": logo or "",
                    "posted_at": None,
                    "status": "NEW",
                }
            )

        browser.close()

        return jobs