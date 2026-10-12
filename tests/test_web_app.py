from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from src.errors import ApifyCredentialError, ApifyError
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
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    app = create_app(Settings(database_path=database), store=store, service=service)
    return TestClient(app), service


def test_importing_app_module_does_not_create_database(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ, PYTHONPATH=project_root)
    subprocess.run(
        [sys.executable, "-c", "import src.web.app"],
        cwd=tmp_path,
        env=env,
        check=True,
    )
    assert not (tmp_path / "leads.db").exists()
    database = tmp_path / "uvicorn.db"
    uvicorn_env = dict(env, DATABASE_PATH=str(database))
    subprocess.run(
        [sys.executable, "-c", "from uvicorn.importer import import_from_string; assert import_from_string('src.web.app:app')"],
        cwd=tmp_path,
        env=uvicorn_env,
        check=True,
    )
    assert database.exists()


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


@pytest.mark.parametrize("path", ["/", "/search", "/campaigns", "/jobs", "/sources"])
def test_workspace_shell_has_accessible_landmarks(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert 'href="#main-content"' in response.text
    assert '<main id="main-content"' in response.text
    assert 'aria-current="page"' in response.text
    assert "workspace.css" in response.text


def test_workspace_styles_are_served(client):
    response = client.get("/static/workspace.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert ":focus-visible" in response.text
    assert "@media" in response.text


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


@pytest.mark.parametrize("provider_error", [
    ApifyCredentialError("token-secret"),
    ApifyError("HTTP 400: invalid input; Authorization: Bearer token-secret"),
])
def test_search_route_does_not_leak_provider_error(fake_service, provider_error):
    client, service = fake_service
    service.search.side_effect = provider_error
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
