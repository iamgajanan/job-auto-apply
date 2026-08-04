from time import perf_counter

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder


class SearchPipeline:

    def __init__(
        self,
        repository,
        audit_service,
        cache,
        limiter,
        engine,
    ):
        self.repository = repository
        self.audit = audit_service
        self.cache = cache
        self.limiter = limiter
        self.engine = engine

    def _platforms_for(self, request):
        if request.platform.lower() == "all":
            return self.engine.registry.list()
        return [request.platform.lower()]

    def execute(self, request, client_ip):

        started = perf_counter()

        provider = request.platform
        keyword = request.job_title
        location = request.location

        # Cache FIRST: a cache hit causes zero upstream traffic and therefore
        # should not consume either client or platform scrape allowance.
        cached = self.cache.get(request)

        if cached:
            duration = int((perf_counter() - started) * 1000)
            self.audit.log(
                provider=provider,
                keyword=keyword,
                location=location,
                client_ip=client_ip,
                response_source="CACHE",
                jobs_found=len(cached),
                duration_ms=duration,
                status="SUCCESS",
            )
            return cached

        # Client protection applies only when work would actually reach a scraper.
        allowed, ttl = self.limiter.allow_client(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many uncached searches. Try again in {ttl} seconds.",
            )

        # Upstream protection is separate from the caller/IP limiter. For 'all',
        # reserve every provider atomically before starting either scraper.
        platforms = self._platforms_for(request)
        allowed, ttl = self.limiter.allow_platforms(platforms)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Search provider cooldown active. Try again in {ttl} seconds.",
            )

        try:
            jobs = self.engine.search(request)
            saved_jobs = self.repository.save_many(jobs)

            self.cache.set(
                request,
                jsonable_encoder(saved_jobs),
            )

            duration = int((perf_counter() - started) * 1000)
            self.audit.log(
                provider=provider,
                keyword=keyword,
                location=location,
                client_ip=client_ip,
                response_source="SCRAPER",
                jobs_found=len(saved_jobs),
                duration_ms=duration,
                status="SUCCESS",
            )
            return saved_jobs

        except Exception as e:
            duration = int((perf_counter() - started) * 1000)
            self.audit.log(
                provider=provider,
                keyword=keyword,
                location=location,
                client_ip=client_ip,
                response_source="SCRAPER",
                jobs_found=0,
                duration_ms=duration,
                status="FAILED",
                error=str(e),
            )
            raise
