import asyncio
from concurrent.futures import ThreadPoolExecutor

from apify import Actor

from app.features.jobs.schema import JobSearchRequest
from app.providers.naukri.search import NaukriSearch


def run_scraper(
    request: JobSearchRequest,
    max_results: int,
) -> list:
    """
    Run the synchronous Playwright scraper in its own worker thread.

    The Apify Actor itself runs inside an asyncio event loop,
    while the backend currently uses Playwright's synchronous API.
    """

    scraper = NaukriSearch()

    # Respect the Actor input and avoid scraping more jobs than needed.
    scraper.JOB_LIMIT = max_results

    jobs = scraper.search(request)

    return jobs[:max_results]


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        # ---------------------------------------------------------
        # INPUT
        # ---------------------------------------------------------

        platform = (
            actor_input
            .get("platform", "naukri")
            .strip()
            .lower()
        )

        job_title = (
            actor_input
            .get("job_title", "")
            .strip()
        )

        location = (
            actor_input
            .get("location", "")
            .strip()
        )

        experience = actor_input.get("experience") or None

        work_mode = (
            actor_input.get("work_mode", "any")
            or "any"
        )

        posted_within = (
            actor_input.get("posted_within", "any")
            or "any"
        )

        try:
            max_results = int(
                actor_input.get("maxResults", 10)
            )
        except (TypeError, ValueError):
            max_results = 10

        max_results = min(
            max(max_results, 1),
            100,
        )

        # ---------------------------------------------------------
        # VALIDATION
        # ---------------------------------------------------------

        if platform != "naukri":
            raise ValueError(
                f"Platform '{platform}' is not supported by the "
                "current cloud Actor. "
                "Use platform='naukri'."
            )

        if not job_title:
            raise ValueError(
                "job_title is required."
            )

        if not location:
            raise ValueError(
                "location is required."
            )

        # ---------------------------------------------------------
        # START
        # ---------------------------------------------------------

        Actor.log.info(
            "Starting Naukri search: %s in %s "
            "(max %s results)",
            job_title,
            location,
            max_results,
        )

        # IMPORTANT:
        #
        # We intentionally do NOT call:
        #
        # Actor.create_proxy_configuration(
        #     groups=["DATACENTER"]
        # )
        #
        # The previous Actor crashed here because the Apify account
        # does not currently have access to that proxy group.
        #
        # First we test Naukri's public job-search pages directly.
        Actor.log.info(
            "Running initial Naukri test without Apify proxy."
        )

        # ---------------------------------------------------------
        # BUILD BACKEND REQUEST
        # ---------------------------------------------------------

        request = JobSearchRequest(
            platform="naukri",
            job_title=job_title,
            location=location,
            experience=experience,
            work_mode=work_mode,
            easy_apply=False,
            posted_within=posted_within,
        )

        # ---------------------------------------------------------
        # RUN SCRAPER
        # ---------------------------------------------------------

        try:
            loop = asyncio.get_running_loop()

            # Playwright sync API cannot run directly inside the
            # Actor's asyncio event loop.
            #
            # Run it in one worker thread instead.
            with ThreadPoolExecutor(
                max_workers=1
            ) as executor:

                jobs = await loop.run_in_executor(
                    executor,
                    run_scraper,
                    request,
                    max_results,
                )

            Actor.log.info(
                "Naukri scraper finished: %s jobs found",
                len(jobs),
            )

            # -----------------------------------------------------
            # DATASET
            # -----------------------------------------------------

            if jobs:
                await Actor.push_data(jobs)

                Actor.log.info(
                    "Pushed %s jobs to Actor dataset.",
                    len(jobs),
                )
            else:
                Actor.log.warning(
                    "Naukri search completed but returned 0 jobs."
                )

            # -----------------------------------------------------
            # ACTOR STATS
            # -----------------------------------------------------

            await Actor.set_value(
                "ACTOR_STATS",
                {
                    "status": "completed",
                    "platform": "naukri",
                    "job_title": job_title,
                    "location": location,
                    "jobs_scraped": len(jobs),
                    "max_requested": max_results,
                    "proxy_enabled": False,
                    "browser_mode": "ephemeral",
                },
            )

            Actor.log.info(
                "Actor completed successfully: %s jobs scraped.",
                len(jobs),
            )

        except Exception as exc:
            Actor.log.exception(
                "Actor failed while running Naukri scraper: %s",
                str(exc),
            )

            try:
                await Actor.set_value(
                    "ACTOR_STATS",
                    {
                        "status": "failed",
                        "platform": "naukri",
                        "job_title": job_title,
                        "location": location,
                        "jobs_scraped": 0,
                        "error": str(exc),
                    },
                )
            except Exception:
                pass

            raise


if __name__ == "__main__":
    asyncio.run(main())
