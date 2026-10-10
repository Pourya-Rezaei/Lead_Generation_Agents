from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .service import SearchLeadsService


@dataclass(frozen=True)
class SourceExecution:
    source: str
    state: str
    error_code: str | None = None


class MultiSourceOrchestrator:
    """Run validated sources independently and preserve partial outcomes."""

    def __init__(self, service: SearchLeadsService):
        self.service = service

    def run(
        self,
        query: str,
        location: str,
        sources: list[str] | tuple[str, ...],
        limit: int = 20,
        campaign_id: str | None = None,
        *,
        provider_run_ids: dict[str, str] | None = None,
        on_provider_run_factory=None,
    ) -> dict[str, Any]:
        selected = self.service.select_sources(sources)
        executions: list[SourceExecution] = []
        for capability in selected:
            try:
                options = {}
                provider_run_id = (provider_run_ids or {}).get(capability.name)
                if provider_run_id:
                    options["provider_run_id"] = provider_run_id
                callback = on_provider_run_factory(capability.name) if callable(on_provider_run_factory) else None
                if callable(callback):
                    callback(capability.name, provider_run_id, None, "resuming" if provider_run_id else "starting")
                    options["on_provider_run"] = callback
                result = self.service.search(query, location, capability.name, limit, campaign_id, **options)
            except Exception as exc:
                executions.append(SourceExecution(capability.name, "failed", type(exc).__name__))
            else:
                status = getattr(result, "status", None) if result is not None else "succeeded"
                state = getattr(status, "value", status)
                if state in {"succeeded", "partial", "failed", "aborted", "timed_out", "running", "pending"}:
                    executions.append(SourceExecution(capability.name, str(state)))
                else:
                    executions.append(SourceExecution(capability.name, "failed", "InvalidSearchResultStatus"))
        succeeded = sum(item.state == "succeeded" for item in executions)
        active = sum(item.state in {"pending", "running"} for item in executions)
        failed = sum(item.state in {"failed", "aborted", "timed_out"} for item in executions)
        state = (
            "succeeded" if succeeded == len(executions)
            else "running" if active and not failed
            else "partial" if succeeded
            else "failed"
        )
        return {
            "state": state,
            "sources": [item.__dict__ for item in executions],
            "completed_steps": [item.source for item in executions if item.state == "succeeded"],
        }
