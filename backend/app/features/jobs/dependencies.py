from app.features.jobs.pipeline import SearchPipeline
from app.features.jobs.service import JobService
from app.gateway.cache import SearchCache
from app.gateway.limiter import RateLimiter
from app.providers.search_engine import SearchEngine


# All job searches are in-memory/direct scraper operations. No database
# session or repository is required for the scraping-only branch.
def get_job_service():
    pipeline = SearchPipeline(
        cache=SearchCache(),
        limiter=RateLimiter(),
        engine=SearchEngine(),
    )

    return JobService(pipeline=pipeline)
