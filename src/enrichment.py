from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .domain import Lead


@dataclass(frozen=True)
class ProfileCandidate:
    url: str
    title: str
    evidence: tuple[str, ...]
    confidence: float
    status: str


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
