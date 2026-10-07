from collections.abc import Callable
from typing import Any

from .connectors.base import Connector
from .connectors.apify_places import ApifyPlacesConnector
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
        }

    def create(self, name: str, settings: Any) -> Connector:
        if name == "web":
            raise DisabledSourceError("source 'web' is disabled")
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise ValueError(f"unknown source: {name}") from exc
        return factory(settings)
