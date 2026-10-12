import csv
import io
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.exporters import render_instagram_profiles
from src.migrations import MIGRATIONS, migrate
from src.results import RunStatus, SearchResult
from src.source_contracts import InstagramRecord
from src.storage import LeadStore
from src.web.app import create_app


def profile(username="cafe", source_id="123", **fields):
    return InstagramRecord(username=username, source_id=source_id, source_url=f"https://www.instagram.com/{username}/", private=False, is_business_account=fields.pop("is_business_account", True), **fields)


def result(run_id, day=1, profiles=(), status=RunStatus.SUCCEEDED):
    at = datetime(2026, 10, day, tzinfo=timezone.utc)
    return SearchResult(source="instagram", run_id=run_id, projections=list(profiles), status=status, started_at=at, finished_at=at)


@pytest.fixture
def store(tmp_path):
    store = LeadStore(str(tmp_path / "campaigns.db"))
    store.create_instagram_campaign("کافه‌ها", campaign_id="ig")
    return store


def test_existing_v17_database_migration_does_not_import_old_runs(tmp_path):
    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as db:
        for migration in MIGRATIONS[:-1]:
            migration(db)
        db.execute("INSERT INTO schema_metadata(key,value) VALUES('schema_version','17')")
        db.execute("INSERT INTO runs(run_id,payload,status,campaign_id,started_at) VALUES('old', ?, 'succeeded', 'general', '2026-10-01')", (json.dumps({"source": "instagram", "projections": [profile().model_dump()]}),))
        assert migrate(db) == 18
        assert migrate(db) == 18
        assert db.execute("SELECT COUNT(*) FROM instagram_campaign_runs").fetchone()[0] == 0
        assert db.execute("SELECT payload FROM runs WHERE run_id='old'").fetchone()
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_campaigns_are_separate_and_selection_is_required(store):
    assert [c.campaign_id for c in store.campaigns()] == ["general"]
    assert store.get_campaign("ig") is None
    with pytest.raises(ValueError):
        store.persist_search_result("general", result("invalid", profiles=[profile()]), "cafe", "")
    assert store.instagram_campaign_runs("ig") == []
    assert store.all() == []


def test_latest_valid_profile_and_run_history_and_replay(store):
    store.persist_search_result("ig", result("new", 3, [profile("renamed", biography="جدید")]), "cafe", "")
    store.persist_search_result("ig", result("old", 1, [profile(biography="قدیم")]), "cafe", "")
    store.persist_search_result("ig", result("new", 4, [profile(biography="replay")]), "cafe", "")
    store.persist_search_result("ig", result("empty", 5), "cafe", "")
    store.persist_search_result("ig", result("failed", 6, status=RunStatus.FAILED), "cafe", "")
    profiles = store.instagram_campaign_profiles("ig")
    assert len(profiles) == 1
    assert profiles[0].username == "renamed" and profiles[0].biography == "جدید"
    assert len(store.instagram_campaign_runs("ig")) == 4
    assert store.campaign_stats("general").run_count == 0
    assert store.all() == []


def test_username_fallback_and_campaign_isolation(store):
    store.create_instagram_campaign("Other", campaign_id="other")
    store.persist_search_result("ig", result("a", profiles=[profile(source_id=None)]), "cafe", "")
    store.persist_search_result("ig", result("b", 2, [profile(biography="latest")]), "cafe", "")
    assert len(store.instagram_campaign_profiles("ig")) == 1
    assert store.instagram_campaign_profiles("other") == []
    with pytest.raises(ValueError):
        store.persist_search_result("other", result("a"), "cafe", "")


def test_transaction_rolls_back_invalid_projection(store):
    from src.instagram_campaigns import InstagramCampaignRepository
    with pytest.raises(ValueError):
        with store._connect() as db:
            InstagramCampaignRepository(db).persist("ig", "invalid", {"started_at": "2026-10-01", "status": "succeeded", "projections": [{"username": "invalid"}]})
    assert store.instagram_campaign_runs("ig") == []


def test_exports_unicode_escaping_and_formula_mitigation(store):
    p = profile(full_name="=SUM(1,2)", biography='متن، "نقل قول"\nخط دوم', external_links=["javascript:alert(1)", "https://safe.example"])
    content = render_instagram_profiles([p], "json")
    assert "متن" in content.decode()
    assert json.loads(content)[0]["external_links"] == ["https://safe.example"]
    content = render_instagram_profiles([p], "csv")
    assert content.startswith(b"\xef\xbb\xbf")
    row = next(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    assert row["full_name"].startswith("'=SUM")
    assert row["biography"] == p.biography
    assert json.loads(row["external_links"]) == ["https://safe.example"]


def test_web_selection_detail_export_and_invalid_campaign(store):
    client = TestClient(create_app(Settings(database_path=store.path), store=store))
    response = client.get("/search?source=instagram")
    assert 'value="ig"' in response.text and 'value="general"' not in response.text
    for campaign in (None, "general", "missing"):
        response = client.post("/api/jobs", json={"source": "instagram", "search": "cafe", "campaign_id": campaign, "idempotency_key": "invalid"})
        assert response.status_code == 422
    response = client.post("/instagram-campaigns", data={"campaign_id": "new", "name": "جدید"}, follow_redirects=False)
    assert response.status_code == 303
    assert "جدید" in client.get("/instagram-campaigns").text
    store.persist_search_result("ig", result("run", profiles=[profile(biography="<script>unsafe</script>")]), "cafe", "")
    response = client.get("/instagram-campaigns/ig")
    assert "&lt;script&gt;" in response.text and "<script>unsafe" not in response.text
    for format in ("json", "csv"):
        response = client.get(f"/instagram-campaigns/ig/export?format={format}")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert ("application/json" if format == "json" else "text/csv") in response.headers["content-type"]
    assert client.get("/instagram-campaigns/missing").status_code == 404
    assert client.get("/campaigns/ig").status_code == 404


def test_stable_ids_are_not_merged_when_username_is_reused(store):
    store.persist_search_result("ig", result("a", profiles=[profile(source_id="first")]), "cafe", "")
    store.persist_search_result("ig", result("b", 2, [profile(source_id="second")]), "cafe", "")
    assert {p.source_id for p in store.instagram_campaign_profiles("ig")} == {"first", "second"}


def test_latest_username_only_observation_updates_stable_identity(store):
    store.persist_search_result("ig", result("a", profiles=[profile()]), "cafe", "")
    store.persist_search_result("ig", result("b", 2, [profile(source_id=None, biography="جدید")]), "cafe", "")
    profiles = store.instagram_campaign_profiles("ig")
    assert len(profiles) == 1 and profiles[0].biography == "جدید"


def test_empty_csv_and_whitespace_formula_protection():
    assert "username" in render_instagram_profiles([], "csv").decode("utf-8-sig")
    row = next(csv.DictReader(io.StringIO(render_instagram_profiles([profile(biography="  =SUM(1,2)")], "csv").decode("utf-8-sig"))))
    assert row["biography"].startswith("'  =")


def test_api_creation_and_campaign_cache_identity(store):
    from src.execution.cache import ExecutionCache
    client = TestClient(create_app(Settings(database_path=store.path), store=store))
    response = client.post("/api/instagram-campaigns", json={"name": "جدید", "campaign_id": "api"})
    assert response.status_code == 201
    assert client.post("/api/instagram-campaigns", json={"name": "duplicate", "campaign_id": "api"}).status_code == 422
    assert len(client.get("/api/instagram-campaigns").json()) == 2
    request = {"source": "instagram", "search": "cafe", "campaign_id": "ig"}
    assert ExecutionCache.key(request) != ExecutionCache.key({**request, "campaign_id": "api"})


def test_cache_replay_validates_instagram_run_and_campaign(store):
    from src.execution.cache import ExecutionCache
    from src.execution.worker import JobWorker
    store.persist_search_result("ig", result("run"), "cafe", "")
    refs = {"source": "instagram", "run_id": "run", "campaign_id": "ig", "lead_ids": [], "raw_record_refs": [], "observation_ids": []}
    assert ExecutionCache.is_replayable({"persisted_refs": refs})
    with store._connect() as db:
        worker = JobWorker(db, "offline")
        assert worker._replay_cached_refs(refs)
        assert not worker._replay_cached_refs({**refs, "campaign_id": "general"})
        assert not worker._replay_cached_refs({**refs, "run_id": "missing"})


def test_cli_campaign_creation_and_export(tmp_path):
    from typer.testing import CliRunner
    from src.cli import app
    runner = CliRunner()
    db = str(tmp_path / "cli.db")
    response = runner.invoke(app, ["instagram-campaign", "create", "کافه", "--campaign", "ig", "--db", db])
    assert response.exit_code == 0
    assert json.loads(response.stdout)["campaign_id"] == "ig"
    output = str(tmp_path / "profiles.json")
    response = runner.invoke(app, ["instagram-campaign", "export", "ig", output, "--db", db])
    assert response.exit_code == 0
    from pathlib import Path
    assert json.loads(Path(output).read_text()) == []


def test_same_timestamp_run_id_tie_break_and_optional_business_status(store):
    store.persist_search_result("ig", result("z", profiles=[profile(is_business_account=None, biography="latest")]), "cafe", "")
    store.persist_search_result("ig", result("a", profiles=[profile(biography="older")]), "cafe", "")
    assert store.instagram_campaign_profiles("ig")[0].biography == "latest"


def test_safe_failure_journaling_preserves_existing_profiles(store):
    store.persist_search_result("ig", result("good", profiles=[profile()]), "cafe", "")
    run_id = store.record_failed_search("ig", "cafe", "", "instagram", "ApifyError", "Provider failed safely", started_at=datetime.now(timezone.utc), failure_metadata={"provider_run_id": "known", "token": "never-persist"})
    assert len(store.instagram_campaign_profiles("ig")) == 1
    assert len(store.instagram_campaign_runs("ig")) == 2
    with store._connect() as db:
        payload = db.execute("SELECT payload FROM instagram_campaign_runs WHERE run_id=?", (run_id,)).fetchone()[0]
        assert "never-persist" not in payload
        assert json.loads(payload)["provider_run_id"] == "known"
