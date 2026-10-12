import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .domain import Campaign, CampaignStats, Lead
from .errors import CampaignNotFoundError
from .exporters import export_csv, export_json
from .migrations import migrate
from .repositories import (
    CampaignRepository,
    LeadRepository,
    RawRecordRepository,
    RunRepository,
    UpsertSummary,
)
from .results import RunStatus, SearchResult
from .quality.repository import QualityRepository


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
        now = datetime.now(timezone.utc)
        run_id = metadata.get("run_id") or f"local-{now.isoformat()}"
        status = str(metadata.get("status", "succeeded")).lower().replace("-", "_")
        payload = {**metadata, "run_id": run_id, "recorded_at": now.isoformat()}
        with self._connect() as db:
            runs = RunRepository(db)
            default_campaign_id = CampaignRepository.DEFAULT_CAMPAIGN_ID
            if CampaignRepository(db).get(default_campaign_id) is None:
                raise CampaignNotFoundError(
                    f"default campaign not found: {default_campaign_id}"
                )
            runs.start(
                run_id,
                payload,
                started_at=metadata.get("started_at", now),
                campaign_id=default_campaign_id,
            )
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

    def persist_search_result(
        self,
        campaign_id: str,
        result: SearchResult,
        query: str,
        location: str,
    ) -> UpsertSummary:
        now = datetime.now(timezone.utc)
        run_id = result.run_id or f"local-{uuid.uuid4()}"
        status = result.status.value
        metadata = {
            "run_id": run_id,
            "source": result.source,
            "contract_version": "instagram-search-standard-v1" if result.source == "instagram" else "places-v1",
            "actor": "apify~instagram-search-scraper" if result.source == "instagram" else "compass~crawler-google-places",
            "dataset_id": result.dataset_id,
            "status": status,
            "partial": result.partial,
            "warnings": result.warnings,
            "projections": [record.model_dump(mode="json") for record in result.projections],
            "received_count": result.received_count,
            "accepted_count": result.accepted_count,
            "rejected_count": result.rejected_count,
            "rejection_reasons": result.rejection_reasons,
            "query": query,
            "location": location,
            "started_at": result.started_at.isoformat(),
            "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        }
        if result.source == "instagram":
            from .instagram_campaigns import InstagramCampaignRepository
            with self._connect() as db:
                InstagramCampaignRepository(db).persist(campaign_id, run_id, metadata)
            return UpsertSummary()
        with self._connect() as db:
            campaigns = CampaignRepository(db)
            if campaigns.get(campaign_id) is None:
                raise CampaignNotFoundError(f"campaign not found: {campaign_id}")
            runs = RunRepository(db)
            runs.start(
                run_id,
                metadata,
                started_at=result.started_at,
                campaign_id=campaign_id,
            )
            failed = status in {
                RunStatus.FAILED.value,
                RunStatus.ABORTED.value,
                RunStatus.TIMED_OUT.value,
            }
            summary = UpsertSummary()
            observation_ids: list[str] = []
            if not failed:
                summary = LeadRepository(db).upsert(result.leads)
                quality = QualityRepository(db)
                for lead in result.leads:
                    campaigns.add_lead(campaign_id, lead.dedup_key(), seen_at=now)
                    row = db.execute("SELECT lead_id FROM leads WHERE dedup_key = ?", (lead.dedup_key(),)).fetchone()
                    if row is not None:
                        observation = quality.record_lead_observation(row[0], lead, run_id=run_id)
                        observation_ids.append(observation.observation_id)
                from .source_contracts import SOURCE_ALLOWLISTS
                RawRecordRepository(db).save_allowlisted(
                    run_id, result.raw_records, recorded_at=now,
                    allowlist=SOURCE_ALLOWLISTS["instagram"] if result.source == "instagram" else None,
                )
            if failed:
                runs.fail(
                    run_id,
                    " ".join(result.warnings) or status.replace("_", " "),
                    metadata,
                    finished_at=result.finished_at,
                )
            elif status in {RunStatus.PENDING.value, RunStatus.RUNNING.value}:
                pass
            else:
                runs.finish(
                    run_id,
                    metadata,
                    status=status,
                    finished_at=result.finished_at,
                )
        return UpsertSummary(
            inserted=summary.inserted,
            updated=summary.updated,
            lead_ids=summary.lead_ids,
            observation_ids=tuple(observation_ids),
            raw_record_refs=tuple((run_id, index) for index in range(len(result.raw_records))),
        )

    def record_failed_search(
        self,
        campaign_id: str,
        query: str,
        location: str,
        source: str,
        error_type: str,
        error_summary: str,
        *,
        started_at: datetime,
        failure_metadata: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        run_id = f"local-{uuid.uuid4()}"
        metadata = {
            "run_id": run_id,
            "campaign_id": campaign_id,
            "query": query,
            "location": location,
            "source": source,
            "error_type": error_type,
            "error_summary": error_summary,
            "started_at": started_at.isoformat(),
        }
        provider_run_id = (failure_metadata or {}).get("provider_run_id")
        if isinstance(provider_run_id, str) and provider_run_id:
            metadata["provider_run_id"] = provider_run_id
        if source == "instagram":
            for key, allowed in (("failure_stage", {"start", "polling", "dataset", "contract"}), ("failure_code", {"start_unknown", "rate_limited", "start_failed", "poll_timeout", "poll_failed", "dataset_failed", "unknown_schema"})):
                value = (failure_metadata or {}).get(key)
                if isinstance(value, str) and value in allowed:
                    metadata[key] = value
            for key in ("received_count", "accepted_count", "rejected_count"):
                value = (failure_metadata or {}).get(key)
                if type(value) is int and value >= 0:
                    metadata[key] = value
            reasons = (failure_metadata or {}).get("rejection_reasons")
            if isinstance(reasons, dict):
                allowed_reasons = {"unknown_schema", "private_profile", "privacy_unverified", "business_unverified", "invalid_identity", "duplicate_profile"}
                metadata["rejection_reasons"] = {key: value for key, value in reasons.items() if key in allowed_reasons and type(value) is int and value >= 0}
        if source == "instagram":
            from .instagram_campaigns import InstagramCampaignRepository
            metadata.update(status="failed", finished_at=now.isoformat())
            with self._connect() as db:
                InstagramCampaignRepository(db).persist(campaign_id, run_id, metadata)
            return run_id
        with self._connect() as db:
            campaigns = CampaignRepository(db)
            if campaigns.get(campaign_id) is None:
                raise CampaignNotFoundError(f"campaign not found: {campaign_id}")
            runs = RunRepository(db)
            runs.start(
                run_id,
                metadata,
                started_at=started_at,
                campaign_id=campaign_id,
            )
            runs.fail(
                run_id,
                error_summary,
                metadata,
                finished_at=now,
            )
        return run_id

    def create_campaign(
        self,
        name: str,
        description: str | None = None,
        campaign_id: str | None = None,
    ) -> Campaign:
        with self._connect() as db:
            return CampaignRepository(db).create(name, description, campaign_id)

    def campaigns(self) -> list[Campaign]:
        with self._connect() as db:
            return CampaignRepository(db).list()

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        with self._connect() as db:
            return CampaignRepository(db).get(campaign_id)

    def default_campaign(self) -> Campaign:
        with self._connect() as db:
            return CampaignRepository(db).get_default()

    def campaign_stats(self, campaign_id: str) -> CampaignStats:
        with self._connect() as db:
            return CampaignRepository(db).stats(campaign_id)

    def all(self) -> list[Lead]:
        with self._connect() as db:
            return LeadRepository(db).all()

    def leads_for_campaign(self, campaign_id: str) -> list[Lead]:
        with self._connect() as db:
            campaigns = CampaignRepository(db)
            if campaigns.get(campaign_id) is None:
                raise CampaignNotFoundError(f"campaign not found: {campaign_id}")
            return LeadRepository(db).for_campaign(campaign_id)

    def instagram_campaigns(self):
        from .instagram_campaigns import InstagramCampaignRepository
        with self._connect() as db:
            return InstagramCampaignRepository(db).list()

    def get_instagram_campaign(self, campaign_id):
        from .instagram_campaigns import InstagramCampaignRepository
        with self._connect() as db:
            return InstagramCampaignRepository(db).get(campaign_id)

    def create_instagram_campaign(self, name, description=None, campaign_id=None):
        from .instagram_campaigns import InstagramCampaignRepository
        with self._connect() as db:
            return InstagramCampaignRepository(db).create(name, description, campaign_id)

    def instagram_campaign_profiles(self, campaign_id):
        from .instagram_campaigns import InstagramCampaignRepository
        with self._connect() as db:
            return InstagramCampaignRepository(db).profiles(campaign_id)

    def instagram_campaign_runs(self, campaign_id):
        from .instagram_campaigns import InstagramCampaignRepository
        with self._connect() as db:
            return InstagramCampaignRepository(db).runs(campaign_id)

    def instagram_profiles(self, run_id: str):
        """Reload only this run's independent, privacy-validated profiles."""
        import json
        from .source_contracts import InstagramRecord
        with self._connect() as db:
            row = db.execute("SELECT payload, status FROM instagram_campaign_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                row = db.execute("SELECT payload, status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("run not found")
        payload = json.loads(row[0])
        if payload.get("source") != "instagram" or payload.get("contract_version") != "instagram-search-standard-v1":
            raise ValueError("run is not an independent Instagram search")
        profiles = []
        for item in payload.get("projections", []):
            try:
                profile = InstagramRecord.model_validate(item)
                if profile.private is False:
                    profiles.append(profile)
            except ValueError:
                continue
        return profiles

    def export_instagram(self, run_id: str, target: str, format: str = "json") -> None:
        from .exporters import export_instagram_profiles
        export_instagram_profiles(self.instagram_profiles(run_id), target, format)

    def export(
        self,
        path: str,
        fmt: str,
        extended: bool = False,
        campaign_id: str | None = None,
        min_completeness: float | None = None,
        has_phone: bool = False,
        has_website: bool = False,
    ) -> None:
        leads = self.all() if campaign_id is None else self.leads_for_campaign(campaign_id)
        if min_completeness is not None or has_phone or has_website:
            from .quality.metrics import metrics
            leads = [lead for lead in leads if (min_completeness is None or metrics(lead).completeness >= min_completeness) and (not has_phone or bool(lead.phone)) and (not has_website or bool(lead.website))]
        if fmt == "json":
            export_json(leads, path, extended=extended)
        elif fmt == "csv":
            export_csv(leads, path, extended=extended)
        else:
            raise ValueError("format must be json or csv")
