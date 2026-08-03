import redis

from app.config.settings import settings
from app.core.logger import app_logger

# Shared pool -- see cache.py for why.
_redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


class RateLimiter:

    def __init__(self):
        self.redis = redis.Redis(connection_pool=_redis_pool)

        self.limit = 10          # 10 searches
        self.window = 60         # per minute

    def allow(self, key: str):

        redis_key = f"rate:{key}"

        current = self.redis.incr(redis_key)

        if current == 1:
            self.redis.expire(redis_key, self.window)

        ttl = self.redis.ttl(redis_key)

        app_logger.debug(f"{redis_key} count={current} ttl={ttl}")

        if current > self.limit:
            return False, ttl

        return True, ttl
