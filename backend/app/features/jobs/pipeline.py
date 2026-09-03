from time import perf_counter

from fastapi import HTTPException


class SearchPipeline:
    # A successful scrape can occasionally return an empty page when the
    # upstream job site responds incompletely. Retry a small number of times
    # before treating the search as genuinely empty.
    EMPTY_RESULT_RETRIES = 2
    EMPTY_RESULT_RETRY_DELAY_SECONDS = 2

    def __init__(self, cache, limiter, engine):
        self.cache = cache
        self.limiter = limiter
        self.engine = engine

    def _platforms_for(self, request):
        if request.platform.lower() == "all":
            return self.engine.registry.list()
        return [request.platform.lower()]

    def execute(self, request, client_ip):
        started = perf_counter()

        cached = self.cache.get(request)
        if cached:
            return cached

        allowed, ttl = self.limiter.allow_client(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many uncached searches. Try again in {ttl} seconds.",
            )

        platforms = self._platforms_for(request)
        allowed, ttl = self.limiter.allow_platforms(platforms)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Search provider cooldown active. Try again in {ttl} seconds.",
            )

        jobs = self.engine.search(request)

        # Some upstream providers can temporarily return an empty result even
        # though matching jobs are available. Retry without re-running the
        # client/platform limiter checks: the search has already reserved its
        # request slot, and re-checking here could incorrectly trigger the
        # provider cooldown against our own retry.
        for attempt in range(self.EMPTY_RESULT_RETRIES):
            if jobs:
                break

            import time

            time.sleep(self.EMPTY_RESULT_RETRY_DELAY_SECONDS)
            jobs = self.engine.search(request)

        # Do not cache an empty scrape. Otherwise a transient empty upstream
        # response can make subsequent requests appear empty until cache expiry.
        if jobs:
            self.cache.set(request, jobs)

        _ = perf_counter() - started
        return jobs
