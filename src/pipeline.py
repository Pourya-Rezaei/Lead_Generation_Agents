from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PipelineResult:
    completed_steps: tuple[str, ...]
    skipped_steps: tuple[str, ...]
    failed_steps: tuple[str, ...]
    state: str


def run_pipeline(
    places: Callable[[], None],
    web: Callable[[], None] | None = None,
    social: Callable[[], None] | None = None,
    eligible_social_candidates: int = 0,
) -> PipelineResult:
    completed: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    try:
        places()
        completed.append("places")
    except Exception:
        failed.append("places")
    if web is not None and not failed:
        try:
            web()
            completed.append("web")
        except Exception:
            failed.append("web")
    elif web is not None:
        skipped.append("web")
    if social is not None:
        if eligible_social_candidates == 0:
            skipped.append("social:no-eligible-candidates")
        elif not failed:
            try:
                social()
                completed.append("social")
            except Exception:
                failed.append("social")
        else:
            skipped.append("social:upstream-failure")
    state = "failed" if not completed else ("partial" if failed else "succeeded")
    return PipelineResult(tuple(completed), tuple(skipped), tuple(failed), state)
