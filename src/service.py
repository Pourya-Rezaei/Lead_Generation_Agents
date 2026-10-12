from datetime import datetime, timezone

from .config import Settings
from .errors import (
    ApifyCredentialError,
    ApifyError,
    ApifyMalformedResponseError,
    ApifyNotFoundError,
    ApifyStartOutcomeUnknown,
    ApifyTransientError,
    CampaignNotFoundError,
    ProviderAbortOutcomeUnknown,
)
from .registry import ConnectorRegistry, SourceCapability
from .results import SearchResult
from .storage import LeadStore


def _safe_error_summary(error: Exception) -> str:
    if isinstance(error, ApifyCredentialError):
        return "Apify rejected the configured credentials."
    if isinstance(error, ApifyNotFoundError):
        return "Apify actor or endpoint was not found."
    if isinstance(error, ApifyStartOutcomeUnknown):
        return "Apify Actor start outcome is unknown and requires review."
    if isinstance(error, ProviderAbortOutcomeUnknown):
        return "Provider run abort outcome is unknown and requires review."
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
        if registry is not None:
            self.registry = registry
        else:
            try:
                self.registry = ConnectorRegistry(settings)
            except TypeError:
                # Preserve compatibility with test/integration registries using the legacy no-arg constructor.
                self.registry = ConnectorRegistry()
        self.last_provider_run_id: str | None = None
        self.last_persisted_refs: dict[str, object] = {}

    def source_capabilities(self) -> tuple[SourceCapability, ...]:
        """Describe selectable sources without constructing or running connectors."""
        return self.registry.capabilities()

    def select_sources(self, sources: list[str] | tuple[str, ...]) -> tuple[SourceCapability, ...]:
        """Validate a multi-source selection before any Actor can be activated."""
        return self.registry.select_sources(sources)

    def abort_provider_run(self, source: str, run_id: str) -> dict[str, object]:
        if not run_id.strip():
            raise ValueError("run_id must not be empty")
        connector = self.registry.create(source, self.settings)
        return connector.abort(run_id)

    def search(
        self,
        query: str,
        location: str,
        source: str = "places",
        limit: int = 20,
        campaign_id: str | None = None,
        provider_run_id: str | None = None,
        on_provider_run=None,
    ) -> SearchResult:
        self.registry.validate_source(source)
        if source == "instagram":
            from .search_requests import InstagramSearchRequest
            validated = InstagramSearchRequest(search=query, searchLimit=limit)
            if location:
                raise ValueError("Instagram does not accept location")
            query = validated.search
        if not query.strip() or (source == "places" and not location.strip()):
            raise ValueError("query and location must not be empty")
        if limit < 1 or limit > (250 if source == "instagram" else self.settings.max_limit):
            raise ValueError(f"limit must be between 1 and {self.settings.max_limit}")
        if source == "instagram":
            campaign_data = self.store.get_instagram_campaign(campaign_id) if campaign_id else None
            if campaign_data is None:
                raise ValueError("Select an existing Instagram campaign")
            from .domain import Campaign
            campaign = Campaign(**campaign_data)
        else:
            campaign = self.store.get_campaign(campaign_id) if campaign_id is not None else self.store.default_campaign()
        if campaign is None:
            raise CampaignNotFoundError(f"campaign not found: {campaign_id}")
        self.registry.validate_source(source)
        started_at = datetime.now(timezone.utc)
        connector = None
        try:
            if not self.settings.apify_api_token:
                raise ValueError(f"APIFY_API_TOKEN is required for {source}")
            connector = self.registry.create(source, self.settings)
            if callable(on_provider_run):
                connector.on_provider_run = on_provider_run
            resume = getattr(connector, "search_existing_run", None)
            if provider_run_id:
                if not callable(resume):
                    raise RuntimeError("connector cannot safely resume the persisted provider run")
                result = resume(provider_run_id, query, limit)
            else:
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
                        getattr(connector, "failure_metadata", None) if connector is not None else None
                    ),
                )
            except Exception:
                # A provider failure must retain its safe public classification even
                # when failure journaling is unavailable (for example, a transient
                # SQLite error). Do not replace it with a 500-inducing wrapper.
                pass
            raise
        summary = self.store.persist_search_result(campaign.campaign_id, result, query, location)
        self.last_persisted_refs = {
            "lead_ids": list(summary.lead_ids),
            "run_id": result.run_id,
            "campaign_id": campaign.campaign_id,
            "observation_ids": list(summary.observation_ids),
            "raw_record_refs": [
                {"run_id": ref_run_id, "record_index": record_index}
                for ref_run_id, record_index in summary.raw_record_refs
            ],
        }
        if source == "instagram":
            self.last_persisted_refs["source"] = "instagram"
        return result
