import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from apify import Actor
from apify_client import ApifyClient

from app.features.jobs.schema import JobSearchRequest
from app.providers.naukri.search import NaukriSearch


def run_scraper(request: JobSearchRequest, max_results: int, proxy_url: str = None) -> list:
    """
    Runs the sync Playwright scraper in a plain thread,
    completely outside the asyncio event loop.
    """
    scraper = NaukriSearch()
    scraper.JOB_LIMIT = max_results
    if proxy_url:
        scraper.PROXY_URL = proxy_url
    jobs = scraper.search(request)
    return jobs[:max_results]


async def main() -> None:
    async with Actor:

        actor_input = await Actor.get_input() or {}

        # ── Required ──────────────────────────────────────────────────
        platform  = actor_input.get("platform", "naukri").lower()
        job_title = actor_input.get("job_title", "").strip()
        location  = actor_input.get("location",  "").strip()

        if platform != "naukri":
            raise ValueError(
                f"Platform '{platform}' is not supported yet. "
                "LinkedIn support is coming soon — use 'naukri' for now."
            )
        if not job_title:
            raise ValueError("job_title is required")
        if not location:
            raise ValueError("location is required")

        # ── Optional filters ──────────────────────────────────────────
        experience    = actor_input.get("experience")    or None
        work_mode     = actor_input.get("work_mode",     "any")
        posted_within = actor_input.get("posted_within", "any")
        max_results   = min(max(int(actor_input.get("maxResults", 100)), 1), 100)

        Actor.log.info(
            "Starting Naukri search: %s in %s (max %s results)",
            job_title, location, max_results,
        )

        # ── Apify residential proxy ───────────────────────────────────
        # Routes requests through residential IPs to avoid 403 blocks
        proxy_config = await Actor.create_proxy_configuration(
            groups=["DATACENTER"],
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None
        if proxy_url:
            Actor.log.info("Using datacenter proxy: %s", proxy_url)
        else:
            Actor.log.warning("No proxy available — may get blocked by Naukri")

        request = JobSearchRequest(
            platform=platform,
            job_title=job_title,
            location=location,
            experience=experience,
            work_mode=work_mode,
            easy_apply=False,
            posted_within=posted_within,
        )

        # Run sync Playwright scraper in a thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            jobs = await loop.run_in_executor(
                pool, run_scraper, request, max_results, proxy_url
            )

        Actor.log.info("Scraper finished: %s jobs found", len(jobs))

        if jobs:
            await Actor.push_data(jobs)

        await Actor.set_value(
            "ACTOR_STATS",
            {
                "jobs_scraped":  len(jobs),
                "platform":      platform,
                "job_title":     job_title,
                "location":      location,
                "max_requested": max_results,
            },
        )

        Actor.log.info("Actor completed: %s jobs scraped", len(jobs))


if __name__ == "__main__":
    asyncio.run(main())