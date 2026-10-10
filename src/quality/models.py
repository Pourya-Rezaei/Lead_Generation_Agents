from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class Observation(BaseModel):
    observation_id: str
    lead_id: str
    source: str
    source_record_id: str | None = None
    source_url: str | None = None
    run_id: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fields: dict[str, Any] = Field(default_factory=dict)
    mapper_version: str = "1"


class Evidence(BaseModel):
    field: str
    value: Any
    source_url: str | None = None
    observation_id: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_kind: str = "source"
    confidence: float | None = Field(default=None, ge=0, le=1)
    policy_version: str = "quality-v1"


class MatchDecision(BaseModel):
    action: Literal["merge", "review", "separate"]
    candidate_lead_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    reasons: tuple[str, ...] = ()
    policy_version: str = "identity-v1"


class QualityMetrics(BaseModel):
    completeness: float = Field(ge=0, le=100)
    identity_confidence: float | None = Field(default=None, ge=0, le=1)
    field_confidence: dict[str, float | None] = Field(default_factory=dict)
    popularity: float = Field(ge=0)
    policy_version: str = "quality-v1"
