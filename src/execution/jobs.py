from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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


class JobRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    @staticmethod
    def fingerprint(request: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def submit(self, request: dict[str, Any], idempotency_key: str) -> Job:
        now = datetime.now(UTC).isoformat()
        row = self.connection.execute("SELECT job_id FROM jobs WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        if row:
            return self.get(row[0])  # type: ignore[return-value]
        job_id = uuid.uuid4().hex
        self.connection.execute(
            "INSERT INTO jobs(job_id, idempotency_key, request, state, progress, error_code, worker_id, lease_until, fencing_token, created_at, updated_at) VALUES (?, ?, ?, 'queued', ?, NULL, NULL, NULL, 0, ?, ?)",
            (job_id, idempotency_key, json.dumps(request, ensure_ascii=False), json.dumps({"completed_steps": []}), now, now),
        )
        return self.get(job_id)  # type: ignore[return-value]

    def get(self, job_id: str) -> Job | None:
        row = self.connection.execute("SELECT job_id, idempotency_key, request, state, progress, error_code, fencing_token FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return Job(row[0], row[1], json.loads(row[2]), row[3], json.loads(row[4]), row[5], row[6])

    def claim(self, worker_id: str, lease_seconds: int = 60) -> Job | None:
        now = datetime.now(UTC)
        expired = now.isoformat()
        row = self.connection.execute("SELECT job_id FROM jobs WHERE (state = 'queued' OR (state = 'running' AND lease_until < ?)) ORDER BY created_at LIMIT 1", (expired,)).fetchone()
        if row is None:
            return None
        job_id = row[0]
        lease = (now + timedelta(seconds=lease_seconds)).isoformat()
        self.connection.execute("UPDATE jobs SET state = 'running', worker_id = ?, lease_until = ?, fencing_token = fencing_token + 1, updated_at = ? WHERE job_id = ? AND (state = 'queued' OR (state = 'running' AND lease_until < ?))", (worker_id, lease, now.isoformat(), job_id, expired))
        return self.get(job_id)

    def request_cancel(self, job_id: str) -> None:
        self.connection.execute("UPDATE jobs SET state = CASE WHEN state = 'queued' THEN 'cancelled' WHEN state = 'running' THEN 'cancel_requested' ELSE state END, updated_at = ? WHERE job_id = ?", (datetime.now(UTC).isoformat(), job_id))

    def update_progress(self, job_id: str, worker_id: str, fencing_token: int, completed_steps: list[str]) -> None:
        self.connection.execute("UPDATE jobs SET progress = ?, lease_until = ?, updated_at = ? WHERE job_id = ? AND state = 'running' AND worker_id = ? AND fencing_token = ?", (json.dumps({"completed_steps": completed_steps}), (datetime.now(UTC) + timedelta(seconds=60)).isoformat(), datetime.now(UTC).isoformat(), job_id, worker_id, fencing_token))
