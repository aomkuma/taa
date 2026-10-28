"""The pattern library (owner, 2026-10-18): a list of patterns, not a pile of pictures. Each pattern = one leader
fingerprint, how many times it occurred (once a day at most), what followed each occurrence, and up to five example
moments (different days) for pictures. A new moment >= 80 % alike the most similar pattern counts as a repeat of it;
otherwise it starts a new pattern. Evidence for a decision uses only occurrences of earlier days.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SIM_TOL = 1e-6  # similarities are shares k / n of equal attributes (n <= 120): far apart; float32 inputs round by ~1e-7
OUTCOMES = ("ran_up", "slow_up", "ran_dn", "slow_dn", "fake_up", "fake_dn", "flat", "drift")


@dataclass
class Pattern:
    pid: int
    leader: np.ndarray
    created_day: int
    occ_days: list[int] = field(default_factory=list)  # one entry per counted day
    occ_outcomes: list[str] = field(default_factory=list)  # the first occurrence's outcome on each counted day
    examples: list[tuple[int, object]] = field(default_factory=list)  # (day, moment) - at most max_examples


class PatternLibrary:
    def __init__(self, dim: int, thr: float = 0.8, max_examples: int = 5) -> None:
        self.thr, self.max_examples = thr, max_examples
        self.patterns: list[Pattern] = []
        self._L = np.zeros((0, dim))  # float64 (float32 put an exact 80 % at 0.79999999: bug to 2026-10-19)

    def most_similar(self, vec: np.ndarray, before_day: int | None = None) -> tuple[int, float]:
        """The most similar pattern (index, similarity) among those created before `before_day` (all when None);
        (-1, nan) when there is none."""
        if not self.patterns:
            return -1, np.nan
        # rounded: equal shares k / n came out as floats 2e-16 apart, so ties went to float noise instead of the
        # earliest pattern (bug to 2026-10-19, found by the independent check of V2)
        sims = np.round(self._L @ vec, 9)
        if before_day is not None:
            created = np.array([p.created_day for p in self.patterns])
            sims = np.where(created < before_day, sims, -np.inf)
        k = int(np.argmax(sims))
        return (k, float(sims[k])) if np.isfinite(sims[k]) else (-1, np.nan)

    def add(self, vec: np.ndarray, day: int, outcome: str, moment: object = None) -> tuple[int, bool]:
        """Count a moment: a repeat of the most similar pattern (>= thr) or a new pattern. Returns (pid, is_new)."""
        k, sim = self.most_similar(vec)
        if k >= 0 and sim >= self.thr - SIM_TOL:
            p = self.patterns[k]
            if not p.occ_days or p.occ_days[-1] != day:  # once a day at most
                p.occ_days.append(day)
                p.occ_outcomes.append(outcome)
                if len(p.examples) < self.max_examples and all(d != day for d, _ in p.examples):
                    p.examples.append((day, moment))
            return k, False
        p = Pattern(pid=len(self.patterns), leader=vec.astype(np.float32), created_day=day, occ_days=[day],
                    occ_outcomes=[outcome], examples=[(day, moment)])
        self.patterns.append(p)
        self._L = np.vstack([self._L, vec[None, :].astype(float)])
        return p.pid, True

    def evidence(self, vec: np.ndarray, day: int, side: int) -> dict:
        """What the library knew before `day` about a moment like vec: its pattern, the times it occurred, and what
        followed - relative to the trade's side (+1 buy / -1 sell)."""
        k, sim = self.most_similar(vec, before_day=day)
        if k < 0 or sim < self.thr - SIM_TOL:
            return dict(pid=-1, sim=sim, count=0, with_=np.nan, against=np.nan, fake=np.nan, flat=np.nan)
        p = self.patterns[k]
        outs = [o for d, o in zip(p.occ_days, p.occ_outcomes) if d < day]
        if not outs:
            return dict(pid=k, sim=sim, count=0, with_=np.nan, against=np.nan, fake=np.nan, flat=np.nan)
        o = np.array(outs)
        up = np.isin(o, ["ran_up", "slow_up"]).mean()
        dn = np.isin(o, ["ran_dn", "slow_dn"]).mean()
        return dict(pid=k, sim=sim, count=len(outs), with_=up if side > 0 else dn, against=dn if side > 0 else up,
                    fake=np.isin(o, ["fake_up", "fake_dn"]).mean(), flat=(o == "flat").mean())
