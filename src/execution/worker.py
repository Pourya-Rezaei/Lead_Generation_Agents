from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal

from .budget import BudgetRepository
from .cache import ExecutionCache
from typing import Any

from ..errors import ApifyStartOutcomeUnknown, ProviderAbortOutcomeUnknown
from .jobs import Job, JobRepository


class JobWorker:
    def __init__(self, connection: sqlite3.Connection, worker_id: str, lease_seconds: int = 60):
        if lease_seconds <= 2:
            raise ValueError("lease_seconds must be greater than two")
        self.connection = connection
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.jobs = JobRepository(connection)
        self._stop_event = threading.Event()

    def _record_worker_heartbeat(self) -> None:
        self.connection.execute(
            "INSERT INTO worker_heartbeats(worker_id, heartbeat_at) VALUES (?, datetime('now')) "
            "ON CONFLICT(worker_id) DO UPDATE SET heartbeat_at = excluded.heartbeat_at",
            (self.worker_id,),
        )
        self.connection.commit()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def _replay_cached_refs(self, refs: dict[str, Any]) -> bool:
        if refs.get("source") == "instagram":
            run_id, campaign_id = refs.get("run_id"), refs.get("campaign_id")
            if not isinstance(run_id, str) or not isinstance(campaign_id, str):
                return False
            row = self.connection.execute(
                "SELECT 1 FROM instagram_campaign_runs r JOIN instagram_campaigns c "
                "ON c.campaign_id=r.campaign_id WHERE r.run_id=? AND r.campaign_id=? AND r.status='succeeded'",
                (run_id, campaign_id),
            ).fetchone()
            return row is not None
        lead_ids = refs.get("lead_ids")
        campaign_id = refs.get("campaign_id")
        run_id = refs.get("run_id")
        if not isinstance(lead_ids, list) or not (lead_ids or refs.get("raw_record_refs")) or not isinstance(campaign_id, str) or not isinstance(run_id, str) or not run_id:
            return False
        campaign = self.connection.execute(
            "SELECT 1 FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        if campaign is None:
            return False
        run = self.connection.execute(
            "SELECT status FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if run is None or run[0] not in {"succeeded", "partial"}:
            return False
        placeholders = ",".join("?" for _ in lead_ids)
        rows = self.connection.execute(
            f"SELECT lead_id FROM leads WHERE lead_id IN ({placeholders})",
            tuple(str(item) for item in lead_ids),
        ).fetchall()
        if len(rows) != len(set(str(item) for item in lead_ids)):
            return False
        observation_ids = refs.get("observation_ids")
        raw_record_refs = refs.get("raw_record_refs")
        if not isinstance(observation_ids, list) or not isinstance(raw_record_refs, list):
            return False
        if observation_ids:
            observation_placeholders = ",".join("?" for _ in observation_ids)
            observation_count = self.connection.execute(
                f"SELECT COUNT(*) FROM observations WHERE observation_id IN ({observation_placeholders}) AND run_id = ?",
                (*[str(item) for item in observation_ids], run_id),
            ).fetchone()[0]
            if observation_count != len(set(str(item) for item in observation_ids)):
                return False
        for ref in raw_record_refs:
            if not isinstance(ref, dict) or ref.get("run_id") != run_id or not isinstance(ref.get("record_index"), int):
                return False
        if raw_record_refs:
            raw_count = self.connection.execute(
                "SELECT COUNT(*) FROM raw_records WHERE run_id = ? AND record_index IN ("
                + ",".join("?" for _ in raw_record_refs) + ")",
                (run_id, *[ref["record_index"] for ref in raw_record_refs]),
            ).fetchone()[0]
            if raw_count != len({ref["record_index"] for ref in raw_record_refs}):
                return False
        now = datetime.now(timezone.utc).isoformat()
        for (lead_id,) in rows:
            self.connection.execute(
                "INSERT INTO campaign_leads(campaign_id, lead_id, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(campaign_id, lead_id) DO UPDATE SET last_seen_at = excluded.last_seen_at",
                (campaign_id, lead_id, now, now),
            )
        return True

    def _start_heartbeat(
        self,
        job_id: str,
        fencing_token: int,
        stop: threading.Event,
        lost: threading.Event,
    ) -> threading.Thread:
        interval = max(1.0, self.lease_seconds / 3)
        database = self.connection.execute("PRAGMA database_list").fetchone()
        database_path = database[2] if database else ""

        def beat() -> None:
            if not database_path or database_path == ":memory:":
                return
            try:
                with sqlite3.connect(database_path, timeout=5) as connection:
                    repository = JobRepository(connection)
                    while not stop.wait(interval):
                        if not repository.heartbeat(
                            job_id, self.worker_id, fencing_token, self.lease_seconds
                        ):
                            lost.set()
                            return
            except sqlite3.Error:
                lost.set()

        thread = threading.Thread(target=beat, name=f"heartbeat-{job_id}", daemon=True)
        thread.start()
        return thread

    def run_once(self, handler: Callable[[dict[str, Any]], list[str]]) -> Job | None:
        if self.stopped:
            return None
        self._record_worker_heartbeat()
        self.jobs.recover_expired_leases()
        job = self.jobs.claim(self.worker_id, self.lease_seconds)
        if job is None:
            return None
        reservation_id = None
        cache = ExecutionCache(self.connection)
        try:
            if job.request.get("source", "places") not in {"places", "instagram"} or job.request.get("operation") not in {None, "search"} or job.request.get("sources"):
                raise ValueError("unsupported_source")
            if job.request.get("source") == "instagram":
                from ..search_requests import validate_job_request
                try:
                    validate_job_request(job.request)
                except ValueError:
                    raise ValueError("unsupported_source: historical Instagram request") from None
            preflight = getattr(handler, "preflight", None)
            if callable(preflight):
                preflight(job.request)
            cached = None if job.request.get("force_refresh") else cache.get(job.request)
            if cached is not None and cache.is_replayable(cached) and self._replay_cached_refs(cached["persisted_refs"]):
                self.connection.execute("UPDATE jobs SET state = 'succeeded', progress = ?, lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (json.dumps({**cached, "cached": True}), job.job_id, self.worker_id, job.fencing_token))
                self.connection.commit()
                return self.jobs.get(job.job_id)
            if job.request.get("estimated_cost") is not None:
                reservation = BudgetRepository(self.connection).reserve(
                    job.job_id,
                    str(job.request.get("source", "places")),
                    Decimal(str(job.request["estimated_cost"])),
                    str(job.request.get("currency", "USD")),
                    Decimal(str(job.request.get("max_cost", job.request["estimated_cost"]))),
                    str(job.request.get("pricing_version", "unknown")),
                )
                reservation_id = reservation.reservation_id
            request = dict(job.request)
            request["_job_id"] = job.job_id
            request["_worker_id"] = self.worker_id
            request["_fencing_token"] = job.fencing_token
            existing_attempts = self.jobs.provider_attempts(job.job_id)
            if existing_attempts:
                run_ids = {item["source"]: item["provider_run_id"] for item in existing_attempts if item.get("provider_run_id")}
                request["provider_run_ids"] = run_ids
                attempt = next((item for item in existing_attempts if item["source"] == request.get("source")), existing_attempts[0])
                if attempt.get("provider_run_id"):
                    request["provider_run_id"] = attempt["provider_run_id"]
            elif job.provider_run_id:
                request["provider_run_id"] = job.provider_run_id
            heartbeat_stop = threading.Event()
            heartbeat_lost = threading.Event()
            heartbeat_thread = self._start_heartbeat(
                job.job_id, job.fencing_token, heartbeat_stop, heartbeat_lost
            )
            try:
                result = handler(request)
            finally:
                heartbeat_stop.set()
                heartbeat_thread.join(timeout=2)
            if heartbeat_lost.is_set():
                raise RuntimeError("job lease lost during handler execution")
            result_state = "succeeded"
            result_details: dict[str, Any] = {}
            if isinstance(result, dict):
                steps = list(result.get("completed_steps", []))
                result_state = str(result.get("state", "succeeded"))
                result_details = {"sources": result.get("sources", [])}
                for count_name in ("received_count", "accepted_count", "rejected_count"):
                    if count_name in result:
                        result_details[count_name] = result[count_name]
                if isinstance(result.get("persisted_refs"), dict):
                    result_details["persisted_refs"] = result["persisted_refs"]
                provider_run_id = result.get("provider_run_id")
                if isinstance(provider_run_id, str) and provider_run_id:
                    provider_state = {
                        "succeeded": "SUCCEEDED",
                        "partial": "SUCCEEDED",
                        "failed": "FAILED",
                        "aborted": "ABORTED",
                        "timed_out": "TIMED-OUT",
                        "running": "RUNNING",
                        "pending": "READY",
                    }.get(result_state, "UNKNOWN")
                    self.jobs.update_provider_run(
                        job.job_id, self.worker_id, job.fencing_token, provider_run_id, provider_state
                    )
                checkpoint = result.get("checkpoint")
                if isinstance(checkpoint, dict):
                    result_details["checkpoint"] = checkpoint
            else:
                steps = list(result)
            self.jobs.update_progress(
                job.job_id, self.worker_id, job.fencing_token, steps, **result_details
            )
            if result_state not in {"succeeded", "partial", "failed", "aborted", "timed_out", "running", "pending"}:
                result_state = "failed"
                result_details["error_code"] = "InvalidHandlerResultState"
            attempt_state = result_state if result_state in {"succeeded", "partial", "failed", "aborted", "timed_out"} else "running"
            self.connection.execute(
                "UPDATE provider_attempts SET status = ?, updated_at = datetime('now') WHERE job_id = ? AND status != 'cancel_requested'",
                (attempt_state, job.job_id),
            )
            if result_state == "aborted":
                current = self.jobs.get(job.job_id)
                if current is not None and current.state == "cancel_requested":
                    self.connection.execute(
                        "UPDATE jobs SET state = 'cancelled', lease_until = NULL, updated_at = datetime('now') "
                        "WHERE job_id = ? AND worker_id = ? AND fencing_token = ?",
                        (job.job_id, self.worker_id, job.fencing_token),
                    )
                else:
                    self.connection.execute(
                        "UPDATE jobs SET state = 'failed', error_code = ?, lease_until = NULL, updated_at = datetime('now') "
                        "WHERE job_id = ? AND worker_id = ? AND fencing_token = ?",
                        ("SourceExecutionFailed", job.job_id, self.worker_id, job.fencing_token),
                    )
            elif result_state in {"failed", "timed_out"}:
                self.connection.execute("UPDATE jobs SET state = 'failed', error_code = ?, lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", ("SourceExecutionFailed", job.job_id, self.worker_id, job.fencing_token))
            elif result_state == "partial":
                self.connection.execute("UPDATE jobs SET state = 'partial', lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (job.job_id, self.worker_id, job.fencing_token))
            elif result_state in {"running", "pending"}:
                self.connection.execute("UPDATE jobs SET state = 'queued', lease_until = NULL, updated_at = datetime('now') WHERE job_id = ? AND worker_id = ? AND fencing_token = ?", (job.job_id, self.worker_id, job.fencing_token))
            else:
                cache_details = {key: value for key, value in result_details.items() if key in {"persisted_refs", "received_count", "accepted_count", "rejected_count"}}
                cache.put(job.request, {"state": "succeeded", "completed_steps": steps, **cache_details})
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
            self.connection.commit()
        except Exception as exc:
            current = self.jobs.get(job.job_id)
            if current is not None and current.state == "needs_review":
                state = "needs_review"
                error_code = current.error_code or "ProviderOutcomeUnknown"
            elif isinstance(exc, ApifyStartOutcomeUnknown):
                state = "needs_review"
                error_code = "ProviderStartOutcomeUnknown"
            elif isinstance(exc, ProviderAbortOutcomeUnknown):
                state = "needs_review"
                error_code = "ProviderAbortOutcomeUnknown"
            else:
                state = "failed"
                error_code = "unsupported_source" if isinstance(exc, ValueError) and "unsupported_source" in str(exc) else type(exc).__name__
            self.connection.execute(
                "UPDATE jobs SET state = ?, error_code = ?, lease_until = NULL, updated_at = datetime('now') "
                "WHERE job_id = ? AND worker_id = ? AND fencing_token = ?",
                (state, error_code, job.job_id, self.worker_id, job.fencing_token),
            )
            if reservation_id:
                BudgetRepository(self.connection).reconcile(reservation_id, None)
            self.connection.commit()
        return self.jobs.get(job.job_id)
