"""Versioned SQLite schema migrations."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable

CURRENT_SCHEMA_VERSION = 10


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


def _migration_2(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE campaigns ("
        "campaign_id TEXT PRIMARY KEY CHECK (length(trim(campaign_id)) > 0), "
        "name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0), "
        "description TEXT, "
        "is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)), "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX idx_campaigns_single_default "
        "ON campaigns(is_default) WHERE is_default = 1"
    )
    connection.execute(
        "INSERT INTO campaigns(campaign_id, name, is_default) "
        "VALUES('general', 'جست‌وجوهای عمومی', 1)"
    )
    connection.execute("ALTER TABLE runs ADD COLUMN campaign_id TEXT REFERENCES campaigns(campaign_id)")
    connection.execute("UPDATE runs SET campaign_id = 'general' WHERE campaign_id IS NULL")
    connection.execute("CREATE INDEX idx_runs_campaign_id ON runs(campaign_id)")
    connection.execute(
        "CREATE TABLE campaign_leads ("
        "campaign_id TEXT NOT NULL REFERENCES campaigns(campaign_id) ON DELETE RESTRICT, "
        "lead_dedup_key TEXT NOT NULL REFERENCES leads(dedup_key) ON DELETE CASCADE, "
        "first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, "
        "PRIMARY KEY (campaign_id, lead_dedup_key))"
    )
    connection.execute(
        "CREATE INDEX idx_campaign_leads_lead ON campaign_leads(lead_dedup_key)"
    )


def _migration_3(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS leads (dedup_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
    )
    columns = _table_columns(connection, "leads")
    if "lead_id" not in columns:
        connection.execute("ALTER TABLE leads ADD COLUMN lead_id TEXT")
    rows = connection.execute("SELECT rowid, lead_id FROM leads").fetchall()
    for rowid, lead_id in rows:
        if not lead_id:
            connection.execute("UPDATE leads SET lead_id = ? WHERE rowid = ?", (str(uuid.uuid4()), rowid))
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_lead_id ON leads(lead_id)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS observations ("
        "observation_id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, source TEXT NOT NULL, "
        "source_record_id TEXT, source_url TEXT, run_id TEXT, collected_at TEXT NOT NULL, "
        "fields TEXT NOT NULL, mapper_version TEXT NOT NULL, "
        "FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_observations_lead ON observations(lead_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_observations_source_record ON observations(source, source_record_id)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS field_evidence ("
        "evidence_id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, field TEXT NOT NULL, value TEXT, "
        "source_url TEXT, observation_id TEXT, collected_at TEXT NOT NULL, evidence_kind TEXT NOT NULL, "
        "confidence REAL, policy_version TEXT NOT NULL, "
        "FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE, "
        "FOREIGN KEY (observation_id) REFERENCES observations(observation_id) ON DELETE SET NULL)"
    )


def _migration_4(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS lead_merge_audit ("
        "merge_id TEXT PRIMARY KEY, source_lead_id TEXT NOT NULL, target_lead_id TEXT NOT NULL, "
        "reason TEXT NOT NULL, confidence REAL NOT NULL, created_at TEXT NOT NULL, "
        "source_key TEXT NOT NULL, target_key TEXT NOT NULL, source_payload TEXT NOT NULL, "
        "undone_at TEXT, status TEXT NOT NULL DEFAULT 'active')"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_merge_source ON lead_merge_audit(source_lead_id)")


def _migration_5(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS budget_reservations ("
        "reservation_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, step_id TEXT NOT NULL, "
        "amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0), currency TEXT NOT NULL, "
        "actual_minor INTEGER, state TEXT NOT NULL CHECK (state IN ('reserved','reconciled','released','unknown')), "
        "pricing_version TEXT NOT NULL, created_at TEXT NOT NULL, reconciled_at TEXT, "
        "UNIQUE(job_id, step_id))"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_budget_state ON budget_reservations(state)")


def _migration_6(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS jobs ("
        "job_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, request TEXT NOT NULL, "
        "state TEXT NOT NULL CHECK (state IN ('queued','running','cancel_requested','succeeded','partial','failed','cancelled','needs_review')), "
        "progress TEXT NOT NULL, error_code TEXT, worker_id TEXT, lease_until TEXT, fencing_token INTEGER NOT NULL DEFAULT 0, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state_created ON jobs(state, created_at)")


def _migration_7(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS execution_cache ("
        "cache_key TEXT PRIMARY KEY, result TEXT NOT NULL, collected_at TEXT NOT NULL, expires_at TEXT NOT NULL, mapper_version TEXT NOT NULL)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_cache_expiry ON execution_cache(expires_at)")


def _migration_8(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS profile_candidates ("
        "candidate_id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, platform TEXT NOT NULL, url TEXT NOT NULL, "
        "status TEXT NOT NULL CHECK (status IN ('unverified','probable','confirmed','rejected')), confidence REAL NOT NULL, "
        "evidence TEXT NOT NULL, review_reason TEXT, reviewed_at TEXT, created_at TEXT NOT NULL, "
        "UNIQUE(lead_id, platform, url), FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_profile_lead_status ON profile_candidates(lead_id, status)")


def _migration_9(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE jobs ADD COLUMN provider_run_id TEXT")
    connection.execute("ALTER TABLE jobs ADD COLUMN provider_state TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_provider_run ON jobs(provider_run_id)")


def _migration_10(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS profile_review_audit ("
        "audit_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, old_status TEXT, new_status TEXT NOT NULL, "
        "reason TEXT NOT NULL, reviewed_at TEXT NOT NULL, FOREIGN KEY(candidate_id) REFERENCES profile_candidates(candidate_id) ON DELETE CASCADE)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_profile_review_candidate ON profile_review_audit(candidate_id, reviewed_at)")


MIGRATIONS: tuple[Callable[[sqlite3.Connection], None], ...] = (_migration_1, _migration_2, _migration_3, _migration_4, _migration_5, _migration_6, _migration_7, _migration_8, _migration_9, _migration_10)


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
