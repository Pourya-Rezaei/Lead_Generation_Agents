from datetime import UTC, datetime

from .config import Settings
from .errors import (
    ApifyCredentialError,
    ApifyError,
    ApifyMalformedResponseError,
    ApifyNotFoundError,
    ApifyTransientError,
    CampaignNotFoundError,
    SearchAttemptPersistenceError,
)
from .registry import ConnectorRegistry
from .results import SearchResult
from .storage import LeadStore


def _safe_error_summary(error: Exception) -> str:
    if isinstance(error, ApifyCredentialError):
        return "Apify rejected the configured credentials."
    if isinstance(error, ApifyNotFoundError):
        return "Apify actor or endpoint was not found."
    if isinstance(error, ApifyTransientError):
        return "Apify request failed after retries."
    if isinstance(error, ApifyMalformedResponseError):
        return "Apify returned an invalid response."
    if isinstance(error, ApifyError):
        return "Apify request failed."
    if isinstance(error, ValueError) and str(error) == "APIFY_API_TOKEN is required for places":
        return "APIFY_API_TOKEN is required for places."
    if isinstance(error, ValueError) and str(error).startswith("APIFY_API_TOKEN is required for "):
        return "APIFY_API_TOKEN is required for the selected source."
    return "Search failed with an unexpected error."


class SearchLeadsService:
    def __init__(
        self,
        settings: Settings,
        store: LeadStore | None = None,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.store = store or LeadStore(settings.database_path)
        self.registry = registry or ConnectorRegistry()
        self.last_provider_run_id: str | None = None

    def search(
        self,
        query: str,
        location: str,
        source: str = "places",
        limit: int = 20,
        campaign_id: str | None = None,
    ) -> SearchResult:
        if not query.strip() or not location.strip():
            raise ValueError("query and location must not be empty")
        if limit < 1 or limit > self.settings.max_limit:
            raise ValueError(f"limit must be between 1 and {self.settings.max_limit}")
        campaign = (
            self.store.get_campaign(campaign_id)
            if campaign_id is not None
            else self.store.default_campaign()
        )
        if campaign is None:
            raise CampaignNotFoundError(f"campaign not found: {campaign_id}")
        self.registry.validate_source(source)
        started_at = datetime.now(UTC)
        connector = None
        try:
            if source in {"places", "google_search"} and not self.settings.apify_api_token:
                raise ValueError(f"APIFY_API_TOKEN is required for {source}")
            connector = self.registry.create(source, self.settings)
            result = connector.search(query, location, limit)
            metadata = getattr(connector, "failure_metadata", {})
            self.last_provider_run_id = (
                metadata.get("provider_run_id")
                if isinstance(metadata, dict)
                else None
            )
        except Exception as exc:
            try:
                self.store.record_failed_search(
                    campaign.campaign_id,
                    query,
                    location,
                    source,
                    type(exc).__name__,
                    _safe_error_summary(exc),
                    started_at=started_at,
                    failure_metadata=(
                        connector.failure_metadata if connector is not None else None
                    ),
                )
            except Exception as persistence_error:
                raise SearchAttemptPersistenceError(
                    f"Search failed ({type(exc).__name__}) and its failure record "
                    "could not be saved "
                    f"({type(persistence_error).__name__})."
                ) from exc
            raise
        self.store.persist_search_result(campaign.campaign_id, result, query, location)
        return result
