import unittest

from app.api.v1.saved_searches import router


class AlertTestEndpointTests(unittest.TestCase):
    def test_test_alert_endpoint_is_authenticated_saved_search_route(self):
        routes = {
            (route.path, tuple(sorted(route.methods or [])))
            for route in router.routes
        }
        self.assertIn(
            ("/saved-searches/{saved_search_id}/alert-test", ("POST",)),
            routes,
        )


if __name__ == "__main__":
    unittest.main()
