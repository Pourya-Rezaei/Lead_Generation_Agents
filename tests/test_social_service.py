from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.registry import DisabledSourceError
from src.results import PlatformObservation, PlatformSearchResult, RunStatus
from src.social_service import SocialSearchRequest, SocialSearchService


def test_request_supports_explicit_profiles_or_keyword_mode():
    profiles = SocialSearchRequest(sources=("instagram",), profile_urls=("https://instagram.com/cafe",))
    keywords = SocialSearchRequest(sources=("instagram", "linkedin_jobs"), query="cafes", location="Tehran")
    assert profiles.mode == "profiles"
    assert keywords.mode == "keywords"
    with pytest.raises(ValidationError):
        SocialSearchRequest(sources=("instagram",), profile_urls=("http://instagram.com/cafe",))
    with pytest.raises(ValidationError):
        SocialSearchRequest(sources=("instagram",))


def test_disabled_sources_are_rejected_before_executor_runs():
    called = False

    def executor(request, selected):
        nonlocal called
        called = True
        return ()

    service = SocialSearchService(executor=executor)
    request = SocialSearchRequest(sources=("instagram",), query="cafe")
    with pytest.raises(DisabledSourceError, match="disabled"):
        service.search(request)
    assert called is False


def test_executor_receives_selected_capabilities_and_preserves_platform_results():
    expected = PlatformSearchResult(
        platform="instagram",
        status=RunStatus.SUCCEEDED,
        observations=[PlatformObservation(platform="instagram", profile_url="https://instagram.com/cafe", name="Cafe", source="instagram")],
        finished_at=datetime.now(UTC),
    )
    seen = {}

    def executor(request, selected):
        seen["mode"] = request.mode
        seen["platforms"] = tuple(item.platform for item in selected)
        return (expected,)

    # A test-only registry override models a future enabled connector without
    # activating a real Actor.
    from src.registry import ConnectorRegistry, SourceCapability

    registry = ConnectorRegistry()
    registry._capability_by_name["instagram"] = SourceCapability("instagram", "instagram", "test~actor", True, "test")
    service = SocialSearchService(registry=registry, executor=executor)
    result = service.search(SocialSearchRequest(sources=("instagram",), query="cafe"))
    assert result == (expected,)
    assert seen == {"mode": "keywords", "platforms": ("instagram",)}
