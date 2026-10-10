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
    ) -> dict[str, Any]:
        selected = self.service.select_sources(sources)
        executions: list[SourceExecution] = []
        for capability in selected:
            try:
                self.service.search(query, location, capability.name, limit, campaign_id)
            except Exception as exc:
                executions.append(SourceExecution(capability.name, "failed", type(exc).__name__))
            else:
                executions.append(SourceExecution(capability.name, "succeeded"))
        succeeded = sum(item.state == "succeeded" for item in executions)
        state = "succeeded" if succeeded == len(executions) else "partial" if succeeded else "failed"
        return {
            "state": state,
            "sources": [item.__dict__ for item in executions],
            "completed_steps": [item.source for item in executions if item.state == "succeeded"],
        }
