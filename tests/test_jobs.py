import sqlite3

from src.execution.jobs import JobRepository
from src.migrations import migrate


def test_duplicate_submission_returns_same_job():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        first = repo.submit({"query": "cafe", "location": "Tehran"}, "key-1")
        second = repo.submit({"query": "cafe", "location": "Tehran"}, "key-1")
        assert first.job_id == second.job_id


def test_only_one_worker_claims_queued_job():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "key-1")
        claimed = repo.claim("worker-1")
        assert claimed and claimed.job_id == job.job_id
        assert repo.claim("worker-2") is None


def test_cancel_queued_job_is_terminal():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "key-1")
        repo.request_cancel(job.job_id)
        assert repo.get(job.job_id).state == "cancelled"
