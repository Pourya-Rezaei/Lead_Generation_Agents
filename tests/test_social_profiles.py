import pytest
from pydantic import ValidationError
from src.connectors.social_profiles import (
    INSTAGRAM,
    TIKTOK,
    YOUTUBE,
    InstagramProfileInput,
    TikTokProfileInput,
    YouTubeProfileInput,
    normalize_contact_links,
)
from src.results import PlatformObservation, PlatformSearchResult, RunStatus


def test_social_connectors_are_disabled_by_default():
    assert not INSTAGRAM.enabled and not TIKTOK.enabled and not YOUTUBE.enabled


def test_mapping_allows_only_public_https_profile_fields():
    result = INSTAGRAM.map_public_profile({"profileUrl": "https://instagram.com/cafe", "username": "cafe", "bio": "business", "website": "https://cafe.example", "email": "private@example"})
    assert result and result.status == "unverified"
    assert result.title == "cafe"
    assert not hasattr(result, "email")


def test_invalid_or_personal_unstructured_result_is_ignored():
    assert TIKTOK.map_public_profile({"url": "http://tiktok.com/cafe", "username": "cafe"}) is None
    assert YOUTUBE.map_public_profile({"profileUrl": "https://youtube.com/cafe"}) is None


def test_mapping_normalizes_shared_fields_and_allowlists_contacts():
    result = INSTAGRAM.map_public_profile({
        "profileUrl": "https://WWW.Instagram.com/cafe/", "username": "  cafe   تهران ",
        "bio": "  قهوه\u200f و کیک ", "location": " تهران ",
        "contactLinks": ["https://wa.me/989121234567", "http://evil.example", "mailto:owner@example.test"],
        "followers": 1200, "ownerName": "must not be retained",
    })
    assert result is not None
    assert result.url == "https://instagram.com/cafe"
    assert result.title == "cafe تهران"
    assert result.bio == "قهوه و کیک"
    assert result.location == "تهران"
    assert result.contact_links == ("https://wa.me/989121234567",)
    assert dict(result.metadata) == {"followers": "1200"}


def test_contact_allowlist_and_platform_result_contract():
    assert normalize_contact_links(["https://t.me/cafe", "https://example.com/contact", "https://tiktok.com/@cafe"], "tiktok") == ("https://t.me/cafe", "https://tiktok.com/@cafe")
    observation = PlatformObservation(platform="youtube", profile_url="https://youtube.com/@cafe", name="Cafe", metadata={"subscribers": 42}, contact_links=("https://wa.me/1",), source="youtube")
    result = PlatformSearchResult(platform="youtube", status=RunStatus.SUCCEEDED, observations=[observation])
    assert result.observations[0].metadata["subscribers"] == 42


def test_platform_inputs_are_independent_and_https_contract_gated():
    assert InstagramProfileInput(profile_url="https://instagram.com/cafe").platform == "instagram"
    assert YouTubeProfileInput(profile_url="https://youtube.com/@cafe").platform == "youtube"
    assert TikTokProfileInput(profile_url="https://tiktok.com/@cafe").platform == "tiktok"
    with pytest.raises(ValidationError):
        InstagramProfileInput(profile_url="http://instagram.com/cafe")
    with pytest.raises(ValidationError):
        TikTokProfileInput(profile_url="https://tiktok.com/@cafe", audience={})


@pytest.mark.parametrize("item", [None, [], {"profileUrl": "not-a-url", "username": "x"}])
def test_safe_mapping_classifies_malformed_records(item):
    observation, error = INSTAGRAM.map_public_profile_safe(item)
    assert observation is None
    assert error == "malformed_record"


def test_safe_mapping_rejects_private_and_drops_commenter_audience_data():
    observation, error = INSTAGRAM.map_public_profile_safe({"profileUrl": "https://instagram.com/cafe", "username": "cafe", "private": True})
    assert observation is None and error == "private_profile"
    observation, error = INSTAGRAM.map_public_profile_safe({
        "profileUrl": "https://instagram.com/cafe", "username": "cafe",
        "commenters": [{"username": "person"}], "audience": {"age": 20}, "followers": 10,
    })
    assert error is None and observation is not None
    assert dict(observation.metadata) == {"followers": "10"}
