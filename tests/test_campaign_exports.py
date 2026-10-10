import csv
import json
from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.domain import Lead
from src.errors import CampaignNotFoundError
from src.results import RunStatus, SearchResult
from src.storage import LeadStore


def _result(run_id: str, name: str) -> SearchResult:
    return SearchResult(
        source="fixture",
        run_id=run_id,
        status=RunStatus.SUCCEEDED,
        leads=[Lead(name=name)],
        raw_records=[],
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc),
    )


def _store_with_campaign_leads(tmp_path):
    store = LeadStore(str(tmp_path / "leads.db"))
    store.create_campaign("North", campaign_id="north")
    store.persist_search_result("general", _result("run-general", "General Cafe"), "cafe", "City")
    store.persist_search_result("north", _result("run-north", "North Cafe"), "cafe", "North")
    return store


def test_json_export_is_global_by_default_and_campaign_export_is_scoped(tmp_path):
    store = _store_with_campaign_leads(tmp_path)

    store.export(str(tmp_path / "all.json"), "json")
    store.export(str(tmp_path / "north.json"), "json", campaign_id="north")

    all_names = [item["name"] for item in json.loads((tmp_path / "all.json").read_text())]
    north_names = [item["name"] for item in json.loads((tmp_path / "north.json").read_text())]
    assert all_names == ["General Cafe", "North Cafe"]
    assert north_names == ["North Cafe"]


def test_export_cli_accepts_campaign_filter(tmp_path):
    store = _store_with_campaign_leads(tmp_path)
    output = tmp_path / "north.json"

    result = CliRunner().invoke(
        app,
        ["export", str(output), "--format", "json", "--campaign", "north", "--db", store.path],
    )

    assert result.exit_code == 0
    assert [item["name"] for item in json.loads(output.read_text())] == ["North Cafe"]


def test_csv_export_of_empty_campaign_has_header_without_leads(tmp_path):
    store = LeadStore(str(tmp_path / "leads.db"))
    store.create_campaign("Empty", campaign_id="empty")
    output = tmp_path / "empty.csv"

    store.export(str(output), "csv", campaign_id="empty")

    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows == []
    assert "name" in output.read_text(encoding="utf-8").splitlines()[0]


def test_export_rejects_unknown_campaign(tmp_path):
    store = _store_with_campaign_leads(tmp_path)

    with pytest.raises(CampaignNotFoundError, match="campaign not found: missing"):
        store.export(str(tmp_path / "missing.json"), "json", campaign_id="missing")

    assert not (tmp_path / "missing.json").exists()
