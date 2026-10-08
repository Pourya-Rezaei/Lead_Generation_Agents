from src.domain import Lead, normalize, score
from src.storage import LeadStore

def test_normalize_score_and_roundtrip(tmp_path):
    lead = normalize(Lead(name="  Acme   Co ", address=" Main  St ", phone="123", website="https://acme.test/", rating=5, reviews=100))
    assert lead.name == "Acme Co" and score(lead) == 100
    store = LeadStore(str(tmp_path / "x.db")); store.upsert([lead])
    assert store.all()[0].name == "Acme Co"

def test_export(tmp_path):
    store = LeadStore(str(tmp_path / "x.db")); store.upsert([Lead(name="A")])
    store.export(str(tmp_path / "nested" / "out.json"), "json"); store.export(str(tmp_path / "nested" / "out.csv"), "csv")
    assert (tmp_path / "nested" / "out.json").exists() and (tmp_path / "nested" / "out.csv").exists()


def test_run_metadata_and_raw_records(tmp_path):
    store = LeadStore(str(tmp_path / "x.db"))
    store.record_run({"run_id": "run-1", "dataset_id": "ds-1", "status": "SUCCEEDED"}, [{"title": "Cafe"}])
    with __import__("sqlite3").connect(tmp_path / "x.db") as db:
        assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 1
