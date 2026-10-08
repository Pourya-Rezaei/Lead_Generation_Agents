import json
import sqlite3
import uuid
from datetime import UTC, datetime

from .models import Evidence, Observation


class QualityRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def save_observation(self, observation: Observation) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO observations(observation_id, lead_id, source, source_record_id, source_url, run_id, collected_at, fields, mapper_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (observation.observation_id, observation.lead_id, observation.source, observation.source_record_id,
             observation.source_url, observation.run_id, observation.collected_at.isoformat(),
             json.dumps(observation.fields, ensure_ascii=False), observation.mapper_version),
        )

    def save_evidence(self, lead_id: str, evidence: Evidence) -> str:
        evidence_id = uuid.uuid4().hex
        self.connection.execute(
            "INSERT INTO field_evidence(evidence_id, lead_id, field, value, source_url, observation_id, collected_at, evidence_kind, confidence, policy_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (evidence_id, lead_id, evidence.field, json.dumps(evidence.value, ensure_ascii=False), evidence.source_url,
             evidence.observation_id, evidence.collected_at.isoformat(), evidence.evidence_kind,
             evidence.confidence, evidence.policy_version),
        )
        return evidence_id

    def observations_for_lead(self, lead_id: str) -> list[Observation]:
        rows = self.connection.execute(
            "SELECT observation_id, lead_id, source, source_record_id, source_url, run_id, collected_at, fields, mapper_version FROM observations WHERE lead_id = ? ORDER BY collected_at",
            (lead_id,),
        )
        return [Observation(observation_id=r[0], lead_id=r[1], source=r[2], source_record_id=r[3], source_url=r[4], run_id=r[5], collected_at=datetime.fromisoformat(r[6]), fields=json.loads(r[7]), mapper_version=r[8]) for r in rows]
