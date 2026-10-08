import sqlite3
from datetime import UTC, datetime

from typer.testing import CliRunner

from leadgen.cli import app
from leadgen.domain import Lead
from leadgen.results import RunStatus, SearchResult
from leadgen.storage import LeadStore


runner = CliRunner()


def test_campaign_create_list_and_show(tmp_path):
    database = str(tmp_path / "campaign.db")

    created = runner.invoke(
        app,
        ["campaign", "create", "North Side", "--description", "Dental leads", "--id", "north"],
        env={"DATABASE_PATH": database},
    )
    assert created.exit_code == 0
    assert "north" in created.stdout
    assert "North Side" in created.stdout

    listed = runner.invoke(app, ["campaign", "list"], env={"DATABASE_PATH": database})
    assert listed.exit_code == 0
    assert "جست‌وجوهای عمومی" in listed.stdout
    assert "North Side" in listed.stdout

    shown = runner.invoke(app, ["campaign", "show", "north"], env={"DATABASE_PATH": database})
    assert shown.exit_code == 0
    assert "Dental leads" in shown.stdout
    assert "Leads: 0" in shown.stdout
    assert "Runs: 0" in shown.stdout


def test_campaign_show_reports_unknown_id(tmp_path):
    result = runner.invoke(
        app,
        ["campaign", "show", "missing"],
        env={"DATABASE_PATH": str(tmp_path / "campaign.db")},
    )
    assert result.exit_code != 0
    assert "campaign not found: missing" in result.output


class FixedConnector:
    def search(self, query, location, limit):
        return SearchResult(
            source="fake",
            run_id=f"run-{location.lower()}",
            status=RunStatus.SUCCEEDED,
            leads=[Lead(name="North Cafe")],
            raw_records=[],
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
            finished_at=datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
        )


class FixedRegistry:
    def validate_source(self, name):
        assert name == "fake"

    def create(self, source, settings):
        assert source == "fake"
        return FixedConnector()


def test_search_cli_uses_default_or_selected_campaign(tmp_path, monkeypatch):
    import leadgen.service as service_module

    database = str(tmp_path / "campaign.db")
    store = LeadStore(database)
    store.create_campaign("Selected", campaign_id="selected")
    monkeypatch.setattr(service_module, "ConnectorRegistry", FixedRegistry)

    default = runner.invoke(
        app,
        ["search", "cafe", "North", "--source", "fake", "--db", database],
    )
    assert default.exit_code == 0
    assert "campaign 'general'" in default.stdout

    selected = runner.invoke(
        app,
        ["search", "cafe", "South", "--source", "fake", "--campaign", "selected", "--db", database],
    )
    assert selected.exit_code == 0
    assert "campaign 'selected'" in selected.stdout

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT campaign_id FROM runs ORDER BY rowid"
        ).fetchall() == [("general",), ("selected",)]
        assert connection.execute(
            "SELECT campaign_id FROM campaign_leads ORDER BY campaign_id"
        ).fetchall() == [("general",), ("selected",)]
