from src.domain import Lead
from src.enrichment import build_enrichment_request, map_search_candidates


def test_enrichment_attaches_candidates_to_specific_lead_and_builds_deterministic_query():
    lead = Lead(name="Cafe ABC", website="https://cafe.example")
    request = build_enrichment_request(lead, lead_id="lead-1", city="Tehran")
    result = map_search_candidates(request, [{"title": "Cafe ABC Tehran", "url": "https://cafe.example/about", "snippet": "Cafe in Tehran"}])
    assert result.lead_id == "lead-1"
    assert result.query == "Cafe ABC Tehran"
    assert result.candidates[0].status == "probable"


def test_unrelated_city_and_directory_are_not_promoted_to_official():
    lead = Lead(name="Cafe ABC", website="https://cafe.example")
    request = build_enrichment_request(lead, lead_id="lead-1", city="Tehran")
    result = map_search_candidates(request, [
        {"title": "Cafe ABC Toronto", "url": "https://directory.example/cafe", "snippet": "Toronto"},
        {"title": "Cafe ABC Tehran", "url": "https://directory.example/cafe", "snippet": "Tehran"},
    ])
    assert len(result.candidates) == 1
    assert result.candidates[0].status == "unverified"


def test_malformed_search_items_are_discarded():
    lead = Lead(name="Cafe ABC")
    request = build_enrichment_request(lead, lead_id="lead-1", city="Tehran")
    result = map_search_candidates(request, [{"title": "bad", "url": "http://bad.example"}, {}])
    assert result.candidates == ()
    assert result.discarded_count == 2
