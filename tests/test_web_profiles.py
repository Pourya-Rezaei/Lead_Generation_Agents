import sqlite3

from fastapi.testclient import TestClient

from src.config import Settings
from src.enrichment import ProfileCandidate
from src.migrations import migrate
from src.quality.profiles import ProfileRepository
from src.web.app import create_app


def test_web_profile_review(tmp_path):
    path = tmp_path / "profiles.db"
    app = create_app(Settings(database_path=str(path), _env_file=None))
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO leads(dedup_key, payload, lead_id) VALUES ('k', '{\"name\":\"Cafe\"}', 'lead-1')")
        ProfileRepository(db).save("lead-1", "instagram", ProfileCandidate("https://instagram.com/cafe", "Cafe", (), 0.8, "probable"))
        candidate_id = db.execute("SELECT candidate_id FROM profile_candidates").fetchone()[0]
    client = TestClient(app)
    assert client.get("/api/profile-candidates/lead-1").status_code == 200
    assert client.get("/profiles/lead-1").status_code == 200
    response = client.post(f"/api/profile-candidates/{candidate_id}/review", json={"status": "rejected", "reason": "no first-party link"})
    assert response.status_code == 200
