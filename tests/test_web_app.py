import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.storage import LeadStore
from src.web.app import create_app


@pytest.fixture
def client(tmp_path):
    database = str(tmp_path / "web.db")
    store = LeadStore(database)
    app = create_app(Settings(database_path=database), store=store)
    return TestClient(app)


def test_create_app_registers_web_routes(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "web.db")))
    paths = {
        path
        for route in app.router.routes
        for path in [getattr(route, "path", None)]
        if path is not None
    }
    included = next(route for route in app.router.routes if hasattr(route, "original_router"))
    paths.update(route.path for route in included.original_router.routes)
    assert "/" in paths
    assert "/campaigns" in paths
    assert "/search" in paths


def test_campaign_create_and_detail_render(client):
    response = client.post(
        "/campaigns", data={"campaign_id": "demo", "name": "Demo"}, follow_redirects=False
    )
    assert response.status_code == 303
    detail = client.get("/campaigns/demo")
    assert detail.status_code == 200
    assert "Demo" in detail.text


def test_unknown_campaign_returns_404(client):
    response = client.get("/campaigns/missing")
    assert response.status_code == 404
