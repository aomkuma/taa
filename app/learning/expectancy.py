"""Expectancy decomposition: E[R] = p·W − (1 − p)·L − c (PLAN_LEARNING §L20.0; TAA-L801).

A single trade's outcome cannot be predicted; the expected value over many trades is what the system designs.
This module splits the measured expectancy of a group of trades into its levers, so a change can be traced to
the lever it moved:

- ``p``: the share of trades with a positive result **before costs** (``pre_cost_r > 0``);
- ``W``: the mean pre-cost R of those trades;
- ``L``: the mean pre-cost loss in R (as a positive number) of the others (zero counts here, adding nothing);
- ``c``: the mean known cost in R (``cost_r``).

With every cost known, ``p·W − (1 − p)·L − c`` equals the mean net R exactly. Trades without a known cost are
left out of the decomposition (``unknown_costs`` counts them) and the measured mean uses the same trades, so
the identity holds by construction; the bootstrap CI comes from the analytics recommendations (seeded,
reproducible).

Pure functions over analytics :class:`~app.analytics.trade_builder.Trade` records (§L0.2: nothing they read is
changed). Results built from shadow, paper or backtest trades are hypothetical, as the trades are.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta

from app.analytics.recommendations import Interval, bootstrap_mean_ci
from app.analytics.trade_builder import Trade

WEEK = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class Decomposition:
    key: Hashable
    n: int
    p: float
    win_r: float  # W
    loss_r: float  # L, positive
    cost_r: float  # c
    expectancy_r: float  # p·W − (1 − p)·L − c
    measured_r: float  # mean net R of the same trades
    ci: Interval  # bootstrap CI of the mean net R
    per_week: float | None  # trades per week over the span of entry times; None for a single instant
    unknown_costs: int  # trades left out because their cost in R is unknown
    hypothetical: bool


@dataclass(frozen=True, slots=True)
class LeverChange:
    """Contribution of each lever to the change in expectancy between two decompositions (the parts sum to
    ΔE[R] exactly: Δp·(W₀ + L₀) + p₁·ΔW − (1 − p₁)·ΔL − Δc)."""

    p: float  # Δp · (W + L), at the previous W and L
    win_r: float  # p · ΔW
    loss_r: float  # −(1 − p) · ΔL
    cost_r: float  # −Δc
    total: float  # ΔE[R]

    @property
    def main(self) -> str:
        """The lever that moved expectancy the most (by absolute contribution)."""
        parts = {"p": self.p, "W": self.win_r, "L": self.loss_r, "c": self.cost_r}
        return max(parts, key=lambda k: abs(parts[k]))


def _usable(trades: Iterable[Trade]) -> tuple[list[Trade], int]:
    usable, unknown = [], 0
    for t in trades:
        pre, net = t.pre_cost_r, t.r_multiple
        if pre is None or net is None or not math.isfinite(pre) or not math.isfinite(net):
            unknown += 1
            continue
        usable.append(t)
    return usable, unknown


def decompose(trades: Sequence[Trade], key: Hashable = "all", *, seed: int = 0) -> Decomposition | None:
    """The decomposition of one group; None when no trade has a known R and cost."""
    usable, unknown = _usable(trades)
    if not usable:
        return None
    n = len(usable)
    pre = [t.pre_cost_r for t in usable if t.pre_cost_r is not None]
    net = [t.r_multiple for t in usable if t.r_multiple is not None]
    costs = [t.cost_r for t in usable if t.cost_r is not None]
    wins = [r for r in pre if r > 0]
    losses = [-r for r in pre if r <= 0]
    p = len(wins) / n
    win_r = sum(wins) / len(wins) if wins else 0.0
    loss_r = sum(losses) / len(losses) if losses else 0.0
    cost_r = sum(costs) / n
    times = sorted(t.entry_time for t in usable)
    span = times[-1] - times[0]
    return Decomposition(
        key=key,
        n=n,
        p=p,
        win_r=win_r,
        loss_r=loss_r,
        cost_r=cost_r,
        expectancy_r=p * win_r - (1 - p) * loss_r - cost_r,
        measured_r=sum(net) / n,
        ci=bootstrap_mean_ci(net, seed=seed),
        per_week=n / (span / WEEK) if span > timedelta(0) else None,
        unknown_costs=unknown,
        hypothetical=any(t.hypothetical for t in usable),
    )


def by_group(
    trades: Iterable[Trade], key: Callable[[Trade], Hashable], *, seed: int = 0
) -> list[Decomposition]:
    groups: dict[Hashable, list[Trade]] = defaultdict(list)
    for t in trades:
        groups[key(t)].append(t)
    out = [decompose(rows, k, seed=seed) for k, rows in sorted(groups.items(), key=lambda kv: str(kv[0]))]
    return [d for d in out if d is not None]


def lever_change(previous: Decomposition, current: Decomposition) -> LeverChange:
    """Which lever moved: an exact split of ΔE[R] into the four levers."""
    dp = current.p - previous.p
    return LeverChange(
        p=dp * (previous.win_r + previous.loss_r),
        win_r=current.p * (current.win_r - previous.win_r),
        loss_r=-(1 - current.p) * (current.loss_r - previous.loss_r),
        cost_r=-(current.cost_r - previous.cost_r),
        total=current.expectancy_r - previous.expectancy_r,
    )
