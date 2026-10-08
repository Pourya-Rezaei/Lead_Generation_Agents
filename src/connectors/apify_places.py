from datetime import UTC, datetime
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
            "reviews", "placeId", "cid",
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

    def search_existing_run(self, run_id: str, query: str, limit: int = 20) -> SearchResult:
        """Resume an already-started Actor run without creating a duplicate."""
        started_at = datetime.now(UTC)
        run = self.client.wait_for_run(run_id)
        return self._result_from_run(run, query, limit, started_at)

    def search(self, query: str, location: str, limit: int = 20) -> SearchResult:
        started_at = datetime.now(UTC)
        run = self.client.run_actor(
            self.actor,
            {
                "searchStringsArray": [query],
                "locationQuery": location,
                "maxCrawledPlacesPerSearch": limit,
            },
            wait_for_finish=60,
        )
        status = map_apify_status(str(run.get("status", "")))
        run_id = str(run["id"]) if run.get("id") is not None else None
        dataset_value = run.get("defaultDatasetId") or run.get("datasetId")
        dataset_id = str(dataset_value) if dataset_value is not None else None
        self._set_compatibility_state(run_id, dataset_id, status)

        if status is not RunStatus.SUCCEEDED:
            return SearchResult(
                source=self.source,
                run_id=run_id,
                dataset_id=dataset_id,
                status=status,
                warnings=[f"Apify Actor finished with status {status.value}"],
                started_at=started_at,
                finished_at=(
                    datetime.now(UTC)
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
            finished_at=datetime.now(UTC),
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
        payload = self.client.dataset_items(dataset_id)
        items = payload[:limit]
        self.raw_items = [self._allowlisted(item) for item in items]
        self.last_run["item_count"] = len(self.raw_items)
        return SearchResult(
            source=self.source, run_id=run_id, dataset_id=dataset_id,
            status=RunStatus.SUCCEEDED,
            leads=[self._lead(item, query) for item in items], raw_records=self.raw_items,
            warnings=["Apify dataset was empty"] if not items else [],
            started_at=started_at, finished_at=datetime.now(UTC),
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
            finished_at=datetime.now(UTC),
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
                reviews=item.get("reviewsCount") or item.get("reviews"),
                source_id=item.get("placeId") or item.get("cid"),
                source_url=item.get("url"),
            )
        )
        return lead.model_copy(update={"score": score(lead)})
