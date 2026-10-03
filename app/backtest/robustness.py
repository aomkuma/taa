"""Robustness tools (PLAN §A17 "Robustness"; TAA-505): walk-forward, a parameter sensitivity grid, Monte Carlo
trade-order resampling and explicit overfitting warnings.

Every tool takes a ``RunFn`` (``run(params, start, end) -> BacktestResult``), so the same code drives the
real engine (the CLI builds it) and fast fakes in tests. The objective is a metric name of
:class:`~app.backtest.metrics.Metrics` (``expectancy_r`` by default); a run with fewer than ``min_trades``
trades scores ``None`` and is never selected, because a handful of trades says nothing.

These tools *measure fragility*; none of them makes a strategy profitable or proves it will be.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from app.backtest.engine import BacktestResult
from app.backtest.metrics import Metrics, compute_metrics

RunFn = Callable[[Mapping[str, Any], datetime | None, datetime | None], BacktestResult]
Params = dict[str, Any]


def score(result: BacktestResult, objective: str, min_trades: int) -> tuple[float | None, Metrics]:
    metrics = compute_metrics(result.trades, result.equity_curve, result.initial_balance)
    if metrics.trades < min_trades:
        return None, metrics
    value = getattr(metrics, objective)
    return (float(value) if value is not None and math.isfinite(value) else None), metrics


def grid(space: Mapping[str, Sequence[Any]]) -> list[Params]:
    """Every combination of the parameter values, in a stable order."""
    keys = sorted(space)
    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*(space[k] for k in keys))]


# --- sensitivity grid -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GridRow:
    params: Params
    score: float | None
    metrics: Metrics


@dataclass(frozen=True)
class SensitivityReport:
    rows: tuple[GridRow, ...]
    objective: str

    @property
    def best(self) -> GridRow | None:
        scored = [r for r in self.rows if r.score is not None]
        return max(scored, key=lambda r: r.score or 0.0) if scored else None

    def neighbours(self, row: GridRow, space: Mapping[str, Sequence[Any]]) -> list[GridRow]:
        """Rows that differ from *row* by one step in exactly one parameter."""
        out = []
        for other in self.rows:
            diffs = [k for k in space if other.params[k] != row.params[k]]
            if len(diffs) != 1:
                continue
            values = list(space[diffs[0]])
            if abs(values.index(other.params[diffs[0]]) - values.index(row.params[diffs[0]])) == 1:
                out.append(other)
        return out

    def stability(self, space: Mapping[str, Sequence[Any]]) -> float | None:
        """Mean neighbour score / best score: near 1 is a plateau, near 0 (or negative) an isolated peak."""
        best = self.best
        if best is None or not best.score:
            return None
        scores = [n.score for n in self.neighbours(best, space) if n.score is not None]
        if not scores:
            return None
        return float(np.mean(scores)) / best.score


def sensitivity(
    run: RunFn,
    space: Mapping[str, Sequence[Any]],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    objective: str = "expectancy_r",
    min_trades: int = 30,
) -> SensitivityReport:
    rows = []
    for params in grid(space):
        value, metrics = score(run(params, start, end), objective, min_trades)
        rows.append(GridRow(params, value, metrics))
    return SensitivityReport(tuple(rows), objective)


# --- walk-forward ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    in_start: datetime
    in_end: datetime
    out_start: datetime
    out_end: datetime


def windows(start: datetime, end: datetime, in_sample: timedelta, out_sample: timedelta) -> list[Window]:
    """Rolling windows: in-sample, then the out-of-sample period right after it; rolled by the OOS length."""
    if in_sample <= timedelta(0) or out_sample <= timedelta(0):
        raise ValueError("window lengths must be positive")
    out = []
    cursor = start
    while cursor + in_sample + out_sample <= end:
        out.append(Window(cursor, cursor + in_sample, cursor + in_sample, cursor + in_sample + out_sample))
        cursor += out_sample
    return out


@dataclass(frozen=True)
class FoldResult:
    window: Window
    params: Params | None  # None: no parameter set had enough trades in-sample
    in_score: float | None
    out_score: float | None
    out_metrics: Metrics | None


@dataclass(frozen=True)
class WalkForwardReport:
    folds: tuple[FoldResult, ...]
    objective: str

    @property
    def efficiency(self) -> float | None:
        """Mean OOS score / mean IS score of the selected sets (≈ 1: the edge held out of sample)."""
        pairs = [
            (f.in_score, f.out_score)
            for f in self.folds
            if f.in_score is not None and f.out_score is not None
        ]
        if not pairs:
            return None
        mean_in = float(np.mean([p[0] for p in pairs]))
        return None if mean_in == 0 else float(np.mean([p[1] for p in pairs])) / mean_in

    @property
    def out_of_sample_trades(self) -> int:
        return sum(f.out_metrics.trades for f in self.folds if f.out_metrics is not None)


def walk_forward(
    run: RunFn,
    space: Mapping[str, Sequence[Any]],
    folds: Sequence[Window],
    *,
    objective: str = "expectancy_r",
    min_trades: int = 30,
) -> WalkForwardReport:
    out = []
    for w in folds:
        in_report = sensitivity(
            run, space, start=w.in_start, end=w.in_end, objective=objective, min_trades=min_trades
        )
        best = in_report.best
        if best is None:
            out.append(FoldResult(w, None, None, None, None))
            continue
        # out-of-sample: whatever trades happened count, even fewer than min_trades
        value, metrics = score(run(best.params, w.out_start, w.out_end), objective, 0)
        out.append(FoldResult(w, best.params, best.score, value, metrics))
    return WalkForwardReport(tuple(out), objective)


# --- Monte Carlo --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MonteCarloReport:
    runs: int
    max_drawdowns: np.ndarray = field(repr=False)  # money, one per run
    final_equities: np.ndarray = field(repr=False)
    initial_equity: float = 0.0

    def drawdown_percentile(self, q: float) -> float:
        return float(np.percentile(self.max_drawdowns, q))

    def probability_drawdown_above(self, money: float) -> float:
        return float(np.mean(self.max_drawdowns > money))

    def probability_of_loss(self) -> float:
        return float(np.mean(self.final_equities < self.initial_equity))


def _max_drawdown(path: np.ndarray) -> float:
    peaks = np.maximum.accumulate(path)
    return float(np.max(peaks - path))


def monte_carlo(
    nets: Sequence[float],
    initial_equity: float,
    *,
    runs: int = 1000,
    seed: int = 42,
    bootstrap: bool = False,
) -> MonteCarloReport:
    """Reorder (or, with *bootstrap*, resample with replacement) the trades' net results *runs* times."""
    values = np.asarray(nets, dtype=float)
    rng = np.random.default_rng(seed)
    dds = np.zeros(runs)
    finals = np.full(runs, initial_equity)
    if len(values):
        for i in range(runs):
            sample = (
                rng.choice(values, size=len(values), replace=True) if bootstrap else rng.permutation(values)
            )
            path = initial_equity + np.concatenate(([0.0], np.cumsum(sample)))
            dds[i] = _max_drawdown(path)
            finals[i] = path[-1]
    return MonteCarloReport(runs, dds, finals, initial_equity)


# --- overfitting warnings -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Thresholds:
    min_trades: int = 30
    min_efficiency: float = 0.5
    min_stability: float = 0.5
    max_combinations_per_trade: float = 0.1  # parameter sets tried per trade
    suspicious_profit_factor: float = 3.0
    mc_drawdown_multiple: float = 2.0  # MC 95th-percentile DD vs the backtest's own DD


def overfitting_warnings(
    metrics: Metrics,
    *,
    combinations: int = 1,
    walk: WalkForwardReport | None = None,
    sens: SensitivityReport | None = None,
    space: Mapping[str, Sequence[Any]] | None = None,
    mc: MonteCarloReport | None = None,
    thresholds: Thresholds | None = None,
) -> list[str]:
    """Plain-language warnings; an empty list is *not* a guarantee that a result is robust."""
    t = thresholds or Thresholds()
    out = []
    if metrics.trades < t.min_trades:
        out.append(f"only {metrics.trades} trades (< {t.min_trades}): the statistics are not meaningful")
    if metrics.trades and combinations / metrics.trades > t.max_combinations_per_trade:
        out.append(
            f"{combinations} parameter sets tried for {metrics.trades} trades: high risk of curve fitting"
        )
    if metrics.profit_factor is not None and metrics.profit_factor > t.suspicious_profit_factor:
        out.append(
            f"profit factor {metrics.profit_factor:.2f} is unusually high: check for look-ahead or "
            "overfitting"
        )
    if walk is not None:
        eff = walk.efficiency
        if eff is None:
            out.append("walk-forward produced no comparable folds")
        elif eff < t.min_efficiency:
            out.append(
                f"walk-forward efficiency {eff:.2f} < {t.min_efficiency}: the edge faded out of sample"
            )
    if sens is not None and space is not None:
        stab = sens.stability(space)
        if stab is not None and stab < t.min_stability:
            out.append(f"best parameters are an isolated peak (neighbour stability {stab:.2f})")
    if mc is not None and metrics.max_drawdown > 0:
        p95 = mc.drawdown_percentile(95)
        if p95 > t.mc_drawdown_multiple * metrics.max_drawdown:
            out.append(
                f"Monte Carlo 95th-percentile drawdown {p95:.2f} is more than "
                f"{t.mc_drawdown_multiple:g}x the backtest's {metrics.max_drawdown:.2f}: "
                "the trade order flattered the result"
            )
    return out
