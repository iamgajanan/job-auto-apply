import time

import redis


class RateLimiter:

    def __init__(self):
        self.redis = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True,
        )

        self.limit = 10          # 10 searches
        self.window = 60         # per minute

    def allow(self, key: str):

        redis_key = f"rate:{key}"

        current = self.redis.incr(redis_key)

        print(redis_key)
        print(current)

        if current == 1:
            self.redis.expire(redis_key, self.window)

        ttl = self.redis.ttl(redis_key)

        if current > self.limit:
            return False, ttl

        return True, ttl