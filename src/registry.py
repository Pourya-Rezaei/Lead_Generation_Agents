from collections.abc import Callable
from typing import Any

from .connectors.base import Connector
from .connectors.apify_places import ApifyPlacesConnector
from .connectors.apify_google_search import ApifyGoogleSearchConnector
from .errors import ApifyError

ConnectorFactory = Callable[[Any], Connector]


class DisabledSourceError(ValueError):
    pass


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

    def validate_source(self, name: str) -> None:
        if name == "web":
            raise DisabledSourceError("source 'web' is disabled")
        if name not in self._factories:
            raise ValueError(f"unknown source: {name}")

    def create(self, name: str, settings: Any) -> Connector:
        self.validate_source(name)
        return self._factories[name](settings)
