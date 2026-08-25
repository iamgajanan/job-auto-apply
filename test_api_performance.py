import unittest
from unittest.mock import patch

from app.auth.dependencies import AUTH_CACHE_TTL_SECONDS, _cache_get, _cache_put


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiry = {}
        self.now = 100.0

    def _purge(self, key):
        if key in self.expiry and self.expiry[key] <= self.now:
            self.values.pop(key, None)
            self.expiry.pop(key, None)

    def get(self, key):
        self._purge(key)
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.expiry[key] = self.now + ttl

    def delete(self, key):
        self.values.pop(key, None)
        self.expiry.pop(key, None)


class AuthCacheTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.redis_patch = patch("app.auth.dependencies._redis", return_value=self.redis)
        self.redis_patch.start()

    def tearDown(self):
        self.redis_patch.stop()

    def test_reuses_auth_result_within_ttl(self):
        user = {"id": "user-1", "email": "test@example.com"}
        _cache_put("token-1", user)
        self.assertEqual(_cache_get("token-1"), user)

    def test_expires_auth_result_after_ttl(self):
        user = {"id": "user-1"}
        _cache_put("token-1", user)
        self.redis.now += AUTH_CACHE_TTL_SECONDS + 0.01
        self.assertIsNone(_cache_get("token-1"))

    def test_cache_is_token_specific(self):
        _cache_put("token-1", {"id": "user-1"})
        _cache_put("token-2", {"id": "user-2"})
        self.assertEqual(_cache_get("token-1")["id"], "user-1")
        self.assertEqual(_cache_get("token-2")["id"], "user-2")

    def test_json_round_trip(self):
        user = {"id": "user-1", "nested": {"role": "user"}}
        _cache_put("token-1", user)
        self.assertEqual(_cache_get("token-1"), user)

    def test_cache_fail_open_when_redis_errors(self):
        class BrokenRedis:
            def get(self, _key):
                import redis
                raise redis.RedisError("redis unavailable")

            def setex(self, *_args):
                import redis
                raise redis.RedisError("redis unavailable")

        with patch("app.auth.dependencies._redis", return_value=BrokenRedis()):
            self.assertIsNone(_cache_get("token-1"))
            _cache_put("token-1", {"id": "user-1"})


if __name__ == "__main__":
    unittest.main()
