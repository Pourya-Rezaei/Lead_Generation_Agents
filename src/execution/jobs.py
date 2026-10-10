from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class Job:
    job_id: str
    idempotency_key: str
    request: dict[str, Any]
    state: str
    progress: dict[str, Any]
    error_code: str | None
    fencing_token: int
    provider_run_id: str | None
    provider_state: str | None


class JobRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    @staticmethod
    def fingerprint(request: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def submit(self, request: dict[str, Any], idempotency_key: str) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        row = self.connection.execute(
            "SELECT job_id, request FROM jobs WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row:
            if self.fingerprint(json.loads(row[1])) != self.fingerprint(request):
                raise ValueError("idempotency key already belongs to a different request")
            return self.get(row[0])  # type: ignore[return-value]
        job_id = uuid.uuid4().hex
        self.connection.execute(
            "INSERT INTO jobs(job_id, idempotency_key, request, state, progress, error_code, worker_id, lease_until, fencing_token, created_at, updated_at) VALUES (?, ?, ?, 'queued', ?, NULL, NULL, NULL, 0, ?, ?)",
            (job_id, idempotency_key, json.dumps(request, ensure_ascii=False), json.dumps({"completed_steps": []}), now, now),
        )
        self.connection.commit()
        return self.get(job_id)  # type: ignore[return-value]

    def recent(self, limit: int = 50) -> list[Job]:
        rows = self.connection.execute(
            "SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [job for row in rows if (job := self.get(row[0])) is not None]

    def get(self, job_id: str) -> Job | None:
        row = self.connection.execute("SELECT job_id, idempotency_key, request, state, progress, error_code, fencing_token, provider_run_id, provider_state FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return Job(row[0], row[1], json.loads(row[2]), row[3], json.loads(row[4]), row[5], row[6], row[7], row[8])

    def claim(self, worker_id: str, lease_seconds: int = 60) -> Job | None:
        if not worker_id.strip() or lease_seconds <= 0:
            raise ValueError("worker_id and lease_seconds must be valid")
        now = datetime.now(timezone.utc)
        expired = now.isoformat()
        lease = (now + timedelta(seconds=lease_seconds)).isoformat()
        if self.connection.in_transaction:
            self.connection.commit()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT job_id FROM jobs WHERE state = 'queued' OR (state = 'running' AND lease_until < ?) ORDER BY created_at LIMIT 1",
                (expired,),
            ).fetchone()
            if row is None:
                self.connection.commit()
                return None
            updated = self.connection.execute(
                "UPDATE jobs SET state = 'running', worker_id = ?, lease_until = ?, fencing_token = fencing_token + 1, updated_at = ? "
                "WHERE job_id = ? AND (state = 'queued' OR (state = 'running' AND lease_until < ?))",
                (worker_id, lease, now.isoformat(), row[0], expired),
            )
            if updated.rowcount != 1:
                self.connection.rollback()
                return None
            self.connection.commit()
            return self.get(row[0])
        except Exception:
            self.connection.rollback()
            raise

    def recover_expired_leases(self, now: datetime | None = None) -> int:
        """Return expired running jobs to the queue without changing their fencing token."""
        current = now or datetime.now(timezone.utc)
        timestamp = current.isoformat()
        self.connection.execute(
            "UPDATE jobs SET state = 'needs_review', worker_id = NULL, lease_until = NULL, error_code = 'ProviderStartOutcomeUnknown', updated_at = ? "
            "WHERE state = 'running' AND lease_until IS NOT NULL AND lease_until < ? "
            "AND EXISTS (SELECT 1 FROM provider_attempts pa WHERE pa.job_id = jobs.job_id AND pa.status = 'starting' AND pa.provider_run_id IS NULL)",
            (timestamp, timestamp),
        )
        result = self.connection.execute(
            "UPDATE jobs SET state = 'queued', worker_id = NULL, lease_until = NULL, updated_at = ? "
            "WHERE state = 'running' AND lease_until IS NOT NULL AND lease_until < ?",
            (timestamp, timestamp),
        )
        return result.rowcount

    def request_cancel(self, job_id: str) -> None:
        self.connection.execute("UPDATE jobs SET state = CASE WHEN state = 'queued' THEN 'cancelled' WHEN state = 'running' THEN 'cancel_requested' ELSE state END, updated_at = ? WHERE job_id = ?", (datetime.now(timezone.utc).isoformat(), job_id))
        self.connection.execute(
            "UPDATE provider_attempts SET cancellation_requested = 1, status = 'cancel_requested', updated_at = ? "
            "WHERE job_id = ? AND status NOT IN ('succeeded','failed','aborted','timed_out')",
            (datetime.now(timezone.utc).isoformat(), job_id),
        )
        self.connection.commit()

    def record_provider_attempt(
        self, job_id: str, source: str, *, run_id: str | None = None,
        dataset_id: str | None = None, status: str = "starting",
        checkpoint: dict[str, Any] | None = None, worker_id: str | None = None,
        fencing_token: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if worker_id is not None and fencing_token is not None:
            owned = self.connection.execute(
                "SELECT 1 FROM jobs WHERE job_id = ? AND worker_id = ? AND fencing_token = ? AND state IN ('running','cancel_requested')",
                (job_id, worker_id, fencing_token),
            ).fetchone()
            if owned is None:
                raise RuntimeError("job ownership lost")
        self.connection.execute(
            "INSERT INTO provider_attempts(attempt_id, job_id, source, status, provider_run_id, dataset_id, checkpoint, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(job_id, source) DO UPDATE SET "
            "status = excluded.status, provider_run_id = COALESCE(excluded.provider_run_id, provider_attempts.provider_run_id), "
            "dataset_id = COALESCE(excluded.dataset_id, provider_attempts.dataset_id), checkpoint = excluded.checkpoint, updated_at = excluded.updated_at",
            (uuid.uuid4().hex, job_id, source, status, run_id, dataset_id,
             json.dumps(checkpoint or {}), now, now),
        )
        self.connection.commit()

    def provider_attempts(self, job_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT source, status, provider_run_id, dataset_id, checkpoint, cancellation_requested "
            "FROM provider_attempts WHERE job_id = ? ORDER BY created_at, source", (job_id,)
        )
        return [
            {"source": r[0], "status": r[1], "provider_run_id": r[2], "dataset_id": r[3],
             "checkpoint": json.loads(r[4]), "cancellation_requested": bool(r[5])}
            for r in rows
        ]

    def claim_provider_abort(self, job_id: str, source: str, run_id: str) -> bool:
        result = self.connection.execute(
            "UPDATE provider_attempts SET status = 'aborting', updated_at = ? "
            "WHERE job_id = ? AND source = ? AND provider_run_id = ? AND cancellation_requested = 1 "
            "AND status NOT IN ('aborting','succeeded','failed','aborted','timed_out')",
            (datetime.now(timezone.utc).isoformat(), job_id, source, run_id),
        )
        return result.rowcount == 1

    def request_provider_cancellation(self, job_id: str) -> None:
        self.connection.execute(
            "UPDATE provider_attempts SET cancellation_requested = 1, status = 'cancel_requested', updated_at = ? "
            "WHERE job_id = ? AND provider_run_id IS NOT NULL AND status NOT IN ('succeeded','failed','aborted','timed_out')",
            (datetime.now(timezone.utc).isoformat(), job_id),
        )
        self.connection.commit()

    def update_provider_run(self, job_id: str, worker_id: str, fencing_token: int, run_id: str, state: str) -> None:
        updated = self.connection.execute(
            "UPDATE jobs SET provider_run_id = ?, provider_state = ?, updated_at = ? "
            "WHERE job_id = ? AND state IN ('running', 'cancel_requested') AND worker_id = ? AND fencing_token = ?",
            (run_id, state, datetime.now(timezone.utc).isoformat(), job_id, worker_id, fencing_token),
        )
        if updated.rowcount != 1:
            raise RuntimeError("job ownership lost")

    def heartbeat(self, job_id: str, worker_id: str, fencing_token: int, lease_seconds: int = 60) -> bool:
        now = datetime.now(timezone.utc)
        updated = self.connection.execute(
            "UPDATE jobs SET lease_until = ?, updated_at = ? "
            "WHERE job_id = ? AND state IN ('running', 'cancel_requested') AND worker_id = ? AND fencing_token = ?",
            ((now + timedelta(seconds=lease_seconds)).isoformat(), now.isoformat(), job_id, worker_id, fencing_token),
        )
        self.connection.commit()
        return updated.rowcount == 1

    def update_progress(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        completed_steps: list[str],
        **details: Any,
    ) -> None:
        progress = {"completed_steps": completed_steps, **details}
        updated = self.connection.execute(
            "UPDATE jobs SET progress = ?, lease_until = ?, updated_at = ? "
            "WHERE job_id = ? AND state IN ('running', 'cancel_requested') AND worker_id = ? AND fencing_token = ?",
            (json.dumps(progress), (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
             datetime.now(timezone.utc).isoformat(), job_id, worker_id, fencing_token),
        )
        if updated.rowcount != 1:
            raise RuntimeError("job ownership lost")
