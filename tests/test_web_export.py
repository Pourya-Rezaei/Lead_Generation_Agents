import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.domain import Lead
from src.results import RunStatus, SearchResult
from src.storage import LeadStore
from src.web.app import create_app


@pytest.fixture
def populated_client(tmp_path):
    database = str(tmp_path / "export.db")
    store = LeadStore(database)
    result = SearchResult(
        source="places",
        status=RunStatus.SUCCEEDED,
        leads=[Lead(name="Example Clinic", address="Tehran")],
        finished_at=datetime.now(UTC),
    )
    store.persist_search_result("general", result, "clinic", "Tehran")
    return TestClient(create_app(Settings(database_path=database), store=store))


def test_campaign_export_returns_csv_download(populated_client):
    response = populated_client.get("/campaigns/general/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "Example Clinic" in response.text


def test_campaign_export_returns_json_download(populated_client):
    response = populated_client.get("/campaigns/general/export?format=json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.content)[0]["name"] == "Example Clinic"


def test_campaign_export_rejects_unknown_format(populated_client):
    response = populated_client.get("/campaigns/general/export?format=xml")
    assert response.status_code == 400


def test_campaign_export_unknown_campaign_returns_404(populated_client):
    response = populated_client.get("/campaigns/missing/export?format=csv")
    assert response.status_code == 404
