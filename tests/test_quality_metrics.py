from src.domain import Lead
from src.quality.metrics import metrics
from src.storage import LeadStore


def test_quality_metrics_are_separate_from_legacy_score():
    result = metrics(Lead(name="Cafe", phone="+9812"))
    assert result.completeness == 40
    assert result.identity_confidence is None


def test_export_quality_filters(tmp_path):
    store = LeadStore(str(tmp_path / "quality.db"))
    store.upsert([Lead(name="Complete", phone="+9812", website="https://example.test"), Lead(name="Bare")])
    store.export(str(tmp_path / "out.json"), "json", min_completeness=40, has_phone=True)
    assert "Complete" in (tmp_path / "out.json").read_text()
    assert "Bare" not in (tmp_path / "out.json").read_text()
