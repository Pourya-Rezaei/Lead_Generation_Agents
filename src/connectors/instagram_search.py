from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from ..apify import ApifyClient
from ..errors import ApifyMalformedResponseError, ApifyTransientError, ApifyStartOutcomeUnknown
from ..results import map_apify_status
from ..source_contracts import InstagramRecord

SOURCE = "instagram"
ACTOR = "apify~instagram-search-scraper"
PROFILE_FIELDS = frozenset({"id", "username", "url", "fullName", "externalUrl", "businessCategoryName", "isBusinessAccount", "private", "verified", "biography", "followersCount", "followsCount", "postsCount", "externalUrls"})
_RESERVED = frozenset({"p", "reel", "reels", "stories", "explore", "accounts", "direct", "about", "developer", "legal", "web", "api", "tv"})


def canonical_profile_url(value: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("invalid Instagram profile URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc not in {"instagram.com", "www.instagram.com"}
            or parsed.query or parsed.fragment):
        raise ValueError("invalid Instagram profile URL")
    match = re.fullmatch(r"/([A-Za-z0-9_][A-Za-z0-9_.]{0,29})/?", parsed.path)
    if not match or match[1].lower() in _RESERVED or match[1].isdigit() or match[1].endswith(".") or ".." in match[1]:
        raise ValueError("invalid Instagram profile URL")
    return f"https://www.instagram.com/{match[1].lower()}/"


def project_profile(item: dict[str, Any], expected_url: str) -> dict[str, Any] | None:
    # Standard search aliases are normalized before privacy projection.
    aliases = {"profileUrl": "url", "name": "fullName", "isBusiness": "isBusinessAccount", "isPrivate": "private"}
    normalized = dict(item)
    for alias, canonical in aliases.items():
        if canonical not in normalized and alias in normalized:
            normalized[canonical] = normalized[alias]
    # Never pass provider objects (including nested values) across the ingestion boundary.
    projected = {key: value for key, value in normalized.items() if key in PROFILE_FIELDS
                 and ((key in {"private", "verified", "isBusinessAccount"} and type(value) is bool)
                      or (key in {"id", "username", "url", "fullName", "externalUrl", "businessCategoryName", "biography"} and isinstance(value, str) and len(value) <= (2200 if key == "biography" else 500))
                      or (key in {"followersCount", "followsCount", "postsCount"} and type(value) is int and value >= 0))}
    links = []
    for candidate in normalized.get("externalUrls", [])[:20] if isinstance(normalized.get("externalUrls"), list) else []:
        value = candidate.get("url") if isinstance(candidate, dict) and candidate.get("link_type") != "facebook" else None
        if not isinstance(value, str) or len(value) > 2048:
            continue
        try:
            parsed = urlsplit(value)
            if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password and not any(ord(char) < 32 for char in value):
                if value not in links:
                    links.append(value)
        except ValueError:
            continue
    if links:
        projected["externalUrls"] = links
    item.clear()
    if projected.get("private") is not False:
        return None
    username = projected.get("username")
    if not username:
        return None
    try:
        if canonical_profile_url(f"https://www.instagram.com/{username}/") != expected_url:
            return None
        if "url" in projected and canonical_profile_url(projected["url"]) != expected_url:
            return None
    except ValueError:
        return None
    projected["url"] = expected_url
    projected["username"] = expected_url.rstrip("/").rsplit("/", 1)[-1]
    external = projected.get("externalUrl")
    if external:
        try:
            parsed = urlsplit(external)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or any(ord(char) < 32 for char in external):
                projected.pop("externalUrl")
        except ValueError:
            projected.pop("externalUrl")
    return projected


class InstagramDiscoveryConnector:
    actor = ACTOR
    source = "instagram"

    def __init__(self, token: str, timeout: float = 30, client: ApifyClient | None = None):
        self.client = client or ApifyClient(token, timeout)
        self.last_run: dict[str, Any] = {}
        self.failure_metadata: dict[str, Any] = {}

    def abort(self, run_id: str):
        return self.client.abort_run(run_id)

    def _notify(self, run_id, dataset_id, status):
        callback = getattr(self, "on_provider_run", None)
        if callable(callback):
            callback(self.source, run_id, dataset_id, status)

    @staticmethod
    def _allowlist(item: dict[str, Any]) -> dict[str, Any] | None:
        username = item.get("username")
        url = item.get("url") or item.get("profileUrl")
        if not isinstance(url, str) and (not isinstance(username, str) or not username):
            return None
        try:
            identity = canonical_profile_url(url if isinstance(url, str) else f"https://www.instagram.com/{username}/")
        except ValueError:
            return None
        normalized = dict(item)
        if normalized.get("username") in (None, ""):
            normalized["username"] = identity.rstrip("/").rsplit("/", 1)[-1]
        return project_profile(normalized, identity)

    def search(self, query: str, location: str = "", limit: int = 10):
        from ..search_requests import InstagramSearchRequest
        if location:
            raise ValueError("Instagram does not accept location")
        actor_input = InstagramSearchRequest(search=query, searchLimit=limit).actor_input()
        try:
            run = self.client.start_actor(self.actor, actor_input, wait_for_finish=0)
        except ApifyStartOutcomeUnknown:
            self.failure_metadata = {"failure_stage": "start", "failure_code": "start_unknown"}
            self._notify(None, None, "start_unknown")
            raise
        except Exception as error:
            self.failure_metadata = {"failure_stage": "start", "failure_code": "rate_limited" if isinstance(error, ApifyTransientError) and "rate-limited" in str(error) else "start_failed"}
            self._notify(None, None, "failed")
            raise
        run_id = run.get("id")
        if not isinstance(run_id, str) or not run_id:
            self._notify(None, None, "start_unknown")
            raise ApifyStartOutcomeUnknown("Instagram start response has no run ID")
        self.last_run = {"run_id": run_id}
        self.failure_metadata = {"provider_run_id": run_id}
        self._notify(run_id, run.get("defaultDatasetId"), "running")
        return self.search_existing_run(run_id, query, limit)

    def search_existing_run(self, run_id: str, query: str, limit: int = 20):
        from datetime import datetime, timezone
        from ..results import RunStatus, SearchResult
        del query
        started = datetime.now(timezone.utc)
        self.failure_metadata = {"provider_run_id": run_id}
        try:
            run = self.client.wait_for_run(run_id, timeout=300, poll_interval=2)
        except ApifyTransientError as error:
            self.failure_metadata.update(failure_stage="polling", failure_code="poll_timeout" if "polling timed out" in str(error).lower() else "poll_failed")
            self._notify(run_id, None, "timed_out" if "polling timed out" in str(error).lower() else "failed")
            raise
        except Exception:
            self._notify(run_id, None, "failed")
            raise
        try:
            status = map_apify_status(str(run.get("status", "")))
        except ValueError:
            self._notify(run_id, None, "failed")
            raise ApifyMalformedResponseError("Instagram run status is unknown") from None
        dataset_id = run.get("defaultDatasetId")
        if status is not RunStatus.SUCCEEDED:
            self._notify(run_id, dataset_id, status.value)
            return SearchResult(source=self.source, run_id=run_id, dataset_id=dataset_id, status=status, started_at=started, finished_at=datetime.now(timezone.utc))
        if not isinstance(dataset_id, str) or not dataset_id:
            self._notify(run_id, None, "failed")
            raise ApifyMalformedResponseError("Instagram successful run has no dataset ID")
        self._notify(run_id, dataset_id, "fetching_dataset")
        records, projections, reasons = [], [], {}
        received = 0
        seen = set()
        seen_ids = set()
        try:
            for page in self.client.iter_dataset_items(dataset_id, max_items=min(limit, 250)):
                for item in page:
                    received += 1
                    reason = None
                    if not isinstance(item, dict) or not any(key in item for key in ("username", "profileUrl", "private", "isPrivate", "isBusinessAccount", "isBusiness")):
                        reason = "unknown_schema"
                    elif item.get("private", item.get("isPrivate")) is True:
                        reason = "private_profile"
                    elif item.get("private", item.get("isPrivate")) is not False:
                        reason = "privacy_unverified"
                    record = self._allowlist(item) if reason is None else None
                    if isinstance(item, dict):
                        item.clear()
                    if record is None:
                        reason = reason or "invalid_identity"
                    elif record["url"] in seen or (record.get("id") and record["id"] in seen_ids):
                        reason = "duplicate_profile"
                    if reason:
                        reasons[reason] = reasons.get(reason, 0) + 1
                        continue
                    seen.add(record["url"])
                    if record.get("id"):
                        seen_ids.add(record["id"])
                    record["fullName"] = " ".join((record.get("fullName") or record["username"]).split()) or record["username"]
                    records.append(record)
                    projections.append(InstagramRecord(username=record["username"], full_name=record["fullName"], source_id=record.get("id"), source_url=record["url"], external_url=record.get("externalUrl"), business_category=record.get("businessCategoryName"), verified=record.get("verified"), private=False, biography=record.get("biography"), is_business_account=record.get("isBusinessAccount"), external_links=record.get("externalUrls", []) + ([record["externalUrl"]] if record.get("externalUrl") else []), followers_count=record.get("followersCount"), follows_count=record.get("followsCount"), posts_count=record.get("postsCount")))
                page.clear()
        except Exception:
            self.failure_metadata.update(failure_stage="dataset", failure_code="dataset_failed", received_count=received, accepted_count=len(records), rejected_count=received-len(records), rejection_reasons=reasons)
            self._notify(run_id, dataset_id, "failed")
            raise
        self.failure_metadata.update(received_count=received, accepted_count=len(records), rejected_count=received-len(records), rejection_reasons=reasons)
        if received and not records and reasons.get("unknown_schema") == received:
            self.failure_metadata.update(failure_stage="contract", failure_code="unknown_schema")
            self._notify(run_id, dataset_id, "failed")
            raise ApifyMalformedResponseError("Instagram profile dataset contract mismatch")
        self._notify(run_id, dataset_id, "succeeded")
        return SearchResult(source=self.source, run_id=run_id, dataset_id=dataset_id, status=RunStatus.SUCCEEDED, raw_records=records, projections=projections, received_count=received, accepted_count=len(records), rejected_count=received-len(records), rejection_reasons=reasons, warnings=["instagram_no_public_profiles"] if not records else [], started_at=started, finished_at=datetime.now(timezone.utc))
