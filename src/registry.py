from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .connectors.base import Connector
from .connectors.apify_places import ApifyPlacesConnector
from .connectors.apify_google_search import ApifyGoogleSearchConnector
from .errors import ApifyError

ConnectorFactory = Callable[[Any], Connector]


class DisabledSourceError(ValueError):
    pass


@dataclass(frozen=True)
class SourceCapability:
    name: str
    platform: str
    actor: str | None
    enabled: bool
    description: str


class ConnectorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ConnectorFactory] = {
            "places": lambda settings: ApifyPlacesConnector(
                settings.apify_api_token or "", settings.http_timeout
            ),
            "google_search": lambda settings: ApifyGoogleSearchConnector(
                settings.apify_api_token or "", settings.http_timeout
            ),
        }
        self._capabilities = (
            SourceCapability("places", "google_maps", ApifyPlacesConnector.actor, True, "Google Places business listings"),
            SourceCapability("google_search", "google_search", ApifyGoogleSearchConnector.actor, True, "Google Search candidate results"),
            SourceCapability("instagram", "instagram", "apify~instagram-scraper", False, "Public business profiles (not enabled)"),
            SourceCapability("tiktok", "tiktok", "clockworks~tiktok-scraper", False, "Public business profiles (not enabled)"),
            SourceCapability("youtube", "youtube", "streamers~youtube-scraper", False, "Public business profiles (not enabled)"),
            SourceCapability("web", "web", None, False, "Web discovery (not enabled)"),
        )
        self._capability_by_name = {item.name: item for item in self._capabilities}

    def capabilities(self) -> tuple[SourceCapability, ...]:
        return self._capabilities

    def validate_source(self, name: str) -> None:
        capability = self._capability_by_name.get(name)
        if capability is None:
            raise ValueError(f"unknown source: {name}")
        if not capability.enabled:
            raise DisabledSourceError(f"source '{name}' is disabled")

    def select_sources(self, names: Iterable[str]) -> tuple[SourceCapability, ...]:
        selected = tuple(names)
        if not selected:
            raise ValueError("at least one source must be selected")
        if len(set(selected)) != len(selected):
            raise ValueError("sources must be unique")
        for name in selected:
            self.validate_source(name)
        return tuple(self._capability_by_name[name] for name in selected)

    def create(self, name: str, settings: Any) -> Connector:
        self.validate_source(name)
        return self._factories[name](settings)
