from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SocialProfileObservation:
    platform: str
    url: str
    title: str
    bio: str | None
    official_url: str | None
    status: str


class DisabledSocialProfileConnector:
    enabled = False

    def __init__(self, platform: str, actor: str):
        self.platform = platform
        self.actor = actor

    def map_public_profile(self, item: dict[str, Any]) -> SocialProfileObservation | None:
        url = item.get("url") or item.get("profileUrl") or item.get("channelUrl")
        if not isinstance(url, str) or urlsplit(url).scheme != "https":
            return None
        title = item.get("title") or item.get("username") or item.get("channelName")
        if not isinstance(title, str) or not title.strip():
            return None
        official_url = item.get("website") or item.get("externalUrl")
        return SocialProfileObservation(self.platform, url, title.strip(), item.get("bio") if isinstance(item.get("bio"), str) else None, official_url if isinstance(official_url, str) else None, "unverified")


INSTAGRAM = DisabledSocialProfileConnector("instagram", "apify~instagram-scraper")
TIKTOK = DisabledSocialProfileConnector("tiktok", "clockworks~tiktok-scraper")
YOUTUBE = DisabledSocialProfileConnector("youtube", "streamers~youtube-scraper")
