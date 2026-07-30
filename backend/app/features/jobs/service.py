from time import perf_counter

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from app.common.services.base_service import BaseService


class JobService(BaseService):

    def __init__(
        self,
        repository,
        audit_service,
        cache,
        limiter,
        engine,
    ):
        super().__init__(repository)

        self.audit = audit_service
        self.cache = cache
        self.limiter = limiter
        self.engine = engine

    def search_jobs(self, request, client_ip):

        started = perf_counter()

        provider = request.platform
        keyword = request.job_title
        location = request.location

        allowed, ttl = self.limiter.allow(client_ip)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {ttl} seconds.",
            )

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

    def get_jobs(self):
        return self.repository.get_all()