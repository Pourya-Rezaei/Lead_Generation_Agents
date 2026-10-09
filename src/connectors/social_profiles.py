from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


PLATFORM_HOSTS = {
    "instagram": {"instagram.com"},
    "youtube": {"youtube.com", "youtu.be"},
    "tiktok": {"tiktok.com"},
}
_CONTACT_HOSTS = {"instagram.com", "youtube.com", "youtu.be", "tiktok.com", "wa.me", "whatsapp.com", "telegram.me", "t.me"}
_INVISIBLE = str.maketrans({char: " " for char in "\u200b\u200c\u200d\u200e\u200f\ufeff"})


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.translate(_INVISIBLE).split())
    return text or None


def _https_url(value: object, *, hosts: set[str] | None = None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if parsed.scheme.lower() != "https" or not host or (hosts is not None and host not in hosts):
        return None
    return urlunsplit(("https", host, parsed.path.rstrip("/"), parsed.query, ""))


def normalize_contact_links(values: object, platform: str) -> tuple[str, ...]:
    """Keep only deterministic HTTPS links to known professional contact surfaces."""
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return ()
    allowed = PLATFORM_HOSTS.get(platform, set()) | _CONTACT_HOSTS
    return tuple(sorted({_https_url(value, hosts=allowed) for value in values if _https_url(value, hosts=allowed)}))


class SocialProfileInput(BaseModel):
    """Contract-gated, public profile input; no person or audience fields are accepted."""

    model_config = ConfigDict(extra="forbid")
    profile_url: HttpUrl
    query: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)

    @field_validator("profile_url")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("profile_url must use HTTPS")
        return value


class InstagramProfileInput(SocialProfileInput):
    platform: ClassVar[str] = "instagram"


class YouTubeProfileInput(SocialProfileInput):
    platform: ClassVar[str] = "youtube"


class TikTokProfileInput(SocialProfileInput):
    platform: ClassVar[str] = "tiktok"


@dataclass(frozen=True)
class ActorContract:
    actor: str
    platform: str
    enabled: bool = False
    contract_status: str = "unverified"
    pricing_status: str = "not_verified"
    execution_policy: str = "disabled_no_paid_calls"
    request_fields: tuple[str, ...] = ("profile_url", "query", "location")
    output_fields: tuple[str, ...] = (
        "url", "title", "bio", "location", "website", "contact_links", "metadata"
    )
    excluded_fields: tuple[str, ...] = (
        "email", "owner", "reviewer", "commenter", "comments", "audience", "viewer"
    )


@dataclass(frozen=True)
class ActorRequest:
    actor: str
    payload: Mapping[str, object]
    executable: bool = False
    reason: str = "actor_contract_unverified"


@dataclass(frozen=True)
class SocialProfileObservation:
    platform: str
    url: str
    title: str
    bio: str | None
    official_url: str | None
    status: str
    location: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    contact_links: tuple[str, ...] = ()


class DisabledSocialProfileConnector:
    enabled = False

    def __init__(self, platform: str, actor: str):
        self.platform = platform
        self.actor = actor
        self.contract = ActorContract(actor=actor, platform=platform)

    def build_request(self, request: SocialProfileInput) -> ActorRequest:
        """Build a non-executable, privacy-filtered request preview.

        Actor input schemas and pricing are intentionally unverified; this method
        never authorizes or performs a paid call.
        """
        payload = {"profile_url": str(request.profile_url)}
        if request.query is not None:
            payload["query"] = request.query
        if request.location is not None:
            payload["location"] = request.location
        return ActorRequest(self.actor, payload, executable=False)

    def status(self, raw_status: object) -> str:
        """Return a stable status without exposing provider response details."""
        if not isinstance(raw_status, str):
            return "malformed_status"
        normalized = raw_status.upper()
        return {"READY": "pending", "RUNNING": "running", "SUCCEEDED": "succeeded",
                "FAILED": "failed", "ABORTED": "aborted", "TIMED-OUT": "timed_out"}.get(
            normalized, "unknown_status"
        )

    def execute(self, request: SocialProfileInput) -> tuple[None, str]:
        del request
        return None, "disabled_actor_contract_unverified"

    def map_public_profile(self, item: dict[str, Any]) -> SocialProfileObservation | None:
        """Map a provider record without retaining private, commenter, or audience data."""
        if not isinstance(item, dict) or item.get("isPrivate") is True or item.get("private") is True:
            return None
        url = _https_url(item.get("url") or item.get("profileUrl") or item.get("channelUrl"), hosts=PLATFORM_HOSTS[self.platform])
        title = item.get("title") or item.get("username") or item.get("channelName")
        if url is None or not isinstance(title, str) or not title.strip():
            return None
        official_url = _https_url(item.get("website") or item.get("externalUrl"))
        metadata_keys = {"category", "followers", "subscribers", "videoCount", "verified"}
        metadata = tuple(sorted((key, str(item[key]).strip()) for key in metadata_keys if item.get(key) not in (None, "", [], {})))
        contact_values = item.get("contactLinks") or item.get("links") or item.get("externalLinks") or []
        return SocialProfileObservation(
            self.platform, url, _clean_text(title) or "",
            _clean_text(item.get("bio")), official_url, "unverified", _clean_text(item.get("location")),
            metadata, normalize_contact_links(contact_values, self.platform),
        )

    def map_public_profile_safe(self, item: object) -> tuple[SocialProfileObservation | None, str | None]:
        """Return a stable error code instead of exposing provider exceptions or raw data."""
        if not isinstance(item, dict):
            return None, "malformed_record"
        if item.get("isPrivate") is True or item.get("private") is True:
            return None, "private_profile"
        if item.get("commenters") is not None or item.get("comments") is not None:
            item = {key: value for key, value in item.items() if key not in {"commenters", "comments"}}
        if any(key in item for key in ("audience", "audienceData", "viewerData")):
            item = {key: value for key, value in item.items() if key not in {"audience", "audienceData", "viewerData"}}
        observation = self.map_public_profile(item)
        return (observation, None) if observation else (None, "malformed_record")


INSTAGRAM = DisabledSocialProfileConnector("instagram", "apify~instagram-scraper")
TIKTOK = DisabledSocialProfileConnector("tiktok", "clockworks~tiktok-scraper")
YOUTUBE = DisabledSocialProfileConnector("youtube", "streamers~youtube-scraper")

SOCIAL_ACTOR_ADAPTERS = {"instagram": INSTAGRAM, "tiktok": TIKTOK, "youtube": YOUTUBE}
