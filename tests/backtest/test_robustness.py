from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.backtest.engine import BacktestResult
from app.backtest.metrics import compute_metrics
from app.backtest.robustness import (
    Thresholds,
    grid,
    monte_carlo,
    overfitting_warnings,
    sensitivity,
    walk_forward,
    windows,
)
from app.execution.simulated_broker import EquityPoint
from tests.backtest.test_metrics_report import trade

T = datetime(2026, 1, 1, tzinfo=UTC)


def result(nets: list[float]) -> BacktestResult:
    trades = [trade(n, i=i) for i, n in enumerate(nets)]
    equity, curve = 10_000.0, [EquityPoint(T, 10_000.0, 10_000.0, 0.0, 0)]
    for i, n in enumerate(nets):
        equity += n
        curve.append(EquityPoint(T + timedelta(days=i + 1), equity, equity, 0.0, 0))
    return BacktestResult(trades, curve, 10_000.0, T, curve[-1].at, ["EURUSD"])


def fake_run(peak: Mapping[str, Any] | None = None, trades: int = 40):  # type: ignore[no-untyped-def]
    """Expectancy falls off with distance from *peak*; in-sample (before July) is a little better."""
    best = peak or {"a": 2, "b": 20}

    def run(params: Mapping[str, Any], start: datetime | None, end: datetime | None) -> BacktestResult:
        distance = abs(params["a"] - best["a"]) + abs(params["b"] - best["b"]) / 10
        edge = 50.0 - 20.0 * distance
        if start is not None and start >= datetime(2026, 7, 1, tzinfo=UTC):
            edge -= 10.0
        return result([edge + 100.0, -100.0] * (trades // 2))

    return run


SPACE = {"a": [1, 2, 3], "b": [10, 20, 30]}


class TestSensitivity:
    def test_grid_is_every_combination(self) -> None:
        assert len(grid(SPACE)) == 9
        assert grid({"x": [1, 2]}) == [{"x": 1}, {"x": 2}]

    def test_best_and_stability(self) -> None:
        rep = sensitivity(fake_run(), SPACE)
        assert rep.best is not None and rep.best.params == {"a": 2, "b": 20}
        assert len(rep.neighbours(rep.best, SPACE)) == 4
        stab = rep.stability(SPACE)
        assert stab is not None and 0 < stab < 1

    def test_too_few_trades_never_wins(self) -> None:
        rep = sensitivity(fake_run(trades=10), SPACE)
        assert rep.best is None
        assert all(r.score is None for r in rep.rows)


class TestWalkForward:
    def test_windows_roll_by_the_out_of_sample_length(self) -> None:
        folds = windows(T, T + timedelta(days=100), timedelta(days=60), timedelta(days=20))
        assert [(f.in_start, f.out_start) for f in folds] == [
            (T, T + timedelta(days=60)),
            (T + timedelta(days=20), T + timedelta(days=80)),
        ]
        with pytest.raises(ValueError):
            windows(T, T + timedelta(days=10), timedelta(0), timedelta(days=1))

    def test_selected_parameters_and_efficiency(self) -> None:
        folds = windows(T, datetime(2026, 12, 31, tzinfo=UTC), timedelta(days=120), timedelta(days=60))
        rep = walk_forward(fake_run(), SPACE, folds)
        assert all(f.params == {"a": 2, "b": 20} for f in rep.folds)
        eff = rep.efficiency
        assert eff is not None and 0.5 < eff <= 1.0
        assert rep.out_of_sample_trades == 40 * len(folds)


class TestMonteCarlo:
    def test_order_resampling_keeps_the_final_equity(self) -> None:
        mc = monte_carlo([100, -50, 80, -120, 60], 1_000, runs=200, seed=1)
        assert set(mc.final_equities) == {1_070.0}
        assert mc.probability_of_loss() == 0.0
        assert mc.drawdown_percentile(95) >= mc.drawdown_percentile(50) >= 0

    def test_seeded_and_bootstrap(self) -> None:
        a = monte_carlo([10, -5, 3, -8], 100, runs=50, seed=3, bootstrap=True)
        b = monte_carlo([10, -5, 3, -8], 100, runs=50, seed=3, bootstrap=True)
        assert (a.max_drawdowns == b.max_drawdowns).all()
        assert len(set(a.final_equities)) > 1

    def test_worst_order_is_found(self) -> None:
        # four losses in a row are possible in some order: the worst drawdown is their sum
        mc = monte_carlo([-10, -10, -10, -10, 50, 50], 100, runs=2000, seed=0)
        assert mc.max_drawdowns.max() == pytest.approx(40.0)
        assert mc.probability_drawdown_above(39.0) > 0

    def test_no_trades(self) -> None:
        mc = monte_carlo([], 100, runs=10)
        assert mc.drawdown_percentile(95) == 0.0


class TestWarnings:
    def test_clean_case_has_no_warnings(self) -> None:
        m = compute_metrics(
            result([150.0, -100.0] * 30).trades, result([150.0, -100.0] * 30).equity_curve, 10_000
        )
        assert overfitting_warnings(m, combinations=2) == []

    def test_each_warning(self) -> None:
        few = result([500.0, -100.0] * 5)
        m = compute_metrics(few.trades, few.equity_curve, 10_000)
        found = overfitting_warnings(m, combinations=9)
        assert any("only 10 trades" in w for w in found)
        assert any("parameter sets" in w for w in found)
        assert any("profit factor" in w for w in found)

    def test_walk_forward_stability_and_mc_warnings(self) -> None:
        folds = windows(T, datetime(2026, 12, 31, tzinfo=UTC), timedelta(days=120), timedelta(days=60))
        decaying = walk_forward(fake_run(), SPACE, folds)
        res = result([150.0, -100.0] * 30)
        m = compute_metrics(res.trades, res.equity_curve, 10_000)
        strict = Thresholds(min_efficiency=0.99, min_stability=0.99, mc_drawdown_multiple=1.0)
        sens = sensitivity(fake_run(), SPACE)
        mc = monte_carlo([t.net for t in res.trades], 10_000, runs=500)
        found = overfitting_warnings(m, walk=decaying, sens=sens, space=SPACE, mc=mc, thresholds=strict)
        assert any("walk-forward efficiency" in w for w in found)
        assert any("isolated peak" in w for w in found)
        assert any("Monte Carlo" in w for w in found)
