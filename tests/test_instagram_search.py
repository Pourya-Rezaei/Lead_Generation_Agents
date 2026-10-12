import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.config import Settings
from src.connectors.instagram_search import InstagramDiscoveryConnector
from src.errors import ApifyMalformedResponseError, ApifyStartOutcomeUnknown
from src.execution.cache import ExecutionCache
from src.execution.service import JobService
from src.search_requests import InstagramSearchRequest, validate_job_request
from src.service import SearchLeadsService
from src.storage import LeadStore
from src.web.app import create_app


def connector(items):
    client = Mock()
    client.start_actor.return_value = {"id": "ig-run", "defaultDatasetId": "dataset"}
    client.wait_for_run.return_value = {"status": "SUCCEEDED", "defaultDatasetId": "dataset"}
    client.iter_dataset_items.return_value = [[dict(item) if isinstance(item, dict) else item for item in items]]
    return InstagramDiscoveryConnector("dummy-token", client=client), client


def public(**fields):
    return {"username": "cafe", "fullName": "کافه", "isPrivate": False, **fields}


def test_standard_request_and_public_profile_allowlist():
    source, client = connector([public(biography="تماس 123 <script>bad</script>", externalUrl="https://example.org", followersCount=42, isBusinessAccount=False, email="hidden", posts=[{"owner": "hidden"}])])
    result = source.search("کافه تهران", "", 250)
    client.start_actor.assert_called_once_with("apify~instagram-search-scraper", {"search": "کافه تهران", "searchLimit": 250, "searchType": "user", "liveSearch": False, "enhanceUserSearchWithFacebookPage": False}, wait_for_finish=0)
    assert result.leads == []
    profile = result.projections[0]
    assert profile.source_url == "https://www.instagram.com/cafe/"
    assert profile.biography.startswith("تماس")
    assert profile.is_business_account is False
    assert profile.followers_count == 42
    assert "email" not in result.raw_records[0] and "posts" not in result.raw_records[0]
    assert not hasattr(profile, "phone")


@pytest.mark.parametrize("search", ["", "a,b", "الف،ب", "a，b"])
def test_single_phrase_validation(search):
    with pytest.raises(ValidationError):
        InstagramSearchRequest(search=search)


@pytest.mark.parametrize("limit", [0, 251, True, "10"])
def test_limit_validation(limit):
    with pytest.raises(ValidationError):
        InstagramSearchRequest(search="cafe", searchLimit=limit)


def test_privacy_duplicates_and_malformed_records():
    source, _ = connector([public(), public(), {"username": "private", "private": True, "biography": "secret"}, {"username": "unknown", "biography": "secret"}, {"location_id": "123"}])
    result = source.search("cafe")
    assert result.received_count == 5 and result.accepted_count == 1 and result.rejected_count == 4
    assert result.rejection_reasons == {"duplicate_profile": 1, "private_profile": 1, "privacy_unverified": 1, "unknown_schema": 1}
    assert "secret" not in result.model_dump_json()


def test_empty_and_contract_failure_are_distinct():
    source, _ = connector([])
    assert source.search("cafe").accepted_count == 0
    source, _ = connector([{"location_id": "123"}])
    with pytest.raises(ApifyMalformedResponseError):
        source.search("cafe")


def test_safe_external_links_and_name_fallback():
    source, _ = connector([public(fullName="", externalUrl="javascript:alert(1)")])
    profile = source.search("cafe").projections[0]
    assert profile.full_name == "cafe" and profile.external_links == []


def test_start_unknown_not_retried():
    source, client = connector([])
    client.start_actor.side_effect = ApifyStartOutcomeUnknown("unknown")
    with pytest.raises(ApifyStartOutcomeUnknown):
        source.search("cafe")
    assert client.start_actor.call_count == 1
    client.wait_for_run.assert_not_called()


def test_success_requires_dataset():
    source, client = connector([])
    client.wait_for_run.return_value = {"status": "SUCCEEDED"}
    with pytest.raises(ApifyMalformedResponseError):
        source.search("cafe")


def test_resume_does_not_start_actor():
    source, client = connector([public()])
    result = source.search_existing_run("known-run", "cafe", 10)
    assert result.accepted_count == 1
    client.start_actor.assert_not_called()


def test_round_trip_export_api_and_ui(tmp_path):
    store = LeadStore(str(tmp_path / "leads.db"))
    source, _ = connector([public(biography="<script>escaped</script>", externalUrl="https://example.org")])
    result = source.search("cafe")
    store.create_instagram_campaign("Instagram", campaign_id="general")
    store.persist_search_result("general", result, "cafe", "")
    assert store.instagram_profiles("ig-run")[0].biography == "<script>escaped</script>"
    for format in ("json", "csv"):
        target = tmp_path / ("profiles." + format)
        store.export_instagram("ig-run", str(target), format)
        assert "username" in target.read_text(encoding="utf-8-sig")
    settings = Settings(database_path=store.path)
    client = TestClient(create_app(settings=settings, store=store))
    for format in ("json", "csv"):
        response = client.get(f"/api/instagram-runs/ig-run/export/{format}")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
    response = client.get("/search?source=instagram")
    assert 'name="search"' in response.text and 'name="location"' not in response.text
    assert 'max="250"' in response.text and 'value="10"' in response.text
    response = client.post("/api/jobs", json={"source": "instagram", "search": "cafe", "campaign_id": "general", "idempotency_key": "ig"})
    assert response.status_code == 200
    for payload in ({"source": "instagram", "search": "a,b"}, {"source": "instagram", "search": "cafe", "location": "Tehran"}, {"source": "google_search", "query": "cafe", "location": "Tehran"}):
        assert client.post("/api/jobs", json={**payload, "idempotency_key": "bad"}).status_code == 422


@pytest.mark.parametrize("source", ["google_search", "linkedin_jobs", "youtube", "tiktok", "instagram_enrichment"])
def test_historical_source_cannot_execute(source, tmp_path):
    settings = Settings(database_path=str(tmp_path / "leads.db"), apify_api_token="dummy-token")
    service = SearchLeadsService(settings)
    with pytest.raises(ValueError):
        service.search("cafe", "Tehran", source)
    with pytest.raises(ValueError, match="unsupported_source"):
        JobService(settings.database_path).submit({"source": source, "query": "cafe", "location": "Tehran"}, "legacy")


def test_cache_contract_identity():
    request = {"source": "instagram", "search": "cafe", "searchLimit": 10}
    import hashlib
    legacy_key = hashlib.sha256(json.dumps({**request, "instagram_contract": "public-business-profile-v2"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert ExecutionCache.key(request) != legacy_key
    with pytest.raises(ValueError):
        validate_job_request({"sources": ["places", "instagram"], "query": "cafe", "location": "Tehran"})


def test_optional_malformed_counts_links_and_stable_id_dedup():
    source, _ = connector([public(id="123", followersCount="bad", externalUrls="bad"), public(id="123", username="other"), public(username="third", externalUrls=[{"url": "https://safe.example", "link_type": "external", "title": "discard"}, {"url": "javascript:alert(1)"}, {"url": "https://user:password@example.org"}, {"url": "https://facebook.com/page", "link_type": "facebook"}])])
    result = source.search("cafe")
    assert result.accepted_count == 2
    assert result.projections[0].followers_count is None
    assert result.projections[1].external_links == ["https://safe.example"]
    assert result.raw_records[1]["externalUrls"] == ["https://safe.example"]
    assert "facebook" not in result.model_dump_json()


def test_job_defaults_and_handler_execute_independent_request(tmp_path):
    from src.execution.handlers import places_handler
    settings = Settings(database_path=str(tmp_path / "handler.db"))
    LeadStore(settings.database_path).create_instagram_campaign("Instagram", campaign_id="ig")
    job = JobService(settings.database_path).submit({"source": "instagram", "search": " cafe ", "campaign_id": "ig"}, "defaults")
    assert job.request["searchLimit"] == 10
    assert job.request["search"] == "cafe"
    service = Mock(spec=SearchLeadsService)
    source, _ = connector([public()])
    service.search.return_value = source.search("cafe")
    service.last_persisted_refs = {"run_id": "ig-run", "raw_record_refs": [{"run_id": "ig-run", "record_index": 0}], "observation_ids": []}
    result = places_handler(service)(job.request)
    service.search.assert_called_once_with("cafe", "", "instagram", 10, "ig")
    assert result["accepted_count"] == 1


def test_dataset_pagination_is_bounded_and_isolates_bad_records():
    source, client = connector([])
    client.iter_dataset_items.return_value = [[public()], [None, public(username="second")]]
    result = source.search("cafe", "", 10)
    client.iter_dataset_items.assert_called_once_with("dataset", max_items=10)
    assert result.received_count == 3 and result.accepted_count == 2
    assert result.rejection_reasons == {"unknown_schema": 1}


def test_independent_instagram_cli_requests(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    import src.cli as cli
    runner = CliRunner()
    source, _ = connector([public()])
    service = Mock(spec=SearchLeadsService)
    service.search.return_value = source.search("cafe")
    monkeypatch.setattr(cli, "SearchLeadsService", lambda settings: service)
    response = runner.invoke(cli.app, ["instagram-search", "cafe", "--campaign", "ig"])
    assert response.exit_code == 0
    service.search.assert_called_once_with("cafe", "", "instagram", 10, "ig")
    assert json.loads(response.stdout)["accepted_count"] == 1
    assert runner.invoke(cli.app, ["instagram-search", "a,b"]).exit_code != 0
    path = str(tmp_path / "cli.db")
    LeadStore(path).create_instagram_campaign("Instagram", campaign_id="ig")
    response = runner.invoke(cli.app, ["jobs", "submit-instagram", "cafe", "--campaign", "ig", "--idempotency-key", "cli-instagram", "--db", path])
    assert response.exit_code == 0
    job = JobService(path).recent()[0]
    assert job.request["searchLimit"] == 10 and "location" not in job.request
