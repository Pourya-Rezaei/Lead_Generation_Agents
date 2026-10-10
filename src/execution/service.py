from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .jobs import Job, JobRepository


class JobService:
    def __init__(self, database_path: str):
        self.database_path = database_path
        Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    def submit(self, request: dict[str, Any], idempotency_key: str) -> Job:
        with self._connect() as db:
            return JobRepository(db).submit(request, idempotency_key)

    def recent(self, limit: int = 50) -> list[Job]:
        with self._connect() as db:
            return JobRepository(db).recent(limit)

    def get(self, job_id: str) -> Job | None:
        with self._connect() as db:
            return JobRepository(db).get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        with self._connect() as db:
            repo = JobRepository(db)
            repo.request_cancel(job_id)
            return repo.get(job_id)

    def _connect(self):
        import sqlite3
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        from ..migrations import migrate
        migrate(connection)
        return connection
