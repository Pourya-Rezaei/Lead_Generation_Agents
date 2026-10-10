from datetime import UTC, datetime
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
