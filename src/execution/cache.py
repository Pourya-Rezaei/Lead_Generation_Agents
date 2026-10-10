from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


class ExecutionCache:
    def __init__(self, connection: sqlite3.Connection, ttl_seconds: int = 86400):
        self.connection = connection
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(request: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def get(self, request: dict[str, Any], mapper_version: str = "1", policy_version: str = "1") -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT result, expires_at, mapper_version, policy_version FROM execution_cache WHERE cache_key = ?",
            (self.key(request),),
        ).fetchone()
        if row is None or row[2] != mapper_version or row[3] != policy_version or datetime.fromisoformat(row[1]) <= datetime.now(timezone.utc):
            return None
        result = json.loads(row[0])
        return result if isinstance(result, dict) and result.get("state", "succeeded") == "succeeded" else None

    def put(self, request: dict[str, Any], result: dict[str, Any], mapper_version: str = "1", policy_version: str = "1") -> None:
        now = datetime.now(timezone.utc)
        self.connection.execute(
            "INSERT INTO execution_cache(cache_key, result, collected_at, expires_at, mapper_version, policy_version) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(cache_key) DO UPDATE SET result = excluded.result, collected_at = excluded.collected_at, expires_at = excluded.expires_at, mapper_version = excluded.mapper_version, policy_version = excluded.policy_version",
            (self.key(request), json.dumps(result, ensure_ascii=False), now.isoformat(), (now + timedelta(seconds=self.ttl_seconds)).isoformat(), mapper_version, policy_version),
        )

    @staticmethod
    def is_replayable(result: dict[str, Any]) -> bool:
        refs = result.get("persisted_refs")
        return (
            isinstance(refs, dict)
            and bool(refs.get("lead_ids"))
            and isinstance(refs.get("observation_ids"), list)
            and isinstance(refs.get("raw_record_refs"), list)
        )

    def purge_expired(self) -> int:
        return self.connection.execute("DELETE FROM execution_cache WHERE expires_at <= ?", (datetime.now(timezone.utc).isoformat(),)).rowcount
