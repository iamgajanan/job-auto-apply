import asyncio

from apify import Actor

from app.features.jobs.schema import JobSearchRequest
from app.providers.naukri_api import NaukriAPISearch


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
            "Starting Naukri API search: %s in %s (max %s)",
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

        # NaukriAPISearch uses httpx (pure HTTP) — no browser, no Akamai,
        # no 403. Works from any IP including Apify's cloud containers.
        scraper = NaukriAPISearch()
        scraper.JOB_LIMIT = max_results

        try:
            jobs = scraper.search(request)

            Actor.log.info("Search finished: %s jobs found", len(jobs))

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
                "method":        "api",
            })

            Actor.log.info("Actor completed: %s jobs", len(jobs))

        except Exception as exc:
            Actor.log.exception("Actor failed: %s", str(exc))
            await Actor.set_value("ACTOR_STATS", {
                "status":   "failed",
                "error":    str(exc),
                "platform": "naukri",
            })
            raise


if __name__ == "__main__":
    asyncio.run(main())