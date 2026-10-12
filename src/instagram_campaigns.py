"""Independent Instagram campaign storage; historical Places runs are untouched."""
import json
import uuid
from datetime import datetime, timezone

from .source_contracts import InstagramRecord


def migrate_instagram(db):
    db.execute("CREATE TABLE instagram_campaigns (campaign_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL)")
    db.execute("CREATE TABLE instagram_campaign_runs (run_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES instagram_campaigns(campaign_id), started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, payload TEXT NOT NULL)")
    db.execute("CREATE INDEX idx_instagram_campaign_runs ON instagram_campaign_runs(campaign_id, started_at, run_id)")
    db.execute("CREATE TABLE instagram_profile_observations (run_id TEXT NOT NULL REFERENCES instagram_campaign_runs(run_id), identity TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id, identity))")


class InstagramCampaignRepository:
    def __init__(self, db):
        self.db = db

    def create(self, name, description=None, campaign_id=None):
        campaign_id = campaign_id or str(uuid.uuid4())
        import re
        if not name.strip() or not re.fullmatch(r"[\w.-]+", campaign_id) or campaign_id in {".", ".."}:
            raise ValueError("Campaign name and identifier are required")
        if self.get(campaign_id):
            raise ValueError("Campaign already exists")
        self.db.execute("INSERT INTO instagram_campaigns VALUES (?, ?, ?, ?)", (campaign_id, name.strip(), description, datetime.now(timezone.utc).isoformat()))
        return self.get(campaign_id)

    def get(self, campaign_id):
        row = self.db.execute("SELECT campaign_id, name, description, created_at FROM instagram_campaigns WHERE campaign_id = ?", (campaign_id,)).fetchone()
        return dict(zip(("campaign_id", "name", "description", "created_at"), row)) if row else None

    def list(self):
        return [self.get(row[0]) for row in self.db.execute("SELECT campaign_id FROM instagram_campaigns ORDER BY created_at, campaign_id")]

    def persist(self, campaign_id, run_id, payload):
        if not self.get(campaign_id):
            raise ValueError("Instagram campaign not found")
        existing = self.db.execute("SELECT campaign_id, payload FROM instagram_campaign_runs WHERE run_id = ?", (run_id,)).fetchone()
        if existing:
            if existing[0] != campaign_id:
                raise ValueError("Run already belongs to another Instagram campaign")
            if json.loads(existing[1]).get("status") in {"succeeded", "partial"}:
                return
        self.db.execute("INSERT INTO instagram_campaign_runs VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET finished_at=excluded.finished_at, status=excluded.status, payload=excluded.payload", (run_id, campaign_id, payload["started_at"], payload.get("finished_at"), payload["status"], json.dumps(payload, ensure_ascii=False)))
        if payload["status"] not in {"succeeded", "partial"}:
            return
        for item in payload.get("projections", []):
            profile = InstagramRecord.model_validate(item)
            if profile.private is not False:
                continue
            identity = "id:" + profile.source_id if profile.source_id else "username:" + profile.username.casefold()
            self.db.execute("INSERT INTO instagram_profile_observations VALUES (?, ?, ?) ON CONFLICT(run_id, identity) DO NOTHING", (run_id, identity, profile.model_dump_json()))

    def runs(self, campaign_id):
        return [dict(zip(("run_id", "started_at", "finished_at", "status"), row)) for row in self.db.execute("SELECT run_id, started_at, finished_at, status FROM instagram_campaign_runs WHERE campaign_id = ? ORDER BY started_at DESC, run_id DESC", (campaign_id,))]

    def profiles(self, campaign_id):
        if not self.get(campaign_id):
            raise ValueError("Instagram campaign not found")
        rows = self.db.execute("SELECT o.payload FROM instagram_profile_observations o JOIN instagram_campaign_runs r ON r.run_id=o.run_id WHERE r.campaign_id=? AND r.status IN ('succeeded','partial') ORDER BY r.started_at DESC, r.run_id DESC, o.identity", (campaign_id,))
        observations = [InstagramRecord.model_validate_json(row[0]) for row in rows]
        username_ids = {}
        for profile in observations:
            if profile.source_id:
                username_ids.setdefault(profile.username.casefold(), set()).add(profile.source_id)
        profiles, identities = [], set()
        for profile in observations:
            ids = username_ids.get(profile.username.casefold(), set())
            source_id = profile.source_id or (next(iter(ids)) if len(ids) == 1 else None)
            identity = "id:" + source_id if source_id else "username:" + profile.username.casefold()
            if identity not in identities:
                profiles.append(profile)
                identities.add(identity)
        return sorted(profiles, key=lambda p: (p.username.casefold(), p.source_id or ""))
