from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .registry import ConnectorRegistry, DisabledSourceError, SourceCapability
from .results import PlatformSearchResult


class SocialSearchRequest(BaseModel):
    """Explicit, platform-independent request for public social discovery."""

    model_config = ConfigDict(extra="forbid")

    sources: tuple[str, ...] = Field(min_length=1)
    profile_urls: tuple[str, ...] = ()
    query: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_mode(self) -> "SocialSearchRequest":
        has_profiles = bool(self.profile_urls)
        has_query = bool(self.query and self.query.strip())
        if has_profiles == has_query:
            raise ValueError("provide either profile_urls or query, but not both")
        if any(not url.startswith("https://") for url in self.profile_urls):
            raise ValueError("profile_urls must use HTTPS")
        if self.query is not None and not self.query.strip():
            raise ValueError("query must not be empty")
        if self.location is not None and not self.location.strip():
            raise ValueError("location must not be empty")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("sources must be unique")
        return self

    @property
    def mode(self) -> str:
        return "profiles" if self.profile_urls else "keywords"


SocialExecutor = Callable[[SocialSearchRequest, tuple[SourceCapability, ...]], Sequence[PlatformSearchResult]]


class SocialSearchService:
    """Validate social requests before handing them to any provider executor.

    The default registry intentionally has no social executors. This service is
    therefore safe to expose to API/CLI callers without activating paid Actors.
    """

    def __init__(self, registry: ConnectorRegistry | None = None, executor: SocialExecutor | None = None) -> None:
        self.registry = registry or ConnectorRegistry()
        self.executor = executor

    def source_capabilities(self) -> tuple[SourceCapability, ...]:
        return tuple(capability for capability in self.registry.capabilities() if capability.platform in {"instagram", "tiktok", "youtube"})

    def validate(self, request: SocialSearchRequest) -> tuple[SourceCapability, ...]:
        return self.registry.select_sources(request.sources)

    def search(self, request: SocialSearchRequest) -> tuple[PlatformSearchResult, ...]:
        selected = self.validate(request)
        if self.executor is None:
            raise DisabledSourceError("social search is disabled; no provider executor is enabled")
        return tuple(self.executor(request, selected))
