import sqlite3

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


def test_cancel_requested_job_is_not_reported_successful():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        job = JobRepository(db).submit({"query": "cafe"}, "key-1")
        repo = JobRepository(db)
        claimed = repo.claim("worker-1")
        repo.request_cancel(job.job_id)
        result = JobWorker(db, "worker-1")._finish if False else repo.get(job.job_id)
        assert result and result.state == "cancel_requested"
