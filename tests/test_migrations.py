import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.domain import Lead
from src.migrations import CURRENT_SCHEMA_VERSION, migrate
from src.repositories import LeadRepository, RawRecordRepository, RunRepository
from src.storage import LeadStore


FIXTURE = Path(__file__).parent / "fixtures" / "legacy_leads.sql"


def legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(FIXTURE.read_text(encoding="utf-8"))


def test_legacy_upgrade_is_idempotent_and_preserves_payload(tmp_path):
    path = tmp_path / "legacy.db"
    legacy_database(path)
    with sqlite3.connect(path) as connection:
        before = connection.execute("SELECT payload FROM leads").fetchall()
        assert migrate(connection) == CURRENT_SCHEMA_VERSION
        assert migrate(connection) == CURRENT_SCHEMA_VERSION
        assert connection.execute("SELECT payload FROM leads").fetchall() == before
        assert connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"schema_metadata", "leads", "runs", "raw_records"} <= tables


def test_campaign_migration_creates_general_and_is_idempotent(tmp_path):
    path = tmp_path / "empty.db"
    with sqlite3.connect(path) as connection:
        assert migrate(connection) == CURRENT_SCHEMA_VERSION
        assert migrate(connection) == CURRENT_SCHEMA_VERSION
        assert connection.execute(
            "SELECT campaign_id, name, is_default FROM campaigns"
        ).fetchall() == [("general", "جست‌وجوهای عمومی", 1)]
        assert connection.execute("SELECT campaign_id FROM runs").fetchall() == []


def test_campaign_migration_backfills_runs_and_preserves_raw_records(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
            "INSERT INTO schema_metadata VALUES ('schema_version', '1');"
            "CREATE TABLE runs (run_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "payload TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, error TEXT);"
            "INSERT INTO runs VALUES ('old-run', 'succeeded', '{}', '2024-01-01', NULL, NULL);"
            "CREATE TABLE raw_records (run_id TEXT NOT NULL, record_index INTEGER NOT NULL, "
            "payload TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(run_id, record_index));"
            "INSERT INTO raw_records VALUES ('old-run', 0, '{\"title\":\"Cafe\"}', '2024-01-01');"
        )
        assert migrate(connection) == CURRENT_SCHEMA_VERSION
        assert connection.execute("SELECT campaign_id FROM runs WHERE run_id='old-run'").fetchone() == ("general",)
        assert connection.execute(
            "SELECT run_id, record_index, payload, recorded_at FROM raw_records"
        ).fetchall() == [("old-run", 0, '{"title":"Cafe"}', "2024-01-01")]


def test_campaign_constraints_reject_duplicate_name_and_default(tmp_path):
    path = tmp_path / "constraints.db"
    with sqlite3.connect(path) as connection:
        migrate(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO campaigns(campaign_id, name, is_default) VALUES ('second', 'جست‌وجوهای عمومی', 0)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO campaigns(campaign_id, name, is_default) VALUES ('second', 'Other', 1)"
            )


def test_migration_rolls_back_on_failure(tmp_path, monkeypatch):
    import src.migrations as migrations

    path = tmp_path / "broken.db"
    legacy_database(path)

    def fail(connection):
        connection.execute("CREATE TABLE should_rollback(value TEXT)")
        raise RuntimeError("boom")

    monkeypatch.setattr(migrations, "MIGRATIONS", (fail,))
    with sqlite3.connect(path) as connection:
        with pytest.raises(RuntimeError, match="boom"):
            migrations.migrate(connection)
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='should_rollback'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='schema_metadata'"
        ).fetchone()[0] == 0


def test_repositories_lifecycle_allowlist_purge_and_foreign_key(tmp_path):
    path = tmp_path / "repo.db"
    LeadStore(str(path))
    old = datetime(2024, 1, 1, tzinfo=UTC)
    cutoff = datetime(2024, 2, 1, tzinfo=UTC)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        runs = RunRepository(connection)
        runs.start("run-1", {"query": "cafe"}, started_at=old)
        raw = RawRecordRepository(connection)
        assert raw.save_allowlisted(
            "run-1", [{"title": "Cafe", "email": "private@example.test"}], recorded_at=old
        ) == 1
        payload = json.loads(connection.execute("SELECT payload FROM raw_records").fetchone()[0])
        assert payload == {"title": "Cafe"}
        assert raw.purge_before(cutoff) == 1
        runs.finish("run-1", status="succeeded", finished_at=cutoff)
        assert connection.execute("SELECT status FROM runs").fetchone()[0] == "succeeded"
        with pytest.raises(sqlite3.IntegrityError):
            raw.save_allowlisted("missing", [{"title": "No parent"}])


def test_upsert_updates_without_replacing_row_and_creates_parent(tmp_path):
    path = tmp_path / "nested" / "leads.db"
    LeadStore(str(path))
    assert path.exists()
    with sqlite3.connect(path) as connection:
        repository = LeadRepository(connection)
        first = Lead(name="Cafe", address="A", score=1)
        assert repository.upsert([first]).inserted == 1
        rowid = connection.execute("SELECT rowid FROM leads").fetchone()[0]
        changed = first.model_copy(update={"score": 42})
        summary = repository.upsert([changed])
        assert (summary.inserted, summary.updated) == (0, 1)
        assert connection.execute("SELECT rowid FROM leads").fetchone()[0] == rowid
