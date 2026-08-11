from time import perf_counter

from fastapi import HTTPException


class SearchPipeline:
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

        # Results are returned directly. They are not persisted in PostgreSQL.
        # Redis remains responsible only for short-lived cache/rate-limit state.
        self.cache.set(request, jobs)

        _ = perf_counter() - started
        return jobs
