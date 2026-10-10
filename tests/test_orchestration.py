from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.orchestration import MultiSourceOrchestrator
from src.registry import SourceCapability


def test_orchestrator_preserves_nonterminal_search_status():
    service = Mock()
    service.select_sources.return_value = (SourceCapability("places", "google_maps", "places", True, "places"),)
    service.search.return_value = SimpleNamespace(status=SimpleNamespace(value="running"))
    result = MultiSourceOrchestrator(service).run("cafe", "Tehran", ["places"])
    assert result["state"] == "running"
    assert result["sources"][0]["state"] == "running"


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


@pytest.mark.parametrize(
    ("source_states", "expected_state", "expected_steps"),
    [
        (["succeeded", "succeeded"], "succeeded", ["source-0", "source-1"]),
        (["failed", "aborted"], "failed", []),
        (["partial"], "partial", ["source-0"]),
        (["partial", "failed"], "partial", ["source-0"]),
        (["succeeded", "failed"], "partial", ["source-0"]),
        (["running"], "running", []),
        (["succeeded", "running"], "running", ["source-0"]),
    ],
)
def test_orchestrator_aggregates_partial_and_terminal_states(
    source_states, expected_state, expected_steps
):
    service = Mock()
    service.select_sources.return_value = tuple(
        SourceCapability(f"source-{index}", "platform", "actor", True, "test")
        for index in range(len(source_states))
    )
    service.search.side_effect = [
        SimpleNamespace(status=SimpleNamespace(value=state))
        for state in source_states
    ]

    result = MultiSourceOrchestrator(service).run(
        "cafe", "Tehran", [f"source-{index}" for index in range(len(source_states))]
    )

    assert result["state"] == expected_state
    assert result["completed_steps"] == expected_steps
