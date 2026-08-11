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
    MAX_SCROLLS = 12
    SCROLL_WAIT_MS = 700
    MAX_CONSECUTIVE_STALLS = 3
    NAVIGATION_TIMEOUT_MS = 20000
    SEARCH_RESULT_TIMEOUT_MS = 12000

    PROXY_URL = settings.SCRAPER_PROXY_URL or None
    DEBUG_DIR = Path(__file__).resolve().parents[3] / "debug"

    JOB_LINK_SELECTORS = (
        "a[href*='/jobs/view/']",
        "a[href*='/jobs/collections/']",
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
    def _build_ai_query(request) -> str:
        """Build the natural-language query expected by LinkedIn's new Jobs UI."""
        parts = []
        title = (request.job_title or "").strip()
        location = (request.location or "").strip()
        experience = (request.experience or "").strip()
        work_mode = (request.work_mode or "any").strip().lower()
        posted = (request.posted_within or "").strip().lower()

        if title:
            parts.append(title)
        parts.append("jobs")
        if location:
            parts.append(f"in {location}")
        if experience:
            parts.append(f"for {experience} experience")
        if work_mode not in {"", "any", "all"}:
            parts.append({
                "remote": "remote",
                "hybrid": "hybrid",
                "onsite": "on-site",
                "on-site": "on-site",
                "on site": "on-site",
            }.get(work_mode, work_mode))
        if posted:
            posted_phrase = {
                "day": "posted in the past day",
                "week": "posted in the past week",
                "month": "posted in the past month",
            }.get(posted)
            if posted_phrase:
                parts.append(posted_phrase)
        if request.easy_apply:
            parts.append("Easy Apply")
        return " ".join(parts).strip()

    def _extract_results(self, page):
        """Extract LinkedIn job links in one browser-side pass."""
        return page.evaluate(
            """
            () => {
                const selectors = [
                    "a[href*='/jobs/view/']",
                    "a[href*='/jobs/collections/']"
                ];
                const results = [];
                const seen = new Set();

                for (const selector of selectors) {
                    for (const link of document.querySelectorAll(selector)) {
                        const href = link.href || link.getAttribute('href') || '';
                        const match = href.match(/\\/jobs\\/view\\/([^/?#]+)/);
                        if (!match || seen.has(match[1])) continue;
                        seen.add(match[1]);

                        let root = link;
                        for (let i = 0; i < 8 && root.parentElement; i++) {
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

                        const pick = (selectors) => {
                            for (const s of selectors) {
                                const el = root.querySelector(s);
                                const value = el?.innerText?.trim();
                                if (value) return value;
                            }
                            return '';
                        };

                        results.push({
                            job_id: match[1],
                            href,
                            text: (root.innerText || link.innerText || '').trim(),
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
                return results;
            }
            """
        )

    def _open_ai_search(self, page, query: str):
        """Submit a natural-language search through LinkedIn's current Jobs UI."""
        started = time.time()
        try:
            page.wait_for_selector(
                '[data-testid="typeahead-input"]',
                timeout=self.SEARCH_RESULT_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            app_logger.warning("LinkedIn Jobs search input was not found")
            return False

        search_input = page.locator('[data-testid="typeahead-input"]').first
        search_input.fill(query)
        search_input.press("Enter")

        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except PlaywrightTimeoutError:
            pass

        try:
            page.wait_for_function(
                """() => location.pathname.includes('/jobs/search-results') ||
                         document.querySelectorAll("a[href*='/jobs/view/']").length > 0""",
                timeout=self.SEARCH_RESULT_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            pass

        app_logger.debug(
            f"LinkedIn AI search submitted in {time.time() - started:.2f}s | "
            f"query={query!r} | url={page.url}"
        )
        return True

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
            query = self._build_ai_query(request)
            app_logger.info(f"LinkedIn AI job search query: {query}")

            try:
                response = None
                try:
                    response = page.goto(
                        "https://www.linkedin.com/jobs/",
                        wait_until="commit",
                        timeout=self.NAVIGATION_TIMEOUT_MS,
                    )
                except PlaywrightTimeoutError:
                    app_logger.warning(
                        "LinkedIn Jobs landing navigation timed out; continuing"
                    )

                if response is not None:
                    BlockDetector.check("linkedin", page, response)

                if not self._open_ai_search(page, query):
                    self._save_debug(page, "search-input-missing")
                    return []

                results = self._extract_results(page)
                app_logger.debug(
                    f"LinkedIn initial job links: {len(results)} | url={page.url}"
                )

                previous_count = len(results)
                stalls = 0
                for scroll_num in range(self.MAX_SCROLLS):
                    if len(results) >= self.JOB_LIMIT:
                        break

                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(self.SCROLL_WAIT_MS)
                    current = self._extract_results(page)
                    current_count = len(current)
                    app_logger.debug(
                        f"LinkedIn scroll {scroll_num + 1}: {current_count} job links"
                    )

                    if current_count <= previous_count:
                        stalls += 1
                    else:
                        stalls = 0
                        results = current

                    if stalls >= self.MAX_CONSECUTIVE_STALLS:
                        break
                    previous_count = current_count

                results = self._extract_results(page)
                if not results:
                    self._save_debug(page, "zero-results")
                    app_logger.warning(
                        f"LinkedIn returned zero job links for query={query!r}; url={page.url}"
                    )
                    return []

                jobs = []
                seen_job_ids = set()
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

                jobs = jobs[: self.JOB_LIMIT]
                app_logger.info(f"TOTAL LINKEDIN JOBS SCRAPED: {len(jobs)}")
                return jobs

            except Exception:
                self._save_debug(page, "error")
                raise
        finally:
            browser.close()
