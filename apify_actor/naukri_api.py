"""
Naukri API Client — replaces Playwright scraper for Apify.

Uses Naukri's internal JSON API (same one their website calls).
No browser needed, no Akamai, works from any IP including cloud.
"""
import re
import time
from typing import Optional, List

import httpx

from app.core.logger import app_logger


class NaukriAPISearch:
    """
    Calls Naukri's internal search API directly.
    Drop-in replacement for NaukriSearch on Apify.
    """

    API_URL = "https://www.naukri.com/jobapi/v3/search"
    JOB_LIMIT = 100
    PAGE_SIZE = 20

    HEADERS = {
        "appid": "109",
        "systemid": "Naukri",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://www.naukri.com/",
        "Origin": "https://www.naukri.com",
    }

    def _requested_years(self, value) -> Optional[int]:
        if not value or str(value).strip().lower() in {"any", "all", ""}:
            return None
        match = re.search(r"(\d+)", str(value))
        return int(match.group(1)) if match else None

    def _experience_matches(self, exp_text: str, requested) -> bool:
        """Filter by experience. e.g. '3-6 Yrs' vs '5 years'"""
        years = self._requested_years(requested)
        if years is None:
            return True
        if not exp_text:
            return False
        range_match = re.search(r"(\d+)\s*-\s*(\d+)", exp_text)
        if range_match:
            lo, hi = int(range_match.group(1)), int(range_match.group(2))
            return lo <= years <= hi
        plus_match = re.search(r"(\d+)\+", exp_text)
        if plus_match:
            return years >= int(plus_match.group(1))
        single = re.search(r"(\d+)", exp_text)
        if single:
            return years == int(single.group(1))
        return True

    def _work_mode_matches(self, tags: str, work_mode: Optional[str]) -> bool:
        if not work_mode or work_mode.lower() in ("any", "all", ""):
            return True
        tags_lower = tags.lower()
        mode = work_mode.lower()
        if mode == "remote":
            return any(x in tags_lower for x in ("work from home", "remote", "wfh"))
        if mode == "hybrid":
            return "hybrid" in tags_lower
        if mode in ("onsite", "on-site"):
            return not any(x in tags_lower for x in ("work from home", "remote", "wfh", "hybrid"))
        return True

    def _posted_matches(self, posted_text: str, posted_within: Optional[str]) -> bool:
        if not posted_within or posted_within.lower() in ("any", "all", ""):
            return True
        text = posted_text.lower()
        if any(x in text for x in ("just now", "today", "hour", "minute")):
            days = 0
        else:
            match = re.search(r"(\d+)\s*(day|week|month)", text)
            if not match:
                return True
            n, unit = int(match.group(1)), match.group(2)
            days = n if "day" in unit else (n * 7 if "week" in unit else n * 30)

        limits = {"day": 1, "week": 7, "month": 30}
        return days <= limits.get(posted_within.lower(), 9999)

    def _parse_job(self, job: dict) -> dict:
        """Convert Naukri API job dict to our standard schema."""
        placeholders = job.get("placeholders", [])
        location = next(
            (p.get("label", "") for p in placeholders if p.get("type") == "location"),
            "",
        )
        exp_text = job.get("experienceText", "") or ""
        salary   = job.get("salaryDetail", "") or ""
        tags     = " ".join(job.get("tagsAndSkills", []) or [])
        posted   = (job.get("footerPlaceholderLabel", "") or "").lower()

        # work mode from tags
        if any(x in tags.lower() for x in ("work from home", "remote", "wfh")):
            work_mode = "Remote"
        elif "hybrid" in tags.lower():
            work_mode = "Hybrid"
        elif tags:
            work_mode = "On-site"
        else:
            work_mode = "Unknown"

        job_url = job.get("jdURL", "") or ""
        if job_url and not job_url.startswith("http"):
            job_url = f"https://www.naukri.com{job_url}"

        return {
            "platform":      "naukri",
            "job_id":        str(job.get("jobId", "")),
            "title":         job.get("title", ""),
            "company":       job.get("companyName", ""),
            "location":      location,
            "experience":    exp_text,
            "salary":        salary,
            "work_mode":     work_mode,
            "tags":          tags,
            "job_url":       job_url,
            "description":   job.get("jobDescription", ""),
            "posted_within": posted,
            "status":        "NEW",
        }

    def search(self, request) -> List[dict]:
        jobs     = []
        seen_ids = set()
        page_no  = 1
        max_pages = max(1, (self.JOB_LIMIT + self.PAGE_SIZE - 1) // self.PAGE_SIZE)

        with httpx.Client(headers=self.HEADERS, timeout=30) as client:
            while len(jobs) < self.JOB_LIMIT and page_no <= max_pages:
                params = {
                    "noOfResults": self.PAGE_SIZE,
                    "urlType":    "search_by_key_loc",
                    "searchType": "adv",
                    "keyword":    request.job_title,
                    "location":   request.location,
                    "pageNo":     page_no,
                    "src":        "jobsearchDesk",
                    "xp":         "1",
                    "areaTypeID": "0",
                }

                app_logger.debug(f"Naukri API page {page_no} | {request.job_title} in {request.location}")

                try:
                    r = client.get(self.API_URL, params=params)
                    if r.status_code != 200:
                        app_logger.warning(f"Naukri API returned {r.status_code} on page {page_no}")
                        break
                    data = r.json()
                except Exception as e:
                    app_logger.error(f"Naukri API request failed: {e}")
                    break

                raw_jobs = data.get("jobDetails", [])
                if not raw_jobs:
                    app_logger.info(f"No more jobs at page {page_no}")
                    break

                page_added = 0
                for raw in raw_jobs:
                    job = self._parse_job(raw)
                    job_id = job["job_id"]
                    if job_id in seen_ids:
                        continue
                    # Apply filters
                    if not self._experience_matches(job["experience"], request.experience):
                        continue
                    if not self._work_mode_matches(job["tags"], request.work_mode):
                        continue
                    if not self._posted_matches(job["posted_within"], request.posted_within):
                        continue
                    seen_ids.add(job_id)
                    jobs.append(job)
                    page_added += 1
                    if len(jobs) >= self.JOB_LIMIT:
                        break

                app_logger.debug(f"Page {page_no}: {page_added} jobs added. Total: {len(jobs)}")
                page_no += 1
                time.sleep(0.5)  # polite delay

        app_logger.info(f"TOTAL NAUKRI API JOBS: {len(jobs)}")
        return jobs