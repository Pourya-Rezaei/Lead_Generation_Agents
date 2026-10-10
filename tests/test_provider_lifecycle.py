import sqlite3
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from src.execution.handlers import places_handler
from src.execution.jobs import JobRepository
from src.execution.service import JobService
from src.execution.worker import JobWorker
from src.migrations import migrate
from src.results import RunStatus, SearchResult


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


def test_cancel_during_actor_start_aborts_run_when_id_arrives(tmp_path):
    database = tmp_path / "cancel-during-start.db"
    with sqlite3.connect(database) as db:
        migrate(db)
        job = JobRepository(db).submit(
            {"query": "cafe", "location": "Tehran", "source": "places"},
            "cancel-during-start",
        )
    start_entered = threading.Event()
    allow_run_id = threading.Event()
    aborted = []
    service = Mock()
    service.settings = SimpleNamespace(database_path=str(database))
    service.last_persisted_refs = {}
    service.abort_provider_run.side_effect = lambda source, run_id: aborted.append((source, run_id))

    def search(query, location, source, limit, campaign_id, **options):
        start_entered.set()
        assert allow_run_id.wait(5)
        options["on_provider_run"](source, "apify-run-2", "dataset-2", "running")
        return SearchResult(
            source=source, run_id="apify-run-2", dataset_id="dataset-2",
            status=RunStatus.ABORTED, finished_at=datetime.now(timezone.utc),
        )

    service.search.side_effect = search
    handler = places_handler(service)
    worker_results = []

    def run_worker():
        with sqlite3.connect(database, timeout=5) as db:
            migrate(db)
            worker_results.append(JobWorker(db, "worker").run_once(handler))

    thread = threading.Thread(target=run_worker)
    thread.start()
    assert start_entered.wait(5)
    cancel_result = JobService(str(database)).cancel(
        job.job_id,
        abort_provider_run=service.abort_provider_run,
    )
    assert cancel_result is not None and cancel_result.state == "cancel_requested"
    allow_run_id.set()
    thread.join(10)

    assert not thread.is_alive()
    assert aborted == [("places", "apify-run-2")]
    assert worker_results[0] is not None and worker_results[0].state == "cancelled"
    with sqlite3.connect(database) as db:
        attempt = db.execute(
            "SELECT status, cancellation_requested, provider_run_id FROM provider_attempts WHERE job_id = ?",
            (job.job_id,),
        ).fetchone()
    assert attempt == ("aborted", 1, "apify-run-2")


def test_cancel_during_start_with_abort_error_requires_review(tmp_path):
    database = tmp_path / "cancel-abort-unknown.db"
    with sqlite3.connect(database) as db:
        migrate(db)
        job = JobRepository(db).submit(
            {"query": "cafe", "location": "Tehran", "source": "places"},
            "cancel-abort-unknown",
        )
    service = Mock()
    service.settings = SimpleNamespace(database_path=str(database))
    service.abort_provider_run.side_effect = RuntimeError("provider error")

    def search(query, location, source, limit, campaign_id, **options):
        JobService(str(database)).cancel(job.job_id)
        options["on_provider_run"](source, "apify-run-3", "dataset-3", "running")

    service.search.side_effect = search
    handler = places_handler(service)

    with sqlite3.connect(database, timeout=5) as db:
        migrate(db)
        result = JobWorker(db, "worker").run_once(handler)

    assert result is not None and result.state == "needs_review"
    assert result.error_code == "ProviderAbortOutcomeUnknown"
    attempt = JobService(str(database)).provider_attempts(job.job_id)[0]
    assert attempt["provider_run_id"] == "apify-run-3"
    assert attempt["cancellation_requested"] is True
    assert attempt["status"] == "abort_unknown"


def test_cancel_with_known_run_and_abort_error_requires_review(tmp_path):
    database = tmp_path / "cancel-known-abort-unknown.db"
    with sqlite3.connect(database) as db:
        migrate(db)
        repo = JobRepository(db)
        job = repo.submit({"query": "cafe"}, "cancel-known-abort-unknown")
        claimed = repo.claim("worker")
        assert claimed is not None
        repo.record_provider_attempt(
            job.job_id, "places", run_id="apify-run-4", status="running",
            worker_id="worker", fencing_token=claimed.fencing_token,
        )

    result = JobService(str(database)).cancel(
        job.job_id,
        abort_provider_run=lambda *_: (_ for _ in ()).throw(RuntimeError("provider detail")),
    )

    assert result is not None and result.state == "needs_review"
    assert result.error_code == "ProviderAbortOutcomeUnknown"
    attempt = JobService(str(database)).provider_attempts(job.job_id)[0]
    assert attempt["status"] == "abort_unknown"
    assert attempt["cancellation_requested"] is True
