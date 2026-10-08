import pytest
from pydantic import ValidationError

import sqlite3
from datetime import UTC, datetime

from src.domain import Campaign, Lead
from src.errors import (
    CampaignNotFoundError,
    DuplicateCampaignIdError,
    DuplicateCampaignNameError,
)
from src.migrations import migrate
from src.repositories import CampaignRepository, LeadRepository, RunRepository
from src.results import RunStatus, SearchResult
from src.storage import LeadStore


def test_campaign_validates_and_normalizes_name():
    campaign = Campaign(campaign_id="general", name="  جست‌وجوهای عمومی  ")
    assert campaign.campaign_id == "general"
    assert campaign.name == "جست‌وجوهای عمومی"
    assert campaign.description is None
    assert campaign.is_default is False


@pytest.mark.parametrize("name", ["", "   ", None])
def test_campaign_rejects_empty_name(name):
    with pytest.raises(ValidationError):
        Campaign(campaign_id="x", name=name)


def test_campaign_rejects_empty_id():
    with pytest.raises(ValidationError):
        Campaign(campaign_id="  ", name="Campaign")


def campaign_db():
    connection = sqlite3.connect(":memory:")
    migrate(connection)
    return connection


def test_campaign_repository_create_get_list_and_default():
    connection = campaign_db()
    repository = CampaignRepository(connection)
    created = repository.create("  North   Side ", "  test  ", "north-1")
    assert created.campaign_id == "north-1"
    assert created.name == "North Side"
    assert created.description == "test"
    assert repository.get("north-1") == created
    assert repository.get("unknown") is None
    assert repository.get_default().campaign_id == "general"
    assert [item.campaign_id for item in repository.list()] == ["general", "north-1"]


def test_campaign_repository_automatic_id_is_deterministic_and_collision_safe():
    repository = CampaignRepository(campaign_db())
    assert repository.create("North Side").campaign_id == "north-side"
    with pytest.raises(DuplicateCampaignNameError, match="North Side"):
        repository.create(" North   Side ")
    with pytest.raises(DuplicateCampaignIdError, match="north-side"):
        repository.create("Different Name", campaign_id="north-side")


def test_campaign_repository_stats_and_missing_campaign():
    connection = campaign_db()
    repository = CampaignRepository(connection)
    with pytest.raises(CampaignNotFoundError, match="missing"):
        repository.stats("missing")
    repository.create("One", campaign_id="one")
    repository.create("Two", campaign_id="two")
    connection.execute(
        "INSERT INTO runs(run_id, status, payload, started_at, campaign_id) "
        "VALUES ('one-run', 'running', '{}', '2025-01-01T00:00:00+00:00', 'one')"
    )
    assert repository.stats("one").lead_count == 0
    assert repository.stats("one").run_count == 1


def test_lead_can_belong_to_multiple_campaigns_and_membership_upsert_is_idempotent():
    connection = campaign_db()
    campaigns = CampaignRepository(connection)
    campaigns.create("One", campaign_id="one")
    campaigns.create("Two", campaign_id="two")
    lead = Lead(name="Cafe", address="Main Street")
    LeadRepository(connection).upsert([lead])
    first = datetime(2025, 1, 1, tzinfo=UTC)
    later = datetime(2025, 1, 3, tzinfo=UTC)
    campaigns.add_lead("one", lead.dedup_key(), seen_at=first)
    campaigns.add_lead("one", lead.dedup_key(), seen_at=later)
    campaigns.add_lead("two", lead.dedup_key(), seen_at=first)
    assert connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM campaign_leads").fetchone()[0] == 2
    assert connection.execute(
        "SELECT first_seen_at, last_seen_at FROM campaign_leads WHERE campaign_id='one'"
    ).fetchone() == (first.isoformat(), later.isoformat())


def _search_result(*, leads=None, status=RunStatus.SUCCEEDED, raw_records=None):
    return SearchResult(
        source="fake",
        run_id="remote-run",
        dataset_id="dataset-1",
        status=status,
        partial=status is RunStatus.PARTIAL,
        leads=(leads if leads is not None else [Lead(name="Cafe One", address="Main"), Lead(name="Cafe Two", address="Broadway")]),
        raw_records=(raw_records if raw_records is not None else [{"title": "Cafe One", "private": "excluded"}]),
        started_at=datetime(2025, 1, 1, tzinfo=UTC),
        finished_at=datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
    )


def test_persist_search_result_scopes_run_leads_memberships_and_raw_records(tmp_path):
    store = LeadStore(str(tmp_path / "campaign.db"))
    with store._connect() as db:
        CampaignRepository(db).create("Chosen", campaign_id="chosen")
    store.persist_search_result("chosen", _search_result(), "coffee", "North")
    with store._connect() as db:
        assert db.execute("SELECT campaign_id FROM runs WHERE run_id='remote-run'").fetchone() == ("chosen",)
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM campaign_leads WHERE campaign_id='chosen'").fetchone()[0] == 2
        assert db.execute("SELECT campaign_id FROM campaign_leads LIMIT 1").fetchone() == ("chosen",)
        assert db.execute("SELECT payload FROM raw_records").fetchone()[0] == '{"title": "Cafe One"}'


def test_run_creation_requires_campaign_and_compatibility_uses_default(tmp_path):
    connection = campaign_db()
    runs = RunRepository(connection)
    with pytest.raises(ValueError, match="campaign_id is required"):
        runs.start("missing-campaign", campaign_id=None)
    store = LeadStore(str(tmp_path / "campaign.db"))
    store.record_run({"run_id": "legacy-run", "status": "succeeded"})
    with store._connect() as db:
        assert db.execute("SELECT campaign_id FROM runs WHERE run_id='legacy-run'").fetchone() == ("general",)


def test_persist_search_result_repeats_and_shares_leads_across_campaigns(tmp_path):
    store = LeadStore(str(tmp_path / "campaign.db"))
    with store._connect() as db:
        campaigns = CampaignRepository(db)
        campaigns.create("One", campaign_id="one")
        campaigns.create("Two", campaign_id="two")
    result = _search_result(leads=[Lead(name="Shared Cafe")], raw_records=[{"name": "Shared Cafe"}])
    store.persist_search_result("one", result, "coffee", "North")
    with store._connect() as db:
        first_seen = db.execute("SELECT first_seen_at FROM campaign_leads WHERE campaign_id='one'").fetchone()[0]
    store.persist_search_result("one", result, "coffee", "North")
    cross_campaign_result = result.model_copy(update={"run_id": "remote-run-second"})
    store.persist_search_result("two", cross_campaign_result, "coffee", "South")
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM campaign_leads").fetchone()[0] == 2
        membership = db.execute("SELECT first_seen_at, last_seen_at FROM campaign_leads WHERE campaign_id='one'").fetchone()
        assert membership[0] == first_seen
        assert membership[1] >= membership[0]
        assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
        assert {row[0] for row in db.execute("SELECT campaign_id FROM runs")} == {"one", "two"}


def test_persist_search_result_rejects_cross_campaign_run_id_reuse(tmp_path):
    store = LeadStore(str(tmp_path / "campaign.db"))
    with store._connect() as db:
        campaigns = CampaignRepository(db)
        campaigns.create("One", campaign_id="one")
        campaigns.create("Two", campaign_id="two")
    result = _search_result(leads=[Lead(name="Shared Cafe")])
    store.persist_search_result("one", result, "coffee", "North")
    with pytest.raises(ValueError, match="already belongs to campaign 'one'"):
        store.persist_search_result("two", result, "coffee", "South")
    with store._connect() as db:
        assert db.execute("SELECT campaign_id FROM runs WHERE run_id='remote-run'").fetchone() == ("one",)
        assert db.execute("SELECT COUNT(*) FROM campaign_leads WHERE campaign_id='two'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1


def test_persist_search_result_rolls_back_all_writes_when_raw_insert_fails(tmp_path, monkeypatch):
    store = LeadStore(str(tmp_path / "campaign.db"))
    with store._connect() as db:
        CampaignRepository(db).create("Chosen", campaign_id="chosen")
    def fail_raw(*args, **kwargs):
        raise RuntimeError("injected raw insert failure")
    monkeypatch.setattr("src.storage.RawRecordRepository.save_allowlisted", fail_raw)
    with pytest.raises(RuntimeError, match="injected raw"):
        store.persist_search_result("chosen", _search_result(), "coffee", "North")
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM campaign_leads").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 0


def test_failed_search_result_persists_only_failed_campaign_run(tmp_path):
    store = LeadStore(str(tmp_path / "campaign.db"))
    with store._connect() as db:
        CampaignRepository(db).create("Chosen", campaign_id="chosen")
    result = _search_result(leads=[], status=RunStatus.FAILED, raw_records=[{"name": "must not save"}])
    store.persist_search_result("chosen", result, "coffee", "North")
    with store._connect() as db:
        assert db.execute("SELECT status, campaign_id FROM runs").fetchone() == ("failed", "chosen")
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM campaign_leads").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 0


def test_campaign_membership_enforces_campaign_and_lead_foreign_keys():
    connection = campaign_db()
    repository = CampaignRepository(connection)
    with pytest.raises(sqlite3.IntegrityError):
        repository.add_lead("missing", "lead")
    repository.create("Existing", campaign_id="existing")
    with pytest.raises(sqlite3.IntegrityError):
        repository.add_lead("existing", "missing-lead")
