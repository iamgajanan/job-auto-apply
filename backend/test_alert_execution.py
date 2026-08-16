import unittest

from app.features.saved_searches.alert_executor import _fingerprint


class AlertExecutionTests(unittest.TestCase):
    def test_same_provider_job_id_has_same_fingerprint(self):
        first = {"platform": "naukri", "job_id": "123", "job_url": "https://example.com/a"}
        second = {"platform": "naukri", "job_id": "123", "job_url": "https://example.com/b"}
        self.assertEqual(_fingerprint(first), _fingerprint(second))

    def test_different_job_ids_have_different_fingerprints(self):
        first = {"platform": "naukri", "job_id": "123"}
        second = {"platform": "naukri", "job_id": "456"}
        self.assertNotEqual(_fingerprint(first), _fingerprint(second))

    def test_url_is_used_when_job_id_is_missing(self):
        first = {"platform": "linkedin", "job_url": "https://example.com/job/123"}
        second = {"platform": "linkedin", "job_url": "https://example.com/job/123"}
        self.assertEqual(_fingerprint(first), _fingerprint(second))


if __name__ == "__main__":
    unittest.main()
