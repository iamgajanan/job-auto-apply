from urllib.parse import quote
from pathlib import Path

from app.providers.linkedin.browser import BrowserManager
from app.gateway.block_detector import BlockDetector
from app.core.logger import app_logger
import time

from app.providers.base import BaseProvider, ProviderCapabilities
from app.config.settings import settings


class LinkedInSearch(BaseProvider):

    name = "linkedin"

    capabilities = ProviderCapabilities(
        easy_apply=True,
        remote=True,
        salary=True,
        login=True,
    )
    JOB_LIMIT = 100          # hard cap: never scrape/return more than this
    PROXY_URL = settings.SCRAPER_PROXY_URL or None  # from .env, or set externally by Apify actor
    PAGE_SIZE = 25           # LinkedIn's cards-per-page
    MAX_PAGES = 8             # safety cap on pagination loop
    # Keep pagination responsive. LinkedIn normally renders a page's cards after
    # a small number of scrolls; the old 15-scroll loop could spend tens of
    # seconds waiting even when no more cards were available.
    MAX_SCROLLS_PER_PAGE = 6
    SCROLL_POLL_TIMEOUT_MS = 800
    MAX_CONSECUTIVE_STALLS = 2
    POST_NAV_WAIT_MS = 800

    DEBUG_DIR = Path(__file__).resolve().parents[3] / "debug"

    def _save_debug(self, page, tag: str):
        try:
            self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(self.DEBUG_DIR / f"linkedin-{tag}.png"),
                full_page=True,
            )
            (self.DEBUG_DIR / f"linkedin-{tag}.html").write_text(
                page.content(), encoding="utf-8"
            )
        except Exception as e:
            app_logger.warning(f"LinkedIn debug save failed: {e}")

    def search(self, request):

        browser = BrowserManager()

        if self.PROXY_URL:
            masked = self.PROXY_URL.split("@")[-1]  # hide credentials in logs
            app_logger.info(f"LinkedIn scraping via PROXY: {masked}")
        else:
            app_logger.info("LinkedIn scraping via DIRECT connection (no proxy)")

        try:
            page = browser.launch(proxy_url=self.PROXY_URL)

            keyword = quote(request.job_title or "")
            location = quote(request.location or "")

            base_url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={keyword}"
                f"&location={location}"
            )

            if request.easy_apply:
                base_url += "&f_AL=true"

            mode = (request.work_mode or "any").lower()
            if mode == "remote":
                base_url += "&f_WT=2"
            elif mode == "hybrid":
                base_url += "&f_WT=3"
            elif mode in ["onsite", "on-site", "on site"]:
                base_url += "&f_WT=1"

            # LinkedIn exposes experience levels rather than exact years.
            if request.experience:
                try:
                    years = int(request.experience.split()[0])

                    if years <= 2:
                        base_url += "&f_E=1"
                    elif years <= 5:
                        base_url += "&f_E=3"
                    elif years <= 10:
                        base_url += "&f_E=4"
                    else:
                        base_url += "&f_E=5"

                except Exception:
                    pass

            if request.posted_within:
                posted = request.posted_within.lower()

                if posted == "day":
                    base_url += "&f_TPR=r86400"
                elif posted == "week":
                    base_url += "&f_TPR=r604800"
                elif posted == "month":
                    base_url += "&f_TPR=r2592000"

            jobs = []
            seen_job_ids = set()

            for page_num in range(self.MAX_PAGES):

                page_start_time = time.time()
                start_offset = page_num * self.PAGE_SIZE
                url = base_url + f"&start={start_offset}"

                app_logger.debug(f"LinkedIn page {page_num + 1} | start={start_offset} | {url}")

                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                BlockDetector.check("linkedin", page, response)
                app_logger.debug(f"goto took {time.time() - page_start_time:.2f}s")

                # Wait only until cards appear. Avoid the previous 1.2-3.0s
                # humanizer delay on every page; this endpoint is a scraper,
                # not an interactive browser workflow.
                try:
                    page.wait_for_selector(
                        ".job-card-container",
                        timeout=self.POST_NAV_WAIT_MS,
                    )
                except Exception:
                    page.wait_for_timeout(self.POST_NAV_WAIT_MS)

                app_logger.debug(f"Actual URL: {page.url}")

                cards = page.locator(".job-card-container")
                app_logger.debug(f"Initially rendered: {cards.count()}")

                # Find the real scrollable container in one browser-side pass.
                best_info = page.evaluate("""
                () => {
                    const all = document.querySelectorAll('*');
                    let best = null;
                    let bestHeight = 0;

                    for (const e of all) {
                        const diff = e.scrollHeight - e.clientHeight;
                        if (diff > bestHeight) {
                            bestHeight = diff;
                            best = e;
                        }
                    }

                    if (!best) return null;

                    window.__scrollTarget = best;

                    return {
                        tag: best.tagName,
                        cls: best.className,
                        id: best.id,
                        scrollHeight: best.scrollHeight,
                        clientHeight: best.clientHeight,
                        diff: bestHeight
                    };
                }
                """)

                app_logger.debug(f"Largest scrollable element: {best_info}")

                if best_info:
                    # Start from the cards already rendered. The previous code
                    # started at zero, causing an unnecessary full polling cycle
                    # before detecting the first batch of cards.
                    previous = cards.count()
                    stall_count = 0

                    for i in range(self.MAX_SCROLLS_PER_PAGE):
                        page.evaluate("""
                        () => {
                            if (window.__scrollTarget) {
                                window.__scrollTarget.scrollBy(0, 1200);
                            }
                        }
                        """)

                        # Poll briefly for newly rendered cards and stop as soon
                        # as LinkedIn has no more cards to add.
                        poll_interval_ms = 200
                        elapsed_ms = 0
                        current = previous

                        while elapsed_ms < self.SCROLL_POLL_TIMEOUT_MS:
                            page.wait_for_timeout(poll_interval_ms)
                            elapsed_ms += poll_interval_ms

                            current = cards.count()

                            if current > previous:
                                break

                        app_logger.debug(f"Scroll {i + 1}: {current} (waited {elapsed_ms}ms)")

                        if current == previous:
                            stall_count += 1
                            if stall_count >= self.MAX_CONSECUTIVE_STALLS:
                                break
                        else:
                            stall_count = 0

                        previous = current
                        app_logger.debug(f"scroll cumulative time: {time.time() - page_start_time:.2f}s")

                        if len(jobs) + current >= self.JOB_LIMIT:
                            break

                cards = page.locator(".job-card-container")

                app_logger.debug(f"Page {page_num + 1} final jobs: {cards.count()}")

                if cards.count() == 0:
                    BlockDetector.check("linkedin", page, response)
                    if page_num == 0:
                        self._save_debug(page, "zero-results")
                    app_logger.debug("No cards found on this page. Stopping pagination.")
                    break

                page_new_count = 0

                for i in range(cards.count()):

                    if len(jobs) >= self.JOB_LIMIT:
                        break

                    card = cards.nth(i)
                    text = (card.text_content() or "").lower()

                    try:
                        title = (
                            card.locator("strong")
                            .first
                            .text_content()
                            .strip()
                        )
                    except Exception:
                        title = ""

                    try:
                        company = (
                            card.locator(".artdeco-entity-lockup__subtitle")
                            .first
                            .text_content()
                            .strip()
                        )
                    except Exception:
                        company = ""

                    try:
                        job_location = (
                            card.locator(".artdeco-entity-lockup__caption")
                            .first
                            .text_content()
                            .strip()
                        )
                    except Exception:
                        job_location = ""

                    try:
                        logo = card.locator("img").first.get_attribute("src") or ""
                    except Exception:
                        logo = ""

                    try:
                        link = card.locator("a").first.get_attribute("href") or ""

                        if link.startswith("/"):
                            link = "https://www.linkedin.com" + link

                    except Exception:
                        link = ""

                    job_id = ""

                    if "/jobs/view/" in link:
                        try:
                            job_id = (
                                link.split("/jobs/view/")[1]
                                .split("/")[0]
                                .split("?")[0]
                            )
                        except Exception:
                            pass

                    if not job_id:
                        continue

                    if job_id in seen_job_ids:
                        continue

                    seen_job_ids.add(job_id)

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
                            "location": job_location,
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

                    page_new_count += 1

                app_logger.debug(f"Page {page_num + 1} added {page_new_count} new jobs. Total so far: {len(jobs)}")

                if len(jobs) >= self.JOB_LIMIT:
                    app_logger.info(f"Reached JOB_LIMIT ({self.JOB_LIMIT}). Stopping pagination.")
                    break

                if page_new_count == 0:
                    app_logger.debug("No new jobs added from this page. Stopping pagination.")
                    break

            jobs = jobs[: self.JOB_LIMIT]

            app_logger.info(f"TOTAL LINKEDIN JOBS SCRAPED: {len(jobs)}")
            return jobs
        finally:
            browser.close()
