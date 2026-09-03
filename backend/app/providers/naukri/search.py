import hashlib
import re
import time
from pathlib import Path

from app.providers.common.browser import BrowserManager
from app.gateway.humanizer import Humanizer
from app.gateway.block_detector import BlockDetector, PlatformAccessError
from app.core.logger import app_logger
from app.providers.base import BaseProvider, ProviderCapabilities
from app.config.settings import settings

NAUKRI_PROFILE = "browser-data-naukri"
CARD_SELECTORS = ["div.srp-jobtuple-wrapper", "div.cust-job-tuple", "article.jobTuple"]
TITLE_SELECTORS = ["a.title", ".title.ellipsis"]
COMPANY_SELECTORS = ["a.comp-name", ".comp-name", ".subTitle"]
LOCATION_SELECTORS = ["span.locWdth", ".loc-wrap span", ".location"]
EXPERIENCE_SELECTORS = ["span.expwdth", ".exp-wrap span", ".experience"]
SALARY_SELECTORS = ["span.sal-wrap span", ".sal", ".salary"]
POSTED_SELECTORS = ["span.job-post-day", ".job-post-day"]
DESCRIPTION_SELECTORS = ["span.job-desc", ".job-description"]

class NaukriSearch(BaseProvider):
    name = "naukri"
    capabilities = ProviderCapabilities(easy_apply=False, remote=True, salary=True, login=True)
    JOB_LIMIT = 60
    PROXY_URL = settings.SCRAPER_PROXY_URL or None
    PAGE_SIZE = 20
    MAX_PAGES = 3
    POST_NAV_WAIT_MS = 1200
    DEBUG_DIR = Path(__file__).resolve().parents[3] / "debug"

    def _first_match(self, card, selectors):
        for sel in selectors:
            try:
                loc = card.locator(sel)
                if loc.count() == 0:
                    continue
                text = loc.first.text_content(timeout=1000)
                if text and text.strip():
                    return text.strip()
            except Exception:
                continue
        return ""

    def _find_cards(self, page):
        for sel in CARD_SELECTORS:
            cards = page.locator(sel)
            if cards.count() > 0:
                return cards, sel
        return page.locator(CARD_SELECTORS[0]), CARD_SELECTORS[0]

    def _slugify(self, value: str) -> str:
        value = (value or "").strip().lower()
        value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
        return value or "jobs"

    def _save_debug(self, page, tag: str):
        try:
            self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(self.DEBUG_DIR / f"naukri-{tag}.png"), full_page=True)
            (self.DEBUG_DIR / f"naukri-{tag}.html").write_text(page.content(), encoding="utf-8")
        except Exception as e:
            app_logger.warning(f"Naukri debug save failed: {e}")

    def _requested_years(self, value):
        if not value or str(value).strip().lower() in {"any", "all"}:
            return None
        match = re.search(r"(\d+)", str(value))
        return int(match.group(1)) if match else None

    def _experience_matches(self, card_experience: str, requested_experience) -> bool:
        years = self._requested_years(requested_experience)
        if years is None:
            return True
        nums = [int(x) for x in re.findall(r"\d+", card_experience or "")]
        if not nums:
            return False
        if len(nums) == 1:
            return years >= nums[0]
        return nums[0] <= years <= nums[1]

    def _posted_days(self, posted: str):
        text = (posted or "").strip().lower()
        if not text:
            return None
        if any(x in text for x in ("just now", "today", "few hours", "hour ago", "hours ago", "minute ago", "minutes ago")):
            return 0
        m = re.search(r"(\d+)\s*day", text)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)\s*week", text)
        if m:
            return int(m.group(1)) * 7
        m = re.search(r"(\d+)\s*month", text)
        if m:
            return int(m.group(1)) * 30
        return None

    def _posted_matches(self, posted: str, requested) -> bool:
        value = (requested or "").strip().lower()
        if value in {"", "any", "all"}:
            return True
        limit = {
            "day": 1,
            "24h": 1,
            "3 days": 3,
            "3days": 3,
            "3-day": 3,
            "week": 7,
            "15 days": 15,
            "15days": 15,
            "15-day": 15,
            "month": 30,
        }.get(value)
        if limit is None:
            return True
        days = self._posted_days(posted)
        return days is not None and days <= limit

    def _detect_work_mode(self, text: str) -> str:
        text = (text or "").lower()
        if "remote" in text or "work from home" in text or "wfh" in text:
            return "Remote"
        if "hybrid" in text:
            return "Hybrid"
        if any(marker in text for marker in ("on-site", "onsite", "on site", "work from office", "wfo")):
            return "On-site"
        return "Unknown"

    def _work_mode_matches(self, actual: str, request) -> bool:
        requested = (request.work_mode or "any").strip().lower()
        if requested in {"", "any", "all"}:
            return True
        requested = {"onsite": "on-site", "on site": "on-site"}.get(requested, requested)
        if requested == "on-site" and actual.lower() == "unknown":
            return True
        return actual.lower() == requested

    def _job_id_from_link(self, link: str) -> str:
        if not link:
            return ""
        match = re.search(r"(?:-|/)(\d{5,})(?:[/?#-]|$)", link)
        if match:
            return match.group(1)
        return hashlib.sha1(link.encode("utf-8")).hexdigest()[:20]

    def _extract_job_link(self, card) -> str:
        selectors = ["a.title", 'a[href*="/job-listings/"]', 'a[href*="/job/"]', "a[href]"]
        for sel in selectors:
            try:
                loc = card.locator(sel)
                if loc.count() == 0:
                    continue
                href = loc.first.get_attribute("href", timeout=1000) or ""
                if href.strip():
                    return href.strip()
            except Exception:
                continue
        return ""

    def _fallback_job_id(self, title, company, location, link):
        raw = "|".join((title or "", company or "", location or "", link or "")).strip().lower()
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20] if raw else ""

    def search(self, request):
        browser = BrowserManager(profile_name=NAUKRI_PROFILE)
        if self.PROXY_URL:
            app_logger.info(f"Naukri scraping via PROXY: {self.PROXY_URL.split('@')[-1]}")
        else:
            app_logger.info("Naukri scraping via DIRECT connection (no proxy)")
        try:
            page = browser.launch(block_resources=False, proxy_url=self.PROXY_URL)
            base_path = f"https://www.naukri.com/{self._slugify(request.job_title)}-jobs-in-{self._slugify(request.location)}"
            jobs, seen_job_ids = [], set()
            start_time = time.time()
            for page_num in range(self.MAX_PAGES):
                url = base_path if page_num == 0 else f"{base_path}-{page_num + 1}"
                app_logger.debug(f"Naukri page {page_num + 1} | {url}")
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    BlockDetector.check("naukri", page, response)
                except PlatformAccessError:
                    raise
                except Exception as e:
                    app_logger.warning(f"Naukri navigation failed: {e}")
                    raise
                Humanizer.think(page)
                cards, used_selector = self._find_cards(page)
                try:
                    page.wait_for_selector(used_selector, timeout=self.POST_NAV_WAIT_MS)
                except Exception:
                    page.wait_for_timeout(self.POST_NAV_WAIT_MS)
                cards, used_selector = self._find_cards(page)
                count = cards.count()
                app_logger.debug(f"Naukri page {page_num + 1}: {count} cards via '{used_selector}'")
                if count == 0:
                    BlockDetector.check("naukri", page, response)
                    if page_num == 0:
                        self._save_debug(page, "zero-results")
                    break
                page_new_count = 0
                for i in range(count):
                    if len(jobs) >= self.JOB_LIMIT:
                        break
                    card = cards.nth(i)
                    title = self._first_match(card, TITLE_SELECTORS)
                    company = self._first_match(card, COMPANY_SELECTORS)
                    location = self._first_match(card, LOCATION_SELECTORS)
                    experience = self._first_match(card, EXPERIENCE_SELECTORS)
                    salary = self._first_match(card, SALARY_SELECTORS)
                    posted = self._first_match(card, POSTED_SELECTORS)
                    description = self._first_match(card, DESCRIPTION_SELECTORS)
                    link = self._extract_job_link(card)
                    job_id = card.get_attribute("data-job-id") or self._job_id_from_link(link)
                    if not job_id:
                        job_id = self._fallback_job_id(title, company, location, link)
                    if not job_id or job_id in seen_job_ids:
                        continue
                    seen_job_ids.add(job_id)
                    work_mode = self._detect_work_mode(card.text_content() or "")
                    if not self._work_mode_matches(work_mode, request):
                        continue
                    if not self._experience_matches(experience, request.experience):
                        continue
                    if not self._posted_matches(posted, request.posted_within):
                        continue
                    jobs.append({"platform": "naukri", "job_id": job_id, "title": title, "company": company, "location": location or request.location, "salary": salary or "Not Disclosed", "experience": experience or request.experience, "easy_apply": False, "work_mode": work_mode, "job_url": link, "apply_url": "", "description": description, "company_logo": "", "posted_at": None, "posted_within": posted or request.posted_within, "status": "NEW"})
                    page_new_count += 1
                app_logger.debug(f"Naukri page {page_num + 1} added {page_new_count} new jobs. Total: {len(jobs)}")
                if len(jobs) >= self.JOB_LIMIT or page_new_count == 0:
                    break
                Humanizer.random_delay(page)
            app_logger.info(f"TOTAL NAUKRI JOBS SCRAPED: {len(jobs)} (took {time.time() - start_time:.1f}s)")
            return jobs
        finally:
            browser.close()
