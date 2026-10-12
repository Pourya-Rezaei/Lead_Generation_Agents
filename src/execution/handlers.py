from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..service import SearchLeadsService


def _provider_run_callback(service: SearchLeadsService, request: dict[str, Any], source: str):
    job_id = request.get("_job_id")
    worker_id = request.get("_worker_id")
    fencing_token = request.get("_fencing_token")
    if not isinstance(job_id, str) or not isinstance(worker_id, str) or not isinstance(fencing_token, int):
        return None

    def persist(source_name: str, run_id: str | None, dataset_id: str | None, status: str) -> None:
        import sqlite3
        from ..errors import ProviderAbortOutcomeUnknown
        from .jobs import JobRepository

        with sqlite3.connect(service.settings.database_path, timeout=5) as db:
            db.execute("PRAGMA foreign_keys = ON")
            repo = JobRepository(db)
            repo.record_provider_attempt(
                job_id, source, run_id=run_id, dataset_id=dataset_id, status=status,
                worker_id=worker_id, fencing_token=fencing_token,
            )
            if run_id and status in {"starting", "pending", "running", "resuming"}:
                job = repo.get(job_id)
                if job is not None and job.state == "cancel_requested":
                    db.execute("UPDATE provider_attempts SET cancellation_requested = 1 WHERE job_id = ? AND source = ?", (job_id, source))
                attempt = next(
                    (item for item in repo.provider_attempts(job_id) if item["source"] == source),
                    None,
                )
                if (
                    attempt
                    and attempt["cancellation_requested"]
                    and repo.claim_provider_abort(job_id, source, run_id)
                ):
                    db.commit()
                    try:
                        service.abort_provider_run(source, run_id)
                    except Exception:
                        db.execute(
                            "UPDATE provider_attempts SET status = 'abort_unknown', updated_at = datetime('now') "
                            "WHERE job_id = ? AND source = ? AND provider_run_id = ? AND status = 'aborting'",
                            (job_id, source, run_id),
                        )
                        db.commit()
                        raise ProviderAbortOutcomeUnknown(
                            "Provider run abort outcome is unknown"
                        ) from None
                    db.execute(
                        "UPDATE provider_attempts SET status = 'aborted', updated_at = datetime('now') "
                        "WHERE job_id = ? AND source = ? AND provider_run_id = ?",
                        (job_id, source, run_id),
                    )
                    db.commit()
    return persist


def places_handler(service: SearchLeadsService) -> Callable[[dict[str, Any]], Any]:
    """Build a worker handler for the existing synchronous Places use case."""
    def handle(request: dict[str, Any]) -> list[str]:
        from ..search_requests import validate_job_request
        request = validate_job_request(request)
        query = str(request.get("search", request.get("query", ""))).strip()
        location = str(request.get("location", "")).strip()
        source = str(request.get("source", "places"))
        limit = int(request.get("searchLimit", request.get("limit", 20)))
        campaign_id = request.get("campaign_id")
        provider_run_id = request.get("provider_run_id")
        callback = _provider_run_callback(service, request, source)
        if callback:
            callback(source, provider_run_id, None, "resuming" if provider_run_id else "starting")
        options = {"provider_run_id": provider_run_id} if provider_run_id else {}
        if callback:
            options["on_provider_run"] = callback
        search_result = service.search(query, location, source, limit, campaign_id, **options)
        provider_run_id = getattr(search_result, "run_id", None)
        result_status = getattr(search_result, "status", "succeeded")
        result_state = getattr(result_status, "value", result_status)
        if not isinstance(result_state, str):
            result_state = "succeeded"
        details = getattr(service, "last_persisted_refs", {})
        result = {"completed_steps": [source], "state": result_state}
        if isinstance(details, dict) and (details.get("lead_ids") or details.get("raw_record_refs") or (source == "instagram" and details.get("run_id"))):
            result["persisted_refs"] = details
        if source == "instagram":
            result["received_count"] = search_result.received_count
            result["accepted_count"] = search_result.accepted_count
            result["rejected_count"] = search_result.rejected_count
        if isinstance(provider_run_id, str) and provider_run_id:
            result["provider_run_id"] = provider_run_id
        return result

    def preflight(request: dict[str, Any]) -> None:
        from ..search_requests import validate_job_request
        validate_job_request(request)

    setattr(handle, "preflight", preflight)
    return handle


def multi_source_handler(service: SearchLeadsService):
    def handle(request):
        raise ValueError("unsupported_source: multi-source execution is no longer supported")
    return handle
