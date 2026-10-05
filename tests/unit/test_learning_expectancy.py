"""Expectancy decomposition E[R] = p·W − (1 − p)·L − c and the lever split (TAA-L801)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.analytics.trade_builder import Trade
from app.learning.expectancy import by_group, decompose, lever_change
from tests.analytics_data import T0, trade


def rated(r: float, cost: float | None, i: int, **kw: object) -> Trade:
    return trade(
        trade_id=f"BACKTEST:{i}",
        r_multiple=r,
        cost_r=cost,
        entry_time=T0 + timedelta(days=i),
        **kw,  # type: ignore[arg-type]
    )


def book(results: list[tuple[float, float]], **kw: object) -> list[Trade]:
    return [rated(r, c, i, **kw) for i, (r, c) in enumerate(results)]


class TestDecompose:
    def test_the_levers_sum_to_the_measured_expectancy(self) -> None:
        trades = book([(1.9, 0.1), (-1.1, 0.1), (2.85, 0.15), (-1.05, 0.05), (-0.1, 0.1)])
        d = decompose(trades)
        assert d is not None
        # pre-cost R: 2.0, -1.0, 3.0, -1.0, 0.0 → p = 2/5, W = 2.5, L = (1 + 1 + 0) / 3, c = 0.1
        assert d.p == pytest.approx(0.4)
        assert d.win_r == pytest.approx(2.5)
        assert d.loss_r == pytest.approx(2 / 3)
        assert d.cost_r == pytest.approx(0.1)
        assert d.expectancy_r == pytest.approx(d.measured_r)
        assert d.ci.low <= d.measured_r <= d.ci.high and d.ci.n == 5
        assert d.per_week == pytest.approx(5 / (4 / 7))
        assert d.hypothetical and d.unknown_costs == 0

    def test_unknown_costs_are_left_out_and_counted(self) -> None:
        trades = [*book([(1.0, 0.1), (-1.0, 0.1)]), rated(2.0, None, 9)]
        d = decompose(trades)
        assert d is not None and d.n == 2 and d.unknown_costs == 1
        assert d.expectancy_r == pytest.approx(d.measured_r)

    def test_nothing_usable(self) -> None:
        assert decompose([rated(1.0, None, 0)]) is None
        assert decompose([]) is None

    def test_single_instant_has_no_rate(self) -> None:
        d = decompose([rated(1.0, 0.1, 0)])
        assert d is not None and d.per_week is None

    def test_by_group(self) -> None:
        trades = book([(1.0, 0.1), (-1.0, 0.1)]) + book([(2.0, 0.1)], symbol="GBPUSD")
        groups = by_group(trades, key=lambda t: t.symbol)
        assert [g.key for g in groups] == ["EURUSD", "GBPUSD"]
        assert groups[0].n == 2 and groups[1].n == 1


class TestLeverChange:
    def test_parts_sum_exactly_and_name_the_main_lever(self) -> None:
        before = decompose(book([(1.9, 0.1), (-1.1, 0.1), (-1.1, 0.1), (1.9, 0.1)]))
        cheaper = decompose(book([(1.95, 0.05), (-1.05, 0.05), (-1.05, 0.05), (1.95, 0.05)]))
        assert before is not None and cheaper is not None
        change = lever_change(before, cheaper)
        assert change.p + change.win_r + change.loss_r + change.cost_r == pytest.approx(change.total)
        assert change.main == "c" and change.cost_r == pytest.approx(0.05)

        more_wins = decompose(book([(1.9, 0.1), (1.9, 0.1), (-1.1, 0.1), (1.9, 0.1)]))
        assert more_wins is not None
        shift = lever_change(before, more_wins)
        assert shift.p + shift.win_r + shift.loss_r + shift.cost_r == pytest.approx(shift.total)
        assert shift.main == "p"
