def test_resend_deployment_workflow_exists():
    from pathlib import Path

    workflow = Path(__file__).parents[2] / ".github/workflows/configure-resend.yml"
    text = workflow.read_text()
    assert "RESEND_API_KEY" in text
    assert "RESEND_FROM_EMAIL" in text
    assert "job-auto-apply.service" in text
