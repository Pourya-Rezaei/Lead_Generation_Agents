from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any


class ExecutionCache:
    def __init__(self, connection: sqlite3.Connection, ttl_seconds: int = 86400):
        self.connection = connection
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(request: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def get(self, request: dict[str, Any]) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT result, expires_at FROM execution_cache WHERE cache_key = ?", (self.key(request),)).fetchone()
        if row is None or datetime.fromisoformat(row[1]) <= datetime.now(UTC):
            return None
        return json.loads(row[0])

    def put(self, request: dict[str, Any], result: dict[str, Any], mapper_version: str = "1") -> None:
        now = datetime.now(UTC)
        self.connection.execute(
            "INSERT INTO execution_cache(cache_key, result, collected_at, expires_at, mapper_version) VALUES (?, ?, ?, ?, ?) ON CONFLICT(cache_key) DO UPDATE SET result = excluded.result, collected_at = excluded.collected_at, expires_at = excluded.expires_at, mapper_version = excluded.mapper_version",
            (self.key(request), json.dumps(result, ensure_ascii=False), now.isoformat(), (now + timedelta(seconds=self.ttl_seconds)).isoformat(), mapper_version),
        )

    def purge_expired(self) -> int:
        return self.connection.execute("DELETE FROM execution_cache WHERE expires_at <= ?", (datetime.now(UTC).isoformat(),)).rowcount
