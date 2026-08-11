from urllib.parse import quote
from pathlib import Path
import time

from app.providers.linkedin.browser import BrowserManager
from app.gateway.block_detector import BlockDetector
from app.core.logger import app_logger
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

    JOB_LIMIT = 100
    PAGE_SIZE = 25
    MAX_PAGES = 8
    MAX_SCROLLS_PER_PAGE = 6
    SCROLL_POLL_TIMEOUT_MS = 800
    MAX_CONSECUTIVE_STALLS = 2
    POST_NAV_WAIT_MS = 1200

    PROXY_URL = settings.SCRAPER_PROXY_URL or None
    DEBUG_DIR = Path(__file__).resolve().parents[3] / "debug"

    # LinkedIn has changed its search-results DOM several times. Prefer the
    # stable job-link signal and use card containers only as a fallback.
    JOB_LINK_SELECTORS = (
        "a[href*='/jobs/view/']",
        "a[href*='/jobs/collections/']",
    )
    CARD_SELECTORS = (
        ".job-card-container",
        "li.jobs-search-results__list-item",
        ".jobs-search-results__list-item",
        "li.base-card",
    )

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

    def _job_elements(self, page):
        """Return unique result elements using several LinkedIn DOM variants."""
        # The job URL is more stable than LinkedIn's presentation classes.
        links = page.locator(", ".join(self.JOB_LINK_SELECTORS))
        if links.count():
            elements = []
            seen = set()
            for i in range(links.count()):
                link = links.nth(i)
                try:
                    href = link.get_attribute("href") or ""
                    job_id = self._extract_job_id(href)
                    if not job_id or job_id in seen:
                        continue
                    seen.add(job_id)
                    # Walk up to the nearest result/card element. If no known
                    # card exists, use the link itself; field extraction has
                    # additional fallbacks below.
                    card = link.locator(
                        "xpath=ancestor::*[self::li or contains(@class,'job-card') or contains(@class,'base-card')][1]"
                    )
                    if card.count():
                        elements.append(card.first)
                    else:
                        elements.append(link)
                except Exception:
                    continue
            if elements:
                return elements

        for selector in self.CARD_SELECTORS:
            cards = page.locator(selector)
            if cards.count():
                return [cards.nth(i) for i in range(cards.count())]
        return []

    @staticmethod
    def _extract_job_id(link: str) -> str:
        if not link:
            return ""
        if "/jobs/view/" in link:
            try:
                return link.split("/jobs/view/", 1)[1].split("/", 1)[0].split("?", 1)[0]
            except Exception:
                return ""
        return ""

    @staticmethod
    def _first_text(element, selectors) -> str:
        for selector in selectors:
            try:
                value = element.locator(selector).first.text_content()
                if value and value.strip():
                    return value.strip()
            except Exception:
                continue
        return ""

    def search(self, request):
        browser = BrowserManager()

        if self.PROXY_URL:
            masked = self.PROXY_URL.split("@")[-1]
            app_logger.info(f"LinkedIn scraping via PROXY: {masked}")
        else:
            app_logger.info("LinkedIn scraping via DIRECT connection (no proxy)")

        try:
            page = browser.launch(proxy_url=self.PROXY_URL)

            keyword = quote(request.job_title or "")
            location = quote(request.location or "")
            base_url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={keyword}&location={location}"
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
                app_logger.debug(
                    f"LinkedIn page {page_num + 1} | start={start_offset} | {url}"
                )

                response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                BlockDetector.check("linkedin", page, response)
                app_logger.debug(f"goto took {time.time() - page_start_time:.2f}s")

                # Wait for either a known card or a job URL. This handles both
                # the classic and newer jobs-search-results DOM.
                try:
                    page.wait_for_selector(
                        ", ".join(self.CARD_SELECTORS + self.JOB_LINK_SELECTORS),
                        timeout=self.POST_NAV_WAIT_MS,
                    )
                except Exception:
                    page.wait_for_timeout(self.POST_NAV_WAIT_MS)

                app_logger.debug(f"Actual URL: {page.url}")
                elements = self._job_elements(page)
                app_logger.debug(f"Initially rendered result elements: {len(elements)}")

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
                        cls: String(best.className || ''),
                        id: best.id,
                        scrollHeight: best.scrollHeight,
                        clientHeight: best.clientHeight,
                        diff: bestHeight,
                    };
                }
                """)
                app_logger.debug(f"Largest scrollable element: {best_info}")

                if best_info:
                    previous = len(elements)
                    stall_count = 0
                    for i in range(self.MAX_SCROLLS_PER_PAGE):
                        page.evaluate("""
                        () => {
                            if (window.__scrollTarget) {
                                window.__scrollTarget.scrollBy(0, 1200);
                            }
                        }
                        """)

                        poll_interval_ms = 200
                        elapsed_ms = 0
                        current = previous
                        while elapsed_ms < self.SCROLL_POLL_TIMEOUT_MS:
                            page.wait_for_timeout(poll_interval_ms)
                            elapsed_ms += poll_interval_ms
                            current = len(self._job_elements(page))
                            if current > previous:
                                break

                        app_logger.debug(
                            f"Scroll {i + 1}: {current} (waited {elapsed_ms}ms)"
                        )
                        if current == previous:
                            stall_count += 1
                            if stall_count >= self.MAX_CONSECUTIVE_STALLS:
                                break
                        else:
                            stall_count = 0
                        previous = current
                        app_logger.debug(
                            f"scroll cumulative time: {time.time() - page_start_time:.2f}s"
                        )
                        if len(jobs) + current >= self.JOB_LIMIT:
                            break

                elements = self._job_elements(page)
                app_logger.debug(f"Page {page_num + 1} final result elements: {len(elements)}")

                if not elements:
                    BlockDetector.check("linkedin", page, response)
                    if page_num == 0:
                        self._save_debug(page, "zero-results")
                    app_logger.debug("No job result elements found. Stopping pagination.")
                    break

                page_new_count = 0
                for element in elements:
                    if len(jobs) >= self.JOB_LIMIT:
                        break

                    try:
                        text = (element.text_content() or "").lower()
                    except Exception:
                        text = ""

                    try:
                        link = element.locator("a[href*='/jobs/view/']").first.get_attribute("href") or ""
                    except Exception:
                        link = ""
                    if not link and getattr(element, "get_attribute", None):
                        try:
                            link = element.get_attribute("href") or ""
                        except Exception:
                            pass
                    if link.startswith("/"):
                        link = "https://www.linkedin.com" + link

                    job_id = self._extract_job_id(link)
                    if not job_id or job_id in seen_job_ids:
                        continue
                    seen_job_ids.add(job_id)

                    title = self._first_text(element, [
                        "strong",
                        "h3",
                        ".base-search-card__title",
                        ".job-card-list__title",
                    ])
                    company = self._first_text(element, [
                        ".artdeco-entity-lockup__subtitle",
                        ".base-search-card__subtitle",
                        ".job-card-container__company-name",
                    ])
                    job_location = self._first_text(element, [
                        ".artdeco-entity-lockup__caption",
                        ".job-search-card__location",
                        ".base-search-card__metadata",
                    ])
                    try:
                        logo = element.locator("img").first.get_attribute("src") or ""
                    except Exception:
                        logo = ""

                    if not title:
                        title = ""
                    if not company:
                        company = ""
                    if not job_location:
                        job_location = ""

                    work_mode = "Unknown"
                    if "remote" in text:
                        work_mode = "Remote"
                    elif "hybrid" in text:
                        work_mode = "Hybrid"
                    elif "on-site" in text or "onsite" in text:
                        work_mode = "On-site"

                    jobs.append({
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
                    })
                    page_new_count += 1

                app_logger.debug(
                    f"Page {page_num + 1} added {page_new_count} new jobs. Total so far: {len(jobs)}"
                )
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
