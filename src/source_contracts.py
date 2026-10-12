"""Typed, privacy-preserving projections for each discovery source.

These models deliberately keep source-specific fields separate from the shared Lead
identity. Raw provider payloads must not cross the connector boundary.
"""
from __future__ import annotations

from typing import Any, Literal, TypeAlias
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    source_id: str | None = None
    source_url: HttpUrl | str | None = None


class GooglePlacesRecord(SourceRecord):
    source: Literal["places"] = "places"
    name: str
    address: str = ""
    phone: str = ""
    website: HttpUrl | str | None = None
    category: str = ""
    rating: float | None = Field(default=None, ge=0, le=5)
    reviews_count: int | None = Field(default=None, ge=0)


class InstagramRecord(SourceRecord):
    source: Literal["instagram"] = "instagram"
    username: str
    source_url: str
    full_name: str | None = None
    address: str | None = None
    biography: str | None = None
    external_url: HttpUrl | str | None = None
    external_links: list[str] = Field(default_factory=list)
    business_category: str | None = None
    is_business_account: bool | None = None
    private: bool | None = None
    verified: bool | None = None
    followers_count: int | None = Field(default=None, ge=0)
    follows_count: int | None = Field(default=None, ge=0)
    posts_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_identity(self):
        from .connectors.instagram_search import canonical_profile_url
        canonical = canonical_profile_url(self.source_url)
        if canonical != canonical_profile_url(f"https://www.instagram.com/{self.username}/"):
            raise ValueError("Instagram page identity mismatch")
        self.source_url = canonical
        self.username = canonical.rstrip("/").rsplit("/", 1)[-1]
        self.full_name = " ".join((self.full_name or self.username).split()) or self.username
        from urllib.parse import urlsplit
        safe_links = []
        for value in [self.external_url, *self.external_links]:
            if not value:
                continue
            try:
                parsed = urlsplit(str(value))
                if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password and not any(ord(char) < 32 for char in str(value)) and str(value) not in safe_links:
                    safe_links.append(str(value))
            except ValueError:
                continue
        self.external_links = safe_links
        self.external_url = safe_links[0] if safe_links else None
        if self.private is not False:
            self.biography = None
            self.external_url = None
            self.external_links = []
            self.address = None
            self.followers_count = self.follows_count = self.posts_count = None
        return self


SourceProjection: TypeAlias = GooglePlacesRecord | InstagramRecord

SOURCE_ALLOWLISTS: dict[str, frozenset[str]] = {
    "places": frozenset({"title", "name", "address", "street", "phone", "phoneNumber", "website", "url", "categoryName", "rating", "reviewsCount", "placeId", "cid"}),
    "instagram": frozenset({"id", "username", "url", "fullName", "externalUrl", "businessCategoryName", "isBusinessAccount", "private", "verified", "biography", "followersCount", "followsCount", "postsCount", "externalUrls"}),
}


def allowlist_record(source: str, item: dict[str, Any]) -> dict[str, Any]:
    """Return only fields defined by the source contract; never mutate ``item``."""
    allowed = SOURCE_ALLOWLISTS.get(source, frozenset())
    return {key: value for key, value in item.items() if key in allowed}
