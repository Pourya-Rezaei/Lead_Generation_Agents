from fastapi.testclient import TestClient

from src.config import Settings
from src.web.app import create_app


def test_web_job_submit_status_cancel(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "web.db"), _env_file=None))
    client = TestClient(app)
    response = client.post("/api/jobs", json={"query": "cafe", "location": "Tehran", "idempotency_key": "web-1"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "queued"
    assert client.post(f"/api/jobs/{job_id}/cancel").json()["state"] == "cancelled"
