import pytest
from src.registry import ConnectorRegistry


def test_exactly_two_enabled_sources():
    capabilities = {item.name: item for item in ConnectorRegistry().capabilities()}
    assert set(capabilities) == {"places", "instagram"}
    assert all(item.enabled for item in capabilities.values())
    assert capabilities["instagram"].actor == "apify~instagram-search-scraper"


def test_single_source_selection():
    registry = ConnectorRegistry()
    assert registry.select_sources(["instagram"])[0].platform == "instagram"
    for sources in ([], ["places", "instagram"], ["places", "places"], ["google_search"], ["tiktok"]):
        with pytest.raises(ValueError):
            registry.select_sources(sources)
