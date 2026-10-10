import sqlite3

from src.execution.jobs import JobRepository
from src.execution.service import JobService
from src.migrations import migrate


def test_cancel_aborts_every_persisted_provider_run(tmp_path):
    database = tmp_path / "cancel.db"
    with sqlite3.connect(database) as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "cancel-live-run")
        claimed = repo.claim("worker")
        assert claimed is not None
        repo.record_provider_attempt(
            job.job_id, "places", run_id="apify-run-1", status="running",
            worker_id="worker", fencing_token=claimed.fencing_token,
        )
    aborted = []

    result = JobService(str(database)).cancel(
        job.job_id,
        abort_provider_run=lambda source, run_id: aborted.append((source, run_id)) or {"id": run_id},
    )

    assert result is not None and result.state == "cancel_requested"
    assert aborted == [("places", "apify-run-1")]
    with sqlite3.connect(database) as db:
        attempt = db.execute(
            "SELECT status, cancellation_requested FROM provider_attempts WHERE job_id = ?",
            (job.job_id,),
        ).fetchone()
    assert attempt == ("aborted", 1)


def test_cancel_without_run_id_never_calls_provider(tmp_path):
    database = tmp_path / "cancel-unknown.db"
    with sqlite3.connect(database) as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "cancel-unknown")
        claimed = repo.claim("worker")
        assert claimed is not None
        repo.record_provider_attempt(
            job.job_id, "places", status="starting",
            worker_id="worker", fencing_token=claimed.fencing_token,
        )
    called = []
    JobService(str(database)).cancel(job.job_id, abort_provider_run=lambda *args: called.append(args))
    assert called == []
