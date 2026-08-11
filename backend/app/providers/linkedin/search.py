from urllib.parse import quote
from pathlib import Path
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

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
    NAVIGATION_TIMEOUT_MS = 15000
    DOM_CONTENT_TIMEOUT_MS = 10000

    PROXY_URL = settings.SCRAPER_PROXY_URL or None
    DEBUG_DIR = Path(__file__).resolve().parents[3] / "debug"

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

    @staticmethod
    def _extract_job_id(link: str) -> str:
        if not link:
            return ""
        if "/jobs/view/" in link:
            return link.split("/jobs/view/", 1)[1].split("/", 1)[0].split("?", 1)[0]
        return ""

    def _extract_results(self, page):
        """Extract job results in one browser-side pass to avoid locator timeouts."""
        return page.evaluate(
            """
            () => {
                const selectors = [
                    "a[href*='/jobs/view/']",
                    "a[href*='/jobs/collections/']"
                ];
                const links = [];
                const seen = new Set();

                for (const selector of selectors) {
                    for (const link of document.querySelectorAll(selector)) {
                        const href = link.href || link.getAttribute('href') || '';
                        const match = href.match(/\/jobs\/view\/([^/?#]+)/);
                        if (!match || seen.has(match[1])) continue;
                        seen.add(match[1]);

                        let root = link;
                        for (let i = 0; i < 6 && root.parentElement; i++) {
                            const parent = root.parentElement;
                            const cls = String(parent.className || '');
                            if (
                                parent.tagName === 'LI' ||
                                parent.tagName === 'ARTICLE' ||
                                /job-card|base-card|search-result|list-item/i.test(cls)
                            ) {
                                root = parent;
                                break;
                            }
                            root = parent;
                        }

                        const text = (root.innerText || link.innerText || '').trim();
                        const pick = (sels) => {
                            for (const s of sels) {
                                const el = root.querySelector(s);
                                const value = el?.innerText?.trim();
                                if (value) return value;
                            }
                            return '';
                        };

                        links.push({
                            job_id: match[1],
                            href,
                            text,
                            title: pick([
                                'h3', 'h2', 'strong',
                                '.base-search-card__title',
                                '.job-card-list__title',
                                '[class*="job-card-list__title"]',
                                '[class*="search-card__title"]'
                            ]),
                            company: pick([
                                '.artdeco-entity-lockup__subtitle',
                                '.base-search-card__subtitle',
                                '.job-card-container__company-name',
                                '[class*="company-name"]'
                            ]),
                            location: pick([
                                '.artdeco-entity-lockup__caption',
                                '.job-search-card__location',
                                '.base-search-card__metadata',
                                '[class*="location"]'
                            ]),
                            logo: root.querySelector('img')?.src || ''
                        });
                    }
                }
                return links;
            }
            """
        )

    def _build_url(self, request, start_offset: int) -> str:
        keyword = quote(request.job_title or "")
        location = quote(request.location or "")
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={keyword}&location={location}"
        )

        if request.easy_apply:
            url += "&f_AL=true"

        mode = (request.work_mode or "any").lower()
        if mode == "remote":
            url += "&f_WT=2"
        elif mode == "hybrid":
            url += "&f_WT=3"
        elif mode in {"onsite", "on-site", "on site"}:
            url += "&f_WT=1"

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
            except (ValueError, IndexError):
                pass

        posted = (request.posted_within or "").lower()
        if posted == "day":
            url += "&f_TPR=r86400"
        elif posted == "week":
            url += "&f_TPR=r604800"
        elif posted == "month":
            url += "&f_TPR=r2592000"

        return f"{url}&start={start_offset}"

    def search(self, request):
        browser = BrowserManager()

        if self.PROXY_URL:
            app_logger.info(
                f"LinkedIn scraping via PROXY: {self.PROXY_URL.split('@')[-1]}"
            )
        else:
            app_logger.info("LinkedIn scraping via DIRECT connection (no proxy)")

        try:
            page = browser.launch(proxy_url=self.PROXY_URL)
            jobs = []
            seen_job_ids = set()

            for page_num in range(self.MAX_PAGES):
                page_start = time.time()
                start_offset = page_num * self.PAGE_SIZE
                url = self._build_url(request, start_offset)
                app_logger.debug(
                    f"LinkedIn page {page_num + 1} | start={start_offset} | {url}"
                )

                try:
                    response = page.goto(
                        url,
                        wait_until="commit",
                        timeout=self.NAVIGATION_TIMEOUT_MS,
                    )
                except PlaywrightTimeoutError:
                    app_logger.warning(
                        f"LinkedIn navigation exceeded {self.NAVIGATION_TIMEOUT_MS}ms; continuing"
                    )
                    response = None

                try:
                    page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=self.DOM_CONTENT_TIMEOUT_MS,
                    )
                except PlaywrightTimeoutError:
                    app_logger.debug(
                        "LinkedIn DOMContentLoaded timed out; continuing with available DOM"
                    )

                if response is not None:
                    BlockDetector.check("linkedin", page, response)

                app_logger.debug(f"goto/load took {time.time() - page_start:.2f}s")

                try:
                    page.wait_for_selector(
                        ",".join(self.CARD_SELECTORS + self.JOB_LINK_SELECTORS),
                        timeout=self.POST_NAV_WAIT_MS,
                    )
                except PlaywrightTimeoutError:
                    pass

                app_logger.debug(f"Actual URL: {page.url}")
                results = self._extract_results(page)
                app_logger.debug(
                    f"Initially rendered result elements: {len(results)}"
                )

                # LinkedIn often lazy-loads more results while scrolling.
                try:
                    scroll_info = page.evaluate(
                        """
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
                            return {scrollHeight: best.scrollHeight, clientHeight: best.clientHeight, diff: bestHeight};
                        }
                        """
                    )
                except Exception:
                    scroll_info = None

                if scroll_info:
                    previous = len(results)
                    stalls = 0
                    for scroll_num in range(self.MAX_SCROLLS_PER_PAGE):
                        page.evaluate(
                            """
                            () => window.__scrollTarget?.scrollBy(0, 1200)
                            """
                        )
                        page.wait_for_timeout(400)
                        current_results = self._extract_results(page)
                        current = len(current_results)
                        app_logger.debug(
                            f"Scroll {scroll_num + 1}: {current} results"
                        )
                        if current <= previous:
                            stalls += 1
                            if stalls >= self.MAX_CONSECUTIVE_STALLS:
                                break
                        else:
                            stalls = 0
                        previous = current
                        results = current_results
                        if len(jobs) + current >= self.JOB_LIMIT:
                            break

                results = self._extract_results(page)
                app_logger.debug(
                    f"Page {page_num + 1} final result elements: {len(results)}"
                )

                if not results:
                    if response is not None:
                        BlockDetector.check("linkedin", page, response)
                    if page_num == 0:
                        self._save_debug(page, "zero-results")
                    app_logger.debug("No job result elements found. Stopping pagination.")
                    break

                page_new_count = 0
                for result in results:
                    if len(jobs) >= self.JOB_LIMIT:
                        break

                    job_id = result.get("job_id", "")
                    if not job_id or job_id in seen_job_ids:
                        continue
                    seen_job_ids.add(job_id)

                    text = (result.get("text") or "").lower()
                    link = result.get("href") or ""
                    if link.startswith("/"):
                        link = "https://www.linkedin.com" + link

                    jobs.append({
                        "platform": "linkedin",
                        "job_id": job_id,
                        "title": result.get("title") or "",
                        "company": result.get("company") or "",
                        "location": result.get("location") or "",
                        "salary": "Not Disclosed",
                        "experience": request.experience,
                        "easy_apply": "easy apply" in text,
                        "work_mode": (
                            "Remote" if "remote" in text else
                            "Hybrid" if "hybrid" in text else
                            "On-site" if "on-site" in text or "onsite" in text else
                            "Unknown"
                        ),
                        "job_url": link,
                        "apply_url": "",
                        "description": "",
                        "company_logo": result.get("logo") or "",
                        "posted_at": None,
                        "posted_within": request.posted_within,
                        "status": "NEW",
                    })
                    page_new_count += 1

                app_logger.debug(
                    f"Page {page_num + 1} added {page_new_count} new jobs. Total so far: {len(jobs)}"
                )

                if len(jobs) >= self.JOB_LIMIT:
                    app_logger.info(
                        f"Reached JOB_LIMIT ({self.JOB_LIMIT}). Stopping pagination."
                    )
                    break
                if page_new_count == 0:
                    app_logger.debug(
                        "No new jobs added from this page. Stopping pagination."
                    )
                    break

            jobs = jobs[: self.JOB_LIMIT]
            app_logger.info(f"TOTAL LINKEDIN JOBS SCRAPED: {len(jobs)}")
            return jobs
        finally:
            browser.close()
