from src.pipeline import run_pipeline


def test_social_skips_without_eligible_candidates():
    calls = []
    result = run_pipeline(lambda: calls.append("places"), social=lambda: calls.append("social"))
    assert result.state == "succeeded"
    assert result.skipped_steps == ("social:no-eligible-candidates",)
    assert calls == ["places"]


def test_social_failure_keeps_places_as_partial_success():
    result = run_pipeline(lambda: None, social=lambda: (_ for _ in ()).throw(RuntimeError()), eligible_social_candidates=1)
    assert result.state == "partial"
    assert result.completed_steps == ("places",)
    assert result.failed_steps == ("social",)
