from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    job_id: str
    step_id: str
    amount: Decimal
    currency: str
    state: str


def _minor(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class BudgetRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def reserve(self, job_id: str, step_id: str, amount: Decimal, currency: str, max_cost: Decimal, pricing_version: str = "unknown") -> Reservation:
        if amount < 0 or max_cost < 0 or not currency.strip() or not pricing_version.strip():
            raise ValueError("invalid budget reservation")
        amount_minor = _minor(amount)
        max_minor = _minor(max_cost)
        used = self.connection.execute(
            "SELECT COALESCE(SUM(amount_minor), 0) FROM budget_reservations WHERE state IN ('reserved', 'unknown') AND currency = ?",
            (currency.upper(),),
        ).fetchone()[0]
        if used + amount_minor > max_minor:
            raise ValueError("budget limit exceeded")
        reservation_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()
        self.connection.execute(
            "INSERT INTO budget_reservations(reservation_id, job_id, step_id, amount_minor, currency, actual_minor, state, pricing_version, created_at) VALUES (?, ?, ?, ?, ?, NULL, 'reserved', ?, ?)",
            (reservation_id, job_id, step_id, amount_minor, currency.upper(), pricing_version, now),
        )
        return Reservation(reservation_id, job_id, step_id, amount, currency.upper(), "reserved")

    def reconcile(self, reservation_id: str, actual: Decimal | None) -> None:
        row = self.connection.execute("SELECT state FROM budget_reservations WHERE reservation_id = ?", (reservation_id,)).fetchone()
        if row is None or row[0] not in {"reserved", "unknown"}:
            raise ValueError("active reservation not found")
        if actual is None:
            self.connection.execute("UPDATE budget_reservations SET state = 'unknown', reconciled_at = ? WHERE reservation_id = ?", (datetime.now(UTC).isoformat(), reservation_id))
        else:
            if actual < 0:
                raise ValueError("actual cost must not be negative")
            self.connection.execute("UPDATE budget_reservations SET state = 'reconciled', actual_minor = ?, reconciled_at = ? WHERE reservation_id = ?", (_minor(actual), datetime.now(UTC).isoformat(), reservation_id))
