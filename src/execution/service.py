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

    def cancel(self, job_id: str, abort_provider_run=None) -> Job | None:
        with self._connect() as db:
            repo = JobRepository(db)
            repo.request_cancel(job_id)
            job = repo.get(job_id)
            if job is None:
                return None
            attempts = repo.provider_attempts(job_id)
        if callable(abort_provider_run):
            for attempt in attempts:
                run_id = attempt.get("provider_run_id")
                if not run_id:
                    continue
                try:
                    abort_provider_run(attempt["source"], run_id)
                except Exception:
                    continue
                with self._connect() as db:
                    db.execute(
                        "UPDATE provider_attempts SET status = 'aborted', updated_at = datetime('now') WHERE job_id = ? AND source = ? AND provider_run_id = ?",
                        (job_id, attempt["source"], run_id),
                    )
                    db.commit()
        return job

    def provider_attempts(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return JobRepository(db).provider_attempts(job_id)

    def resolve_needs_review(
        self, job_id: str, action: str, *, source: str | None = None,
        provider_run_id: str | None = None, confirmed_no_remote_run: bool = False,
    ) -> Job | None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            repo = JobRepository(db)
            job = repo.get(job_id)
            if job is None:
                return None
            if job.state != "needs_review":
                raise ValueError("job is not awaiting review")
            if action == "retry":
                if not confirmed_no_remote_run:
                    raise ValueError("confirm that no provider run exists before retrying")
                db.execute(
                    "UPDATE provider_attempts SET status = 'manual_retry', provider_run_id = NULL, dataset_id = NULL, updated_at = datetime('now') WHERE job_id = ? AND status = 'starting' AND provider_run_id IS NULL",
                    (job_id,),
                )
                resolution = {"action": action, "confirmed_no_remote_run": True}
                state = "queued"
            elif action == "attach_run":
                if not source or not provider_run_id:
                    raise ValueError("source and provider_run_id are required")
                repo.record_provider_attempt(job_id, source, run_id=provider_run_id, status="running")
                resolution = {"action": action, "source": source, "provider_run_id": provider_run_id}
                state = "queued"
            elif action == "abandon":
                resolution = {"action": action}
                state = "cancelled"
            else:
                raise ValueError("unsupported review action")
            progress = {**job.progress, "manual_resolution": resolution}
            db.execute(
                "UPDATE jobs SET state = ?, error_code = NULL, worker_id = NULL, lease_until = NULL, progress = ?, updated_at = datetime('now') WHERE job_id = ? AND state = 'needs_review'",
                (state, json.dumps(progress, ensure_ascii=False), job_id),
            )
            db.commit()
            return repo.get(job_id)

    def _connect(self):
        import sqlite3
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        from ..migrations import migrate
        migrate(connection)
        return connection
