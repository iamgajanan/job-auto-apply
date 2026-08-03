import hashlib
import json

import redis

from app.config.settings import settings

# One shared connection pool for the whole process instead of every
# SearchCache() instance opening its own connection -- avoids exhausting
# Redis connections under load, and respects REDIS_URL from settings
# instead of a hardcoded localhost that breaks outside local dev
# (Docker networking, managed Redis, staging/prod, ...).
_redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


class SearchCache:

    def __init__(self):

        self.redis = redis.Redis(connection_pool=_redis_pool)

        self.ttl = 60 * 15   # 15 minutes

    def build_key(self, request):

        payload = {
            "platform": request.platform,
            "job_title": request.job_title,
            "location": request.location,
            "experience": request.experience,
            "easy_apply": request.easy_apply,
            "work_mode": request.work_mode,
            "posted_within": request.posted_within,
        }

        raw = json.dumps(payload, sort_keys=True)

        return "jobs:" + hashlib.sha256(raw.encode()).hexdigest()

    def get(self, request):

        key = self.build_key(request)

        value = self.redis.get(key)

        if value:
            return json.loads(value)

        return None

    def set(self, request, jobs):

        key = self.build_key(request)

        self.redis.setex(
            key,
            self.ttl,
            json.dumps(jobs),
        )
