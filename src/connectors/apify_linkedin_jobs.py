from datetime import datetime, timezone
from typing import Any

from ..apify import ApifyClient
from ..domain import Lead, normalize, score
from ..results import RunStatus, SearchResult, map_apify_status
from ..retry import RetryPolicy
from .base import Connector


class ApifyLinkedInJobsConnector(Connector):
    """Fetch public LinkedIn job listings and represent their companies as leads."""

    actor = "dataji~apify-linkdin-jobs"
    source = "apify_linkedin_jobs"

    def __init__(self, token: str, timeout: float = 30, client: ApifyClient | None = None):
        self.client = client or ApifyClient(token, timeout, retry_policy=RetryPolicy(max_attempts=3))
        self.last_run: dict[str, Any] = {}

    @property
    def failure_metadata(self) -> dict[str, str]:
        metadata: dict[str, str] = {}
        if self.last_run.get("run_id"):
            metadata["provider_run_id"] = str(self.last_run["run_id"])
        if self.last_run.get("dataset_id"):
            metadata["dataset_id"] = str(self.last_run["dataset_id"])
        return metadata

    def abort(self, run_id: str) -> dict[str, object]:
        return self.client.abort_run(run_id)

    def search_existing_run(self, run_id: str, query: str, limit: int = 20) -> SearchResult:
        started = datetime.now(timezone.utc)
        run = self.client.wait_for_run(run_id, timeout=300, poll_interval=2)
        status = map_apify_status(str(run.get("status", "")))
        dataset_id = run.get("defaultDatasetId") or run.get("datasetId")
        self.last_run = {"run_id": run_id, "dataset_id": dataset_id}
        if status is not RunStatus.SUCCEEDED or not dataset_id:
            return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id) if dataset_id else None, status=status, warnings=["LinkedIn Jobs Actor did not complete successfully"], started_at=started, finished_at=datetime.now(timezone.utc))
        items = self.client.dataset_items(str(dataset_id))[:min(limit, 100)]
        leads: list[Lead] = []
        raw_records: list[dict[str, Any]] = []
        for item in items:
            lead = self._lead(item, query, "")
            if lead is not None:
                leads.append(lead)
                raw_records.append(self._allowlist(item))
        callback = getattr(self, "on_provider_run", None)
        if callable(callback):
            callback(self.source, run_id, str(dataset_id), status.value)
        return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id), status=status, leads=leads, raw_records=raw_records, started_at=started, finished_at=datetime.now(timezone.utc))

    def search(self, query: str, location: str, limit: int = 20) -> SearchResult:
        started = datetime.now(timezone.utc)
        if limit < 1:
            raise ValueError("limit must be positive")
        bounded_limit = min(limit, 100)
        actor_input = {
            "keywords": query.strip(), "location": location.strip(),
            "maxResults": bounded_limit, "scrapeDetails": True, "scrapeCompany": False,
        }
        if callable(getattr(type(self.client), "start_actor", None)):
            run = self.client.start_actor(self.actor, actor_input, wait_for_finish=0)
            run_id = str(run["id"])
            self.last_run = {"run_id": run_id, "dataset_id": None}
            callback = getattr(self, "on_provider_run", None)
            if callable(callback):
                callback(self.source, run_id, None, "running")
            run = self.client.wait_for_run(run_id, timeout=300, poll_interval=2)
        else:
            run = self.client.run_actor(self.actor, actor_input, wait_for_finish=60)
            run_id = str(run["id"])
        dataset_id = run.get("defaultDatasetId") or run.get("datasetId")
        status = map_apify_status(str(run.get("status", "SUCCEEDED")))
        self.last_run = {"run_id": run_id, "dataset_id": dataset_id}
        callback = getattr(self, "on_provider_run", None)
        if callable(callback):
            callback(self.source, run_id, str(dataset_id) if dataset_id else None, status.value)
        if status is not RunStatus.SUCCEEDED or not dataset_id:
            return SearchResult(
                source=self.source,
                run_id=run_id,
                dataset_id=str(dataset_id) if dataset_id else None,
                status=status,
                warnings=["LinkedIn Jobs Actor did not complete successfully"],
                started_at=started,
                finished_at=datetime.now(timezone.utc) if status is not RunStatus.RUNNING else None,
            )

        iterator = getattr(self.client, "iter_dataset_items", None)
        try:
            items = [item for page in iterator(str(dataset_id), max_items=bounded_limit) for item in page] if callable(iterator) else []
        except (TypeError, AttributeError):
            items = []
        if not items:
            items = self.client.dataset_items(str(dataset_id))[:bounded_limit]
        leads: list[Lead] = []
        raw_records: list[dict[str, Any]] = []
        discarded = 0
        for item in items:
            lead = self._lead(item, query, location)
            if lead is None:
                discarded += 1
                continue
            leads.append(lead)
            raw_records.append(self._allowlist(item))
        warnings = [f"Discarded {discarded} malformed LinkedIn job result(s)"] if discarded else []
        return SearchResult(
            source=self.source,
            run_id=run_id,
            dataset_id=str(dataset_id),
            status=RunStatus.SUCCEEDED,
            leads=leads,
            raw_records=raw_records,
            warnings=warnings,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _allowlist(item: dict[str, Any]) -> dict[str, Any]:
        allowed = ("jobId", "title", "companyName", "location", "salary", "description", "companyWebsite", "companyAddress", "jobUrl")
        return {key: item[key] for key in allowed if key in item}

    @classmethod
    def _lead(cls, item: dict[str, Any], query: str, location: str) -> Lead | None:
        name = item.get("companyName") or item.get("company")
        if not isinstance(name, str) or not name.strip():
            return None
        job_url = item.get("jobUrl") or item.get("url")
        try:
            lead = normalize(Lead(
                name=name,
                # A job's location is not evidence of the company's street address.
                address=item.get("companyAddress") or "",
                website=item.get("companyWebsite"),
                category=query,
                source=cls.source,
                source_id=str(item["jobId"]) if item.get("jobId") is not None else None,
                source_url=job_url,
                field_evidence={
                    "name": ("linkedin:companyName",),
                    "source_id": ("linkedin:jobId",),
                    "source_url": ("linkedin:jobUrl",),
                    **({"address": ("linkedin:companyAddress",)} if item.get("companyAddress") else {}),
                },
                field_confidence={
                    "name": 0.9,
                    "source_id": 1.0,
                    "source_url": 1.0,
                    **({"address": 0.9} if item.get("companyAddress") else {}),
                },
            ))
        except (TypeError, ValueError):
            return None
        return lead.model_copy(update={"score": score(lead)})
