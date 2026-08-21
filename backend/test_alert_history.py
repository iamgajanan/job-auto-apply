from app.features.saved_searches.schemas import AlertRun


def test_queued_alert_count_is_not_presented_as_completed_result():
    run = AlertRun(
        id="run-1",
        saved_search_name="React Pune",
        scheduled_for="2026-08-21T10:00:00Z",
        status="queued",
        created_at="2026-08-21T10:00:00Z",
        started_at=None,
        completed_at=None,
        new_jobs_count=0,
        result_summary={"trigger": "manual_test"},
        error_message=None,
    )
    assert run.saved_search_name == "React Pune"
    assert run.status == "queued"
    assert run.new_jobs_count == 0


def test_completed_alert_preserves_exact_new_job_count():
    run = AlertRun(
        id="run-2",
        saved_search_name="Test Job",
        scheduled_for="2026-08-21T10:00:00Z",
        status="completed",
        created_at="2026-08-21T10:00:00Z",
        started_at="2026-08-21T10:00:01Z",
        completed_at="2026-08-21T10:00:08Z",
        new_jobs_count=8,
        result_summary={"jobs_found": 8, "new_jobs": 8},
        error_message=None,
    )
    assert run.saved_search_name == "Test Job"
    assert run.new_jobs_count == 8
