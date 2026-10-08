from unittest.mock import Mock

from src.execution.handlers import places_handler


def test_places_handler_maps_job_request_to_search_service():
    service = Mock()
    handler = places_handler(service)
    assert handler({"query": "cafe", "location": "Tehran", "limit": 5, "campaign_id": "general"}) == ["places"]
    service.search.assert_called_once_with("cafe", "Tehran", "places", 5, "general")
