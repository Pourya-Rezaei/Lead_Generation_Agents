import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..domain import Lead, normalize

_ARABIC_CHARS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"})


@dataclass(frozen=True)
class CanonicalLead:
    lead_id: str | None
    name: str
    address: str
    phone: str
    domain: str
    source: str
    source_id: str | None
    country_code: str | None


def _canonical_text(value: str) -> str:
    return " ".join(value.translate(_ARABIC_CHARS).casefold().split())


def _domain(value: object) -> str:
    if not value:
        return ""
    return (urlsplit(str(value)).hostname or "").lower().removeprefix("www.")


def canonicalize(lead: Lead, country_code: str | None = None) -> CanonicalLead:
    item = normalize(lead)
    return CanonicalLead(
        lead_id=None,
        name=_canonical_text(item.name),
        address=_canonical_text(item.address),
        phone=item.phone,
        domain=_domain(item.website),
        source=_canonical_text(item.source),
        source_id=item.source_id,
        country_code=country_code,
    )
