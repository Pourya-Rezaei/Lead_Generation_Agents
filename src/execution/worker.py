from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from decimal import Decimal

from .budget import BudgetRepository
from .cache import ExecutionCache
from typing import Any

from .jobs import Job, JobRepository


class JobWorker:
    def __init__(self, connection: sqlite3.Connection, worker_id: str):
        self.connection = connection
        self.worker_id = worker_id
        self.jobs = JobRepository(connection)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def run_once(self, handler: Callable[[dict[str, Any]], list[str]]) -> Job | None:
        if self.stopped:
            return None
        self.jobs.recover_expired_leases()
        job = self.jobs.claim(self.worker_id)
        if job is None:
            return None
        reservation_id = None
        cache = ExecutionCache(self.connection)
        try:
            cached = None if job.request.get("force_refresh") else cache.get(job.request)
            if cached is not None:
                self.connection.execute("UPDATE jobs SET state = 'succeeded', progress = ?, lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (__import__('json').dumps({"completed_steps": cached.get("completed_steps", []), "cached": True}), job.job_id, self.worker_id, job.fencing_token))
                return self.jobs.get(job.job_id)
            if job.request.get("estimated_cost") is not None:
                reservation = BudgetRepository(self.connection).reserve(
                    job.job_id,
                    "places",
                    Decimal(str(job.request["estimated_cost"])),
                    str(job.request.get("currency", "USD")),
                    Decimal(str(job.request.get("max_cost", job.request["estimated_cost"]))),
                    str(job.request.get("pricing_version", "unknown")),
                )
                reservation_id = reservation.reservation_id
            request = dict(job.request)
            if job.provider_run_id:
                request["provider_run_id"] = job.provider_run_id
            result = handler(request)
            result_state = "succeeded"
            result_details: dict[str, Any] = {}
            if isinstance(result, dict):
                steps = list(result.get("completed_steps", []))
                result_state = str(result.get("state", "succeeded"))
                result_details = {"sources": result.get("sources", [])}
                provider_run_id = result.get("provider_run_id")
                if isinstance(provider_run_id, str) and provider_run_id:
                    self.jobs.update_provider_run(job.job_id, self.worker_id, job.fencing_token, provider_run_id, "SUCCEEDED")
                checkpoint = result.get("checkpoint")
                if isinstance(checkpoint, dict):
                    result_details["checkpoint"] = checkpoint
            else:
                steps = list(result)
            self.jobs.update_progress(
                job.job_id, self.worker_id, job.fencing_token, steps, **result_details
            )
            if result_state == "failed":
                self.connection.execute("UPDATE jobs SET state = 'failed', error_code = ?, lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", ("SourceExecutionFailed", job.job_id, self.worker_id, job.fencing_token))
            elif result_state == "partial":
                self.connection.execute("UPDATE jobs SET state = 'partial', lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (job.job_id, self.worker_id, job.fencing_token))
            else:
                cache.put(job.request, {"completed_steps": steps})
            current = self.jobs.get(job.job_id)
            if current is None:
                return None
            if current.state == "cancel_requested":
                self.connection.execute("UPDATE jobs SET state = 'cancelled', updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (job.job_id, self.worker_id, job.fencing_token))
            elif result_state == "succeeded":
                self.connection.execute("UPDATE jobs SET state = 'succeeded', lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (job.job_id, self.worker_id, job.fencing_token))
                if reservation_id:
                    BudgetRepository(self.connection).reconcile(reservation_id, None)
            elif reservation_id:
                BudgetRepository(self.connection).reconcile(reservation_id, None)
        except Exception as exc:
            self.connection.execute("UPDATE jobs SET state = 'failed', error_code = ?, lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (type(exc).__name__, job.job_id, self.worker_id, job.fencing_token))
            if reservation_id:
                BudgetRepository(self.connection).reconcile(reservation_id, None)
        return self.jobs.get(job.job_id)
