from .models import MatchDecision
from .normalization import CanonicalLead


def match(incoming: CanonicalLead, candidates: list[CanonicalLead]) -> MatchDecision:
    if incoming.source_id and incoming.source:
        for candidate in candidates:
            if candidate.source == incoming.source and candidate.source_id == incoming.source_id:
                return MatchDecision(action="merge", candidate_lead_id=candidate.lead_id, confidence=1.0, reasons=("same-source-id",))
    for candidate in candidates:
        if incoming.domain and incoming.domain == candidate.domain:
            if incoming.address and candidate.address and incoming.address == candidate.address:
                return MatchDecision(action="merge", candidate_lead_id=candidate.lead_id, confidence=0.95, reasons=("same-domain", "same-address"))
            if incoming.address and candidate.address and incoming.address != candidate.address:
                return MatchDecision(action="separate", confidence=0.0, reasons=("same-domain-different-address",))
            if incoming.phone and candidate.phone and incoming.phone == candidate.phone:
                return MatchDecision(action="review", candidate_lead_id=candidate.lead_id, confidence=0.7, reasons=("shared-domain", "shared-phone"))
            return MatchDecision(action="review", candidate_lead_id=candidate.lead_id, confidence=0.7, reasons=("shared-domain",))
        if incoming.phone and candidate.phone and incoming.phone == candidate.phone:
            return MatchDecision(action="review", candidate_lead_id=candidate.lead_id, confidence=0.7, reasons=("shared-phone",))
    return MatchDecision(action="separate", confidence=0.0, reasons=("no-sufficient-evidence",))
