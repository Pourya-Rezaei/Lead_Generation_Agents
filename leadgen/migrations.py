"""Versioned SQLite schema migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

CURRENT_SCHEMA_VERSION = 1


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_metadata ("
        "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS leads ("
        "dedup_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
    )

    connection.execute(
        "CREATE TABLE IF NOT EXISTS runs ("
        "run_id TEXT PRIMARY KEY, "
        "status TEXT NOT NULL CHECK (status IN "
        "('pending','running','succeeded','partial','failed','aborted','timed_out')), "
        "payload TEXT NOT NULL, started_at TEXT NOT NULL, "
        "finished_at TEXT, error TEXT)"
    )
    run_columns = _table_columns(connection, "runs")
    for name, declaration in (
        ("status", "TEXT NOT NULL DEFAULT 'succeeded'"),
        ("started_at", "TEXT NOT NULL DEFAULT ''"),
        ("finished_at", "TEXT"),
        ("error", "TEXT"),
    ):
        if name not in run_columns:
            connection.execute(f"ALTER TABLE runs ADD COLUMN {name} {declaration}")

    if "raw_records" in {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    } and "recorded_at" not in _table_columns(connection, "raw_records"):
        connection.execute("ALTER TABLE raw_records RENAME TO raw_records_legacy")

    connection.execute(
        "CREATE TABLE IF NOT EXISTS raw_records ("
        "run_id TEXT NOT NULL, record_index INTEGER NOT NULL CHECK (record_index >= 0), "
        "payload TEXT NOT NULL, recorded_at TEXT NOT NULL, "
        "PRIMARY KEY (run_id, record_index), "
        "FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE)"
    )
    if "raw_records_legacy" in {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }:
        connection.execute(
            "INSERT INTO raw_records(run_id, record_index, payload, recorded_at) "
            "SELECT rr.run_id, rr.record_index, rr.payload, "
            "COALESCE(NULLIF(r.started_at, ''), CURRENT_TIMESTAMP) "
            "FROM raw_records_legacy rr JOIN runs r ON r.run_id = rr.run_id"
        )
        connection.execute("DROP TABLE raw_records_legacy")

    connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_raw_records_recorded_at "
        "ON raw_records(recorded_at)"
    )


MIGRATIONS: tuple[Callable[[sqlite3.Connection], None], ...] = (_migration_1,)


def migrate(connection: sqlite3.Connection) -> int:
    """Apply all pending migrations atomically and return the schema version."""
    connection.execute("PRAGMA foreign_keys = ON")
    savepoint = "leadgen_migration"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_metadata ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        row = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()
        version = int(row[0]) if row else 0
        if version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} is newer than supported "
                f"version {CURRENT_SCHEMA_VERSION}"
            )
        for target_version, migration in enumerate(MIGRATIONS, start=1):
            if target_version <= version:
                continue
            migration(connection)
            connection.execute(
                "INSERT INTO schema_metadata(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(target_version),),
            )
            version = target_version
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return version
    except Exception:
        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise
