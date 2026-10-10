from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .domain import Lead


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    ABORTED = "aborted"
    TIMED_OUT = "timed_out"


_APIFY_STATUSES = {
    "READY": RunStatus.PENDING,
    "RUNNING": RunStatus.RUNNING,
    "SUCCEEDED": RunStatus.SUCCEEDED,
    "FAILED": RunStatus.FAILED,
    "ABORTING": RunStatus.RUNNING,
    "ABORTED": RunStatus.ABORTED,
    "TIMING-OUT": RunStatus.RUNNING,
    "TIMED-OUT": RunStatus.TIMED_OUT,
}


def map_apify_status(status: str) -> RunStatus:
    try:
        return _APIFY_STATUSES[status.upper()]
    except KeyError as exc:
        raise ValueError(f"Unknown Apify run status: {status!r}") from exc


class PlatformObservation(BaseModel):
    """Backward-compatible platform result with shared business fields and safe metadata."""
    platform: str
    profile_url: str
    name: str
    description: str | None = None
    location: str | None = None
    website: str | None = None
    phone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    contact_links: tuple[str, ...] = ()
    source: str = ""
    source_record_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class PlatformSearchResult(BaseModel):
    observations: list[PlatformObservation] = Field(default_factory=list)
    platform: str
    status: RunStatus
    warnings: list[str] = Field(default_factory=list)
    run_id: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class SearchResult(BaseModel):
    leads: list[Lead] = Field(default_factory=list)
    source: str
    run_id: str | None = None
    dataset_id: str | None = None
    status: RunStatus
    partial: bool = False
    warnings: list[str] = Field(default_factory=list)
    raw_records: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "SearchResult":
        terminal = {
            RunStatus.SUCCEEDED,
            RunStatus.PARTIAL,
            RunStatus.FAILED,
            RunStatus.ABORTED,
            RunStatus.TIMED_OUT,
        }
        if self.status in terminal and self.finished_at is None:
            raise ValueError("terminal search results require finished_at")
        if self.partial != (self.status is RunStatus.PARTIAL):
            raise ValueError("partial must be true exactly when status is partial")
        if self.status in {RunStatus.FAILED, RunStatus.ABORTED, RunStatus.TIMED_OUT} and self.leads:
            raise ValueError("failed search results cannot contain leads")
        return self
