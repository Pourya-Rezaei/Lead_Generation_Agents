import pytest
from pydantic import ValidationError

from src.domain import (
    Lead,
    completeness_score,
    dedup_reason,
    identity_candidates,
    match_leads,
    normalize,
    popularity_score,
    score,
)


def test_lead_validates_required_quality_fields():
    with pytest.raises(ValidationError):
        Lead(name=" \u200f \t")
    with pytest.raises(ValidationError):
        Lead(name="A", rating=5.1)
    with pytest.raises(ValidationError):
        Lead(name="A", reviews=-1)


def test_normalizes_persian_whitespace_phone_and_url():
    lead = normalize(
        Lead(
            name="  کافه\u00a0  تهران  ",
            address=" خیابان\u200f  ولیعصر ",
            phone="۰۰۹۸ (۹۱۲) ۱۲۳-۴۵۶۷",
            website="EXAMPLE.com/path/",
        )
    )
    assert lead.name == "کافه تهران"
    assert lead.address == "خیابان ولیعصر"
    assert lead.phone == "+989121234567"
    assert str(lead.website) == "https://example.com/path"


def test_rejects_malformed_websites():
    with pytest.raises(ValidationError):
        Lead(name="A", website="not a website")


def test_scores_are_separate_and_legacy_score_is_compatible():
    lead = Lead(name="A", website="https://a.test", phone="021123", rating=5, reviews=100)
    assert completeness_score(lead) == 50
    assert popularity_score(lead) == 50
    assert score(lead) == 100


def test_identity_and_match_evidence():
    first = normalize(Lead(name="کافه آبی", address="تهران، ولیعصر", phone="۰۹۱۲۱۲۳۴۵۶۷", source="places", source_id="42"))
    second = normalize(Lead(name=" کافه  آبی ", address="تهران، ولیعصر", phone="+۹۸ ۹۱۲ ۱۲۳ ۴۵۶۷", source="places", source_id="42"))

    assert "source:places:42" in identity_candidates(first)
    assert "phone:+989121234567" in identity_candidates(first)
    result = match_leads(first, second)
    assert result.is_match
    assert {"source_id", "phone", "address_name"}.issubset(result.evidence)


def test_domain_can_match_leads_without_other_evidence():
    result = match_leads(Lead(name="One", website="https://www.Example.com/a"), Lead(name="Two", website="http://example.com/b"))
    assert result.is_match
    assert "domain" in result.evidence


def test_field_quality_metadata_is_optional_and_validated():
    lead = Lead(name="Cafe", field_evidence={"website": ["places:website"]}, field_confidence={"website": 0.9})
    assert lead.field_evidence == {"website": ("places:website",)}
    assert lead.field_confidence["website"] == 0.9
    with pytest.raises(ValidationError):
        Lead(name="Cafe", field_confidence={"website": 1.1})


def test_dedup_reason_follows_identity_precedence():
    assert dedup_reason(Lead(name="A", source="x", source_id="1"), Lead(name="B", source="x", source_id="1")) == "source_id_match"
    assert dedup_reason(Lead(name="A", phone="021"), Lead(name="B", phone="021")) == "phone_match"
    assert dedup_reason(Lead(name="A", website="https://example.com/a"), Lead(name="B", website="https://example.com/b")) == "domain_match"
    assert dedup_reason(Lead(name="A", address="Tehran"), Lead(name="A", address="Tehran")) == "address_name_match"
    assert dedup_reason(Lead(name="A"), Lead(name="B")) is None
