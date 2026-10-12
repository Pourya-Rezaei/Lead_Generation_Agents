from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .connectors.base import Connector
from .connectors.apify_places import ApifyPlacesConnector
from .connectors.instagram_search import InstagramDiscoveryConnector

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
    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings
        self._factories: dict[str, ConnectorFactory] = {
            "places": lambda settings: ApifyPlacesConnector(
                settings.apify_api_token or "", settings.http_timeout
            ),
            "instagram": lambda settings: InstagramDiscoveryConnector(
                settings.apify_api_token or "", settings.http_timeout
            ),
        }
        self._capabilities = (
            SourceCapability("places", "google_maps", ApifyPlacesConnector.actor, True, "Google Places business listings"),
            SourceCapability("instagram", "instagram", InstagramDiscoveryConnector.actor, True, "Independent standard profile search; no geographic guarantee"),
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
        if len(selected) != 1:
            raise ValueError("exactly one source must be selected")
        if len(set(selected)) != len(selected):
            raise ValueError("sources must be unique")
        for name in selected:
            self.validate_source(name)
        return tuple(self._capability_by_name[name] for name in selected)

    def create(self, name: str, settings: Any) -> Connector:
        self.validate_source(name)
        return self._factories[name](settings)
