import pytest

from src.registry import ConnectorRegistry, DisabledSourceError
from src.service import SearchLeadsService


def test_capabilities_describe_platform_and_disabled_actors_without_running_them():
    capabilities = {item.name: item for item in ConnectorRegistry().capabilities()}

    assert capabilities["places"].enabled is True
    assert capabilities["places"].platform == "google_maps"
    assert capabilities["instagram"].enabled is False
    assert capabilities["instagram"].actor == "apify~instagram-scraper"


def test_select_sources_validates_all_sources_and_preserves_platform_specific_results():
    selected = ConnectorRegistry().select_sources(["places", "google_search"])

    assert [item.name for item in selected] == ["places", "google_search"]
    assert [item.platform for item in selected] == ["google_maps", "google_search"]


def test_disabled_social_source_fails_safely_before_connector_creation():
    registry = ConnectorRegistry()

    with pytest.raises(DisabledSourceError, match="source 'instagram' is disabled"):
        registry.select_sources(["places", "instagram"])


def test_service_exposes_backward_compatible_capability_selection(tmp_path):
    from src.config import Settings

    service = SearchLeadsService(Settings(database_path=str(tmp_path / "leads.db")))

    assert service.select_sources(("google_search",))[0].actor == "apify~google-search-scraper"
    assert {item.name for item in service.source_capabilities()} >= {"places", "google_search", "instagram"}
