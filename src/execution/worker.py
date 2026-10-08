from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from .jobs import Job, JobRepository


class JobWorker:
    def __init__(self, connection: sqlite3.Connection, worker_id: str):
        self.connection = connection
        self.worker_id = worker_id
        self.jobs = JobRepository(connection)

    def run_once(self, handler: Callable[[dict[str, Any]], list[str]]) -> Job | None:
        job = self.jobs.claim(self.worker_id)
        if job is None:
            return None
        try:
            steps = handler(job.request)
            current = self.jobs.get(job.job_id)
            if current is None:
                return None
            if current.state == "cancel_requested":
                self.connection.execute("UPDATE jobs SET state = 'cancelled', updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (job.job_id, self.worker_id, job.fencing_token))
            else:
                self.connection.execute("UPDATE jobs SET state = 'succeeded', progress = ?, lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (__import__('json').dumps({"completed_steps": steps}), job.job_id, self.worker_id, job.fencing_token))
        except Exception as exc:
            self.connection.execute("UPDATE jobs SET state = 'failed', error_code = ?, lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (type(exc).__name__, job.job_id, self.worker_id, job.fencing_token))
        return self.jobs.get(job.job_id)
