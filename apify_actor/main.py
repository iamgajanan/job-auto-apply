import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from apify import Actor

from app.features.jobs.schema import JobSearchRequest
from app.providers.naukri.search import NaukriSearch


def get_proxy_url() -> str | None:
    """
    Read the Webshare proxy from the Actor environment.

    Never hard-code proxy credentials in GitHub.

    Expected environment variable:

        WEBSHARE_PROXY_URL=http://username:password@host:port
    """

    value = os.getenv(
        "WEBSHARE_PROXY_URL",
        "",
    ).strip()

    return value or None


def run_scraper(
    request: JobSearchRequest,
    max_results: int,
    proxy_url: str | None,
) -> list:
    """
    Run the synchronous Playwright scraper in a worker thread.
    """

    scraper = NaukriSearch()

    scraper.JOB_LIMIT = max_results
    scraper.PROXY_URL = proxy_url

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

        experience = (
            actor_input.get("experience")
            or None
        )

        work_mode = (
            actor_input.get(
                "work_mode",
                "any",
            )
            or "any"
        )

        posted_within = (
            actor_input.get(
                "posted_within",
                "any",
            )
            or "any"
        )

        try:
            max_results = int(
                actor_input.get(
                    "maxResults",
                    10,
                )
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
                f"Platform '{platform}' is not "
                "supported by this Actor yet. "
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
        # PROXY
        # ---------------------------------------------------------

        proxy_url = get_proxy_url()

        if proxy_url:
            Actor.log.info(
                "Webshare proxy configuration detected."
            )
        else:
            Actor.log.warning(
                "WEBSHARE_PROXY_URL is not configured. "
                "The scraper will use the Actor's direct "
                "network connection."
            )

        # ---------------------------------------------------------
        # REQUEST
        # ---------------------------------------------------------

        Actor.log.info(
            "Starting Naukri search: %s in %s "
            "(max %s results)",
            job_title,
            location,
            max_results,
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

        # ---------------------------------------------------------
        # SCRAPE
        # ---------------------------------------------------------

        try:
            loop = asyncio.get_running_loop()

            with ThreadPoolExecutor(
                max_workers=1
            ) as executor:

                jobs = await loop.run_in_executor(
                    executor,
                    run_scraper,
                    request,
                    max_results,
                    proxy_url,
                )

            Actor.log.info(
                "Scraper finished: %s jobs found",
                len(jobs),
            )

            # -----------------------------------------------------
            # OUTPUT
            # -----------------------------------------------------

            if jobs:
                await Actor.push_data(jobs)

                Actor.log.info(
                    "Pushed %s jobs to dataset.",
                    len(jobs),
                )

            else:
                Actor.log.warning(
                    "Search returned 0 jobs."
                )

            await Actor.set_value(
                "ACTOR_STATS",
                {
                    "status": "completed",
                    "platform": "naukri",
                    "job_title": job_title,
                    "location": location,
                    "jobs_scraped": len(jobs),
                    "max_requested": max_results,
                    "proxy_configured": bool(
                        proxy_url
                    ),
                    "browser_mode": "ephemeral",
                },
            )

            Actor.log.info(
                "Actor completed: %s jobs",
                len(jobs),
            )

        except Exception as exc:
            Actor.log.exception(
                "Actor failed while running "
                "Naukri search: %s",
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
                        "max_requested": max_results,
                        "proxy_configured": bool(
                            proxy_url
                        ),
                        "error": str(exc),
                    },
                )
            except Exception:
                pass

            raise


if __name__ == "__main__":
    asyncio.run(main())