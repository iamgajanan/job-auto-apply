"""
Auth cache tests — updated for Redis-backed cache.

The old tests imported private in-memory dict internals (_auth_cache).
Since the cache now lives in Redis, we mock the redis.Redis client so
the tests run without a real Redis instance (same as CI).
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from app.auth.dependencies import AUTH_CACHE_TTL_SECONDS, _cache_get, _cache_put, invalidate_auth_cache


def _make_redis_mock():
    """Return a simple in-memory Redis mock that supports get/setex/delete."""
    store = {}

    mock = MagicMock()

    def setex(key, ttl, value):
        store[key] = value

    def get(key):
        return store.get(key)

    def delete(*keys):
        for k in keys:
            store.pop(k, None)

    mock.setex.side_effect = setex
    mock.get.side_effect = get
    mock.delete.side_effect = delete
    mock._store = store          # expose for assertions
    return mock


class AuthCacheRedisTests(unittest.TestCase):

    def setUp(self):
        self._redis_mock = _make_redis_mock()
        # Patch the module-level _redis() helper to return our mock.
        self._patcher = patch("app.auth.dependencies._redis", return_value=self._redis_mock)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    # ── basic put / get ──────────────────────────────────────────────────────

    def test_reuses_auth_result_within_ttl(self):
        user = {"id": "user-1", "email": "test@example.com"}
        _cache_put("token-1", user)
        result = _cache_get("token-1")
        self.assertEqual(result, user)

    def test_cache_is_token_specific(self):
        _cache_put("token-1", {"id": "user-1"})
        _cache_put("token-2", {"id": "user-2"})
        self.assertEqual(_cache_get("token-1")["id"], "user-1")
        self.assertEqual(_cache_get("token-2")["id"], "user-2")

    def test_cache_miss_returns_none(self):
        result = _cache_get("nonexistent-token")
        self.assertIsNone(result)

    # ── setex is called with the correct TTL ─────────────────────────────────

    def test_setex_called_with_correct_ttl(self):
        user = {"id": "user-3"}
        _cache_put("token-3", user)
        call_args = self._redis_mock.setex.call_args
        self.assertIsNotNone(call_args, "setex was not called")
        # setex(key, ttl, value)
        _, ttl, _ = call_args.args if call_args.args else (None, None, None)
        if ttl is None and call_args.kwargs:
            ttl = call_args.kwargs.get("time") or call_args.kwargs.get("ttl")
        self.assertEqual(ttl, AUTH_CACHE_TTL_SECONDS)

    # ── invalidate (delete) ──────────────────────────────────────────────────

    def test_invalidate_removes_entry(self):
        user = {"id": "user-4"}
        _cache_put("token-4", user)
        self.assertIsNotNone(_cache_get("token-4"))
        invalidate_auth_cache("token-4")
        self.assertIsNone(_cache_get("token-4"))

    # ── redis errors are swallowed (fail-open) ───────────────────────────────

    def test_cache_put_redis_error_does_not_raise(self):
        import redis as redis_lib
        self._redis_mock.setex.side_effect = redis_lib.RedisError("Redis connection error")
        # Should not raise — cache failures are fail-open
        _cache_put("token-err", {"id": "user-err"})

    def test_cache_get_redis_error_returns_none(self):
        import redis as redis_lib
        self._redis_mock.get.side_effect = redis_lib.RedisError("Redis connection error")
        result = _cache_get("token-err")
        self.assertIsNone(result)

    # ── value is serialised as JSON ──────────────────────────────────────────

    def test_stored_value_is_json_serialisable(self):
        user = {"id": "user-5", "email": "a@b.com", "role": "user"}
        _cache_put("token-5", user)
        # Grab the raw stored bytes/string and decode it
        raw = self._redis_mock._store.get(
            next(k for k in self._redis_mock._store if "token-5" in k), None
        )
        self.assertIsNotNone(raw, "Nothing stored in Redis mock")
        parsed = json.loads(raw)
        self.assertEqual(parsed["id"], "user-5")


if __name__ == "__main__":
    unittest.main()
