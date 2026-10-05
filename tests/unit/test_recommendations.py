"""Recommendations from closed trades: bootstrap CI, the A16 rules, sample sizes, backtest changes (TAA-1004)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.analytics.recommendations import (
    MIN_SAMPLES,
    AccountFacts,
    BacktestChange,
    Inputs,
    Kind,
    as_dict,
    bootstrap_mean_ci,
    cost_drag,
    earlier_break_even,
    recommend,
    reduce_risk,
    request_fields,
    restrict_segments,
    stop_too_tight,
)
from app.analytics.trade_builder import Trade
from app.backtest.presets import BacktestRequest, apply_preset
from app.config import AppConfig
from app.core.enums import ExitReason
from app.core.errors import ConfigError
from tests.analytics_data import T0, trade


def many(n: int, **kw: Any) -> list[Trade]:
    return [trade(trade_id=f"BACKTEST:{i}", entry_time=T0 + timedelta(hours=i), **kw) for i in range(n)]


def losers(n: int, *, mfe: float, start: int = 0, **kw: Any) -> list[Trade]:
    return [
        trade(
            trade_id=f"BACKTEST:L{start + i}",
            exit_reason=ExitReason.STOP_LOSS,
            exit_price=1.095,
            r_multiple=-1.0,
            mfe=mfe,
            entry_time=T0 + timedelta(hours=start + i),
            **kw,
        )
        for i in range(n)
    ]


class TestBootstrap:
    def test_is_seeded_and_brackets_the_mean(self) -> None:
        values = [-1.0, 2.0, -1.0, 0.5, -1.0, 1.5, -1.0, 2.0]
        a, b = bootstrap_mean_ci(values), bootstrap_mean_ci(values)
        assert a == b and a.low <= a.mean <= a.high and a.n == 8
        one = bootstrap_mean_ci([0.5])
        assert one.low == one.high == 0.5
        with pytest.raises(ValueError):
            bootstrap_mean_ci([])


class TestRules:
    def test_a_losing_segment_with_enough_trades_is_restricted(self) -> None:
        bad = many(MIN_SAMPLES, strategy="setup_breakout", r_multiple=-0.8)
        good = many(MIN_SAMPLES, strategy="setup_fib_pullback", r_multiple=1.5)
        recs = restrict_segments(bad + good)
        strategy = [r for r in recs if r.segment == ("strategy", "setup_breakout")]
        assert len(strategy) == 1 and strategy[0].enough and strategy[0].ci is not None
        assert strategy[0].ci.high < 0
        assert strategy[0].change == BacktestChange("exclude_strategy", "setup_breakout")
        assert not [r for r in recs if r.segment == ("strategy", "setup_fib_pullback")]

    def test_a_small_losing_segment_says_nothing(self) -> None:
        bad = many(MIN_SAMPLES - 1, strategy="setup_breakout", r_multiple=-0.8)
        assert restrict_segments(bad + many(40, r_multiple=1.0)) == []

    def test_losers_that_gave_back_one_r(self) -> None:
        trades = losers(12, mfe=0.006) + losers(8, mfe=0.001, start=12)  # 12 of 20 had MFE 1.2R
        [rec] = earlier_break_even(trades)
        assert rec.kind is Kind.EARLIER_BREAK_EVEN and rec.evidence["share"] == 0.6
        assert not rec.enough and rec.sample_size == 20  # shown, with a sample-size warning
        assert earlier_break_even(losers(3, mfe=0.006) + losers(17, mfe=0.001, start=3)) == []

    def test_stops_followed_by_the_target(self) -> None:
        stops = losers(12, mfe=0.001)
        reached = {t.trade_id: i < 6 for i, t in enumerate(stops)}  # 6 of 12 went on to the target
        [rec] = stop_too_tight(Inputs(stops, target_after_stop=reached))
        assert rec.segment == ("strategy", "setup_fib_pullback") and rec.evidence["share"] == 0.5
        assert rec.change == BacktestChange("sl_atr_multiple", 2.0, strategy="setup_fib_pullback")
        assert stop_too_tight(Inputs(stops)) == []  # unknown follow-ups: no claim

    def test_cost_drag_per_symbol(self) -> None:
        costly = many(12, symbol="XAUUSD", r_multiple=0.2, cost_r=0.3)  # 0.3 of 0.5 before costs
        [rec] = cost_drag(costly + many(12, r_multiple=1.9, cost_r=0.05))
        assert rec.segment == ("symbol", "XAUUSD") and rec.evidence["share"] == 0.6

    def test_drawdown_over_half_the_limit(self) -> None:
        [rec] = reduce_risk(AccountFacts(drawdown_percent=6.0, drawdown_limit_percent=10.0, risk_percent=1.5))
        assert rec.change == BacktestChange("risk_percent", 0.75) and rec.enough
        assert reduce_risk(AccountFacts(4.0, 10.0, 1.5)) == [] and reduce_risk(None) == []

    def test_recommend_puts_the_account_first_and_serializes(self) -> None:
        trades = losers(12, mfe=0.006) + losers(8, mfe=0.001, start=12)
        recs = recommend(Inputs(trades, account=AccountFacts(8.0, 10.0, 1.0)))
        assert [r.kind for r in recs][:2] == [Kind.REDUCE_RISK, Kind.EARLIER_BREAK_EVEN]
        doc = as_dict(recs[1])
        assert (
            doc["key"] == "analytics.recommendation.EARLIER_BREAK_EVEN" and doc["min_samples"] == MIN_SAMPLES
        )
        assert doc["change"] == {"kind": "break_even_trigger_r", "value": 0.75, "strategy": None}


class TestBacktestThisChange:
    def base(self, **fields: Any) -> BacktestRequest:
        return BacktestRequest.model_validate(
            {"start": "2026-08-01T00:00:00+00:00", "end": "2026-09-01T00:00:00+00:00"} | fields
        )

    def test_every_change_kind_becomes_a_valid_job(self) -> None:
        cfg = AppConfig()
        changes = [
            BacktestChange("exclude_strategy", "example_trend_pullback"),
            BacktestChange("risk_percent", 0.25),
            BacktestChange("break_even_trigger_r", 0.75),
            BacktestChange("max_spread_to_sl_ratio", 0.10),
            BacktestChange("sl_atr_multiple", 2.0, strategy="example_trend_pullback"),
        ]
        jobs = [apply_preset(cfg, self.base(**(request_fields(c, ["EURUSD"]) or {}))) for c in changes]
        assert [i.enabled for i in jobs[0].strategies.items] == [False]
        assert jobs[1].risk.max_risk_per_trade_percent == 0.25
        assert jobs[2].position_management.break_even_trigger_r == 0.75
        assert jobs[3].risk.max_spread_to_sl_ratio == 0.10
        assert jobs[4].strategies.items[0].params["sl_atr_multiple"] == 2.0
        assert cfg.position_management.break_even_trigger_r == 1.0  # the base config is untouched

    def test_excluding_a_symbol(self) -> None:
        assert request_fields(BacktestChange("exclude_symbol", "XAUUSD"), ["EURUSD", "XAUUSD"]) == {
            "symbols": ["EURUSD"]
        }
        assert request_fields(BacktestChange("exclude_symbol", "XAUUSD"), ["XAUUSD"]) is None

    @pytest.mark.parametrize(
        "bad",
        [
            {"change": {"kind": "break_even_trigger_r", "value": 9}},
            {"change": {"kind": "sl_atr_multiple", "value": 2.0}},  # no strategy
            {"change": {"kind": "max_spread_to_sl_ratio", "value": 0.1, "strategy": "x"}},
            {"change": {"kind": "max_risk", "value": 5}},
            {"strategies": ["a"], "exclude_strategies": ["b"]},
        ],
    )
    def test_out_of_bounds_changes_are_refused(self, bad: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            self.base(symbols=["EURUSD"], **bad)

    def test_unknown_strategies_are_refused(self) -> None:
        with pytest.raises(ConfigError):
            apply_preset(AppConfig(), self.base(symbols=["EURUSD"], exclude_strategies=["nope"]))
