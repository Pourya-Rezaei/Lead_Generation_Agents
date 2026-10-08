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
