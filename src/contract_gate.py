from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractGateReport:
    """Evidence gates required before a paid social Actor may be enabled."""

    schema_verified: bool
    privacy_verified: bool
    pricing_verified: bool

    @property
    def passed(self) -> bool:
        return self.schema_verified and self.privacy_verified and self.pricing_verified

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, passed in (
                ("schema", self.schema_verified),
                ("privacy", self.privacy_verified),
                ("pricing", self.pricing_verified),
            )
            if not passed
        )

    @property
    def status(self) -> str:
        return "passed" if self.passed else "blocked"
