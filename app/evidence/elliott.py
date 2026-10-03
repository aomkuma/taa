"""Elliott Wave counts (PLAN §A29 and R31, family ELLIOTT, tier T3: **heuristic**).

Automated wave counting is ambiguous by nature: the same pivots support several readings, and counts change
as new pivots confirm. So this detector does not claim *the* count. At each bar it lists the candidate
counts that the confirmed zigzag pivots allow, filters them with the hard rules, scores them with Fibonacci
guidelines, and reports the best ones as primary and alternates with a confidence. Every record carries
``heuristic=True``.

Candidates, read on each degree in ``params.degrees`` (bullish shown; bearish mirrors):

- ``wave3``: pivots 0 (low), 1 (high), 2 (low) as waves 1-2. Hard rule: wave 2 never retraces more than
  100 % of wave 1. Reported when pivot 2 is confirmed; a wave 3 up is expected.
- ``wave5``: pivots 0..4 as waves 1-4. Hard rules: wave 2 as above; wave 3 ends beyond wave 1; wave 4 does not
  overlap wave 1's territory. Wave 3 may never be the shortest of 1, 3 and 5, so when wave 3 is shorter than
  wave 1 the target of wave 5 is capped below wave 3's length. Reported when pivot 4 is confirmed.
- ``c_completion``: a zigzag correction against the prior leg: start S (high), A (low), B (high below S), with
  A retracing less than 100 % of the prior leg. Wave C is expected to reach 100–161.8 % of A from B; the first
  bar reaching that zone (before the next pivot confirms, without a close back beyond B or through the zone)
  is a possible C completion, and the prior trend is expected to resume.

Ranking: candidates found at the same bar (all states and degrees, one per distinct pivot set) are sorted by
guideline score; at most ``max_counts`` are kept. ``confidence = score / max(1, Σ scores)`` is the quality,
so a contested count weighs less than an uncontested one. Records are immutable: a later recount adds new
records and never rewrites earlier ones (the look-ahead harness enforces this).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
from pydantic import Field

from app.evidence.framework import (
    DetailValue,
    Detector,
    DetectorParams,
    Direction,
    Evidence,
    EvidenceContext,
    Family,
    KeyLevel,
    Tier,
    swing_level,
)
from app.indicators.price_action import Swing, SwingKind

Band = tuple[float, float]


def guideline(value: float, band: Band, soft: float) -> float:
    """1 inside *band*, falling linearly to 0 at *soft* (ratio units) outside it."""
    lo, hi = band
    miss = max(lo - value, value - hi, 0.0)
    return float(max(0.0, 1.0 - miss / soft))


class ElliottParams(DetectorParams):
    degrees: tuple[str, ...] = Field(default=("minor", "intermediate"), min_length=1)
    min_score: float = Field(default=0.5, ge=0, le=1)  # weaker counts are not reported at all
    max_counts: int = Field(default=2, ge=1, le=10)  # primary + alternates per bar
    c_zone: tuple[float, float] = (1.0, 1.618)  # wave C as a multiple of wave A
    zone_tol: float = Field(default=0.05, gt=0, le=0.25)
    stop_atr: float = Field(default=0.25, ge=0, le=3)


@dataclass
class _Count:
    t: int
    state: str
    direction: Direction
    score: float
    pivots: tuple[int, ...]  # pivot positions: the identity of the count
    degree: str
    key_levels: list[KeyLevel]
    invalidation: float
    targets: list[float]
    details: dict[str, DetailValue] = field(default_factory=dict)


class ElliottWave(Detector):
    """Elliott Wave candidate counts (heuristic): possible wave 3, possible wave 5, possible C completion."""

    id = "elliott.wave"
    name = "Elliott wave count (heuristic)"
    family = Family.ELLIOTT
    tier = Tier.T3
    Params: ClassVar[type[DetectorParams]] = ElliottParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        counts: dict[tuple[str, tuple[int, ...]], _Count] = {}
        for degree in params.degrees:
            pivots = ctx.zigzag(degree)
            for found in (
                *self._impulses(pivots, degree),
                *self._corrections(ctx, pivots, degree, params),
            ):
                if found.score < params.min_score:
                    continue
                key = (found.state, found.pivots)
                # the same pivots seen at two degrees are one count; keep the first (lowest) degree's record
                if key not in counts or found.t < counts[key].t:
                    counts[key] = found
        by_bar: dict[int, list[_Count]] = {}
        for found in counts.values():
            by_bar.setdefault(found.t, []).append(found)
        out: list[Evidence] = []
        for t in sorted(by_bar):
            group = sorted(by_bar[t], key=lambda c: (-c.score, c.state, c.pivots))[: params.max_counts]
            total = max(1.0, sum(c.score for c in group))
            for rank, found in enumerate(group, start=1):
                confidence = found.score / total
                out.append(
                    self.make(
                        ctx,
                        t,
                        found.direction,
                        confidence,
                        key_levels=found.key_levels,
                        invalidation=found.invalidation,
                        targets=found.targets,
                        details={
                            **found.details,
                            "rank": rank,
                            "count": "primary" if rank == 1 else "alternate",
                            "confidence": round(confidence, 4),
                            "score": round(found.score, 4),
                            "degree": found.degree,
                            "heuristic": True,
                        },
                        variant=found.state,
                    )
                )
        return out

    # --- impulse waves -------------------------------------------------------------------------------------

    def _impulses(self, pivots: list[Swing], degree: str) -> list[_Count]:
        out: list[_Count] = []
        for j in range(2, len(pivots)):
            m = 1 if pivots[j].kind is SwingKind.LOW else -1  # bullish when wave 2 / 4 ends at a low
            w3 = self._wave3(pivots, j, m, degree)
            if w3 is not None:
                out.append(w3)
            if j >= 4:
                w5 = self._wave5(pivots, j, m, degree)
                if w5 is not None:
                    out.append(w5)
        return out

    @staticmethod
    def _wave3(pivots: list[Swing], j: int, m: int, degree: str) -> _Count | None:
        p0, p1, p2 = (m * p.price for p in pivots[j - 2 : j + 1])
        w1 = p1 - p0
        if not (w1 > 0 and p2 > p0):  # hard rule 1: wave 2 stays above the start of wave 1
            return None
        r2 = (p1 - p2) / w1
        # wave 1 starts a trend: from a lower low, and through the previous lower high (unknown: neutral)
        prior_low = m * pivots[j - 4].price if j >= 4 else None
        prior_high = m * pivots[j - 3].price if j >= 3 else None
        g_start = 0.5 if prior_low is None else float(p0 < prior_low)
        g_break = 0.5 if prior_high is None else float(p1 > prior_high)
        score = float(np.mean([guideline(r2, (0.5, 0.618), 0.25), g_start, g_break]))
        names = ("wave_0", "wave_1", "wave_2")
        return _Count(
            t=pivots[j].confirm_pos,
            state="wave3",
            direction=Direction.BULL if m > 0 else Direction.BEAR,
            score=score,
            pivots=tuple(p.pivot_pos for p in pivots[j - 2 : j + 1]),
            degree=degree,
            key_levels=[swing_level(n, p) for n, p in zip(names, pivots[j - 2 : j + 1], strict=True)],
            invalidation=m * p0,
            targets=[m * (p2 + r * w1) for r in (1.0, 1.618)],
            details={"wave2_retrace": round(r2, 4)},
        )

    @staticmethod
    def _wave5(pivots: list[Swing], j: int, m: int, degree: str) -> _Count | None:
        p0, p1, p2, p3, p4 = (m * p.price for p in pivots[j - 4 : j + 1])
        w1, w3 = p1 - p0, p3 - p2
        # hard rules: wave 2 above the start of wave 1; wave 3 beyond wave 1; wave 4 above wave 1's end
        if not (w1 > 0 and p2 > p0 and p3 > p1 and p4 > p1):
            return None
        r2, r3, r4 = (p1 - p2) / w1, w3 / w1, (p3 - p4) / w3
        score = float(
            np.mean(
                [
                    guideline(r2, (0.5, 0.618), 0.25),
                    guideline(r3, (1.618, 2.618), 0.6),
                    guideline(r4, (0.236, 0.382), 0.2),
                    min(1.0, abs(r2 - r4) / 0.2),  # alternation: one deep and one shallow correction
                ]
            )
        )
        targets = [p4 + w1, p4 + 0.618 * (p3 - p0)]
        details: dict[str, DetailValue] = {
            "wave2_retrace": round(r2, 4),
            "wave3_ratio": round(r3, 4),
            "wave4_retrace": round(r4, 4),
        }
        if w3 < w1:  # wave 3 may not be the shortest: wave 5 must stay shorter than wave 3
            cap = p4 + w3
            targets = [min(x, cap) for x in targets]
            details["wave5_cap"] = round(m * cap, 10)
        names = ("wave_0", "wave_1", "wave_2", "wave_3", "wave_4")
        return _Count(
            t=pivots[j].confirm_pos,
            state="wave5",
            direction=Direction.BULL if m > 0 else Direction.BEAR,
            score=score,
            pivots=tuple(p.pivot_pos for p in pivots[j - 4 : j + 1]),
            degree=degree,
            key_levels=[swing_level(n, p) for n, p in zip(names, pivots[j - 4 : j + 1], strict=True)],
            invalidation=m * p1,
            targets=[m * x for x in sorted(set(targets))],
            details=details,
        )

    # --- corrections ---------------------------------------------------------------------------------------

    def _corrections(
        self, ctx: EvidenceContext, pivots: list[Swing], degree: str, params: Any
    ) -> list[_Count]:
        atr = ctx.atr_array()
        out: list[_Count] = []
        for j in range(3, len(pivots)):
            # bullish reversal after a correction down: prior leg up (O -> S), A down, B up
            m = 1 if pivots[j].kind is SwingKind.HIGH else -1
            o, s, a, b = (m * p.price for p in pivots[j - 3 : j + 1])
            prior, wa = s - o, s - a
            if not (prior > 0 and a > o and b < s):  # A retraces < 100 % of the prior leg; B below S
                continue
            rb = (b - a) / wa
            lo_r, hi_r = params.c_zone
            near = b - lo_r * (1 - params.zone_tol) * wa
            far = b - hi_r * (1 + params.zone_tol) * wa
            if near <= o:  # even the shortest C would retrace the whole prior leg: not a correction
                continue
            depth = (s - (b - wa)) / prior  # where C = A ends, as a retracement of the prior leg
            score = float(
                np.mean([guideline(rb, (0.5, 0.618), 0.25), guideline(depth, (0.382, 0.618), 0.25)])
            )
            end = pivots[j + 1].confirm_pos if j + 1 < len(pivots) else ctx.last_pos
            for t in range(pivots[j].confirm_pos, end + 1):
                if not np.isfinite(atr[t]):
                    continue
                stop = far - params.stop_atr * float(atr[t])
                close = m * ctx.c[t]
                if close < stop or close > b:
                    break  # C blew through the zone, or price went back beyond B
                probe = m * (ctx.l[t] if m > 0 else ctx.h[t])
                if probe > near:
                    continue
                names = ("origin", "start", "wave_a", "wave_b")
                out.append(
                    _Count(
                        t=t,
                        state="c_completion",
                        direction=Direction.BULL if m > 0 else Direction.BEAR,
                        score=score,
                        pivots=tuple(p.pivot_pos for p in pivots[j - 3 : j + 1]),
                        degree=degree,
                        key_levels=[
                            *(swing_level(n, p) for n, p in zip(names, pivots[j - 3 : j + 1], strict=True)),
                            KeyLevel("c_zone_near", m * near),
                            KeyLevel("c_zone_far", m * far),
                        ],
                        invalidation=m * stop,
                        targets=[m * b, m * s],
                        details={"wave_b_retrace": round(rb, 4), "c_equals_a_depth": round(depth, 4)},
                    )
                )
                break
        return out
