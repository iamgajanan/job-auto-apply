import redis

from app.config.settings import settings
from app.core.logger import app_logger

# Shared Redis pool for all gateway controls.
_redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


class RateLimiter:
    """Two-layer limiter.

    1) Client limiter protects our API from one caller flooding it.
    2) Platform cooldown protects upstream job sites. It is checked ONLY on a
       cache miss, so cached searches never consume platform allowance.

    The platform check uses one Redis Lua script so platform='all' cannot
    reserve LinkedIn and then fail to reserve Naukri (or vice versa).
    """

    CLIENT_LIMIT = 10
    CLIENT_WINDOW_SECONDS = 60

    # Intentionally conservative. This limits *scrape starts*, not individual
    # browser requests inside a scrape. Provider pagination is audited separately.
    PLATFORM_COOLDOWN_SECONDS = {
        "linkedin": 30,
        "naukri": 30,
    }

    _RESERVE_PLATFORMS = """
    local ttl = 0
    for i, key in ipairs(KEYS) do
        local current_ttl = redis.call('TTL', key)
        if current_ttl > ttl then
            ttl = current_ttl
        end
    end
    if ttl > 0 then
        return {0, ttl}
    end
    for i, key in ipairs(KEYS) do
        redis.call('SET', key, '1', 'EX', ARGV[i], 'NX')
    end
    return {1, 0}
    """

    def __init__(self):
        self.redis = redis.Redis(connection_pool=_redis_pool)

    def allow(self, key: str):
        """Backward-compatible client/IP rate limit."""
        return self.allow_client(key)

    def allow_client(self, key: str):
        redis_key = f"rate:client:{key}"
        current = self.redis.incr(redis_key)

        if current == 1:
            self.redis.expire(redis_key, self.CLIENT_WINDOW_SECONDS)

        ttl = max(self.redis.ttl(redis_key), 0)
        app_logger.debug(f"{redis_key} count={current} ttl={ttl}")

        if current > self.CLIENT_LIMIT:
            return False, ttl
        return True, ttl

    def allow_platforms(self, platforms: list[str]):
        """Atomically reserve scrape-start cooldowns for requested platforms."""
        normalized = []
        for platform in platforms:
            name = platform.lower()
            if name in self.PLATFORM_COOLDOWN_SECONDS and name not in normalized:
                normalized.append(name)

        if not normalized:
            return True, 0

        keys = [f"rate:platform:{name}" for name in normalized]
        cooldowns = [str(self.PLATFORM_COOLDOWN_SECONDS[name]) for name in normalized]
        allowed, ttl = self.redis.eval(
            self._RESERVE_PLATFORMS,
            len(keys),
            *keys,
            *cooldowns,
        )

        app_logger.debug(
            f"platform reservation platforms={normalized} allowed={bool(allowed)} ttl={ttl}"
        )
        return bool(allowed), int(ttl)
