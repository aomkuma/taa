"""A validated, inert vessel for research-supplied weighted trade readings."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Wants = Literal["high", "low", "true", "false"]


@dataclass(frozen=True)
class Weight:
    """A reading and the nonnegative amount it contributes to a weighted decision."""

    name: str
    weight: float
    wants: Wants

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("weight name must not be empty")
        if not math.isfinite(self.weight) or self.weight < 0:
            raise ValueError("weight must be finite and >= 0")
        if self.wants not in ("high", "low", "true", "false"):
            raise ValueError(f"unsupported wants value: {self.wants!r}")


@dataclass(frozen=True)
class Scale:
    """The readings and minimum normalized score required to qualify."""

    weights: tuple[Weight, ...]
    threshold: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be finite and in [0, 1]")
        names = [reading.name for reading in self.weights]
        if len(names) != len(set(names)):
            raise ValueError("weight names must be unique")


@dataclass(frozen=True)
class ScoreResult:
    """Normalized score, per-reading classifications, and threshold outcome."""

    score: float
    supported: list[str]
    opposed: list[str]
    missing: list[str]
    meets_threshold: bool


def score(readings: Mapping[str, float | bool | None], scale: Scale) -> ScoreResult:
    """Score available readings over their readable weight only.

    Numeric values must already be normalized to ``[0, 1]`` by the caller. ``high`` earns
    ``weight * value`` and ``low`` earns ``weight * (1 - value)``; a numeric reading supports when
    its contribution is at least half its weight, otherwise it opposes. Boolean readings earn full
    weight only when their value matches ``true`` or ``false``. Missing values are excluded from
    both numerator and denominator. The threshold is met at ``score >= threshold``; an empty or
    zero-readable-weight scale cannot meet it.
    """
    numerator = 0.0
    denominator = 0.0
    supported: list[str] = []
    opposed: list[str] = []
    missing: list[str] = []

    for item in scale.weights:
        value = readings.get(item.name)
        if value is None:
            missing.append(item.name)
            continue

        if isinstance(value, bool):
            if item.wants not in ("true", "false"):
                raise ValueError(f"{item.name}: boolean reading requires wants='true' or 'false'")
            agrees = value is (item.wants == "true")
            contribution = item.weight if agrees else 0.0
            if agrees:
                supported.append(item.name)
            else:
                opposed.append(item.name)
        else:
            if item.wants not in ("high", "low"):
                raise ValueError(f"{item.name}: numeric reading requires wants='high' or 'low'")
            numeric = float(value)
            if not math.isfinite(numeric) or not 0 <= numeric <= 1:
                raise ValueError(f"{item.name}: numeric reading must be finite and in [0, 1]")
            fraction = numeric if item.wants == "high" else 1.0 - numeric
            contribution = item.weight * fraction
            (supported if fraction >= 0.5 else opposed).append(item.name)
        numerator += contribution
        denominator += item.weight

    total = numerator / denominator if denominator > 0 else 0.0
    meets = denominator > 0 and total >= scale.threshold
    return ScoreResult(total, supported, opposed, missing, meets)
