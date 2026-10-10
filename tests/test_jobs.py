import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.execution.jobs import JobRepository
from src.migrations import migrate


def test_duplicate_submission_returns_same_job():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        first = repo.submit({"query": "cafe", "location": "Tehran"}, "key-1")
        second = repo.submit({"query": "cafe", "location": "Tehran"}, "key-1")
        assert first.job_id == second.job_id


def test_idempotency_key_cannot_change_request():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        repo.submit({"query": "cafe"}, "same-key")
        with pytest.raises(ValueError, match="different request"):
            repo.submit({"query": "bakery"}, "same-key")


def test_claimed_job_can_persist_provider_run_state():
    db = sqlite3.connect(":memory:")
    migrate(db)
    repo = JobRepository(db)
    job = repo.submit({"query": "cafe"}, "provider-state-key")
    claimed = repo.claim("worker-1")
    assert claimed is not None

    repo.update_provider_run(claimed.job_id, "worker-1", claimed.fencing_token, "run-123", "RUNNING")

    updated = repo.get(job.job_id)
    assert updated is not None
    assert updated.provider_run_id == "run-123"
    assert updated.provider_state == "RUNNING"


def test_only_one_worker_claims_queued_job():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "key-1")
        claimed = repo.claim("worker-1")
        assert claimed and claimed.job_id == job.job_id
        assert repo.claim("worker-2") is None


def test_unknown_provider_start_crash_requires_review():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "unknown-start")
        claimed = repo.claim("worker", lease_seconds=1)
        assert claimed is not None
        repo.record_provider_attempt(
            job.job_id, "places", status="starting",
            worker_id="worker", fencing_token=claimed.fencing_token,
        )
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.execute("UPDATE jobs SET lease_until = ? WHERE job_id = ?", (past, job.job_id))
        repo.recover_expired_leases()
        recovered = repo.get(job.job_id)
        assert recovered is not None and recovered.state == "needs_review"
        assert recovered.error_code == "ProviderStartOutcomeUnknown"


def test_cancel_queued_job_is_terminal():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "key-1")
        repo.request_cancel(job.job_id)
        assert repo.get(job.job_id).state == "cancelled"
