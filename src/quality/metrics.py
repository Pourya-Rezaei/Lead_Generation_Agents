from ..domain import Lead, popularity_score
from .models import QualityMetrics


def metrics(lead: Lead) -> QualityMetrics:
    fields = {"name": bool(lead.name), "address": bool(lead.address), "phone": bool(lead.phone), "website": bool(lead.website), "category": bool(lead.category)}
    weights = {"name": 15, "address": 25, "phone": 25, "website": 25, "category": 10}
    completeness = sum(weights[key] for key, present in fields.items() if present)
    return QualityMetrics(completeness=float(completeness), popularity=popularity_score(lead), field_confidence={key: None for key in fields})
