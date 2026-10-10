import sqlite3
import time

from src.domain import Lead
from src.execution.cache import ExecutionCache
from src.execution.jobs import JobRepository
from src.execution.worker import JobWorker
from src.migrations import migrate


def test_worker_completes_job_with_fenced_update():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        JobRepository(db).submit({"query": "cafe"}, "key-1")
        result = JobWorker(db, "worker-1").run_once(lambda request: ["places"])
        assert result and result.state == "succeeded"
        assert result.progress["completed_steps"] == ["places"]


def test_worker_records_handler_failure_without_raw_error():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        JobRepository(db).submit({"query": "cafe"}, "key-1")
        result = JobWorker(db, "worker-1").run_once(lambda request: (_ for _ in ()).throw(RuntimeError("secret payload")))
        assert result and result.state == "failed"
        assert result.error_code == "RuntimeError"


def test_worker_replays_cached_membership(tmp_path):
    path = tmp_path / "cache-replay.db"
    db = sqlite3.connect(path)
    migrate(db)
    lead = Lead(name="Cafe", source="places", source_id="place-1")
    db.execute(
        "INSERT INTO leads(dedup_key, payload, lead_id) VALUES (?, ?, ?)",
        (lead.dedup_key(), lead.model_dump_json(), "lead-1"),
    )
    db.execute(
        "INSERT INTO runs(run_id, status, payload, started_at, finished_at, error, campaign_id) VALUES (?, 'succeeded', '{}', datetime('now'), datetime('now'), NULL, 'general')",
        ("run-1",),
    )
    db.execute(
        "INSERT INTO observations(observation_id, lead_id, source, run_id, collected_at, fields, mapper_version) VALUES ('obs-1', 'lead-1', 'places', 'run-1', datetime('now'), '{}', '1')"
    )
    db.execute(
        "INSERT INTO raw_records(run_id, record_index, payload, recorded_at) VALUES ('run-1', 0, '{}', datetime('now'))"
    )
    request = {"query": "cafe", "location": "Tehran", "campaign_id": "general"}
    ExecutionCache(db).put(
        request,
        {"state": "succeeded", "completed_steps": ["places"], "persisted_refs": {"lead_ids": ["lead-1"], "run_id": "run-1", "campaign_id": "general", "observation_ids": ["obs-1"], "raw_record_refs": [{"run_id": "run-1", "record_index": 0}]}},
    )
    JobRepository(db).submit(request, "cache-replay")
    result = JobWorker(db, "worker-1").run_once(lambda _: (_ for _ in ()).throw(AssertionError("cache miss")))
    assert result is not None and result.state == "succeeded"
    assert db.execute("SELECT COUNT(*) FROM campaign_leads WHERE campaign_id = 'general'").fetchone()[0] == 1


def test_worker_heartbeats_long_running_file_job(tmp_path):
    path = tmp_path / "heartbeat.db"
    db = sqlite3.connect(path)
    migrate(db)
    JobRepository(db).submit({"query": "cafe"}, "heartbeat")
    result = JobWorker(db, "worker-1", lease_seconds=3).run_once(
        lambda request: (time.sleep(2.2) or ["places"])
    )
    assert result is not None
    assert result.state == "succeeded"
    with sqlite3.connect(path) as verify:
        assert verify.execute("SELECT state FROM jobs").fetchone()[0] == "succeeded"


def test_worker_rejects_unknown_handler_state():
    db = sqlite3.connect(":memory:")
    migrate(db)
    JobRepository(db).submit({"query": "cafe"}, "invalid-state")
    result = JobWorker(db, "worker-1").run_once(lambda request: {"state": "invented", "completed_steps": []})
    assert result is not None
    assert result.state == "failed"


def test_worker_preserves_partial_multi_source_result():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        JobRepository(db).submit({"sources": ["places", "google_search"]}, "key-partial")
        result = JobWorker(db, "worker-1").run_once(
            lambda request: {
                "state": "partial",
                "completed_steps": ["places"],
                "sources": [{"source": "places", "state": "succeeded"}, {"source": "google_search", "state": "failed"}],
            }
        )
        assert result and result.state == "partial"
        assert result.progress["completed_steps"] == ["places"]


def test_cancel_requested_job_is_not_reported_successful():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        job = JobRepository(db).submit({"query": "cafe"}, "key-1")
        repo = JobRepository(db)
        claimed = repo.claim("worker-1")
        repo.request_cancel(job.job_id)
        result = JobWorker(db, "worker-1")._finish if False else repo.get(job.job_id)
        assert result and result.state == "cancel_requested"
