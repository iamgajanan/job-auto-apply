from urllib.parse import quote

from app.providers.linkedin.browser import BrowserManager


class LinkedInSearch:

    def search(self, request):

        browser = BrowserManager()
        page = browser.launch()

        keyword = quote(request.job_title or "")
        location = quote(request.location or "")

        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={keyword}"
            f"&location={location}"
        )

        # Easy Apply
        if request.easy_apply:
            url += "&f_AL=true"

        # Work Mode
        if request.work_mode:
            mode = request.work_mode.lower()

            if mode == "remote":
                url += "&f_WT=2"
            elif mode == "hybrid":
                url += "&f_WT=3"
            elif mode in ["onsite", "on-site"]:
                url += "&f_WT=1"

        # Experience
        if request.experience:
            try:
                years = int(request.experience.split()[0])

                if years <= 2:
                    url += "&f_E=1"
                elif years <= 5:
                    url += "&f_E=3"
                elif years <= 10:
                    url += "&f_E=4"
                else:
                    url += "&f_E=5"

            except Exception:
                pass

        # Posted Within
        if request.posted_within:
            posted = request.posted_within.lower()

            if posted == "day":
                url += "&f_TPR=r86400"
            elif posted == "week":
                url += "&f_TPR=r604800"
            elif posted == "month":
                url += "&f_TPR=r2592000"

        print("=" * 80)
        print(url)
        print("=" * 80)

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(3000)

        print("Actual URL :", page.url)

        with open("linkedin.html", "w", encoding="utf-8") as f:
            f.write(page.content())

        page.screenshot(path="linkedin.png", full_page=True)

        cards = page.locator(".job-card-container")
        print("Initially rendered:", cards.count())

     # ---------------------------------------
        # Find the real scrollable container
        # ---------------------------------------

        elements = page.locator("*")

        best = None
        best_height = 0

        for i in range(elements.count()):
            try:
                data = elements.nth(i).evaluate("""
                e => ({
                    tag: e.tagName,
                    cls: e.className,
                    id: e.id,
                    scrollHeight: e.scrollHeight,
                    clientHeight: e.clientHeight,
                    overflow: getComputedStyle(e).overflowY
                })
                """)

                diff = data["scrollHeight"] - data["clientHeight"]

                if diff > best_height:
                    best_height = diff
                    best = {
                        "index": i,
                        **data
                    }

            except:
                pass

        print("=" * 80)
        print("Largest scrollable element")
        print(best)
        print("=" * 80)

        if best:

            scroll_container = elements.nth(best["index"])

            previous = 0

            for i in range(50):

                scroll_container.evaluate("""
                el => {
                    el.scrollBy(0, 1200);
                }
                """)

                page.wait_for_timeout(1200)

                current = page.locator(".job-card-container").count()

                print(f"Scroll {i+1}: {current}")

                if current == previous:
                    break

                previous = current

        cards = page.locator(".job-card-container")

        print("Final jobs:", cards.count())

        jobs = []

        for i in range(cards.count()):

            card = cards.nth(i)

            text = (card.text_content() or "").lower()

            try:
                title = (
                    card.locator("strong")
                    .first
                    .text_content()
                    .strip()
                )
            except:
                title = ""

            try:
                company = (
                    card.locator(".artdeco-entity-lockup__subtitle")
                    .first
                    .text_content()
                    .strip()
                )
            except:
                company = ""

            try:
                location = (
                    card.locator(".artdeco-entity-lockup__caption")
                    .first
                    .text_content()
                    .strip()
                )
            except:
                location = ""

            try:
                logo = card.locator("img").first.get_attribute("src") or ""
            except:
                logo = ""

            try:
                link = card.locator("a").first.get_attribute("href") or ""

                if link.startswith("/"):
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
                    pass

            work_mode = "Unknown"

            if "remote" in text:
                work_mode = "Remote"
            elif "hybrid" in text:
                work_mode = "Hybrid"
            elif "on-site" in text or "onsite" in text:
                work_mode = "On-site"

            jobs.append(
                {
                    "platform": "linkedin",
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "salary": "Not Disclosed",
                    "experience": request.experience,
                    "easy_apply": "easy apply" in text,
                    "work_mode": work_mode,
                    "job_url": link,
                    "apply_url": "",
                    "description": "",
                    "company_logo": logo,
                    "posted_at": None,
                    "posted_within": request.posted_within,
                    "status": "NEW",
                }
            )

        browser.close()

        return jobs