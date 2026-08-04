import asyncio

from apify import Actor

from app.features.jobs.schema import JobSearchRequest
from app.providers.search_engine import SearchEngine


async def main() -> None:
    async with Actor:

        actor_input = await Actor.get_input() or {}

        platform = actor_input.get("platform", "linkedin").lower()
        job_title = actor_input.get("job_title", "").strip()
        location = actor_input.get("location", "").strip()

        experience = actor_input.get("experience", "")
        work_mode = actor_input.get("work_mode", "any")
        easy_apply = actor_input.get("easy_apply", False)
        posted_within = actor_input.get("posted_within", "any")

        max_results = min(
            max(int(actor_input.get("maxResults", 100)), 1),
            100,
        )

        Actor.log.info(
            "Starting %s search: %s in %s",
            platform,
            job_title,
            location,
        )

        request = JobSearchRequest(
            platform=platform,
            job_title=job_title,
            location=location,
            experience=experience,
            work_mode=work_mode,
            easy_apply=easy_apply,
            posted_within=posted_within,
        )

        # No PostgreSQL
        # No Redis
        # No SearchPipeline
        # No AuditService
        # Actor only executes the scraper/provider layer.
        engine = SearchEngine()

        try:
            jobs = engine.search(request)

            jobs = jobs[:max_results]

            if jobs:
                await Actor.push_data(jobs)

            await Actor.set_value(
                "ACTOR_STATS",
                {
                    "jobs_scraped": len(jobs),
                    "platform": platform,
                    "job_title": job_title,
                    "location": location,
                },
            )

            Actor.log.info(
                "Actor completed successfully: %s jobs",
                len(jobs),
            )

        except Exception as exc:
            Actor.log.exception(
                "Actor failed: %s",
                str(exc),
            )
            raise


if __name__ == "__main__":
    asyncio.run(main())