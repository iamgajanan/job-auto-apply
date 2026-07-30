from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from app.common.services.base_service import BaseService
from app.gateway.cache import SearchCache
from app.gateway.limiter import RateLimiter
from app.providers.search_engine import SearchEngine


class JobService(BaseService):

    def __init__(self, repository):

        super().__init__(repository)

        self.cache = SearchCache()
        self.limiter = RateLimiter()

    def search_jobs(self, request, client_ip):

        # -------------------------
        # Rate Limit
        # -------------------------

        allowed, ttl = self.limiter.allow(client_ip)

        print(allowed)
        print(ttl)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {ttl} seconds.",
            )

        # -------------------------
        # Redis Cache
        # -------------------------

        cached = self.cache.get(request)

        if cached:
            print("✅ CACHE HIT")
            return cached

        print("❌ CACHE MISS")

        # -------------------------
        # Scrape
        # -------------------------

        engine = SearchEngine()

        jobs = engine.search(request)

        # -------------------------
        # Save
        # -------------------------

        saved_jobs = self.repository.save_many(jobs)

        # -------------------------
        # Cache
        # -------------------------

        self.cache.set(
            request,
            jsonable_encoder(saved_jobs),
        )

        return saved_jobs

    def get_jobs(self):

        return self.repository.get_all()