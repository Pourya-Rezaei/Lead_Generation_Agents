from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src.execution.handlers import places_handler
from src.results import RunStatus, SearchResult


def test_places_handler_maps_job_request_to_search_service():
    service = Mock()
    service.search.return_value = SearchResult(
        source="places", status=RunStatus.SUCCEEDED,
        finished_at=datetime.now(timezone.utc),
    )
    handler = places_handler(service)
    result = handler({"query": "cafe", "location": "Tehran", "limit": 5, "campaign_id": "general"})
    assert result["state"] == "succeeded"
    assert result["completed_steps"] == ["places"]
    service.search.assert_called_once_with("cafe", "Tehran", "places", 5, "general")


@pytest.mark.parametrize(
    ("status", "partial", "expected"),
    [
        (RunStatus.FAILED, False, "failed"),
        (RunStatus.ABORTED, False, "aborted"),
        (RunStatus.TIMED_OUT, False, "timed_out"),
        (RunStatus.PARTIAL, True, "partial"),
    ],
)
def test_places_handler_preserves_search_result_status(status, partial, expected):
    service = Mock()
    service.search.return_value = SearchResult(
        source="places", status=status, partial=partial,
        finished_at=datetime.now(timezone.utc),
    )

    result = places_handler(service)({"query": "cafe", "location": "Tehran"})

    assert result["state"] == expected
