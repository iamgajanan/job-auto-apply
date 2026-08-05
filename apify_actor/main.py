import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from apify import Actor

from app.features.jobs.schema import JobSearchRequest
from app.providers.naukri.search import NaukriSearch

# Webshare rotating residential proxy
# Routes through real residential IPs — bypasses Naukri's Akamai block
# Webshare Rotating Residential — India endpoint
# Get exact URL from: Webshare Dashboard → Rotating Residential → Endpoint Generator → Country: India
PROXY_URL = "http://nvwsanen-in-rotate:2hdb4hzilfe3@p.webshare.io:80"


def run_scraper(request: JobSearchRequest, max_results: int) -> list:
    """
    Runs sync Playwright scraper in a thread (outside asyncio loop).
    Uses Webshare residential proxy so Naukri sees a real home IP.
    """
    scraper = NaukriSearch()
    scraper.JOB_LIMIT = max_results
    scraper.PROXY_URL = PROXY_URL
    jobs = scraper.search(request)
    return jobs[:max_results]


async def main() -> None:
    async with Actor:

        actor_input = await Actor.get_input() or {}

        # ── Required ──────────────────────────────────────────────────
        platform  = actor_input.get("platform", "naukri").strip().lower()
        job_title = actor_input.get("job_title", "").strip()
        location  = actor_input.get("location",  "").strip()

        if platform != "naukri":
            raise ValueError(
                f"Platform '{platform}' is not supported yet. "
                "Use platform='naukri'. LinkedIn coming soon."
            )
        if not job_title:
            raise ValueError("job_title is required.")
        if not location:
            raise ValueError("location is required.")

        # ── Optional filters ──────────────────────────────────────────
        experience    = actor_input.get("experience")    or None
        work_mode     = actor_input.get("work_mode",     "any") or "any"
        posted_within = actor_input.get("posted_within", "any") or "any"

        try:
            max_results = int(actor_input.get("maxResults", 20))
        except (TypeError, ValueError):
            max_results = 20
        max_results = min(max(max_results, 1), 100)

        Actor.log.info(
            "Starting Naukri search: %s in %s (max %s) via residential proxy",
            job_title, location, max_results,
        )

        request = JobSearchRequest(
            platform="naukri",
            job_title=job_title,
            location=location,
            experience=experience,
            work_mode=work_mode,
            easy_apply=False,
            posted_within=posted_within,
        )

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            jobs = await loop.run_in_executor(
                executor, run_scraper, request, max_results
            )

        Actor.log.info("Scraper finished: %s jobs found", len(jobs))

        if jobs:
            await Actor.push_data(jobs)
        else:
            Actor.log.warning("Search returned 0 jobs.")

        await Actor.set_value("ACTOR_STATS", {
            "status":        "completed",
            "platform":      "naukri",
            "job_title":     job_title,
            "location":      location,
            "jobs_scraped":  len(jobs),
            "max_requested": max_results,
            "proxy":         "webshare-residential",
        })

        Actor.log.info("Actor completed: %s jobs", len(jobs))


if __name__ == "__main__":
    asyncio.run(main())