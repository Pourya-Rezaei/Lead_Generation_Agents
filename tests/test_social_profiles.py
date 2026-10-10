import pytest
from pydantic import ValidationError
from src.connectors.social_profiles import (
    INSTAGRAM,
    TIKTOK,
    LINKEDIN_JOBS,
    InstagramProfileInput,
    TikTokProfileInput,
    LinkedInJobsInput,
    normalize_contact_links,
)
from src.results import PlatformObservation, PlatformSearchResult, RunStatus


def test_social_connectors_are_disabled_by_default():
    assert not INSTAGRAM.enabled and not TIKTOK.enabled and not LINKEDIN_JOBS.enabled
    for connector in (INSTAGRAM, TIKTOK):
        assert connector.contract.contract_status == "unverified"
        assert connector.contract.pricing_status == "not_verified"
        assert connector.contract.execution_policy == "disabled_no_paid_calls"
        assert connector.contract.gate_report.status == "blocked"
        assert connector.contract.gate_report.failed_gates == ("schema",)
    assert LINKEDIN_JOBS.contract.gate_report.passed
    assert LINKEDIN_JOBS.contract.execution_policy == "enabled_after_explicit_approval"


def test_actor_metadata_has_official_pricing_references_without_authorizing_calls():
    expected = {
        INSTAGRAM: ("https://apify.com/apify/instagram-scraper", "$1.50 / 1,000 results"),
        TIKTOK: ("https://apify.com/clockworks/tiktok-scraper", "$1.70 / 1,000 results"),
        LINKEDIN_JOBS: ("https://apify.com/dataji/apify-linkdin-jobs", "$0.0008 / job result"),
    }
    for connector, (url, pricing) in expected.items():
        assert connector.contract.docs_url == url
        assert connector.contract.pricing_summary == pricing
        if connector is LINKEDIN_JOBS:
            assert connector.contract.schema_verified is True
            assert connector.contract.gate_report.passed is True
        else:
            assert connector.contract.schema_verified is False
            assert connector.contract.gate_report.passed is False


def test_actor_request_is_safe_preview_and_never_executable():
    request = InstagramProfileInput(profile_url="https://instagram.com/cafe", query="cafe", location="Tehran")
    preview = INSTAGRAM.build_request(request)
    assert preview.actor == "apify~instagram-scraper"
    assert preview.executable is False
    assert dict(preview.payload) == {"profile_url": "https://instagram.com/cafe", "query": "cafe", "location": "Tehran"}
    assert INSTAGRAM.execute(request)[1] == "disabled_actor_contract_unverified"


@pytest.mark.parametrize("raw, expected", [("SUCCEEDED", "succeeded"), ("FAILED", "failed"), (None, "malformed_status"), ("wat", "unknown_status")])
def test_actor_status_is_stable(raw, expected):
    assert INSTAGRAM.status(raw) == expected


def test_mapping_allows_only_public_https_profile_fields():
    result = INSTAGRAM.map_public_profile({"profileUrl": "https://instagram.com/cafe", "username": "cafe", "bio": "business", "website": "https://cafe.example", "email": "private@example"})
    assert result and result.status == "unverified"
    assert result.title == "cafe"
    assert not hasattr(result, "email")


def test_invalid_or_personal_unstructured_result_is_ignored():
    assert TIKTOK.map_public_profile({"url": "http://tiktok.com/cafe", "username": "cafe"}) is None
    assert LINKEDIN_JOBS.map_public_profile({"jobUrl": "https://linkedin.com/jobs/view/1"}) is None


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
    observation = PlatformObservation(platform="linkedin_jobs", profile_url="https://linkedin.com/jobs/view/1", name="Cafe", metadata={"company": "Cafe"}, contact_links=("https://wa.me/1",), source="linkedin_jobs")
    result = PlatformSearchResult(platform="linkedin_jobs", status=RunStatus.SUCCEEDED, observations=[observation])
    assert result.observations[0].metadata["company"] == "Cafe"


def test_platform_inputs_are_independent_and_https_contract_gated():
    assert InstagramProfileInput(profile_url="https://instagram.com/cafe").platform == "instagram"
    linkedin = LinkedInJobsInput(keywords="software engineer", location="Berlin", max_results=5)
    assert linkedin.max_results == 5
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
