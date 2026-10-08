from abc import ABC, abstractmethod

from ..results import SearchResult


class Connector(ABC):
    @property
    def failure_metadata(self) -> dict[str, str]:
        return {}

    @abstractmethod
    def search(self, query: str, location: str, limit: int = 20) -> SearchResult: ...


class SocialConnector(Connector):
    enabled = False

    def search(self, query: str, location: str, limit: int = 20) -> SearchResult:
        raise NotImplementedError("Social connectors are feature-disabled")
