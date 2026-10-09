from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from typing import Any

from .domain import Lead


@dataclass(frozen=True)
class ProfileCandidate:
    url: str
    title: str
    evidence: tuple[str, ...]
    confidence: float
    status: str


@dataclass(frozen=True)
class EnrichmentRequest:
    lead_id: str
    business_name: str
    city: str
    domain: str | None = None
    limit: int = 5

    @property
    def query(self) -> str:
        return " ".join(part for part in (self.business_name, self.city) if part.strip())


@dataclass(frozen=True)
class EnrichmentResult:
    lead_id: str
    query: str
    candidates: tuple[ProfileCandidate, ...]
    discarded_count: int = 0


def build_enrichment_request(lead: Lead, *, lead_id: str, city: str, limit: int = 5) -> EnrichmentRequest:
    if not lead_id.strip():
        raise ValueError("lead_id is required for enrichment")
    if not city.strip() or limit < 1:
        raise ValueError("city must be non-empty and limit must be positive")
    domain = urlsplit(str(lead.website)).hostname if lead.website else None
    return EnrichmentRequest(lead_id, lead.name, city.strip(), domain, limit)


def map_search_candidates(request: EnrichmentRequest, items: list[dict[str, Any]]) -> EnrichmentResult:
    candidates: list[ProfileCandidate] = []
    discarded = 0
    for item in items[: request.limit]:
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not url or not url.startswith("https://"):
            discarded += 1
            continue
        text = " ".join(str(item.get(key, "")) for key in ("title", "description", "snippet")).lower()
        if request.city.lower() not in text:
            discarded += 1
            continue
        evidence = ("google-search-result", "city-match")
        domain = urlsplit(url).hostname or ""
        status = "probable" if request.domain and domain.removeprefix("www.") == request.domain.removeprefix("www.") else "unverified"
        confidence = 0.9 if status == "probable" else 0.5
        candidates.append(ProfileCandidate(url, title, evidence, confidence, status))
    return EnrichmentResult(request.lead_id, request.query, tuple(candidates), discarded)


def match_profile_candidate(
    lead: Lead,
    candidate: ProfileCandidate,
    *,
    first_party_link: bool = False,
    consistent_business_evidence: bool = False,
) -> ProfileCandidate:
    """Apply conservative business-profile matching; never infer an owner."""
    evidence = tuple(candidate.evidence)
    if first_party_link and consistent_business_evidence:
        return ProfileCandidate(candidate.url, candidate.title, evidence + ("first-party-link",), max(candidate.confidence, 0.98), "confirmed")
    if consistent_business_evidence:
        return ProfileCandidate(candidate.url, candidate.title, evidence + ("business-evidence",), max(candidate.confidence, 0.75), "probable")
    return ProfileCandidate(candidate.url, candidate.title, evidence, min(candidate.confidence, 0.5), "unverified")


def enrich_lead(lead: Lead, candidates: list[ProfileCandidate]) -> list[ProfileCandidate]:
    domain = (urlsplit(str(lead.website)).hostname or "").removeprefix("www.") if lead.website else ""
    result: list[ProfileCandidate] = []
    for candidate in candidates:
        candidate_domain = (urlsplit(candidate.url).hostname or "").removeprefix("www.")
        if domain and candidate_domain == domain:
            result.append(ProfileCandidate(candidate.url, candidate.title, candidate.evidence + ("same-official-domain",), max(candidate.confidence, 0.9), "probable"))
        else:
            result.append(candidate)
    return result
