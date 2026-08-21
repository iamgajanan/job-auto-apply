import hashlib
import json

import redis

from app.config.settings import settings

# One shared connection pool for the whole process instead of every
# SearchCache() instance opening its own connection.
_redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


class SearchCache:
    def __init__(self):
        self.redis = redis.Redis(connection_pool=_redis_pool)
        # Job listings change, but an exact repeated search within a session
        # should not launch another expensive browser scrape.
        self.ttl = 60 * 30

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
        self.redis.setex(key, self.ttl, json.dumps(jobs))
