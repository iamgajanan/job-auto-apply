import unittest

from app.features.saved_searches.alert_email import _render_email


class AlertEmailTests(unittest.TestCase):
    def test_render_contains_subject_and_job_details(self):
        subject, body = _render_email(
            "React Pune",
            [
                {
                    "title": "Senior React Developer",
                    "company": "Example Tech",
                    "location": "Pune",
                    "job_url": "https://example.com/jobs/123",
                }
            ],
        )
        self.assertEqual(subject, "1 new job for React Pune")
        self.assertIn("Senior React Developer", body)
        self.assertIn("Example Tech", body)
        self.assertIn("Pune", body)
        self.assertIn("https://example.com/jobs/123", body)

    def test_render_pluralizes_multiple_jobs(self):
        subject, body = _render_email("React Pune", [{"title": "A"}, {"title": "B"}])
        self.assertEqual(subject, "2 new jobs for React Pune")
        self.assertIn("2 new jobs", body)


if __name__ == "__main__":
    unittest.main()
