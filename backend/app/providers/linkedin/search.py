from pathlib import Path
import re
from urllib.parse import urlencode

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

    # Keep a useful result set while avoiding unnecessary browser scrolling.
    # Exact searches are cached upstream for 30 minutes.
    JOB_LIMIT = 60
    MAX_SCROLLS = 6
    SCROLL_WAIT_MS = 350
    MAX_CONSECUTIVE_STALLS = 2
    NAVIGATION_TIMEOUT_MS = 15000
    RESULT_WAIT_TIMEOUT_MS = 5000

    PROXY_URL = settings.SCRAPER_PROXY_URL or None
    DEBUG_DIR = Path(__file__).resolve().parents[3] / "debug"

    def _save_debug(self, page, tag: str):
        try:
            self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(self.DEBUG_DIR / f"linkedin-{tag}.png"), full_page=True)
            (self.DEBUG_DIR / f"linkedin-{tag}.html").write_text(page.content(), encoding="utf-8")
        except Exception as e:
            app_logger.warning(f"LinkedIn debug save failed: {e}")

    @staticmethod
    def _posted_filter(value: str) -> str | None:
        return {"day": "r86400", "week": "r604800", "month": "r2592000"}.get((value or "").strip().lower())

    @staticmethod
    def _work_mode_filter(value: str) -> str | None:
        return {"onsite": "1", "on-site": "1", "on site": "1", "remote": "2", "hybrid": "3"}.get((value or "").strip().lower())

    @staticmethod
    def _experience_filter(value: str) -> str | None:
        text = (value or "").lower()
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return None
        years = float(match.group(1))
        if years <= 0: return "1"
        if years <= 2: return "2"
        if years <= 5: return "3"
        if years <= 10: return "4"
        if years <= 15: return "5"
        return "6"

    @classmethod
    def _build_classic_url(cls, request) -> str:
        params = {"keywords": (request.job_title or "").strip(), "location": (request.location or "").strip()}
        posted = cls._posted_filter(request.posted_within)
        if posted: params["f_TPR"] = posted
        work_mode = cls._work_mode_filter(request.work_mode)
        if work_mode: params["f_WT"] = work_mode
        experience = cls._experience_filter(request.experience)
        if experience: params["f_E"] = experience
        if request.easy_apply: params["f_AL"] = "true"
        params["start"] = "0"
        return "https://www.linkedin.com/jobs/search/?" + urlencode(params)

    def _extract_results(self, page):
        return page.evaluate(
            """
            () => {
                const selectors = ["a[href*='/jobs/view/']", "a[href*='/jobs/collections/']"];
                const results = [];
                const seen = new Set();
                for (const selector of selectors) {
                    for (const link of document.querySelectorAll(selector)) {
                        const href = link.href || link.getAttribute('href') || '';
                        const match = href.match(/\\/jobs\\/view\\/([^/?#]+)/);
                        if (!match || seen.has(match[1])) continue;
                        seen.add(match[1]);
                        let root = link;
                        for (let i = 0; i < 10 && root.parentElement; i++) {
                            const parent = root.parentElement;
                            const cls = String(parent.className || '');
                            if (parent.tagName === 'LI' || parent.tagName === 'ARTICLE' || /base-card|job-card|search-result|list-item/i.test(cls)) {
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
                            job_id: match[1], href,
                            text: (root.innerText || link.innerText || '').trim(),
                            title: pick(['.base-search-card__title', '.job-card-list__title', 'h3', 'h2', 'strong', '[class*="job-card-list__title"]', '[class*="search-card__title"]']),
                            company: pick(['.base-search-card__subtitle', '.artdeco-entity-lockup__subtitle', '.job-card-container__company-name', '[class*="company-name"]']),
                            location: pick(['.job-search-card__location', '.base-search-card__metadata', '.artdeco-entity-lockup__caption', '[class*="location"]']),
                            logo: root.querySelector('img')?.src || ''
                        });
                    }
                }
                return results;
            }
            """
        )

    def search(self, request):
        browser = BrowserManager()
        if self.PROXY_URL:
            app_logger.info(f"LinkedIn scraping via PROXY: {self.PROXY_URL.split('@')[-1]}")
        else:
            app_logger.info("LinkedIn scraping via DIRECT connection (no proxy)")

        page = None
        try:
            page = browser.launch(proxy_url=self.PROXY_URL)
            url = self._build_classic_url(request)
            app_logger.info(f"LinkedIn classic search URL: {url}")
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=self.NAVIGATION_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                app_logger.warning("LinkedIn navigation timed out; continuing with available DOM")
                response = None
            if response is not None:
                BlockDetector.check("linkedin", page, response)

            try:
                page.wait_for_selector("a[href*='/jobs/view/']", timeout=self.RESULT_WAIT_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                pass

            results = self._extract_results(page)
            previous_count = len(results)
            stalls = 0
            for scroll_num in range(self.MAX_SCROLLS):
                if len(results) >= self.JOB_LIMIT:
                    break
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(self.SCROLL_WAIT_MS)
                current = self._extract_results(page)
                current_count = len(current)
                if current_count <= previous_count:
                    stalls += 1
                else:
                    results = current
                    stalls = 0
                previous_count = current_count
                if stalls >= self.MAX_CONSECUTIVE_STALLS:
                    break

            results = self._extract_results(page)
            if not results:
                self._save_debug(page, "zero-results")
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
                    "platform": "linkedin", "job_id": job_id,
                    "title": result.get("title") or "", "company": result.get("company") or "",
                    "location": result.get("location") or "", "salary": "Not Disclosed",
                    "experience": request.experience, "easy_apply": "easy apply" in text,
                    "work_mode": "Remote" if "remote" in text else "Hybrid" if "hybrid" in text else "On-site" if "on-site" in text or "onsite" in text else "Unknown",
                    "job_url": link, "apply_url": "", "description": "",
                    "company_logo": result.get("logo") or "", "posted_at": None,
                    "posted_within": request.posted_within, "status": "NEW",
                })
            return jobs[: self.JOB_LIMIT]
        except Exception:
            if page is not None:
                try: self._save_debug(page, "error")
                except Exception: pass
            raise
        finally:
            browser.close()
