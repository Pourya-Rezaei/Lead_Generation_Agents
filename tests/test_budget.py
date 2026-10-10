import sqlite3
from decimal import Decimal

import pytest

from src.execution.budget import BudgetRepository
from src.migrations import migrate


def test_atomic_budget_reservation_prevents_overspend():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = BudgetRepository(db)
        repo.reserve("job-1", "places", Decimal("0.60"), "usd", Decimal("1.00"))
        with pytest.raises(ValueError, match="budget limit"):
            repo.reserve("job-2", "search", Decimal("0.50"), "usd", Decimal("1.00"))


def test_unknown_cost_keeps_reservation():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        repo = BudgetRepository(db)
        reservation = repo.reserve("job-1", "places", Decimal("0.50"), "usd", Decimal("1.00"))
        repo.reconcile(reservation.reservation_id, None)
        assert db.execute("SELECT state FROM budget_reservations").fetchone()[0] == "unknown"
        with pytest.raises(ValueError, match="budget limit"):
            repo.reserve("job-2", "search", Decimal("0.60"), "usd", Decimal("1.00"))


def test_currency_is_normalized():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        reservation = BudgetRepository(db).reserve("job-1", "places", Decimal("0.10"), "usd", Decimal("1.00"))
        assert reservation.currency == "USD"
