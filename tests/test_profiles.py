import sqlite3

import pytest

from src.enrichment import ProfileCandidate, match_profile_candidate
from src.migrations import migrate
from src.quality.profiles import ProfileRepository


def test_same_name_without_evidence_stays_unverified():
    lead = __import__('src.domain', fromlist=['Lead']).Lead(name="Cafe")
    candidate = ProfileCandidate("https://instagram.com/cafe", "Cafe", ("same-name",), 0.9, "probable")
    assert match_profile_candidate(lead, candidate).status == "unverified"


def test_first_party_link_and_consistent_evidence_can_confirm_business_profile():
    lead = __import__('src.domain', fromlist=['Lead']).Lead(name="Cafe")
    candidate = ProfileCandidate("https://instagram.com/cafe", "Cafe", (), 0.6, "unverified")
    result = match_profile_candidate(lead, candidate, first_party_link=True, consistent_business_evidence=True)
    assert result.status == "confirmed"
    assert "first-party-link" in result.evidence


def test_profile_repository_rejects_non_https_or_unknown_platform():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        db.execute("INSERT INTO leads(dedup_key, payload, lead_id) VALUES ('k', '{\"name\":\"Cafe\"}', 'lead-1')")
        repo = ProfileRepository(db)
        with pytest.raises(ValueError):
            repo.save("lead-1", "twitter", ProfileCandidate("https://x.example", "Cafe", (), 0.2, "unverified"))
        with pytest.raises(ValueError):
            repo.save("lead-1", "instagram", ProfileCandidate("http://instagram.com/cafe", "Cafe", (), 0.2, "unverified"))


def test_profile_review_is_explicit_and_audited():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        db.execute("INSERT INTO leads(dedup_key, payload, lead_id) VALUES ('k', '{\"name\":\"Cafe\"}', 'lead-1')")
        repo = ProfileRepository(db)
        candidate_id = repo.save("lead-1", "instagram", ProfileCandidate("https://instagram.com/cafe", "Cafe", ("same-official-domain",), 0.9, "probable"))
        repo.review(candidate_id, "confirmed", "official business link reviewed")
        assert db.execute("SELECT status, review_reason, reviewed_at FROM profile_candidates").fetchone()[0:2] == ("confirmed", "official business link reviewed")
        assert db.execute("SELECT old_status, new_status, reason FROM profile_review_audit").fetchone() == ("probable", "confirmed", "official business link reviewed")
