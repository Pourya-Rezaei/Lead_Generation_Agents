from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.domain import Lead
from src.results import RunStatus, SearchResult, map_apify_status


def test_maps_apify_statuses() -> None:
    assert map_apify_status("READY") is RunStatus.PENDING
    assert map_apify_status("RUNNING") is RunStatus.RUNNING
    assert map_apify_status("SUCCEEDED") is RunStatus.SUCCEEDED
    assert map_apify_status("FAILED") is RunStatus.FAILED
    assert map_apify_status("ABORTED") is RunStatus.ABORTED
    assert map_apify_status("TIMED-OUT") is RunStatus.TIMED_OUT


def test_rejects_unknown_apify_status() -> None:
    with pytest.raises(ValueError, match="Unknown Apify run status"):
        map_apify_status("MYSTERY")


def test_successful_result_requires_finished_at() -> None:
    with pytest.raises(ValidationError):
        SearchResult(source="places", status=RunStatus.SUCCEEDED)


def test_failed_result_cannot_contain_leads() -> None:
    with pytest.raises(ValidationError):
        SearchResult(
            source="places",
            status=RunStatus.FAILED,
            leads=[Lead(name="Acme")],
            finished_at=datetime.now(UTC),
        )


def test_partial_result_is_explicit() -> None:
    result = SearchResult(
        source="places",
        status=RunStatus.PARTIAL,
        partial=True,
        leads=[Lead(name="Acme")],
        warnings=["Actor did not finish before the wait deadline"],
        finished_at=datetime.now(UTC),
    )
    assert result.partial is True
    assert result.leads[0].name == "Acme"


def test_partial_flag_must_match_status() -> None:
    with pytest.raises(ValidationError):
        SearchResult(
            source="places",
            status=RunStatus.SUCCEEDED,
            partial=True,
            finished_at=datetime.now(UTC),
        )
