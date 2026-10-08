from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from src.errors import ApifyCredentialError
from src.results import RunStatus, SearchResult

from src.config import Settings
from src.storage import LeadStore
from src.web.app import create_app


@pytest.fixture
def client(tmp_path):
    database = str(tmp_path / "web.db")
    store = LeadStore(database)
    app = create_app(Settings(database_path=database), store=store)
    return TestClient(app)


@pytest.fixture
def fake_service(tmp_path):
    database = str(tmp_path / "service.db")
    store = LeadStore(database)
    service = Mock()
    service.search.return_value = SearchResult(
        source="places",
        status=RunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    app = create_app(Settings(database_path=database), store=store, service=service)
    return TestClient(app), service


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


def test_search_route_calls_service_and_redirects(fake_service):
    client, service = fake_service
    response = client.post(
        "/search",
        data={
            "query": "dentist",
            "location": "Tehran",
            "campaign_id": "general",
            "limit": "5",
            "source": "places",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    service.search.assert_called_once_with(
        "dentist", "Tehran", source="places", limit=5, campaign_id="general"
    )


def test_search_route_does_not_leak_provider_error(fake_service):
    client, service = fake_service
    service.search.side_effect = ApifyCredentialError("token-secret")
    response = client.post(
        "/search",
        data={
            "query": "dentist",
            "location": "Tehran",
            "campaign_id": "general",
            "limit": "5",
            "source": "places",
        },
    )
    assert response.status_code == 502
    assert "token-secret" not in response.text
    assert "Authorization" not in response.text


def test_search_route_rejects_invalid_source(fake_service):
    client, service = fake_service
    response = client.post(
        "/search",
        data={
            "query": "dentist",
            "location": "Tehran",
            "campaign_id": "general",
            "limit": "5",
            "source": "web",
        },
    )
    assert response.status_code == 400
    service.search.assert_not_called()
