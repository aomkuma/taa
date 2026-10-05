"""Timing diagnostics: follow-up after a stop, failure modes, random-walk baseline, reports (TAA-L701)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics.trade_builder import EntryContext, Trade
from app.core.enums import ExitReason, Session, Side, Timeframe, Trend
from app.learning.timing import (
    FailureMode,
    TimingError,
    TimingParams,
    Vindication,
    classify,
    first_passage,
    follow_up,
    report,
    sigma_from_atr,
)
from tests.analytics_data import T0, trade

M15 = timedelta(minutes=15)
EXIT = T0 + timedelta(hours=5)


def bars(start: datetime, rows: Sequence[tuple[float, float, float]]) -> pd.DataFrame:
    """M15 bid bars (high, low, close) from ``start``."""
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime([start + i * M15 for i in range(len(rows))], utc=True),
            "high": [r[0] for r in rows],
            "low": [r[1] for r in rows],
            "close": [r[2] for r in rows],
        }
    )


def stopped(**kw: object) -> Trade:
    """A BUY stopped out: entry 1.1000, SL 1.0950 (risk 0.0050), TP 1.1100; ATR 0.0010."""
    base = trade(
        exit_reason=ExitReason.STOP_LOSS,
        exit_price=1.0950,
        exit_time=EXIT,
        r_multiple=-1.0,
        net_pnl=-50.0,
        mfe=0.0010,
        mae=0.0050,
        context=EntryContext(timeframe=Timeframe.M15, atr=0.0010, session=Session.LONDON),
    )
    return dataclasses.replace(base, **kw)  # type: ignore[arg-type]


def flat_before(n: int = 60, price: float = 1.1000) -> pd.DataFrame:
    return bars(T0 - n * M15, [(price + 0.0002, price - 0.0002, price)] * n)


def with_after(rows: Sequence[tuple[float, float, float]], start: datetime = EXIT) -> pd.DataFrame:
    return pd.concat([flat_before(), bars(start, rows)], ignore_index=True)


class TestFollowUp:
    def test_target_before_a_further_r_is_vindicated(self) -> None:
        path = with_after([(1.0990, 1.0940, 1.0985), (1.1105, 1.0980, 1.1100)])
        assert follow_up(stopped(), path, timedelta(hours=72)) is Vindication.VINDICATED

    def test_a_further_r_first_is_not_vindicated(self) -> None:
        path = with_after([(1.0960, 1.0899, 1.0905), (1.1105, 1.0980, 1.1100)])
        assert follow_up(stopped(), path, timedelta(hours=72)) is Vindication.NOT_VINDICATED

    def test_both_in_one_bar_is_pessimistic(self) -> None:
        path = with_after([(1.1105, 1.0899, 1.1000)])
        assert follow_up(stopped(), path, timedelta(hours=72)) is Vindication.NOT_VINDICATED

    def test_bars_before_the_exit_do_not_count(self) -> None:
        # the exit bar opened before the exit: its high is from before the stop was hit
        path = with_after([(1.1105, 1.0940, 1.0950)], start=EXIT - M15)
        assert follow_up(stopped(), path, timedelta(hours=72)) is Vindication.UNKNOWN

    def test_beyond_the_look_ahead_is_unknown(self) -> None:
        path = with_after([(1.1105, 1.0980, 1.1100)], start=EXIT + timedelta(hours=3))
        assert follow_up(stopped(), path, timedelta(hours=2)) is Vindication.UNKNOWN

    def test_a_sell_compares_the_ask(self) -> None:
        sell = stopped(
            side=Side.SELL,
            initial_sl=1.1050,
            initial_tp=1.0900,
            exit_price=1.1050,
            context=EntryContext(timeframe=Timeframe.M15, atr=0.0010, spread=0.0002),
        )
        # bid low 1.0899 is an ask of 1.0901: the take-profit at 1.0900 was not reached
        assert follow_up(sell, with_after([(1.0950, 1.0899, 1.0905)]), timedelta(hours=72)) is (
            Vindication.UNKNOWN
        )
        assert follow_up(sell, with_after([(1.0950, 1.0897, 1.0905)]), timedelta(hours=72)) is (
            Vindication.VINDICATED
        )

    def test_not_a_stop_exit_or_no_target_is_unknown(self) -> None:
        path = with_after([(1.1105, 1.0980, 1.1100)])
        assert follow_up(stopped(exit_reason=ExitReason.TIME_STOP), path, timedelta(hours=72)) is (
            Vindication.UNKNOWN
        )
        assert follow_up(stopped(initial_tp=None), path, timedelta(hours=72)) is Vindication.UNKNOWN


class TestClassify:
    def test_a_winner_is_not_a_failure(self) -> None:
        d = classify(trade(), None)
        assert d.mode is None and d.vindication is None

    def test_vindicated_stop_is_early(self) -> None:
        d = classify(stopped(), with_after([(1.1105, 1.0980, 1.1100)]))
        assert d.mode is FailureMode.EARLY and d.vindication is Vindication.VINDICATED

    def test_a_run_before_entry_is_late(self) -> None:
        run = bars(
            T0 - 11 * M15,
            [(1.0981 + i * 0.0002, 1.0979 + i * 0.0002, 1.0980 + i * 0.0002) for i in range(11)],
        )
        path = pd.concat([run, bars(EXIT, [(1.0960, 1.0899, 1.0905)])], ignore_index=True)
        d = classify(stopped(), path)
        assert d.pre_run_atr == pytest.approx(2.0)
        assert d.mode is FailureMode.LATE

    def test_time_stop_and_flat_manual_closes_are_stall(self) -> None:
        assert classify(stopped(exit_reason=ExitReason.TIME_STOP, r_multiple=-0.4), None).mode is (
            FailureMode.STALL
        )
        manual = stopped(exit_reason=ExitReason.MANUAL, r_multiple=-0.3, mfe=0.0010)  # +0.2R at best
        assert classify(manual, None).mode is FailureMode.STALL
        moved = stopped(exit_reason=ExitReason.MANUAL, r_multiple=-0.3, mfe=0.0040)  # +0.8R, then given back
        assert classify(moved, None).mode is FailureMode.OTHER

    def test_htf_right_entry_tf_against_is_tf_mismatch(self) -> None:
        falling = bars(
            T0 - 60 * M15,
            [(1.1100 - i * 0.0002, 1.1096 - i * 0.0002, 1.1098 - i * 0.0002) for i in range(60)],
        )
        path = pd.concat([falling, bars(EXIT, [(1.0960, 1.0899, 1.0905)])], ignore_index=True)
        aligned = EntryContext(
            timeframe=Timeframe.M15, atr=0.0010, htf_trend=Trend.BULLISH, htf_trend_at_exit=Trend.BULLISH
        )
        assert classify(stopped(context=aligned), path).mode is FailureMode.TF_MISMATCH
        no_htf = EntryContext(timeframe=Timeframe.M15, atr=0.0010)
        assert classify(stopped(context=no_htf), path).mode is FailureMode.WRONG

    def test_not_vindicated_is_wrong_and_no_facts_is_unknown(self) -> None:
        assert classify(stopped(), with_after([(1.0960, 1.0899, 1.0905)])).mode is FailureMode.WRONG
        assert classify(stopped(), None).mode is FailureMode.UNKNOWN

    def test_a_scratch_is_not_a_failure(self) -> None:
        assert classify(stopped(exit_reason=ExitReason.BREAK_EVEN, r_multiple=0.0), None).mode is None


class TestBaseline:
    def test_first_passage_formulas(self) -> None:
        assert first_passage(2.0, 1.0, 1.0) == (pytest.approx(1 / 3), pytest.approx(2.0))
        assert first_passage(2.0, 1.0)[1] is None
        with pytest.raises(TimingError):
            first_passage(0.0, 1.0)

    def test_matches_a_simulated_random_walk(self) -> None:
        rng = np.random.default_rng(7)
        a, b, paths = 4, 2, 4000
        hits, steps = 0, []
        for _ in range(paths):
            x, n = 0, 0
            while -b < x < a:
                x += 1 if rng.random() < 0.5 else -1
                n += 1
            hits += x >= a
            steps.append(n)
        p, expected = first_passage(a, b, 1.0)
        assert hits / paths == pytest.approx(p, abs=0.03)
        assert float(np.mean(steps)) == pytest.approx(expected, rel=0.06)

    def test_trade_baselines(self) -> None:
        d = classify(stopped(), None)
        # reward 0.0100, risk 0.0050: P(TP first) = 1/3; after the stop, TP before a further 1R = 0.25
        assert d.baseline_p_tp == pytest.approx(1 / 3)
        assert d.baseline_vindication == pytest.approx(0.25)
        sigma = sigma_from_atr(0.0010)
        assert d.baseline_bars == pytest.approx(0.0100 * 0.0050 / sigma**2)


class TestReport:
    def test_shares_quantiles_and_hit_rate(self) -> None:
        winners = [
            trade(
                trade_id=f"W{i}",
                mae=0.0005 * (i + 1),
                context=EntryContext(atr=0.0010, session=Session.LONDON),
            )
            for i in range(10)
        ]
        early = [stopped(trade_id=f"E{i}") for i in range(3)]
        wrong = [stopped(trade_id=f"X{i}") for i in range(1)]
        paths = {t.trade_id: with_after([(1.1105, 1.0980, 1.1100)]) for t in early}
        paths |= {t.trade_id: with_after([(1.0960, 1.0899, 1.0905)]) for t in wrong}
        (rep,) = report(winners + early + wrong, lambda t: paths.get(t.trade_id), params=TimingParams())
        assert rep.trades == 14 and rep.losers == 4
        assert rep.modes[FailureMode.EARLY].count == 3 and rep.modes[FailureMode.EARLY].share == 0.75
        assert rep.modes[FailureMode.WRONG].count == 1
        early_share = rep.modes[FailureMode.EARLY]
        assert early_share.low < 0.75 < early_share.high
        assert rep.hit_rate is not None and rep.hit_rate.count == 10 and rep.hit_rate.n == 14
        assert rep.baseline_hit_rate == pytest.approx(1 / 3)
        assert rep.vindicated is not None and rep.vindicated.count == 3 and rep.vindicated.n == 4
        assert rep.winner_mae_r is not None and rep.winner_mae_r[0.5] == pytest.approx(0.55)
        assert rep.winner_bars_to_tp is not None and rep.winner_bars_to_tp[0.5] == 20.0

    def test_small_groups_have_no_quantiles(self) -> None:
        (rep,) = report([trade()], lambda t: None)
        assert rep.winner_mae_r is None and rep.losers == 0
        assert rep.modes[FailureMode.EARLY].n == 0

    def test_groups_by_symbol_strategy_and_session(self) -> None:
        a = trade(trade_id="A", context=EntryContext(session=Session.LONDON))
        b = trade(trade_id="B", symbol="GBPUSD", context=EntryContext(session=Session.LONDON))
        keys = [r.key for r in report([a, b], lambda t: None)]
        assert keys == [
            ("EURUSD", "setup_fib_pullback", "LONDON"),
            ("GBPUSD", "setup_fib_pullback", "LONDON"),
        ]
