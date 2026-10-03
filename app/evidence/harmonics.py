"""Harmonic-pattern detectors (PLAN §A29 and R30, family HARMONIC, tier T2).

Table-driven XABCD structures (Carney). X, A, B and C are consecutive confirmed zigzag pivots of
``params.degree``; D is not a pivot yet, it is the **potential reversal zone (PRZ)** that the ratios predict.

- **Checks.** The ratios of the known legs must lie in the pattern's bands, each widened by ``ratio_tol``
  (relative): ``[lo·(1 − tol), hi·(1 + tol)]``.
- **PRZ.** Every D ratio (XA retracement, XC retracement, BC projection, AB = CD) places D in a price band.
  The PRZ is the intersection of those bands; an empty intersection means the pattern cannot complete.
- **Completion.** From C's confirmation until the next pivot is confirmed, the first bar whose extreme
  reaches the PRZ completes the pattern, unless a close beyond C or beyond the PRZ's far edge (by
  ``stop_atr`` × ATR) came first. A bar that itself closes beyond that edge blew through the zone.
- **Quality** = 1 − mean ratio error. A ratio inside its band has error 0; outside, the error is the distance
  as a share of the tolerance (1 = at the tolerance edge). D's ratios are scored at the *ideal* D, where
  they agree best inside the PRZ: the first touch is always at the zone's edge, so scoring the probe would
  penalize every pattern alike. The details report D's ratios at the probe (clipped to the PRZ).
- Invalidation: the PRZ's far edge ∓ ``stop_atr`` × ATR. Targets: 38.2 % and 61.8 % of AD.
- Patterns sharing X, A, B and C can each complete on the way (a Bat's PRZ is reached before a Crab's);
  the one that is blown through is invalidated by the close beyond its far edge.

Conventions differ between authors (Cypher's C, Shark's B); the table states the ones used here.
Geometry is computed for the bullish case; a bearish pattern is its mirror (prices negated).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
from pydantic import Field

from app.evidence.framework import (
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

# leg ratios checked before D, from the bullish points (y-values) x, a, b, c
CHECKS = {
    "ab_xa": lambda p: (p["A"] - p["B"]) / (p["A"] - p["X"]),
    "bc_ab": lambda p: (p["C"] - p["B"]) / (p["A"] - p["B"]),
}
# ratios that place D: D = base − r · span
PLACEMENTS = {
    "ad_xa": lambda p: (p["A"], p["A"] - p["X"]),
    "cd_xc": lambda p: (p["C"], p["C"] - p["X"]),
    "cd_bc": lambda p: (p["C"], p["C"] - p["B"]),
    "cd_ab": lambda p: (p["C"], p["A"] - p["B"]),
}
AD_TARGETS = (0.382, 0.618)


@dataclass(frozen=True, slots=True)
class HarmonicSpec:
    points: tuple[str, ...]  # pivots before D
    checks: tuple[tuple[str, Band], ...]
    prz: tuple[tuple[str, Band], ...]


SPECS: dict[str, HarmonicSpec] = {
    "gartley": HarmonicSpec(
        ("X", "A", "B", "C"),
        (("ab_xa", (0.618, 0.618)), ("bc_ab", (0.382, 0.886))),
        (("ad_xa", (0.786, 0.786)), ("cd_bc", (1.272, 1.618))),
    ),
    "bat": HarmonicSpec(
        ("X", "A", "B", "C"),
        (("ab_xa", (0.382, 0.5)), ("bc_ab", (0.382, 0.886))),
        (("ad_xa", (0.886, 0.886)), ("cd_bc", (1.618, 2.618))),
    ),
    "butterfly": HarmonicSpec(
        ("X", "A", "B", "C"),
        (("ab_xa", (0.786, 0.786)), ("bc_ab", (0.382, 0.886))),
        (("ad_xa", (1.272, 1.618)), ("cd_bc", (1.618, 2.618))),
    ),
    "crab": HarmonicSpec(
        ("X", "A", "B", "C"),
        (("ab_xa", (0.382, 0.618)), ("bc_ab", (0.382, 0.886))),
        (("ad_xa", (1.618, 1.618)), ("cd_bc", (2.24, 3.618))),
    ),
    # C beyond A (1.13–1.414 of AB), D at 78.6 % of XC
    "cypher": HarmonicSpec(
        ("X", "A", "B", "C"),
        (("ab_xa", (0.382, 0.618)), ("bc_ab", (1.13, 1.414))),
        (("cd_xc", (0.786, 0.786)),),
    ),
    # C beyond A (1.13–1.618 of AB), D at 88.6–113 % of XC
    "shark": HarmonicSpec(
        ("X", "A", "B", "C"),
        (("ab_xa", (0.382, 0.618)), ("bc_ab", (1.13, 1.618))),
        (("cd_xc", (0.886, 1.13)), ("cd_bc", (1.618, 2.24))),
    ),
    "abcd": HarmonicSpec(
        ("A", "B", "C"),
        (("bc_ab", (0.382, 0.886)),),
        (("cd_ab", (1.0, 1.0)), ("cd_bc", (1.13, 2.618))),
    ),
}


def ratio_error(value: float, band: Band, tol: float) -> float:
    """0 inside the band; outside, the distance as a share of the tolerance (> 1 = out of tolerance)."""
    lo, hi = band
    if value < lo:
        return (lo - value) / (lo * tol)
    if value > hi:
        return (value - hi) / (hi * tol)
    return 0.0


def prz(points: dict[str, float], spec: HarmonicSpec, tol: float) -> Band | None:
    """The (low, high) band where D completes the bullish pattern, or None when the D ratios disagree."""
    low, high = -np.inf, np.inf
    for measure, (lo, hi) in spec.prz:
        base, span = PLACEMENTS[measure](points)
        low = max(low, base - hi * (1 + tol) * span)
        high = min(high, base - lo * (1 - tol) * span)
    return (float(low), float(high)) if low <= high else None


def d_errors(points: dict[str, float], spec: HarmonicSpec, tol: float, d: float) -> list[float]:
    out = []
    for measure, band in spec.prz:
        base, span = PLACEMENTS[measure](points)
        out.append(ratio_error((base - d) / span, band, tol))
    return out


def ideal_d(points: dict[str, float], spec: HarmonicSpec, tol: float, zone: Band) -> float:
    """The D in the PRZ where the D ratios agree best (least mean error).

    The mean error is convex and piecewise linear in D, so its minimum lies at a band edge or a zone end.
    """
    candidates = {zone[0], zone[1]}
    for measure, (lo, hi) in spec.prz:
        base, span = PLACEMENTS[measure](points)
        candidates |= {float(np.clip(base - r * span, *zone)) for r in (lo, hi)}
    return min(sorted(candidates), key=lambda d: float(np.mean(d_errors(points, spec, tol, d))))


class HarmonicParams(DetectorParams):
    degree: str = "minor"
    ratio_tol: float = Field(default=0.05, gt=0, le=0.25)  # relative widening of every ratio band
    stop_atr: float = Field(default=0.25, ge=0, le=3)


class _Harmonic(Detector):
    family = Family.HARMONIC
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = HarmonicParams
    spec: ClassVar[HarmonicSpec]

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        atr = ctx.atr_array()
        size, tol = len(self.spec.points), params.ratio_tol
        out: list[Evidence] = []
        for i in range(len(pivots) - size + 1):
            w = pivots[i : i + size]
            # bullish when C is a high (D will be a low); a bearish pattern is the mirror image. Pivots
            # alternate, so the legs X→A and A→B are never zero.
            m = 1 if w[-1].kind is SwingKind.HIGH else -1
            p = {name: m * s.price for name, s in zip(self.spec.points, w, strict=True)}
            ratios = {name: CHECKS[name](p) for name, _ in self.spec.checks}
            errors = [ratio_error(ratios[name], band, tol) for name, band in self.spec.checks]
            if any(e > 1 for e in errors):
                continue
            zone = prz(p, self.spec, tol)
            if zone is None:
                continue
            error = float(np.mean([*errors, *d_errors(p, self.spec, tol, ideal_d(p, self.spec, tol, zone))]))
            end = pivots[i + size].confirm_pos if i + size < len(pivots) else ctx.last_pos
            for t in range(w[-1].confirm_pos, end + 1):
                if not np.isfinite(atr[t]):
                    continue
                stop = zone[0] - params.stop_atr * float(atr[t])
                close = m * ctx.c[t]
                if close < stop or close > p["C"]:
                    break  # blew through the PRZ, or the CD leg failed
                probe = m * (ctx.l[t] if m > 0 else ctx.h[t])
                if probe > zone[1]:
                    continue
                d = float(np.clip(probe, *zone))
                out.append(self._record(ctx, t, m, w, p, ratios, error, zone, d, stop, params))
                break
        return out

    def _record(
        self,
        ctx: EvidenceContext,
        t: int,
        m: int,
        w: list[Swing],
        p: dict[str, float],
        ratios: dict[str, float],
        error: float,
        zone: Band,
        d: float,
        stop: float,
        params: Any,
    ) -> Evidence:
        d_ratios = {}
        for measure, _ in self.spec.prz:
            base, span = PLACEMENTS[measure](p)
            d_ratios[measure] = (base - d) / span
        return self.make(
            ctx,
            t,
            Direction.BULL if m > 0 else Direction.BEAR,
            1.0 - error,
            key_levels=[
                *(swing_level(name, s) for name, s in zip(self.spec.points, w, strict=True)),
                KeyLevel("prz_near", m * zone[1]),
                KeyLevel("prz_far", m * zone[0]),
                KeyLevel("D", m * d),
            ],
            invalidation=m * stop,
            targets=[m * (d + r * (p["A"] - d)) for r in AD_TARGETS],
            details={
                **{k: round(v, 4) for k, v in {**ratios, **d_ratios}.items()},
                "ratio_error": round(error, 4),
                "degree": params.degree,
            },
            variant="bullish" if m > 0 else "bearish",
        )


class Gartley(_Harmonic):
    """Gartley: B at 61.8 % of XA, D at 78.6 % of XA (BC projection 1.272–1.618)."""

    id = "harmonic.gartley"
    name = "Gartley"
    spec = SPECS["gartley"]


class Bat(_Harmonic):
    """Bat: B at 38.2–50 % of XA, D at 88.6 % of XA (BC projection 1.618–2.618)."""

    id = "harmonic.bat"
    name = "Bat"
    spec = SPECS["bat"]


class Butterfly(_Harmonic):
    """Butterfly: B at 78.6 % of XA, D beyond X at 127.2–161.8 % of XA (BC projection 1.618–2.618)."""

    id = "harmonic.butterfly"
    name = "Butterfly"
    spec = SPECS["butterfly"]


class Crab(_Harmonic):
    """Crab: B at 38.2–61.8 % of XA, D far beyond X at 161.8 % of XA (BC projection 2.24–3.618)."""

    id = "harmonic.crab"
    name = "Crab"
    spec = SPECS["crab"]


class Cypher(_Harmonic):
    """Cypher: B at 38.2–61.8 % of XA, C beyond A (1.13–1.414 of AB), D at 78.6 % of XC."""

    id = "harmonic.cypher"
    name = "Cypher"
    spec = SPECS["cypher"]


class Shark(_Harmonic):
    """Shark: C beyond A (1.13–1.618 of AB), D at 88.6–113 % of XC (BC projection 1.618–2.24)."""

    id = "harmonic.shark"
    name = "Shark"
    spec = SPECS["shark"]


class AbCd(_Harmonic):
    """AB = CD: C retraces 38.2–88.6 % of AB, then CD equals AB (BC projection 1.13–2.618)."""

    id = "harmonic.abcd"
    name = "AB=CD"
    spec = SPECS["abcd"]
