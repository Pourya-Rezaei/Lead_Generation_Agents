import sqlite3

from src.execution.jobs import JobRepository
from src.execution.worker import JobWorker
from src.migrations import migrate


def test_worker_reserves_budget_and_keeps_unknown_cost(tmp_path):
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = JobRepository(db)
        repo.submit({"query": "cafe", "estimated_cost": "0.40", "max_cost": "1.00", "currency": "USD"}, "key-1")
        result = JobWorker(db, "worker-1").run_once(lambda request: ["places"])
        assert result.state == "succeeded"
        assert db.execute("SELECT state FROM budget_reservations").fetchone()[0] == "unknown"


def test_worker_rejects_budget_over_limit_before_handler():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        JobRepository(db).submit({"query": "cafe", "estimated_cost": "1.10", "max_cost": "1.00"}, "key-1")
        called = []
        result = JobWorker(db, "worker-1").run_once(lambda request: called.append(True) or ["places"])
        assert result.state == "failed"
        assert called == []
        assert db.execute("SELECT COUNT(*) FROM budget_reservations").fetchone()[0] == 0
