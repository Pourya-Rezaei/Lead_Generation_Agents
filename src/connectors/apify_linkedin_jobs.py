from datetime import UTC, datetime
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
        return {key: str(self.last_run[key]) for key in ("run_id", "dataset_id") if self.last_run.get(key)}

    def search(self, query: str, location: str, limit: int = 20) -> SearchResult:
        started = datetime.now(UTC)
        if limit < 1:
            raise ValueError("limit must be positive")
        bounded_limit = min(limit, 100)
        run = self.client.run_actor(
            self.actor,
            {
                "keywords": query.strip(),
                "location": location.strip(),
                "maxResults": bounded_limit,
                "scrapeDetails": True,
                "scrapeCompany": False,
            },
            wait_for_finish=60,
        )
        run_id = str(run["id"])
        dataset_id = run.get("defaultDatasetId") or run.get("datasetId")
        status = map_apify_status(str(run.get("status", "SUCCEEDED")))
        self.last_run = {"run_id": run_id, "dataset_id": dataset_id}
        if status is not RunStatus.SUCCEEDED or not dataset_id:
            return SearchResult(
                source=self.source,
                run_id=run_id,
                dataset_id=str(dataset_id) if dataset_id else None,
                status=status,
                warnings=["LinkedIn Jobs Actor did not complete successfully"],
                started_at=started,
                finished_at=datetime.now(UTC) if status is not RunStatus.RUNNING else None,
            )

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
            finished_at=datetime.now(UTC),
        )

    @staticmethod
    def _allowlist(item: dict[str, Any]) -> dict[str, Any]:
        allowed = ("jobId", "title", "companyName", "location", "salary", "description", "companyWebsite", "jobUrl")
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
                address=item.get("location") or location,
                website=item.get("companyWebsite"),
                category=query,
                source=cls.source,
                source_id=str(item["jobId"]) if item.get("jobId") is not None else None,
                source_url=job_url,
            ))
        except (TypeError, ValueError):
            return None
        return lead.model_copy(update={"score": score(lead)})
