"""SQLite repositories used by the storage compatibility facade."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from .domain import Campaign, CampaignStats, Lead
from .errors import (
    CampaignNotFoundError,
    DuplicateCampaignIdError,
    DuplicateCampaignNameError,
)


@dataclass(frozen=True)
class UpsertSummary:
    inserted: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated


class CampaignRepository:
    """Persistence operations for campaigns and their lead memberships."""

    DEFAULT_CAMPAIGN_ID = "general"

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.execute("PRAGMA foreign_keys = ON")

    def create(
        self,
        name: str,
        description: str | None = None,
        campaign_id: str | None = None,
    ) -> Campaign:
        normalized_name = " ".join(name.split())
        if not normalized_name:
            raise ValueError("campaign name must not be empty")
        normalized_description = " ".join(description.split()) if description else None
        normalized_id = campaign_id.strip() if campaign_id is not None else normalized_name.lower().replace(" ", "-")
        if not normalized_id:
            raise ValueError("campaign ID must not be empty")
        created_at = datetime.now(UTC).isoformat()
        try:
            self.connection.execute(
                "INSERT INTO campaigns(campaign_id, name, description, is_default, created_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (normalized_id, normalized_name, normalized_description, created_at),
            )
        except sqlite3.IntegrityError as exc:
            if self.connection.execute(
                "SELECT 1 FROM campaigns WHERE name = ?", (normalized_name,)
            ).fetchone():
                raise DuplicateCampaignNameError(
                    f"campaign name already exists: {normalized_name}"
                ) from exc
            if self.connection.execute(
                "SELECT 1 FROM campaigns WHERE campaign_id = ?", (normalized_id,)
            ).fetchone():
                raise DuplicateCampaignIdError(
                    f"campaign ID already exists: {normalized_id}"
                ) from exc
            raise
        return self.get(normalized_id)  # type: ignore[return-value]

    def get(self, campaign_id: str) -> Campaign | None:
        row = self.connection.execute(
            "SELECT campaign_id, name, description, is_default, created_at "
            "FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        if row is None:
            return None
        return Campaign(
            campaign_id=row[0], name=row[1], description=row[2],
            is_default=bool(row[3]), created_at=datetime.fromisoformat(row[4]),
        )

    def get_default(self) -> Campaign:
        row = self.connection.execute(
            "SELECT campaign_id FROM campaigns WHERE is_default = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("default campaign is not configured")
        return self.get(row[0])  # type: ignore[return-value]

    def list(self) -> list[Campaign]:
        rows = self.connection.execute(
            "SELECT campaign_id, name, description, is_default, created_at "
            "FROM campaigns ORDER BY is_default DESC, name COLLATE NOCASE, campaign_id"
        )
        return [
            Campaign(campaign_id=row[0], name=row[1], description=row[2],
                     is_default=bool(row[3]), created_at=datetime.fromisoformat(row[4]))
            for row in rows
        ]

    def stats(self, campaign_id: str) -> CampaignStats:
        if self.get(campaign_id) is None:
            raise CampaignNotFoundError(f"campaign not found: {campaign_id}")
        row = self.connection.execute(
            "SELECT COUNT(DISTINCT cl.lead_dedup_key), "
            "(SELECT COUNT(*) FROM runs WHERE campaign_id = ?) "
            "FROM campaign_leads cl WHERE cl.campaign_id = ?",
            (campaign_id, campaign_id),
        ).fetchone()
        return CampaignStats(campaign_id=campaign_id, lead_count=row[0], run_count=row[1])

    @staticmethod
    def _timestamp(value: datetime | str | None) -> str:
        return RunRepository._timestamp(value)

    def add_lead(self, campaign_id: str, lead_dedup_key: str, *, seen_at: datetime | str | None = None) -> None:
        timestamp = self._timestamp(seen_at)
        self.connection.execute(
            "INSERT INTO campaign_leads(campaign_id, lead_dedup_key, first_seen_at, last_seen_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(campaign_id, lead_dedup_key) DO UPDATE "
            "SET last_seen_at = excluded.last_seen_at",
            (campaign_id, lead_dedup_key, timestamp, timestamp),
        )

    def add_leads(self, campaign_id: str, leads: Iterable[Lead], *, seen_at: datetime | str | None = None) -> None:
        timestamp = self._timestamp(seen_at)
        for lead in leads:
            self.add_lead(campaign_id, lead.dedup_key(), seen_at=timestamp)


class LeadRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert(self, leads: Iterable[Lead]) -> UpsertSummary:
        inserted = updated = 0
        for lead in leads:
            key = lead.dedup_key()
            existing = self.connection.execute(
                "SELECT dedup_key, lead_id, payload FROM leads WHERE dedup_key = ?", (key,)
            ).fetchone()
            if existing is None and lead.source and lead.source_id:
                for candidate_key, candidate_id, payload in self.connection.execute(
                    "SELECT dedup_key, lead_id, payload FROM leads"
                ):
                    old = Lead.model_validate_json(payload)
                    if old.source == lead.source and old.source_id == lead.source_id:
                        existing = (candidate_key, candidate_id, payload)
                        break
            if existing is not None and existing[0] != key:
                self.connection.execute(
                    "UPDATE campaign_leads SET lead_dedup_key = ? WHERE lead_dedup_key = ?",
                    (key, existing[0]),
                )
                self.connection.execute("UPDATE leads SET dedup_key = ?, payload = ? WHERE dedup_key = ?", (key, lead.model_dump_json(), existing[0]))
                updated += 1
                continue
            self.connection.execute(
                "INSERT INTO leads(dedup_key, payload, lead_id) VALUES(?, ?, COALESCE((SELECT lead_id FROM leads WHERE dedup_key = ?), ?)) "
                "ON CONFLICT(dedup_key) DO UPDATE SET payload = excluded.payload",
                (key, lead.model_dump_json(), key, __import__('uuid').uuid4().hex),
            )
            if existing:
                updated += 1
            else:
                inserted += 1
        return UpsertSummary(inserted=inserted, updated=updated)

    def all(self) -> list[Lead]:
        rows = self.connection.execute(
            "SELECT payload FROM leads ORDER BY rowid"
        )
        return [Lead.model_validate_json(row[0]) for row in rows]

    def for_campaign(self, campaign_id: str) -> list[Lead]:
        rows = self.connection.execute(
            "SELECT l.payload FROM leads AS l "
            "JOIN campaign_leads AS cl ON cl.lead_dedup_key = l.dedup_key "
            "WHERE cl.campaign_id = ? ORDER BY l.rowid",
            (campaign_id,),
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
        campaign_id: str | None = CampaignRepository.DEFAULT_CAMPAIGN_ID,
    ) -> None:
        if campaign_id is None:
            raise ValueError("campaign_id is required to create a run")
        if CampaignRepository(self.connection).get(campaign_id) is None:
            raise ValueError(f"campaign not found: {campaign_id}")
        payload = {**(metadata or {}), "run_id": run_id}
        timestamp = self._timestamp(started_at)
        payload.setdefault("started_at", timestamp)
        payload["campaign_id"] = campaign_id
        self.connection.execute(
            "INSERT INTO runs(run_id, status, payload, started_at, finished_at, error, campaign_id) "
            "VALUES(?, 'running', ?, ?, NULL, NULL, ?) "
            "ON CONFLICT(run_id) DO UPDATE SET status = 'running', "
            "payload = excluded.payload, started_at = excluded.started_at, "
            "finished_at = NULL, error = NULL "
            "WHERE runs.campaign_id = excluded.campaign_id",
            (run_id, json.dumps(payload, ensure_ascii=False), timestamp, campaign_id),
        )
        row = self.connection.execute(
            "SELECT campaign_id FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"failed to persist run: {run_id}")
        if row[0] != campaign_id:
            raise ValueError(
                f"run_id '{run_id}' already belongs to campaign '{row[0]}'"
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
