from unittest.mock import Mock

from src.orchestration import MultiSourceOrchestrator
from src.registry import SourceCapability


def test_orchestrator_keeps_partial_results():
    service = Mock()
    service.select_sources.return_value = (
        SourceCapability("places", "google_maps", "places", True, "places"),
        SourceCapability("google_search", "google_search", "search", True, "search"),
    )
    service.search.side_effect = [None, RuntimeError("provider detail")]

    result = MultiSourceOrchestrator(service).run("cafe", "Tehran", ["places", "google_search"], 5, "general")

    assert result["state"] == "partial"
    assert result["completed_steps"] == ["places"]
    assert result["sources"][1]["error_code"] == "RuntimeError"
    assert service.search.call_count == 2
