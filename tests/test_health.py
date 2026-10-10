from fastapi.testclient import TestClient

from src.config import Settings
from src.web.app import create_app


def test_health_endpoints_report_live_and_ready(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "health.db"), _env_file=None))
    client = TestClient(app)
    assert client.get("/health/live").json() == {"status": "ok"}
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": True, "worker": "not_required"}


def test_health_ready_hides_database_error(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "health.db"), _env_file=None))
    app.state.settings.database_path = str(tmp_path / "missing" / "health.db")
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "database_unavailable"}}
