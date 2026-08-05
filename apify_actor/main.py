import asyncio

from apify import Actor

from app.features.jobs.schema import JobSearchRequest
from app.providers.naukri.search import NaukriSearch


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

        request = JobSearchRequest(
            platform=platform,
            job_title=job_title,
            location=location,
            experience=experience,
            work_mode=work_mode,
            easy_apply=False,       # Naukri doesn't have easy apply
            posted_within=posted_within,
        )

        scraper = NaukriSearch()
        scraper.JOB_LIMIT = max_results  # honour user's requested cap

        try:
            jobs = scraper.search(request)
            jobs = jobs[:max_results]   # safety trim

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

        except Exception as exc:
            Actor.log.exception("Actor failed: %s", str(exc))
            raise


if __name__ == "__main__":
    asyncio.run(main())
