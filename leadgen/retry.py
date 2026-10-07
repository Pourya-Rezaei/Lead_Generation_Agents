"""Small, deterministic retry helper for provider clients."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded exponential backoff configuration."""

    max_attempts: int = 3
    initial_backoff: float = 0.5
    max_backoff: float = 4.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_backoff < 0 or self.max_backoff < 0:
            raise ValueError("backoff values cannot be negative")

    def delay(self, failed_attempt: int) -> float:
        """Return the delay after a one-based failed attempt."""
        return min(self.initial_backoff * (2 ** (failed_attempt - 1)), self.max_backoff)


def retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    retry_on: tuple[type[BaseException], ...],
    sleep: Callable[[float], None],
) -> T:
    """Run an operation with bounded retries for explicitly allowed failures."""
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except retry_on:
            if attempt == policy.max_attempts:
                raise
            sleep(policy.delay(attempt))
    raise AssertionError("retry loop exited unexpectedly")
