from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..service import SearchLeadsService
from ..orchestration import MultiSourceOrchestrator


def _provider_run_callback(service: SearchLeadsService, request: dict[str, Any], source: str):
    job_id = request.get("_job_id")
    worker_id = request.get("_worker_id")
    fencing_token = request.get("_fencing_token")
    if not isinstance(job_id, str) or not isinstance(worker_id, str) or not isinstance(fencing_token, int):
        return None

    def persist(source_name: str, run_id: str | None, dataset_id: str | None, status: str) -> None:
        import sqlite3
        from .jobs import JobRepository
        with sqlite3.connect(service.settings.database_path, timeout=5) as db:
            db.execute("PRAGMA foreign_keys = ON")
            JobRepository(db).record_provider_attempt(
                job_id, source, run_id=run_id, dataset_id=dataset_id, status=status,
                worker_id=worker_id, fencing_token=fencing_token,
            )
    return persist


def places_handler(service: SearchLeadsService) -> Callable[[dict[str, Any]], Any]:
    """Build a worker handler for the existing synchronous Places use case."""
    def handle(request: dict[str, Any]) -> list[str]:
        query = str(request.get("query", "")).strip()
        location = str(request.get("location", "")).strip()
        source = str(request.get("source", "places"))
        limit = int(request.get("limit", 20))
        campaign_id = request.get("campaign_id")
        provider_run_id = request.get("provider_run_id")
        callback = _provider_run_callback(service, request, source)
        if callback:
            callback(source, provider_run_id, None, "resuming" if provider_run_id else "starting")
        options = {"provider_run_id": provider_run_id} if provider_run_id else {}
        if callback:
            options["on_provider_run"] = callback
        result = service.search(query, location, source, limit, campaign_id, **options)
        provider_run_id = getattr(result, "run_id", None)
        details = getattr(service, "last_persisted_refs", {})
        result = {"completed_steps": [source]}
        if isinstance(details, dict) and details.get("lead_ids"):
            result["persisted_refs"] = details
        if isinstance(provider_run_id, str) and provider_run_id:
            result["provider_run_id"] = provider_run_id
        return result if len(result) > 1 else [source]

    return handle


def multi_source_handler(service: SearchLeadsService) -> Callable[[dict[str, Any]], Any]:
    """Build a worker handler that isolates each selected source."""
    def handle(request: dict[str, Any]) -> dict[str, Any]:
        sources = request.get("sources", [])
        if not isinstance(sources, list) or not sources:
            raise ValueError("sources must be a non-empty list")
        return MultiSourceOrchestrator(service).run(
            str(request.get("query", "")),
            str(request.get("location", "")),
            sources,
            int(request.get("limit", 20)),
            request.get("campaign_id"),
            provider_run_ids=request.get("provider_run_ids", {}),
            on_provider_run_factory=lambda source: _provider_run_callback(service, request, source),
        )
    return handle
