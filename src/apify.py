"""Secure, injectable client for the Apify HTTP API."""

from collections.abc import Callable, Mapping
from typing import Any, Protocol
from urllib.parse import quote
import time

import httpx

from .errors import (
    ApifyCredentialError,
    ApifyError,
    ApifyMalformedResponseError,
    ApifyNotFoundError,
    ApifyTransientError,
)
from .retry import RetryPolicy, retry


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> httpx.Response: ...

    def get(self, url: str, **kwargs: Any) -> httpx.Response: ...


class _RetryableRequestError(Exception):
    pass


class ApifyClient:
    """Synchronous Apify client that keeps credentials out of request URLs."""

    base_url = "https://api.apify.com/v2"

    def __init__(
        self,
        token: str,
        timeout: float = 30,
        *,
        client: HttpClient | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not token:
            raise ValueError("An Apify API token is required")
        self._headers = {"Authorization": f"Bearer {token}"}
        self.timeout = timeout
        self._client = client or httpx.Client(trust_env=False)
        self._owned_client = client is None
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    def close(self) -> None:
        if self._owned_client:
            self._client.close()  # type: ignore[attr-defined]

    def __enter__(self) -> "ApifyClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def run_actor(
        self,
        actor: str,
        input_data: Mapping[str, Any],
        *,
        wait_for_finish: int = 60,
    ) -> dict[str, Any]:
        """Start an Actor, wait when requested, and return validated run data."""
        run = self.start_actor(actor, input_data, wait_for_finish=wait_for_finish)
        return self._validate_run_data(run)

    def start_actor(
        self,
        actor: str,
        input_data: Mapping[str, Any],
        *,
        wait_for_finish: int = 0,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/acts/{quote(actor, safe='~')}/runs"
        payload = self._request_json("post", url, params={"waitForFinish": str(wait_for_finish)}, json=dict(input_data))
        return self._validate_run_data(payload)

    def get_run(self, run_id: str) -> dict[str, Any]:
        if not run_id:
            raise ValueError("run_id is required")
        payload = self._request_json("get", f"{self.base_url}/actor-runs/{quote(run_id, safe='')}")
        return self._validate_run_data(payload)

    def abort_run(self, run_id: str) -> dict[str, Any]:
        if not run_id:
            raise ValueError("run_id is required")
        payload = self._request_json("post", f"{self.base_url}/actor-runs/{quote(run_id, safe='')}/abort")
        return self._validate_run_data(payload)

    def wait_for_run(
        self,
        run_id: str,
        *,
        timeout: float = 300,
        poll_interval: float = 2,
    ) -> dict[str, Any]:
        """Poll an existing run until it reaches a terminal status."""
        if timeout <= 0 or poll_interval <= 0:
            raise ValueError("timeout and poll_interval must be positive")
        deadline = time.monotonic() + timeout
        terminal = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
        while True:
            run = self.get_run(run_id)
            status = str(run.get("status", "")).upper()
            if status in terminal:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ApifyTransientError("Apify run polling timed out")
            self._sleep(min(poll_interval, remaining))

    @staticmethod
    def _validate_run_data(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ApifyMalformedResponseError("Apify run response must be an object")
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ApifyMalformedResponseError("Apify run response has invalid data")
        if not data.get("id"):
            raise ApifyMalformedResponseError("Apify run response is missing a run id")
        return data

    def dataset_items(self, dataset_id: str) -> list[dict[str, Any]]:
        """Retrieve and validate all clean items using the legacy request shape."""
        if not dataset_id:
            raise ValueError("dataset_id is required")
        url = f"{self.base_url}/datasets/{quote(dataset_id, safe='')}/items"
        payload = self._request_json("get", url, params={"clean": "true"})
        if isinstance(payload, dict):
            payload = payload.get("items")
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ApifyMalformedResponseError("Apify dataset response must be a list of objects")
        return payload

    def iter_dataset_items(
        self, dataset_id: str, *, page_size: int = 1000, max_items: int | None = None
    ) -> Any:
        """Yield dataset pages in order for resumable processing."""
        if page_size < 1 or (max_items is not None and max_items < 0):
            raise ValueError("page_size must be positive and max_items non-negative")
        offset = 0
        yielded = 0
        while max_items is None or yielded < max_items:
            limit = page_size if max_items is None else min(page_size, max_items - yielded)
            page = self.dataset_items_page(dataset_id, offset=offset, limit=limit)
            if not page:
                return
            yield page
            yielded += len(page)
            offset += len(page)
            if len(page) < limit:
                return

    def dataset_items_page(
        self, dataset_id: str, *, offset: int = 0, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Retrieve one deterministic page of clean dataset items."""
        if not dataset_id:
            raise ValueError("dataset_id is required")
        if offset < 0 or limit < 1:
            raise ValueError("offset must be non-negative and limit must be positive")
        url = f"{self.base_url}/datasets/{quote(dataset_id, safe='')}/items"
        payload = self._request_json(
            "get", url, params={"clean": "true", "offset": offset, "limit": limit}
        )
        if isinstance(payload, dict):
            payload = payload.get("items")
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ApifyMalformedResponseError("Apify dataset response must be a list of objects")
        return payload

    def _request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        def request() -> Any:
            try:
                response = getattr(self._client, method)(
                    url,
                    headers=self._headers,
                    timeout=self.timeout,
                    **kwargs,
                )
            except httpx.RequestError as exc:
                raise _RetryableRequestError from exc
            self._classify_status(response.status_code)
            try:
                return response.json()
            except ValueError:
                raise ApifyMalformedResponseError("Apify returned invalid JSON") from None

        try:
            return retry(
                request,
                policy=self.retry_policy,
                retry_on=(_RetryableRequestError,),
                sleep=self._sleep,
            )
        except _RetryableRequestError:
            raise ApifyTransientError(
                f"Apify request failed after {self.retry_policy.max_attempts} attempts"
            ) from None

    @staticmethod
    def _classify_status(status_code: int) -> None:
        if 200 <= status_code < 300:
            return
        if status_code in (401, 403):
            raise ApifyCredentialError("Apify rejected the supplied credentials")
        if status_code == 404:
            raise ApifyNotFoundError("Apify Actor, dataset, or endpoint was not found")
        if status_code == 429 or 500 <= status_code < 600:
            raise _RetryableRequestError
        raise ApifyError(f"Apify request failed with HTTP status {status_code}")
