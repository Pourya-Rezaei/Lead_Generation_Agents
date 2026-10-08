import sqlite3

from src.enrichment import ProfileCandidate
from src.migrations import migrate
from src.quality.profiles import ProfileRepository


def test_profile_review_is_explicit_and_audited():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        db.execute("INSERT INTO leads(dedup_key, payload, lead_id) VALUES ('k', '{\"name\":\"Cafe\"}', 'lead-1')")
        repo = ProfileRepository(db)
        candidate_id = repo.save("lead-1", "instagram", ProfileCandidate("https://instagram.com/cafe", "Cafe", ("same-official-domain",), 0.9, "probable"))
        repo.review(candidate_id, "confirmed", "official business link reviewed")
        assert db.execute("SELECT status, review_reason, reviewed_at FROM profile_candidates").fetchone()[0:2] == ("confirmed", "official business link reviewed")
