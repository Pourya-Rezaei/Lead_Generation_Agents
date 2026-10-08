from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime

from ..enrichment import ProfileCandidate


class ProfileRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def save(self, lead_id: str, platform: str, candidate: ProfileCandidate) -> str:
        candidate_id = uuid.uuid4().hex
        self.connection.execute(
            "INSERT INTO profile_candidates(candidate_id, lead_id, platform, url, status, confidence, evidence, review_reason, reviewed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?) ON CONFLICT(lead_id, platform, url) DO UPDATE SET confidence = excluded.confidence, evidence = excluded.evidence",
            (candidate_id, lead_id, platform, candidate.url, candidate.status, candidate.confidence, json.dumps(candidate.evidence), datetime.now(UTC).isoformat()),
        )
        row = self.connection.execute("SELECT candidate_id FROM profile_candidates WHERE lead_id = ? AND platform = ? AND url = ?", (lead_id, platform, candidate.url)).fetchone()
        return row[0]

    def review(self, candidate_id: str, status: str, reason: str) -> None:
        if status not in {"confirmed", "rejected", "probable", "unverified"} or not reason.strip():
            raise ValueError("invalid profile review")
        self.connection.execute("UPDATE profile_candidates SET status = ?, review_reason = ?, reviewed_at = ? WHERE candidate_id = ?", (status, reason.strip(), datetime.now(UTC).isoformat(), candidate_id))
