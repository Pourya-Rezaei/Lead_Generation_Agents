import sqlite3

from fastapi.testclient import TestClient

from src.config import Settings
from src.web.app import create_app


def test_jobs_history_and_detail_render(tmp_path):
    database = str(tmp_path / "history.db")
    app = create_app(Settings(database_path=database, _env_file=None))
    client = TestClient(app)
    response = client.post("/api/jobs", json={"query": "cafe", "location": "Tehran", "idempotency_key": "history-1"})
    job_id = response.json()["job_id"]
    assert client.get("/jobs").status_code == 200
    detail = client.get(f"/jobs/{job_id}")
    assert detail.status_code == 200
    assert job_id in detail.text
    assert 'id="job-state"' in detail.text
    assert 'id="cancel-job"' in detail.text
    assert 'id="job-progress"' in detail.text
    assert 'هزینه و جزئیات فنی' in detail.text
    assert 'در صف' in detail.text


def test_failed_job_can_be_retried(tmp_path):
    database = str(tmp_path / "retry.db")
    app = create_app(Settings(database_path=database, _env_file=None))
    client = TestClient(app)
    response = client.post("/api/jobs", json={"query": "cafe", "location": "Tehran", "idempotency_key": "retry-1"})
    job_id = response.json()["job_id"]
    from src.execution.service import JobService
    service = JobService(database)
    with service._connect() as db:
        db.execute("UPDATE jobs SET state = 'partial' WHERE job_id = ?", (job_id,))
    retry = client.post(f"/api/jobs/{job_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["retry_of"] == job_id
    assert retry.json()["state"] == "queued"


def test_needs_review_requires_confirmation_before_retry(tmp_path):
    database = str(tmp_path / "review.db")
    app = create_app(Settings(database_path=database, _env_file=None))
    client = TestClient(app)
    job_id = client.post("/api/jobs", json={"query": "cafe", "location": "Tehran", "idempotency_key": "review-1"}).json()["job_id"]
    with sqlite3.connect(database) as db:
        db.execute("UPDATE jobs SET state = 'needs_review', error_code = 'ProviderStartOutcomeUnknown' WHERE job_id = ?", (job_id,))
        db.execute("INSERT INTO provider_attempts(attempt_id, job_id, source, status, checkpoint, created_at, updated_at) VALUES ('attempt-1', ?, 'places', 'starting', '{}', datetime('now'), datetime('now'))", (job_id,))
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["provider_attempts"][0]["status"] == "starting"
    refused = client.post(f"/api/jobs/{job_id}/resolve", json={"action": "retry"})
    assert refused.status_code == 409
    resolved = client.post(f"/api/jobs/{job_id}/resolve", json={"action": "retry", "confirmed_no_remote_run": True})
    assert resolved.status_code == 200
    assert resolved.json()["state"] == "queued"


def test_needs_review_can_attach_known_run_for_resume(tmp_path):
    database = str(tmp_path / "attach-run.db")
    app = create_app(Settings(database_path=database, _env_file=None))
    client = TestClient(app)
    job_id = client.post("/api/jobs", json={"query": "cafe", "location": "Tehran", "idempotency_key": "review-attach"}).json()["job_id"]
    with sqlite3.connect(database) as db:
        db.execute("UPDATE jobs SET state = 'needs_review' WHERE job_id = ?", (job_id,))
    response = client.post(f"/api/jobs/{job_id}/resolve", json={"action": "attach_run", "source": "places", "provider_run_id": "known-run"})
    assert response.status_code == 200
    assert response.json()["state"] == "queued"
    assert client.get(f"/api/jobs/{job_id}").json()["provider_attempts"][0]["provider_run_id"] == "known-run"


def test_web_job_submit_status_cancel(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "web.db"), _env_file=None))
    client = TestClient(app)
    response = client.post("/api/jobs", json={"query": "cafe", "location": "Tehran", "idempotency_key": "web-1"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "queued"
    assert client.post(f"/api/jobs/{job_id}/cancel").json()["state"] == "cancelled"
