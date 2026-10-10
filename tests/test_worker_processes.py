import multiprocessing
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from src.execution.jobs import JobRepository
from src.execution.worker import JobWorker
from src.migrations import migrate


def _run_one(database_path: str, worker_id: str, barrier) -> None:
    db = sqlite3.connect(database_path, timeout=5)
    worker = JobWorker(db, worker_id)

    def handler(request):
        barrier.wait(timeout=5)
        time.sleep(0.1)
        return ["places"]

    worker.run_once(handler)
    db.close()


def _claim_then_crash(database_path: str, ready) -> None:
    db = sqlite3.connect(database_path, timeout=5)
    JobRepository(db).claim("crashing-worker", lease_seconds=30)
    ready.set()
    time.sleep(30)


def test_multiple_process_workers_claim_distinct_jobs(tmp_path):
    database_path = str(tmp_path / "workers.db")
    with sqlite3.connect(database_path) as db:
        migrate(db)
        repo = JobRepository(db)
        repo.submit({"query": "one"}, "one")
        repo.submit({"query": "two"}, "two")
    barrier = multiprocessing.Barrier(2)
    workers = [
        multiprocessing.Process(target=_run_one, args=(database_path, f"worker-{i}", barrier))
        for i in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0
    with sqlite3.connect(database_path) as db:
        assert db.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall() == [("succeeded", 2)]


def test_crashed_process_lease_is_recovered_and_job_retried(tmp_path):
    database_path = str(tmp_path / "crash-recovery.db")
    with sqlite3.connect(database_path) as db:
        migrate(db)
        JobRepository(db).submit({"query": "recover"}, "recover")
    ready = multiprocessing.Event()
    process = multiprocessing.Process(target=_claim_then_crash, args=(database_path, ready))
    process.start()
    assert ready.wait(timeout=5)
    process.terminate()
    process.join(timeout=5)
    assert process.exitcode is not None
    with sqlite3.connect(database_path) as db:
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.execute("UPDATE jobs SET lease_until = ? WHERE state = 'running'", (expired,))
        db.commit()
        result = JobWorker(db, "recovery-worker").run_once(lambda request: ["places"])
        assert result is not None and result.state == "succeeded"
