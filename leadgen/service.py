from .config import Settings
from .registry import ConnectorRegistry
from .results import SearchResult
from .storage import LeadStore


class SearchLeadsService:
    def __init__(self, settings: Settings, store: LeadStore | None = None, registry: ConnectorRegistry | None = None) -> None:
        self.settings = settings
        self.store = store or LeadStore(settings.database_path)
        self.registry = registry or ConnectorRegistry()

    def search(self, query: str, location: str, source: str = "places", limit: int = 20) -> SearchResult:
        if not query.strip() or not location.strip():
            raise ValueError("query and location must not be empty")
        if limit < 1 or limit > self.settings.max_limit:
            raise ValueError(f"limit must be between 1 and {self.settings.max_limit}")
        if source == "places" and not self.settings.apify_api_token:
            raise ValueError("APIFY_API_TOKEN is required for places")
        connector = self.registry.create(source, self.settings)
        result = connector.search(query, location, limit)
        if result.leads:
            self.store.upsert(result.leads)
        metadata = result.model_dump(mode="json", exclude={"leads", "raw_records"})
        metadata.update({"query": query, "location": location, "status": result.status.value})
        self.store.record_run(metadata, result.raw_records)
        return result
