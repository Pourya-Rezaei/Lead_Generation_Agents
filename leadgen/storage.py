import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .domain import Lead
from .exporters import export_csv, export_json
from .migrations import migrate
from .repositories import LeadRepository, RawRecordRepository, RunRepository


class LeadStore:
    """Backward-compatible facade over the versioned SQLite repositories."""

    def __init__(self, path: str = "leads.db"):
        self.path = path
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            migrate(db)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def upsert(self, leads: list[Lead]) -> int:
        with self._connect() as db:
            summary = LeadRepository(db).upsert(leads)
        return summary.total

    def record_run(
        self,
        metadata: dict[str, Any],
        raw_records: list[dict[str, Any]] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        run_id = metadata.get("run_id") or f"local-{now.isoformat()}"
        status = str(metadata.get("status", "succeeded")).lower().replace("-", "_")
        payload = {**metadata, "run_id": run_id, "recorded_at": now.isoformat()}
        with self._connect() as db:
            runs = RunRepository(db)
            runs.start(run_id, payload, started_at=metadata.get("started_at", now))
            if status == "failed":
                runs.fail(
                    run_id,
                    str(metadata.get("error", "run failed")),
                    payload,
                    finished_at=metadata.get("finished_at", now),
                )
            elif status in {"pending", "running"}:
                pass
            else:
                runs.finish(
                    run_id,
                    payload,
                    status=status,
                    finished_at=metadata.get("finished_at", now),
                )
            RawRecordRepository(db).save_allowlisted(
                run_id, raw_records or [], recorded_at=now
            )

    def all(self) -> list[Lead]:
        with self._connect() as db:
            return LeadRepository(db).all()

    def export(self, path: str, fmt: str, extended: bool = False) -> None:
        leads = self.all()
        if fmt == "json":
            export_json(leads, path, extended=extended)
        elif fmt == "csv":
            export_csv(leads, path, extended=extended)
        else:
            raise ValueError("format must be json or csv")
