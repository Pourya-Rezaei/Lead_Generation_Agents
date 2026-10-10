from fastapi.testclient import TestClient

from src.config import Settings
from src.web.app import create_app


def test_source_activation_request_is_blocked_without_schema(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "activation.db"), _env_file=None))
    response = TestClient(app).post("/api/source-contracts/instagram/activation-request")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "contract_gate_blocked"


def test_source_contracts_remain_blocked(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "sources.db"), _env_file=None))
    client = TestClient(app)
    contracts = client.get("/api/source-contracts")
    page = client.get("/sources")
    assert contracts.status_code == 200
    assert all(item["status"] == "blocked" for item in contracts.json())
    assert page.status_code == 200
    assert "دروازه‌های باقی‌مانده" in page.text


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


def test_web_job_submit_status_cancel(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "web.db"), _env_file=None))
    client = TestClient(app)
    response = client.post("/api/jobs", json={"query": "cafe", "location": "Tehran", "idempotency_key": "web-1"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "queued"
    assert client.post(f"/api/jobs/{job_id}/cancel").json()["state"] == "cancelled"
