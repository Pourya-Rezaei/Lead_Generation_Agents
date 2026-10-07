"""SQLite repositories used by the storage compatibility facade."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from .domain import Lead


@dataclass(frozen=True)
class UpsertSummary:
    inserted: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated


class LeadRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert(self, leads: Iterable[Lead]) -> UpsertSummary:
        inserted = updated = 0
        for lead in leads:
            key = lead.dedup_key()
            exists = self.connection.execute(
                "SELECT 1 FROM leads WHERE dedup_key = ?", (key,)
            ).fetchone()
            self.connection.execute(
                "INSERT INTO leads(dedup_key, payload) VALUES(?, ?) "
                "ON CONFLICT(dedup_key) DO UPDATE SET payload = excluded.payload",
                (key, lead.model_dump_json()),
            )
            if exists:
                updated += 1
            else:
                inserted += 1
        return UpsertSummary(inserted=inserted, updated=updated)

    def all(self) -> list[Lead]:
        rows = self.connection.execute(
            "SELECT payload FROM leads ORDER BY rowid"
        )
        return [Lead.model_validate_json(row[0]) for row in rows]


class RunRepository:
    TERMINAL_STATUSES = {"succeeded", "partial", "failed", "aborted", "timed_out"}

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    @staticmethod
    def _timestamp(value: datetime | str | None) -> str:
        if value is None:
            value = datetime.now(UTC)
        return value.isoformat() if isinstance(value, datetime) else value

    def start(
        self,
        run_id: str,
        metadata: dict[str, Any] | None = None,
        *,
        started_at: datetime | str | None = None,
    ) -> None:
        payload = {**(metadata or {}), "run_id": run_id}
        timestamp = self._timestamp(started_at)
        payload.setdefault("started_at", timestamp)
        self.connection.execute(
            "INSERT INTO runs(run_id, status, payload, started_at, finished_at, error) "
            "VALUES(?, 'running', ?, ?, NULL, NULL) "
            "ON CONFLICT(run_id) DO UPDATE SET status = 'running', "
            "payload = excluded.payload, started_at = excluded.started_at, "
            "finished_at = NULL, error = NULL",
            (run_id, json.dumps(payload, ensure_ascii=False), timestamp),
        )

    def finish(
        self,
        run_id: str,
        metadata: dict[str, Any] | None = None,
        *,
        status: str = "succeeded",
        finished_at: datetime | str | None = None,
    ) -> None:
        normalized = status.lower().replace("-", "_")
        if normalized not in self.TERMINAL_STATUSES - {"failed"}:
            raise ValueError(f"invalid successful terminal status: {status}")
        self._complete(run_id, normalized, metadata, finished_at, None)

    def fail(
        self,
        run_id: str,
        error: str,
        metadata: dict[str, Any] | None = None,
        *,
        finished_at: datetime | str | None = None,
    ) -> None:
        self._complete(run_id, "failed", metadata, finished_at, error)

    def _complete(
        self,
        run_id: str,
        status: str,
        metadata: dict[str, Any] | None,
        finished_at: datetime | str | None,
        error: str | None,
    ) -> None:
        row = self.connection.execute(
            "SELECT payload FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown run: {run_id}")
        payload = json.loads(row[0])
        payload.update(metadata or {})
        timestamp = self._timestamp(finished_at)
        payload.update({"run_id": run_id, "status": status, "finished_at": timestamp})
        if error is not None:
            payload["error"] = error
        self.connection.execute(
            "UPDATE runs SET status = ?, payload = ?, finished_at = ?, error = ? "
            "WHERE run_id = ?",
            (status, json.dumps(payload, ensure_ascii=False), timestamp, error, run_id),
        )


class RawRecordRepository:
    DEFAULT_ALLOWLIST = frozenset(
        {
            "title", "name", "address", "phone", "phoneNumber", "website",
            "url", "category", "categories", "rating", "reviewsCount",
            "placeId", "source_id", "latitude", "longitude",
        }
    )

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def save_allowlisted(
        self,
        run_id: str,
        records: Iterable[dict[str, Any]],
        *,
        allowlist: Iterable[str] | None = None,
        recorded_at: datetime | str | None = None,
    ) -> int:
        allowed = set(self.DEFAULT_ALLOWLIST if allowlist is None else allowlist)
        timestamp = RunRepository._timestamp(recorded_at)
        count = 0
        for index, record in enumerate(records):
            payload = {key: value for key, value in record.items() if key in allowed}
            self.connection.execute(
                "INSERT INTO raw_records(run_id, record_index, payload, recorded_at) "
                "VALUES(?, ?, ?, ?) ON CONFLICT(run_id, record_index) DO UPDATE SET "
                "payload = excluded.payload, recorded_at = excluded.recorded_at",
                (run_id, index, json.dumps(payload, ensure_ascii=False), timestamp),
            )
            count += 1
        return count

    def purge_before(self, cutoff: datetime | str) -> int:
        timestamp = RunRepository._timestamp(cutoff)
        cursor = self.connection.execute(
            "DELETE FROM raw_records WHERE recorded_at < ?", (timestamp,)
        )
        return cursor.rowcount
