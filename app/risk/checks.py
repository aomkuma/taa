"""One evaluated rule: the unit the decision engine persists in ``decision_checks`` (PLAN §A8).

Every check carries the measured value and its threshold, so a rejection is explainable without re-running
anything. ``kind`` lets the ADVISORY profile tell hard failures (bad data, impossible geometry) from account
rules (loss limits, exposure), which only become warnings on an opportunity card (§A26).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.risk.reasons import Reason


class CheckKind(StrEnum):
    HARD = "HARD"  # the trade plan itself is invalid or unsafe to show
    ACCOUNT = "ACCOUNT"  # a rule about the account's current state (limits, exposure, breakers)


@dataclass(frozen=True, slots=True)
class Check:
    name: str  # stable rule id, e.g. "max_total_open_risk"
    reason: Reason  # the code reported when the check fails
    passed: bool
    kind: CheckKind = CheckKind.HARD
    value: float | str | None = None
    threshold: float | str | None = None
    detail: str = ""
    code: str = ""  # a parameterized code such as BREAKER_OPEN:DAILY_LOSS; defaults to ``reason``

    @property
    def reason_code(self) -> str:
        return self.code or self.reason.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "reason": self.reason_code,
            "passed": self.passed,
            "kind": self.kind.value,
            "value": self.value,
            "threshold": self.threshold,
            "detail": self.detail,
        }


def failed(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.passed]
