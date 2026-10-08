import sqlite3

from src.domain import Lead
from src.migrations import CURRENT_SCHEMA_VERSION, migrate
from src.quality.matching import match
from src.quality.normalization import canonicalize
from src.storage import LeadStore


def test_phase_a_migration_adds_stable_identity_and_observations(tmp_path):
    path = tmp_path / "quality.db"
    store = LeadStore(str(path))
    store.upsert([Lead(name="Cafe", source="places", source_id="p-1")])
    with sqlite3.connect(path) as db:
        assert migrate(db) == CURRENT_SCHEMA_VERSION
        lead_id = db.execute("SELECT lead_id FROM leads").fetchone()[0]
        assert lead_id
        assert {row[1] for row in db.execute("PRAGMA table_info(observations)")} >= {"lead_id", "fields"}
        assert migrate(db) == CURRENT_SCHEMA_VERSION


def test_lead_id_survives_payload_update(tmp_path):
    path = tmp_path / "quality.db"
    store = LeadStore(str(path))
    first = Lead(name="Cafe", source="places", source_id="p-1", phone="09120000000")
    store.upsert([first])
    with sqlite3.connect(path) as db:
        original = db.execute("SELECT lead_id FROM leads").fetchone()[0]
    store.upsert([first.model_copy(update={"phone": "09121111111"})])
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT lead_id FROM leads").fetchone()[0] == original


def test_matching_does_not_merge_same_domain_different_branches():
    first = canonicalize(Lead(name="Cafe A", address="North", website="https://example.test", source="places", source_id="a"))
    second = canonicalize(Lead(name="Cafe B", address="South", website="https://example.test", source="places", source_id="b"))
    decision = match(second, [first])
    assert decision.action == "separate"


def test_matching_same_source_id_is_confident():
    first = canonicalize(Lead(name="Cafe", source="places", source_id="a"))
    second = canonicalize(Lead(name="Cafe changed", source="places", source_id="a"))
    decision = match(second, [first])
    assert decision.action == "merge"
    assert decision.confidence == 1
