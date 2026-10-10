from datetime import datetime, timezone
from unittest.mock import Mock

from src.connectors.apify_google_search import ApifyGoogleSearchConnector
from src.results import RunStatus


def test_google_search_maps_public_result_to_lead():
    client = Mock()
    client.run_actor.return_value = {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}
    client.dataset_items.return_value = [{"title": "Cafe", "url": "https://cafe.example", "description": "public"}]
    result = ApifyGoogleSearchConnector("token", client=client).search("cafe", "Tehran", 5)
    assert result.status is RunStatus.SUCCEEDED
    assert result.leads[0].website == "https://cafe.example"
    assert result.raw_records == [{"title": "Cafe", "url": "https://cafe.example", "description": "public"}]
    client.run_actor.assert_called_once_with(
        "apify~google-search-scraper",
        {"queries": ["cafe Tehran"], "maxPagesPerQuery": 1},
        wait_for_finish=60,
    )


def test_google_search_resumes_persisted_run_without_starting_actor():
    client = Mock()
    client.wait_for_run.return_value = {"id": "persisted-run", "status": "SUCCEEDED", "defaultDatasetId": "ds-2"}
    client.dataset_items.return_value = [{"title": "Cafe", "url": "https://cafe.example"}]
    result = ApifyGoogleSearchConnector("token", client=client).search_existing_run("persisted-run", "cafe", 5)
    assert result.run_id == "persisted-run"
    client.wait_for_run.assert_called_once_with("persisted-run", timeout=300, poll_interval=2)
    client.run_actor.assert_not_called()
