import sqlite3
from datetime import datetime, timedelta, timezone

from src.maintenance import purge_expired_cache, purge_old_raw_records, purge_old_runs
from src.migrations import migrate


def test_maintenance_supports_dry_run_and_commit():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        db.execute("INSERT INTO execution_cache(cache_key, result, collected_at, expires_at, mapper_version, policy_version) VALUES ('x', '{}', '2020-01-01', '2020-01-01', '1', '1')")
        preview = purge_expired_cache(db, dry_run=True)
        assert preview["count"] == 1
        assert db.execute("SELECT COUNT(*) FROM execution_cache").fetchone()[0] == 1
        purge_expired_cache(db, dry_run=False)
        assert db.execute("SELECT COUNT(*) FROM execution_cache").fetchone()[0] == 0


def test_retention_preserves_cache_lineage():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        db.execute("INSERT INTO runs(run_id, status, payload, started_at, finished_at, error, campaign_id) VALUES ('r', 'succeeded', '{}', ?, ?, NULL, 'general')", (old, old))
        db.execute("INSERT INTO raw_records(run_id, record_index, payload, recorded_at) VALUES ('r', 0, '{}', ?)", (old,))
        db.execute("INSERT INTO execution_cache(cache_key, result, collected_at, expires_at, mapper_version, policy_version) VALUES ('c', ?, ?, ?, '1', '1')", ('{"persisted_refs":{"run_id":"r","raw_record_refs":[{"run_id":"r","record_index":0}]}}', old, (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()))
        assert purge_old_runs(db, retention_days=7, dry_run=True)["count"] == 0
        assert purge_old_raw_records(db, retention_days=7, dry_run=False)["count"] == 0
        assert db.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 1


def test_raw_record_purge_is_bounded():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        db.execute("INSERT INTO runs(run_id, status, payload, started_at, finished_at, error, campaign_id) VALUES ('r', 'succeeded', '{}', '2020-01-01', '2020-01-02', NULL, 'general')")
        db.execute("INSERT INTO raw_records(run_id, record_index, payload, recorded_at) VALUES ('r', 0, '{}', ?)", ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),))
        result = purge_old_raw_records(db, retention_days=7, dry_run=False)
        assert result["count"] == 1
        assert db.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 0
