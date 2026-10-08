import pytest

from leadgen.connectors.apify_places import ApifyPlacesConnector
from leadgen.results import RunStatus, SearchResult


class FakeApifyClient:
    def __init__(self, run, dataset=None):
        self.run = run
        self.dataset = [] if dataset is None else dataset
        self.actor_calls = []
        self.dataset_calls = []

    def run_actor(self, actor, input_data, *, wait_for_finish=60):
        self.actor_calls.append((actor, input_data, wait_for_finish))
        return self.run

    def dataset_items(self, dataset_id):
        self.dataset_calls.append(dataset_id)
        return self.dataset


def connector(run, dataset=None):
    client = FakeApifyClient(run, dataset)
    return ApifyPlacesConnector(client=client), client


def test_sends_exact_actor_input_and_returns_search_result():
    places, client = connector(
        {"id": "run-1", "defaultDatasetId": "ds-1", "status": "SUCCEEDED"},
        [{"title": "Cafe", "address": "A St", "rating": 4.5}],
    )

    result = places.search("cafe", "town", limit=7)

    assert isinstance(result, SearchResult)
    assert client.actor_calls == [
        (
            "compass~crawler-google-places",
            {
                "searchStringsArray": ["cafe"],
                "locationQuery": "town",
                "maxCrawledPlacesPerSearch": 7,
            },
            60,
        )
    ]
    assert client.dataset_calls == ["ds-1"]
    assert result.status is RunStatus.SUCCEEDED
    assert result.finished_at is not None


@pytest.mark.parametrize(
    ("actor_status", "expected"),
    [
        ("READY", RunStatus.PENDING),
        ("RUNNING", RunStatus.RUNNING),
        ("FAILED", RunStatus.FAILED),
        ("ABORTED", RunStatus.ABORTED),
        ("TIMED-OUT", RunStatus.TIMED_OUT),
    ],
)
def test_non_succeeded_runs_do_not_retrieve_dataset(actor_status, expected):
    places, client = connector(
        {"id": "run-1", "defaultDatasetId": "ds-1", "status": actor_status},
        [{"title": "must not be read"}],
    )

    result = places.search("cafe", "town")

    assert result.status is expected
    assert result.leads == []
    assert client.dataset_calls == []
    assert (result.finished_at is None) == (expected in {RunStatus.PENDING, RunStatus.RUNNING})


def test_missing_dataset_id_returns_failure_without_retrieval():
    places, client = connector({"id": "run-1", "status": "SUCCEEDED"})

    result = places.search("cafe", "town")

    assert result.status is RunStatus.FAILED
    assert result.run_id == "run-1"
    assert result.dataset_id is None
    assert result.finished_at is not None
    assert "dataset id" in result.warnings[0].lower()
    assert client.dataset_calls == []
    assert places.failure_metadata == {"provider_run_id": "run-1"}


@pytest.mark.parametrize("dataset", [[], {"items": []}])
def test_empty_list_and_dict_datasets_are_successful_with_warning(dataset):
    places, _ = connector(
        {"id": "run-1", "datasetId": "ds-1", "status": "SUCCEEDED"}, dataset
    )

    result = places.search("cafe", "town")

    assert result.status is RunStatus.SUCCEEDED
    assert result.leads == []
    assert result.raw_records == []
    assert result.warnings == ["Apify dataset was empty"]


@pytest.mark.parametrize(
    "dataset",
    [
        [{"title": "Cafe"}],
        {"items": [{"title": "Cafe"}]},
    ],
)
def test_list_and_dict_dataset_shapes_are_supported(dataset):
    places, _ = connector(
        {"id": "run-1", "defaultDatasetId": "ds-1", "status": "SUCCEEDED"},
        dataset,
    )

    result = places.search("cafe", "town")

    assert [lead.name for lead in result.leads] == ["Cafe"]


def test_maps_provenance_and_allowlists_raw_records():
    places, _ = connector(
        {"id": "run-9", "defaultDatasetId": "ds-9", "status": "SUCCEEDED"},
        [
            {
                "title": "Cafe",
                "address": "A St",
                "phone": "+1 555 0100",
                "website": "https://cafe.example/",
                "url": "https://www.google.com/maps/place/cafe",
                "placeId": "place-123",
                "rating": 4.8,
                "reviewsCount": 12,
                "ownerName": "Must not be retained",
                "scrapedAt": "2026-01-01T00:00:00Z",
            }
        ],
    )

    result = places.search("cafe", "town")

    lead = result.leads[0]
    assert result.run_id == "run-9"
    assert result.dataset_id == "ds-9"
    assert lead.source_id == "place-123"
    assert str(lead.source_url) == "https://www.google.com/maps/place/cafe"
    assert str(lead.website) == "https://cafe.example"
    assert result.raw_records == [
        {
            "title": "Cafe",
            "address": "A St",
            "phone": "+1 555 0100",
            "website": "https://cafe.example/",
            "url": "https://www.google.com/maps/place/cafe",
            "placeId": "place-123",
            "rating": 4.8,
            "reviewsCount": 12,
        }
    ]
    assert places.raw_items == result.raw_records
    assert places.last_run["run_id"] == "run-9"


def test_unknown_actor_status_is_rejected_before_dataset_retrieval():
    places, client = connector(
        {"id": "run-1", "defaultDatasetId": "ds-1", "status": "MYSTERY"}
    )

    with pytest.raises(ValueError, match="Unknown Apify run status"):
        places.search("cafe", "town")

    assert client.dataset_calls == []
