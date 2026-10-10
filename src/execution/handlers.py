from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..service import SearchLeadsService
from ..orchestration import MultiSourceOrchestrator


def places_handler(service: SearchLeadsService) -> Callable[[dict[str, Any]], Any]:
    """Build a worker handler for the existing synchronous Places use case."""
    def handle(request: dict[str, Any]) -> list[str]:
        query = str(request.get("query", "")).strip()
        location = str(request.get("location", "")).strip()
        source = str(request.get("source", "places"))
        limit = int(request.get("limit", 20))
        campaign_id = request.get("campaign_id")
        provider_run_id = request.get("provider_run_id")
        if provider_run_id:
            service.search(
                query, location, source, limit, campaign_id,
                provider_run_id=provider_run_id,
            )
        else:
            service.search(query, location, source, limit, campaign_id)
        provider_run_id = getattr(service, "last_provider_run_id", None)
        if isinstance(provider_run_id, str) and provider_run_id:
            return {"completed_steps": [source], "provider_run_id": provider_run_id}
        return [source]

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
        )
    return handle
