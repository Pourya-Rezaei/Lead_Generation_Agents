import httpx
import pytest

from src.apify import ApifyClient
from src.errors import (
    ApifyCredentialError,
    ApifyMalformedResponseError,
    ApifyNotFoundError,
    ApifyTransientError,
)
from src.retry import RetryPolicy


class ScriptedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def post(self, url, **kwargs):
        return self._send("POST", url, kwargs)

    def get(self, url, **kwargs):
        return self._send("GET", url, kwargs)

    def _send(self, method, url, kwargs):
        self.requests.append((method, url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def response(status, payload=None, *, text=None):
    request = httpx.Request("GET", "https://api.apify.com")
    if text is not None:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=payload, request=request)


def make_client(scripted, *, attempts=1, sleep=lambda _: None):
    return ApifyClient(
        "top-secret-token",
        client=scripted,
        retry_policy=RetryPolicy(max_attempts=attempts, initial_backoff=0.25),
        sleep=sleep,
    )


def test_run_actor_uses_header_and_returns_run_data():
    transport = ScriptedClient([
        response(200, {"data": {"id": "run-1", "defaultDatasetId": "ds-1"}})
    ])

    run = make_client(transport).run_actor("compass~crawler-google-places", {"q": "cafe"})

    assert run["id"] == "run-1"
    method, url, kwargs = transport.requests[0]
    assert method == "POST"
    assert url == "https://api.apify.com/v2/acts/compass~crawler-google-places/runs"
    assert "top-secret-token" not in url
    assert kwargs["headers"] == {"Authorization": "Bearer top-secret-token"}
    assert kwargs["params"] == {"waitForFinish": "60"}
    assert kwargs["json"] == {"q": "cafe"}


def test_wait_for_run_polls_existing_run_until_terminal():
    transport = ScriptedClient([
        response(200, {"data": {"id": "run-1", "status": "RUNNING"}}),
        response(200, {"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}}),
    ])

    run = make_client(transport).wait_for_run("run-1", timeout=5, poll_interval=0.01)

    assert run["status"] == "SUCCEEDED"
    assert [request[0] for request in transport.requests] == ["GET", "GET"]


def test_run_actor_allows_status_without_dataset_id():
    transport = ScriptedClient([
        response(200, {"data": {"id": "run-1", "status": "RUNNING"}})
    ])

    run = make_client(transport).run_actor("actor~name", {})

    assert run == {"id": "run-1", "status": "RUNNING"}


def test_lifecycle_can_start_poll_and_abort_without_exposing_token():
    transport = ScriptedClient([
        response(200, {"data": {"id": "run-1", "status": "RUNNING"}}),
        response(200, {"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}}),
        response(200, {"data": {"id": "run-1", "status": "ABORTED"}}),
    ])
    client = make_client(transport)
    assert client.start_actor("actor~name", {}, wait_for_finish=0)["status"] == "RUNNING"
    assert client.get_run("run-1")["status"] == "SUCCEEDED"
    assert client.abort_run("run-1")["status"] == "ABORTED"
    assert all("top-secret-token" not in request[1] for request in transport.requests)


def test_dataset_items_retrieves_clean_items():
    transport = ScriptedClient([response(200, [{"title": "Cafe"}])])

    items = make_client(transport).dataset_items("ds-1")

    assert items == [{"title": "Cafe"}]
    method, url, kwargs = transport.requests[0]
    assert method == "GET"
    assert url.endswith("/datasets/ds-1/items")
    assert kwargs["params"] == {"clean": "true"}


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(401, ApifyCredentialError), (403, ApifyCredentialError), (404, ApifyNotFoundError)],
)
def test_non_retryable_statuses_are_classified_without_leaking_token(status, error_type):
    transport = ScriptedClient([response(status, {"error": "top-secret-token"})])

    with pytest.raises(error_type) as caught:
        make_client(transport, attempts=3).dataset_items("ds-1")

    assert len(transport.requests) == 1
    assert "top-secret-token" not in str(caught.value)


def test_retries_rate_limit_with_injected_backoff():
    transport = ScriptedClient([
        response(429, {}),
        response(200, [{"title": "Cafe"}]),
    ])
    delays = []

    items = make_client(transport, attempts=2, sleep=delays.append).dataset_items("ds-1")

    assert items == [{"title": "Cafe"}]
    assert delays == [0.25]


def test_timeout_exhaustion_is_transient_and_safe():
    request = httpx.Request("GET", "https://api.apify.com/v2/datasets/ds-1/items")
    transport = ScriptedClient([
        httpx.ReadTimeout("top-secret-token", request=request),
        httpx.ReadTimeout("top-secret-token", request=request),
    ])

    with pytest.raises(ApifyTransientError) as caught:
        make_client(transport, attempts=2).dataset_items("ds-1")

    assert "top-secret-token" not in str(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {}},
        {"data": []},
        [],
    ],
)
def test_rejects_malformed_run_responses(payload):
    transport = ScriptedClient([response(200, payload)])

    with pytest.raises(ApifyMalformedResponseError):
        make_client(transport).run_actor("actor~name", {})


def test_rejects_invalid_json_and_malformed_dataset_items():
    invalid_json = ScriptedClient([response(200, text="not json")])
    with pytest.raises(ApifyMalformedResponseError, match="invalid JSON"):
        make_client(invalid_json).dataset_items("ds-1")

    invalid_items = ScriptedClient([response(200, ["not-an-object"])])
    with pytest.raises(ApifyMalformedResponseError, match="list of objects"):
        make_client(invalid_items).dataset_items("ds-1")
