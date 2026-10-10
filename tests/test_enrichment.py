from src.domain import Lead
from src.enrichment import ProfileCandidate, enrich_lead


def test_official_domain_candidate_is_probable_not_confirmed():
    lead = Lead(name="Cafe", website="https://cafe.example")
    result = enrich_lead(lead, [ProfileCandidate("https://cafe.example/contact", "Cafe", (), 0.4, "unverified")])
    assert result[0].status == "probable"
    assert result[0].confidence == 0.9


def test_unrelated_candidate_is_not_promoted():
    lead = Lead(name="Cafe", website="https://cafe.example")
    result = enrich_lead(lead, [ProfileCandidate("https://other.example", "Cafe", (), 0.4, "unverified")])
    assert result[0].status == "unverified"
