import re
import time
from pathlib import Path

from app.providers.common.browser import BrowserManager
from app.gateway.humanizer import Humanizer
from app.gateway.block_detector import BlockDetector, PlatformAccessError
from app.core.logger import app_logger

from app.providers.base import BaseProvider, ProviderCapabilities

NAUKRI_PROFILE = "browser-data-naukri"

# Naukri's markup gets tweaked periodically. We try candidate selectors
# in order and use whichever one actually matches on the page, instead
# of hard-coding a single class name that silently returns nothing the
# next time Naukri ships a redesign.
CARD_SELECTORS = [
    "div.srp-jobtuple-wrapper",
    "div.cust-job-tuple",
    "article.jobTuple",
]

TITLE_SELECTORS = ["a.title", ".title.ellipsis"]
COMPANY_SELECTORS = ["a.comp-name", ".comp-name", ".subTitle"]
LOCATION_SELECTORS = ["span.locWdth", ".loc-wrap span", ".location"]
EXPERIENCE_SELECTORS = ["span.expwdth", ".exp-wrap span", ".experience"]
SALARY_SELECTORS = ["span.sal-wrap span", ".sal", ".salary"]
POSTED_SELECTORS = ["span.job-post-day", ".job-post-day"]
DESCRIPTION_SELECTORS = ["span.job-desc", ".job-description"]


class NaukriSearch(BaseProvider):
    name = "naukri"

    capabilities = ProviderCapabilities(
        easy_apply=False,
        remote=True,
        salary=True,
        login=True,
    )

    JOB_LIMIT = 100
    PAGE_SIZE = 20
    PROXY_URL = None   # set by actor when running on Apify
    MAX_PAGES = 6
    POST_NAV_WAIT_MS = 2500

    # Save a screenshot + the raw HTML of the first page whenever we
    # come back with zero parsed jobs, so it's easy to see *why* --
    # is it a captcha, a login wall, or just a selector that changed --
    # instead of guessing blind.
    DEBUG_DIR = Path(__file__).resolve().parents[3] / "debug"

    def _first_match(self, card, selectors):
        for sel in selectors:
            try:
                loc = card.locator(sel)
                # count() is instant (no actionability wait). Only call
                # text_content() -- which DOES wait up to the default
                # timeout if nothing matches -- when we know something
                # is actually there.
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
            page.screenshot(
                path=str(self.DEBUG_DIR / f"naukri-{tag}.png"),
                full_page=True,
            )
            (self.DEBUG_DIR / f"naukri-{tag}.html").write_text(
                page.content(), encoding="utf-8"
            )
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
        low, high = nums[0], nums[1]
        return low <= years <= high

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
        limits = {"day": 1, "24h": 1, "week": 7, "month": 30}
        limit = limits.get(value)
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
        # Do not guess On-site when Naukri does not publish a work mode.
        # Unknown jobs can still be returned for work_mode=any, but they
        # must not pass an explicit On-site/Remote/Hybrid request.
        return "Unknown"

    def _work_mode_matches(self, actual: str, request) -> bool:
        requested = (request.work_mode or "").strip().lower()
        if request.remote is True:
            requested = "remote"
        if requested in {"", "any", "all"}:
            return True
        aliases = {"onsite": "on-site", "on site": "on-site"}
        requested = aliases.get(requested, requested)
        return actual.lower() == requested

    def search(self, request):

        browser = BrowserManager(profile_name=NAUKRI_PROFILE)
        # block_resources=False -- Naukri sits behind Akamai bot
        # management, which flags pages that never load a stylesheet,
        # font, or image as a strong bot signal. Loading everything
        # like a real browser matters more here than scrape speed.
        try:
            page = browser.launch(block_resources=False, proxy_url=self.PROXY_URL)

            # ── Proxy diagnostic (only when proxy is configured) ─────
            if self.PROXY_URL:
                try:
                    ip_response = page.goto(
                        "https://ipv4.webshare.io/",
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )
                    ip_text = page.locator("body").inner_text(timeout=3000).strip()
                    app_logger.info(f"Proxy IP check: status={ip_response.status if ip_response else '?'} ip={ip_text}")
                except Exception as e:
                    app_logger.warning(f"Proxy IP check failed: {e} — continuing anyway")

            # ── Retry wrapper for 403 (rotate proxy IP and retry once) ──
            self._max_403_retries = getattr(self, "_max_403_retries", 2)

            keyword_slug = self._slugify(request.job_title)
            location_slug = self._slugify(request.location)

            base_path = f"https://www.naukri.com/{keyword_slug}-jobs-in-{location_slug}"

            jobs = []
            seen_job_ids = set()
            start_time = time.time()
            empty_filtered_pages = 0
            MAX_EMPTY_FILTERED_PAGES = 2
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

                    # Prefer a data-job-id attribute directly on the card if
                    # Naukri exposes one; otherwise fall back to parsing it
                    # out of the job's URL.
                    job_id = card.get_attribute("data-job-id") or ""

                    title = self._first_match(card, TITLE_SELECTORS)
                    company = self._first_match(card, COMPANY_SELECTORS)
                    location = self._first_match(card, LOCATION_SELECTORS)
                    experience = self._first_match(card, EXPERIENCE_SELECTORS)
                    salary = self._first_match(card, SALARY_SELECTORS)
                    posted = self._first_match(card, POSTED_SELECTORS)
                    description = self._first_match(card, DESCRIPTION_SELECTORS)

                    try:
                        title_link = card.locator("a.title")
                        link = (
                            title_link.first.get_attribute("href", timeout=1000)
                            if title_link.count() > 0
                            else ""
                        ) or ""
                    except Exception:
                        link = ""

                    if not link:
                        try:
                            any_link = card.locator("a")
                            link = (
                                any_link.first.get_attribute("href", timeout=1000)
                                if any_link.count() > 0
                                else ""
                            ) or ""
                        except Exception:
                            link = ""

                    if not job_id and link:
                        match = re.search(r"-(\d{6,})(?:\?|$)", link)
                        if match:
                            job_id = match.group(1)

                    if not job_id:
                        # No reliable unique id -- skip rather than risk a
                        # duplicate/blank job_id violating the DB's unique
                        # constraint (same approach as the LinkedIn provider).
                        continue

                    if job_id in seen_job_ids:
                        continue

                    seen_job_ids.add(job_id)

                    text_blob = (card.text_content() or "").lower()
                    work_mode = self._detect_work_mode(text_blob)

                    # Naukri does not expose stable URL parameters for every
                    # API filter we accept. Enforce correctness on the parsed
                    # cards so the response always respects the request.
                    if not self._work_mode_matches(work_mode, request):
                        continue
                    if not self._experience_matches(experience, request.experience):
                        continue
                    if not self._posted_matches(posted, request.posted_within):
                        continue

                    jobs.append(
                        {
                            "platform": "naukri",
                            "job_id": job_id,
                            "title": title,
                            "company": company,
                            "location": location or request.location,
                            "salary": salary or "Not Disclosed",
                            "experience": experience or request.experience,
                            "easy_apply": False,
                            "work_mode": work_mode,
                            "job_url": link,
                            "apply_url": "",
                            "description": description,
                            "company_logo": "",
                            "posted_at": None,
                            "posted_within": posted or request.posted_within,
                            "status": "NEW",
                        }
                    )

                    page_new_count += 1

                app_logger.debug(f"Naukri page {page_num + 1} added {page_new_count} new jobs. Total: {len(jobs)}")

                if len(jobs) >= self.JOB_LIMIT:
                    break

                if page_new_count == 0:
                    empty_filtered_pages += 1
                else:
                    empty_filtered_pages = 0

                if empty_filtered_pages >= MAX_EMPTY_FILTERED_PAGES:
                    app_logger.info(
                        "Stopping Naukri pagination after %s consecutive pages "
                        "with no matching jobs",
                        empty_filtered_pages,
                    )
                    break

                Humanizer.random_delay(page)

            app_logger.info(f"TOTAL NAUKRI JOBS SCRAPED: {len(jobs)} (took {time.time() - start_time:.1f}s)")

            return jobs
        finally:
            browser.close()