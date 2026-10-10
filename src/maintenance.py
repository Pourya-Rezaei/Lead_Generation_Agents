"""Bounded, dry-run-friendly local maintenance operations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


def purge_expired_cache(connection: sqlite3.Connection, *, dry_run: bool = True) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc).isoformat()
    count = connection.execute(
        "SELECT COUNT(*) FROM execution_cache WHERE expires_at <= ?", (cutoff,)
    ).fetchone()[0]
    if not dry_run:
        connection.execute("DELETE FROM execution_cache WHERE expires_at <= ?", (cutoff,))
        connection.commit()
    return {"operation": "purge_expired_cache", "count": count, "dry_run": dry_run}


def purge_old_runs(
    connection: sqlite3.Connection, *, retention_days: int, dry_run: bool = True
) -> dict[str, Any]:
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    rows = connection.execute(
        "SELECT COUNT(*) FROM runs r WHERE r.finished_at IS NOT NULL AND r.finished_at < ? "
        "AND r.status IN ('succeeded', 'partial') "
        "AND NOT EXISTS (SELECT 1 FROM raw_records rr WHERE rr.run_id = r.run_id) "
        "AND NOT EXISTS (SELECT 1 FROM observations o WHERE o.run_id = r.run_id) "
        "AND NOT EXISTS (SELECT 1 FROM execution_cache ec WHERE ec.expires_at > ? "
        "AND json_extract(ec.result, '$.persisted_refs.run_id') = r.run_id)",
        (cutoff, datetime.now(timezone.utc).isoformat()),
    ).fetchone()[0]
    if not dry_run:
        connection.execute(
            "DELETE FROM runs WHERE finished_at IS NOT NULL AND finished_at < ? "
            "AND status IN ('succeeded', 'partial') "
            "AND NOT EXISTS (SELECT 1 FROM raw_records rr WHERE rr.run_id = runs.run_id) "
            "AND NOT EXISTS (SELECT 1 FROM observations o WHERE o.run_id = runs.run_id) "
            "AND NOT EXISTS (SELECT 1 FROM execution_cache ec WHERE ec.expires_at > ? "
            "AND json_extract(ec.result, '$.persisted_refs.run_id') = runs.run_id)",
            (cutoff, datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    return {"operation": "purge_old_runs", "count": rows, "dry_run": dry_run}


def purge_old_raw_records(
    connection: sqlite3.Connection, *, retention_days: int, dry_run: bool = True
) -> dict[str, Any]:
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    import json

    protected: set[tuple[str, int]] = set()
    cache_rows = connection.execute(
        "SELECT result FROM execution_cache WHERE expires_at > ?",
        (datetime.now(timezone.utc).isoformat(),),
    )
    for (payload,) in cache_rows:
        try:
            refs = json.loads(payload).get("persisted_refs", {})
        except (TypeError, json.JSONDecodeError):
            continue
        for ref in refs.get("raw_record_refs", []):
            if isinstance(ref, dict) and isinstance(ref.get("run_id"), str) and isinstance(ref.get("record_index"), int):
                protected.add((ref["run_id"], ref["record_index"]))
    candidates = connection.execute(
        "SELECT rr.run_id, rr.record_index FROM raw_records rr JOIN runs r ON r.run_id = rr.run_id "
        "WHERE rr.recorded_at < ? AND r.status IN ('succeeded', 'partial')",
        (cutoff,),
    ).fetchall()
    deletable = [(run_id, index) for run_id, index in candidates if (run_id, index) not in protected]
    if not dry_run:
        connection.executemany(
            "DELETE FROM raw_records WHERE run_id = ? AND record_index = ?", deletable
        )
        connection.commit()
    return {"operation": "purge_old_raw_records", "count": len(deletable), "dry_run": dry_run}
