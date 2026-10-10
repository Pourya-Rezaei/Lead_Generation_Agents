from datetime import datetime, timezone
from typing import Any

from ..apify import ApifyClient
from ..domain import Lead, normalize, score
from ..results import RunStatus, SearchResult, map_apify_status
from ..retry import RetryPolicy
from .base import Connector


class ApifyPlacesConnector(Connector):
    actor = "compass~crawler-google-places"
    source = "apify_compass_crawler_google_places"
    raw_field_allowlist = frozenset(
        {
            "title", "name", "address", "street", "phone", "phoneNumber",
            "website", "url", "categoryName", "rating", "reviewsCount",
            "placeId", "cid",
        }
    )

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 30,
        client: ApifyClient | None = None,
        retries: int = 2,
    ) -> None:
        self.client = client or ApifyClient(
            token or "",
            timeout,
            retry_policy=RetryPolicy(max_attempts=retries + 1),
        )
        self.last_run: dict[str, Any] = {}
        self.raw_items: list[dict[str, Any]] = []

    @property
    def failure_metadata(self) -> dict[str, str]:
        run_id = self.last_run.get("run_id")
        return {"provider_run_id": run_id} if isinstance(run_id, str) and run_id else {}

    def abort(self, run_id: str) -> dict[str, object]:
        return self.client.abort_run(run_id)

    def search_existing_run(self, run_id: str, query: str, limit: int = 20) -> SearchResult:
        """Resume an already-started Actor run without creating a duplicate."""
        started_at = datetime.now(timezone.utc)
        run = self.client.wait_for_run(run_id)
        result = self._result_from_run(run, query, limit, started_at)
        callback = getattr(self, "on_provider_run", None)
        if callable(callback):
            callback(self.source, run_id, result.dataset_id, result.status.value)
        return result

    def search(self, query: str, location: str, limit: int = 20) -> SearchResult:
        started_at = datetime.now(timezone.utc)
        actor_input = {
            "searchStringsArray": [query],
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": limit,
        }
        if callable(getattr(type(self.client), "start_actor", None)):
            run = self.client.start_actor(self.actor, actor_input, wait_for_finish=0)
            started_run_id = str(run["id"])
            self._set_compatibility_state(started_run_id, None, RunStatus.RUNNING)
            callback = getattr(self, "on_provider_run", None)
            if callable(callback):
                callback(self.source, started_run_id, None, "running")
            run = self.client.wait_for_run(started_run_id, timeout=300, poll_interval=2)
        else:
            run = self.client.run_actor(self.actor, actor_input, wait_for_finish=60)
        status = map_apify_status(str(run.get("status", "")))
        run_id = str(run["id"]) if run.get("id") is not None else None
        dataset_value = run.get("defaultDatasetId") or run.get("datasetId")
        dataset_id = str(dataset_value) if dataset_value is not None else None
        self._set_compatibility_state(run_id, dataset_id, status)
        callback = getattr(self, "on_provider_run", None)
        if callable(callback) and run_id:
            callback(self.source, run_id, dataset_id, status.value)

        if status is not RunStatus.SUCCEEDED:
            return SearchResult(
                source=self.source,
                run_id=run_id,
                dataset_id=dataset_id,
                status=status,
                warnings=[f"Apify Actor finished with status {status.value}"],
                started_at=started_at,
                finished_at=(
                    datetime.now(timezone.utc)
                    if status in {RunStatus.FAILED, RunStatus.ABORTED, RunStatus.TIMED_OUT}
                    else None
                ),
            )

        if not dataset_id:
            return self._failed_result(
                run_id,
                None,
                started_at,
                "Apify run response did not include a dataset id",
            )

        payload = self.client.dataset_items(dataset_id)
        if isinstance(payload, dict):
            payload = payload.get("items", [])
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            return self._failed_result(
                run_id,
                dataset_id,
                started_at,
                "Apify dataset response must contain a list of records",
            )

        items = payload[:limit]
        self.raw_items = [self._allowlisted(item) for item in items]
        self.last_run["item_count"] = len(self.raw_items)
        warnings = ["Apify dataset was empty"] if not items else []
        return SearchResult(
            source=self.source,
            run_id=run_id,
            dataset_id=dataset_id,
            status=RunStatus.SUCCEEDED,
            leads=[self._lead(item, query) for item in items],
            warnings=warnings,
            raw_records=self.raw_items,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

    def _result_from_run(
        self, run: dict[str, Any], query: str, limit: int, started_at: datetime
    ) -> SearchResult:
        status = map_apify_status(str(run.get("status", "")))
        run_id = str(run["id"]) if run.get("id") is not None else None
        dataset_value = run.get("defaultDatasetId") or run.get("datasetId")
        dataset_id = str(dataset_value) if dataset_value is not None else None
        self._set_compatibility_state(run_id, dataset_id, status)
        if status is not RunStatus.SUCCEEDED or not dataset_id:
            return self._failed_result(run_id, dataset_id, started_at, "Resumed Apify run did not produce a usable dataset")
        iterate = getattr(self.client, "iter_dataset_items", None)
        if callable(iterate):
            pages = iterate(dataset_id, page_size=min(1000, max(limit, 1)), max_items=limit)
            items = [item for page in pages for item in page][:limit]
        else:
            items = self.client.dataset_items(dataset_id)[:limit]
        self.raw_items = [self._allowlisted(item) for item in items]
        self.last_run["item_count"] = len(self.raw_items)
        return SearchResult(
            source=self.source, run_id=run_id, dataset_id=dataset_id,
            status=RunStatus.SUCCEEDED,
            leads=[self._lead(item, query) for item in items], raw_records=self.raw_items,
            warnings=["Apify dataset was empty"] if not items else [],
            started_at=started_at, finished_at=datetime.now(timezone.utc),
        )

    def _set_compatibility_state(
        self, run_id: str | None, dataset_id: str | None, status: RunStatus
    ) -> None:
        self.raw_items = []
        self.last_run = {
            "actor_id": self.actor,
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": status.value,
            "item_count": 0,
        }

    def _failed_result(
        self,
        run_id: str | None,
        dataset_id: str | None,
        started_at: datetime,
        warning: str,
    ) -> SearchResult:
        self.last_run["status"] = RunStatus.FAILED.value
        return SearchResult(
            source=self.source,
            run_id=run_id,
            dataset_id=dataset_id,
            status=RunStatus.FAILED,
            warnings=[warning],
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

    @classmethod
    def _allowlisted(cls, item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key in cls.raw_field_allowlist}

    @classmethod
    def _lead(cls, item: dict[str, Any], query: str) -> Lead:
        lead = normalize(
            Lead(
                name=item.get("title") or item.get("name") or "",
                address=item.get("address") or item.get("street") or "",
                phone=item.get("phone") or item.get("phoneNumber") or "",
                website=item.get("website"),
                category=item.get("categoryName") or query,
                source=cls.source,
                rating=item.get("rating"),
                reviews=item.get("reviewsCount"),
                source_id=item.get("placeId") or item.get("cid"),
                source_url=item.get("url"),
                field_evidence={
                    "name": ("places:title",), "address": ("places:address",),
                    "phone": ("places:phone",), "website": ("places:website",),
                    "source_id": ("places:placeId",), "source_url": ("places:url",),
                },
                field_confidence={"name": 0.95, "address": 0.95, "phone": 0.9, "website": 0.9, "source_id": 1.0, "source_url": 1.0},
            )
        )
        return lead.model_copy(update={"score": score(lead)})
