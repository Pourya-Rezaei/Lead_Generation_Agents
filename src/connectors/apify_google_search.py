from datetime import datetime, timezone
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

    def abort(self, run_id: str) -> dict[str, object]:
        return self.client.abort_run(run_id)

    def search_existing_run(self, run_id: str, query: str, limit: int = 20) -> SearchResult:
        started = datetime.now(timezone.utc)
        run = self.client.wait_for_run(run_id, timeout=300, poll_interval=2)
        status = map_apify_status(str(run.get("status", "")))
        dataset_id = run.get("defaultDatasetId") or run.get("datasetId")
        self.last_run = {"run_id": run_id, "dataset_id": dataset_id}
        if status is not RunStatus.SUCCEEDED or not dataset_id:
            return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id) if dataset_id else None, status=status, warnings=["Google Search Actor did not complete successfully"], started_at=started, finished_at=datetime.now(timezone.utc))
        items = self.client.dataset_items(str(dataset_id))[:min(limit, 100)]
        valid_items = [item for item in items if item.get("title") and item.get("url")]
        leads = [self._lead(item, query) for item in valid_items]
        callback = getattr(self, "on_provider_run", None)
        if callable(callback):
            callback(self.source, run_id, str(dataset_id), status.value)
        return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id), status=status, leads=leads, raw_records=[self._allowlist(item) for item in valid_items], started_at=started, finished_at=datetime.now(timezone.utc))

    def search(self, query: str, location: str, limit: int = 20) -> SearchResult:
        started = datetime.now(timezone.utc)
        if limit < 1:
            raise ValueError("limit must be positive")
        bounded_limit = min(limit, 100)
        actor_input = {"queries": [f"{query.strip()} {location.strip()}"], "maxPagesPerQuery": 1}
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
            return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id) if dataset_id else None, status=status, warnings=["Google Search Actor did not complete successfully"], started_at=started, finished_at=datetime.now(timezone.utc) if status is not RunStatus.RUNNING else None)
        iterator = getattr(self.client, "iter_dataset_items", None)
        try:
            items = [item for page in iterator(str(dataset_id), max_items=bounded_limit) for item in page] if callable(iterator) else []
        except (TypeError, AttributeError):
            items = []
        if not items:
            items = self.client.dataset_items(str(dataset_id))[:bounded_limit]
        valid_items = [item for item in items if item.get("title") and item.get("url")]
        discarded = len(items) - len(valid_items)
        leads = [self._lead(item, query) for item in valid_items]
        warnings = [f"Discarded {discarded} malformed search result(s)"] if discarded else []
        return SearchResult(source=self.source, run_id=run_id, dataset_id=str(dataset_id), status=RunStatus.SUCCEEDED, leads=leads, raw_records=[self._allowlist(item) for item in valid_items], warnings=warnings, started_at=started, finished_at=datetime.now(timezone.utc))

    @staticmethod
    def _allowlist(item: dict[str, Any]) -> dict[str, Any]:
        return {key: item[key] for key in ("title", "url", "description", "snippet") if key in item}

    @staticmethod
    def _lead(item: dict[str, Any], query: str) -> Lead:
        lead = normalize(Lead(
            name=str(item["title"]), website=str(item["url"]), category=query,
            source=ApifyGoogleSearchConnector.source, source_url=str(item["url"]),
            field_evidence={"name": ("google_search:title",), "source_url": ("google_search:url",)},
            field_confidence={"name": 0.55, "website": 0.45, "source_url": 0.8},
        ))
        return lead.model_copy(update={"score": score(lead)})
