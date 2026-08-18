import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.features.jobs.schema import JobResponse, ViewedJob, ViewedJobRequest
from app.features.jobs.viewed_service import ViewedJobService


JOB = {
    "id": None,
    "platform": "naukri",
    "job_id": "naukri-123",
    "title": "React Developer",
    "company": "Example Ltd",
    "location": "Pune",
    "salary": None,
    "experience": "5 years",
    "work_mode": "hybrid",
    "easy_apply": False,
    "job_url": "https://example.com/job/123",
    "apply_url": "https://example.com/apply/123",
    "description": None,
    "company_logo": None,
    "status": "active",
}


class ViewedJobSchemaTests(unittest.TestCase):
    def test_viewed_request_matches_job_response_shape(self):
        request = ViewedJobRequest.model_validate(JOB)
        self.assertEqual(request.platform, "naukri")
        self.assertEqual(request.job_id, "naukri-123")

    def test_invalid_platform_is_rejected(self):
        invalid = {**JOB, "platform": "indeed"}
        with self.assertRaises(ValueError):
            JobResponse.model_validate(invalid)

    def test_viewed_job_serializes_timestamps(self):
        value = ViewedJob(
            id="view-1",
            platform="naukri",
            job_id="naukri-123",
            job_data=JOB,
            viewed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.assertEqual(value.job_id, "naukri-123")


class ViewedJobServiceTests(unittest.TestCase):
    @patch("app.features.jobs.viewed_service.get_engine")
    def test_mark_viewed_uses_upsert(self, get_engine):
        connection = MagicMock()
        result = MagicMock()
        result.mappings.return_value.one.return_value = {
            "id": "view-1",
            "platform": "naukri",
            "job_id": "naukri-123",
            "job_data": JOB,
            "viewed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        connection.execute.return_value = result
        get_engine.return_value.begin.return_value.__enter__.return_value = connection

        saved = ViewedJobService().mark_viewed("user-1", JOB)

        self.assertEqual(saved["job_id"], "naukri-123")
        sql = str(connection.execute.call_args.args[0])
        self.assertIn("on conflict (user_id, platform, job_id)", sql.lower())
        self.assertIn("do update set", sql.lower())

    @patch("app.features.jobs.viewed_service.get_engine")
    def test_list_is_scoped_to_user(self, get_engine):
        connection = MagicMock()
        result = MagicMock()
        result.mappings.return_value.all.return_value = []
        connection.execute.return_value = result
        get_engine.return_value.connect.return_value.__enter__.return_value = connection

        ViewedJobService().list_viewed("user-1")

        params = connection.execute.call_args.args[1]
        self.assertEqual(params["user_id"], "user-1")
        sql = str(connection.execute.call_args.args[0])
        self.assertIn("where user_id = :user_id", sql.lower())


if __name__ == "__main__":
    unittest.main()
