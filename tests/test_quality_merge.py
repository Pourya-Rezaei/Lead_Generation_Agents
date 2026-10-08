import sqlite3

from src.domain import Lead
from src.quality.merge import merge, undo
from src.storage import LeadStore


def test_merge_preserves_campaign_membership_and_can_undo(tmp_path):
    path = tmp_path / "merge.db"
    store = LeadStore(str(path))
    store.upsert([Lead(name="Source"), Lead(name="Target")])
    with sqlite3.connect(path) as db:
        ids = [row[0] for row in db.execute("SELECT lead_id FROM leads ORDER BY rowid")]
        merge_id = merge(db, ids[0], ids[1], "same verified business", 0.95)
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
        undo(db, merge_id)
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 2
        assert db.execute("SELECT status FROM lead_merge_audit").fetchone()[0] == "undone"
