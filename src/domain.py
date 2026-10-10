from datetime import datetime, timezone
import re
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, HttpUrl, field_validator

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_INVISIBLE_WHITESPACE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\u2060\ufeff]")


def _normalize_text(value: object) -> str:
    text = _INVISIBLE_WHITESPACE.sub(" ", str(value or ""))
    return " ".join(text.split())


def _normalize_phone(value: object) -> str:
    text = _normalize_text(value).translate(_DIGITS)
    has_plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith("98") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("09") and len(digits) == 11:
        return "+98" + digits[1:]
    return ("+" if has_plus else "") + digits


def _normalize_url(value: object) -> str | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    if any(char.isspace() for char in parsed.netloc) or parsed.username or parsed.password:
        raise ValueError("URL contains an invalid host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL contains an invalid port") from exc
    hostname = parsed.hostname.lower()
    if "." not in hostname and hostname != "localhost":
        raise ValueError("URL contains an invalid host")
    netloc = hostname
    if port is not None and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
        netloc += f":{port}"
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


class Campaign(BaseModel):
    campaign_id: str
    name: str
    description: str | None = None
    is_default: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("campaign_id", "name", mode="before")
    @classmethod
    def validate_required_text(cls, value: object) -> str:
        text = str(value or "").strip()
        normalized = " ".join(text.split())
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> str | None:
        if value is None:
            return None
        return _normalize_text(value) or None


class CampaignStats(BaseModel):
    campaign_id: str
    lead_count: int = Field(ge=0)
    run_count: int = Field(ge=0)


class Lead(BaseModel):
    name: str
    address: str = ""
    phone: str = ""
    website: HttpUrl | str | None = None
    category: str = ""
    source: str = ""
    rating: float | None = Field(default=None, ge=0, le=5)
    reviews: int | None = Field(default=None, ge=0)
    score: float = 0
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_id: str | None = None
    source_url: HttpUrl | str | None = None
    field_evidence: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator("field_evidence", mode="before")
    @classmethod
    def validate_field_evidence(cls, value: object) -> dict[str, tuple[str, ...]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("field_evidence must be an object")
        return {str(key): tuple(str(item).strip() for item in items if str(item).strip()) for key, items in value.items() if isinstance(items, (list, tuple, set))}

    @field_validator("field_confidence", mode="before")
    @classmethod
    def validate_field_confidence(cls, value: object) -> dict[str, float]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("field_confidence must be an object")
        return {str(key): float(item) for key, item in value.items()}

    @field_validator("field_confidence")
    @classmethod
    def validate_confidence_range(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0 <= confidence <= 1 for confidence in value.values()):
            raise ValueError("field confidence must be between 0 and 1")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        name = _normalize_text(value)
        if not name:
            raise ValueError("name must not be empty")
        return name

    @field_validator("website", "source_url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> str | None:
        return _normalize_url(value)

    def dedup_key(self) -> str:
        return "|".join((self.name.strip().lower(), self.address.strip().lower(), self.phone.strip()))


class LeadMatch(BaseModel):
    is_match: bool
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[str, ...] = ()

    @property
    def matched(self) -> bool:
        return self.is_match


def normalize(lead: Lead) -> Lead:
    data = lead.model_dump()
    for key in ("name", "address", "category", "source"):
        data[key] = _normalize_text(data[key])
    data["phone"] = _normalize_phone(data["phone"])
    data["source_id"] = _normalize_text(data.get("source_id")) or None
    for key in ("website", "source_url"):
        data[key] = _normalize_url(data.get(key))
    return Lead.model_validate(data)


def completeness_score(lead: Lead) -> float:
    return float((30 if lead.website else 0) + (20 if lead.phone else 0))


def popularity_score(lead: Lead) -> float:
    value = 0.0
    if lead.rating is not None:
        value += min(30, lead.rating * 6)
    if lead.reviews is not None:
        value += min(20, lead.reviews / 5)
    return round(value, 2)


def score(lead: Lead) -> float:
    return round(completeness_score(lead) + popularity_score(lead), 2)


def _domain(url: object) -> str:
    if not url:
        return ""
    hostname = urlsplit(str(url)).hostname or ""
    return hostname.lower().removeprefix("www.")


def identity_candidates(lead: Lead) -> tuple[str, ...]:
    normalized = normalize(lead)
    candidates: list[str] = []
    if normalized.source and normalized.source_id:
        candidates.append(f"source:{normalized.source.lower()}:{normalized.source_id.lower()}")
    if normalized.phone:
        candidates.append(f"phone:{normalized.phone}")
    domain = _domain(normalized.website)
    if domain:
        candidates.append(f"domain:{domain}")
    if normalized.address and normalized.name:
        candidates.append(f"address-name:{normalized.address.lower()}|{normalized.name.lower()}")
    return tuple(candidates)


def dedup_reason(left: Lead, right: Lead) -> str | None:
    first, second = normalize(left), normalize(right)
    if first.source_id and second.source_id and first.source and first.source == second.source and first.source_id == second.source_id:
        return "source_id_match"
    if first.phone and first.phone == second.phone:
        return "phone_match"
    if _domain(first.website) and _domain(first.website) == _domain(second.website):
        return "domain_match"
    if first.address and second.address and first.name.lower() == second.name.lower() and first.address.lower() == second.address.lower():
        return "address_name_match"
    return None


def match_leads(left: Lead, right: Lead) -> LeadMatch:
    first, second = normalize(left), normalize(right)
    evidence: list[str] = []
    confidence = 0.0
    if first.source and first.source_id and first.source.lower() == second.source.lower() and first.source_id.lower() == (second.source_id or "").lower():
        evidence.append("source_id")
        confidence = 1.0
    if first.phone and first.phone == second.phone:
        evidence.append("phone")
        confidence = max(confidence, 0.95)
    if _domain(first.website) and _domain(first.website) == _domain(second.website):
        evidence.append("domain")
        confidence = max(confidence, 0.9)
    if first.address and first.name and first.address.lower() == second.address.lower() and first.name.lower() == second.name.lower():
        evidence.append("address_name")
        confidence = max(confidence, 0.85)
    return LeadMatch(is_match=confidence >= 0.85, confidence=confidence, evidence=tuple(evidence))
