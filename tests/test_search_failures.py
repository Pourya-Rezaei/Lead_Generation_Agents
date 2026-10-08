import json
import sqlite3
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from leadgen.cli import app
from leadgen.config import Settings
from leadgen.errors import (
    ApifyCredentialError,
    ApifyMalformedResponseError,
    ApifyTransientError,
    SearchAttemptPersistenceError,
)
from leadgen.results import RunStatus, SearchResult
from leadgen.service import SearchLeadsService
from leadgen.storage import LeadStore


class FailingConnector:
    def __init__(self, error):
        self.error = error
        self.failure_metadata = {"provider_run_id": "provider-run-1"}

    def search(self, query, location, limit):
        raise self.error


class FailingRegistry:
    def __init__(self, error):
        self.error = error

    def validate_source(self, name):
        if name != "places":
            raise ValueError(f"unknown source: {name}")

    def create(self, name, settings):
        return FailingConnector(self.error)


def test_search_service_records_missing_token_without_leads_or_raw_records(tmp_path):
    database = str(tmp_path / "failed.db")
    store = LeadStore(database)
    service = SearchLeadsService(
        Settings(database_path=database, _env_file=None),
        store=store,
    )

    with pytest.raises(ValueError, match="APIFY_API_TOKEN is required"):
        service.search("dentist", "Tehran")

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT run_id, status, error, campaign_id, payload FROM runs"
        ).fetchone()
        assert row[0].startswith("local-")
        assert row[1] == RunStatus.FAILED.value
        assert row[2] == "APIFY_API_TOKEN is required for places."
        assert row[3] == "general"
        payload = json.loads(row[4])
        assert payload["query"] == "dentist"
        assert payload["location"] == "Tehran"
        assert payload["source"] == "places"
        assert payload["error_type"] == "ValueError"
        assert connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("error", "expected_summary"),
    [
        (
            ApifyCredentialError("Apify rejected the supplied credentials"),
            "Apify rejected the configured credentials.",
        ),
        (
            ApifyTransientError("request failed for test-token"),
            "Apify request failed after retries.",
        ),
        (
            ApifyMalformedResponseError("unexpected body: test-token"),
            "Apify returned an invalid response.",
        ),
    ],
)
def test_search_service_records_connector_error_and_reraises_original(
    tmp_path, error, expected_summary
):
    database = str(tmp_path / "failed.db")
    store = LeadStore(database)
    campaign = store.create_campaign("North", campaign_id="north")
    service = SearchLeadsService(
        Settings(database_path=database, apify_api_token="test-token"),
        store=store,
        registry=FailingRegistry(error),
    )

    with pytest.raises(type(error)) as caught:
        service.search("dentist", "North", campaign_id=campaign.campaign_id)

    assert caught.value is error
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT status, error, campaign_id, payload FROM runs"
        ).fetchone()
        assert row[0] == "failed"
        assert row[1] == expected_summary
        assert row[2] == "north"
        assert "test-token" not in row[3]
        payload = json.loads(row[3])
        assert payload["provider_run_id"] == "provider-run-1"
        assert connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 0


def test_search_service_reports_failure_when_failure_record_cannot_be_saved(tmp_path, monkeypatch):
    original_error = ApifyTransientError("timeout")
    database = str(tmp_path / "failed.db")
    store = LeadStore(database)
    service = SearchLeadsService(
        Settings(database_path=database, apify_api_token="test-token"),
        store=store,
        registry=FailingRegistry(original_error),
    )

    def fail_to_record(*args, **kwargs):
        raise sqlite3.OperationalError("database is unavailable")

    monkeypatch.setattr(store, "record_failed_search", fail_to_record)
    with pytest.raises(SearchAttemptPersistenceError) as caught:
        service.search("dentist", "North")

    assert caught.value.__cause__ is original_error
    assert isinstance(caught.value.__context__, sqlite3.OperationalError)
    assert "ApifyTransientError" in str(caught.value)
    assert "OperationalError" in str(caught.value)


def test_invalid_campaign_and_source_do_not_create_failed_runs(tmp_path):
    database = str(tmp_path / "invalid.db")
    store = LeadStore(database)
    service = SearchLeadsService(
        Settings(database_path=database, apify_api_token="test-token"),
        store=store,
        registry=FailingRegistry(ApifyTransientError("timeout")),
    )

    with pytest.raises(ValueError, match="campaign not found"):
        service.search("dentist", "North", campaign_id="missing")
    with pytest.raises(ValueError, match="unknown source"):
        service.search("dentist", "North", source="unknown")

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


def test_cli_reports_returned_failed_result_as_failure(tmp_path, monkeypatch):
    import leadgen.service as service_module

    class ReturnedFailureConnector(FailingConnector):
        def search(self, query, location, limit):
            return SearchResult(
                source="places",
                run_id="remote-run",
                status=RunStatus.FAILED,
                warnings=["Apify Actor finished with status failed"],
                started_at=datetime(2025, 1, 1, tzinfo=UTC),
                finished_at=datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
            )

    class ReturnedFailureRegistry(FailingRegistry):
        def __init__(self):
            pass

        def create(self, name, settings):
            return ReturnedFailureConnector(None)

    monkeypatch.setattr(service_module, "ConnectorRegistry", ReturnedFailureRegistry)
    database = str(tmp_path / "returned-failure.db")
    result = CliRunner().invoke(
        app,
        ["search", "dentist", "Tehran", "--source", "places", "--db", database],
        env={"APIFY_API_TOKEN": "test-token"},
    )

    assert result.exit_code == 1
    assert "Search failed: Apify Actor finished with status failed" in result.output
    assert "Saved 0 leads" not in result.output
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT status FROM runs").fetchone() == ("failed",)


def test_cli_shows_safe_apify_failure_and_exits_nonzero(tmp_path, monkeypatch):
    import leadgen.service as service_module

    class CliFailingRegistry(FailingRegistry):
        def __init__(self):
            super().__init__(ApifyCredentialError("Apify rejected the supplied credentials"))

    monkeypatch.setattr(service_module, "ConnectorRegistry", CliFailingRegistry)
    database = str(tmp_path / "cli.db")
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["search", "dentist", "Tehran", "--source", "places", "--db", database],
        env={"APIFY_API_TOKEN": "test-token"},
    )

    assert result.exit_code != 0
    assert "Apify rejected the supplied credentials" in result.output
    assert "Traceback" not in result.output
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT status FROM runs"
        ).fetchone() == (RunStatus.FAILED.value,)


def test_cli_missing_token_records_attempt_and_exits_nonzero(tmp_path, monkeypatch):
    import leadgen.cli as cli_module

    database = str(tmp_path / "missing-token.db")
    monkeypatch.setattr(
        cli_module,
        "Settings",
        lambda **kwargs: Settings(database_path=database, apify_api_token=None),
    )

    result = CliRunner().invoke(
        app,
        ["search", "dentist", "Tehran", "--source", "places", "--db", database],
    )

    assert result.exit_code != 0
    assert "APIFY_API_TOKEN is required for places" in result.output
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT status, error FROM runs"
        ).fetchone() == ("failed", "APIFY_API_TOKEN is required for places.")
