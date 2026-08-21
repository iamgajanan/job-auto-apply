import unittest
from unittest.mock import patch

from app.auth.dependencies import AUTH_CACHE_TTL_SECONDS, _auth_cache, _cache_get, _cache_put


class AuthCacheTests(unittest.TestCase):
    def setUp(self):
        _auth_cache.clear()

    def tearDown(self):
        _auth_cache.clear()

    def test_reuses_auth_result_within_ttl(self):
        user = {"id": "user-1", "email": "test@example.com"}
        _cache_put("token-1", user)
        self.assertEqual(_cache_get("token-1"), user)

    def test_expires_auth_result_after_ttl(self):
        user = {"id": "user-1"}
        with patch("app.auth.dependencies.monotonic", side_effect=[100.0, 100.0 + AUTH_CACHE_TTL_SECONDS + 0.01]):
            _cache_put("token-1", user)
            self.assertIsNone(_cache_get("token-1"))

    def test_cache_is_token_specific(self):
        _cache_put("token-1", {"id": "user-1"})
        _cache_put("token-2", {"id": "user-2"})
        self.assertEqual(_cache_get("token-1")["id"], "user-1")
        self.assertEqual(_cache_get("token-2")["id"], "user-2")


if __name__ == "__main__":
    unittest.main()
