from datetime import UTC, datetime
from typing import Any

from ..apify import ApifyClient
from ..domain import Lead, normalize, score
from ..results import RunStatus, SearchResult, map_apify_status
from ..retry import RetryPolicy
from .base import Connector


class ApifyGoogleSearchConnector(Connector):
    actor = "apify~google-search-scraper"
    source = "apify_google_search"

    def __init__(self, token: str, timeout: float = 30, client: ApifyClient | None = None):
        self.client = client or ApifyClient(token, timeout, retry_policy=RetryPolicy(max_attempts=3))
        self.last_run: dict[str, Any] = {}

    @property
    def failure_metadata(self) -> dict[str, str]:
        return {"provider_run_id": self.last_run["run_id"]} if self.last_run.get("run_id") else {}

    def search(self, query: str, location: str, limit: int = 20) -> SearchResult:
        started = datetime.now(UTC)
        if limit < 1:
            raise ValueError("limit must be positive")
        bounded_limit = min(limit, 100)
        run = self.client.run_actor(
            self.actor,
            {"queries": [f"{query.strip()} {location.strip()}"], "maxPagesPerQuery": 1},
            wait_for_finish=60,
        )
        run_id = str(run["id"])
        dataset_id = run.get("defaultDatasetId") or run.get("datasetId")
        status = map_apify_status(str(run.get("status", "SUCCEEDED")))
        self.last_run = {"run_id": run_id, "dataset_id": dataset_id}
        if status is not RunStatus.SUCCEEDED or not dataset_id:
            return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id) if dataset_id else None, status=status, warnings=["Google Search Actor did not complete successfully"], started_at=started, finished_at=datetime.now(UTC) if status is not RunStatus.RUNNING else None)
        items = self.client.dataset_items(str(dataset_id))[:bounded_limit]
        valid_items = [item for item in items if item.get("title") and item.get("url")]
        discarded = len(items) - len(valid_items)
        leads = [self._lead(item, query) for item in valid_items]
        warnings = [f"Discarded {discarded} malformed search result(s)"] if discarded else []
        return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id), status=RunStatus.SUCCEEDED, leads=leads, raw_records=[self._allowlist(item) for item in valid_items], warnings=warnings, started_at=started, finished_at=datetime.now(UTC))

    @staticmethod
    def _allowlist(item: dict[str, Any]) -> dict[str, Any]:
        return {key: item[key] for key in ("title", "url", "description", "snippet") if key in item}

    @staticmethod
    def _lead(item: dict[str, Any], query: str) -> Lead:
        lead = normalize(Lead(name=str(item["title"]), website=str(item["url"]), category=query, source=ApifyGoogleSearchConnector.source, source_url=str(item["url"])))
        return lead.model_copy(update={"score": score(lead)})
