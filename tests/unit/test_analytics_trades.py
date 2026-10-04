"""Trade builder: backtest, paper and shadow fills into one trade record (TAA-1001)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.analytics.trade_builder import (
    Alignment,
    AnalyticsError,
    EntryContext,
    Outcome,
    Scope,
    Skipped,
    context_from_decision,
    from_closed_trade,
    trades_from_backtest,
    trades_from_paper,
    trades_from_shadow,
)
from app.core.enums import ExitReason, Regime, Session, Side, Timeframe, Trend, VolatilityState
from tests.analytics_data import T0, closed_trade, intent_row, market_dict, position_row, shadow_row, trade

SLIP = 0.00001


class TestBacktest:
    def test_record_fields_r_and_excursions(self) -> None:
        (t,) = trades_from_backtest([closed_trade()], run_id="run1").trades
        assert t.trade_id == "BACKTEST:run1:7"
        assert t.scope is Scope.BACKTEST and t.hypothetical
        assert (t.side, t.exit_reason, t.strategy, t.signal_id) == (
            Side.BUY,
            ExitReason.TAKE_PROFIT,
            "setup_fib_pullback",
            "sig-1",
        )
        assert t.net_pnl == pytest.approx(99.0)
        assert t.r_multiple == pytest.approx(99.0 / 50.0)
        assert t.risk_distance == pytest.approx(0.0050)
        assert t.mae_r == pytest.approx(0.4)
        assert t.mfe_r == pytest.approx(2.0)
        assert t.holding == timedelta(hours=5)
        assert t.outcome is Outcome.WIN

    def test_costs_without_context_or_slippage_model_are_partial(self) -> None:
        (t,) = trades_from_backtest([closed_trade()]).trades
        assert t.costs.commission == pytest.approx(0.7) and t.costs.swap == pytest.approx(0.3)
        assert t.costs.spread is None and t.costs.slippage is None and not t.costs.complete
        assert t.costs.total == pytest.approx(1.0)
        assert t.cost_r == pytest.approx(1.0 / 50.0)  # a lower bound
        assert t.slippage_price is None

    def test_spread_and_fixed_slippage_valued_at_the_trades_money_per_price(self) -> None:
        ctx = EntryContext(spread=0.0002)
        (t,) = trades_from_backtest(
            [closed_trade()], contexts={"sig-1": ctx}, slippage={"EURUSD": SLIP}
        ).trades
        # 100 money over 0.0100 price: 10 000 per price unit
        assert t.costs.spread == pytest.approx(2.0)
        assert t.costs.slippage == pytest.approx(0.1)  # entry only: a take-profit is not slipped
        assert t.costs.complete
        assert t.cost_r == pytest.approx((2.0 + 0.1 + 0.7 + 0.3) / 50.0)
        assert t.pre_cost_r == pytest.approx(t.r_multiple + t.cost_r)
        assert t.spread_to_sl == pytest.approx(0.04)

    def test_stop_exit_slips_twice_and_reports_the_gap_beyond_the_stop(self) -> None:
        stopped = closed_trade(exit_reason=ExitReason.STOP_LOSS, exit_price=1.0940, profit=-60.0)
        (t,) = trades_from_backtest([stopped], slippage={"EURUSD": SLIP}).trades
        assert t.slippage_price == pytest.approx(2 * SLIP)
        assert t.slippage_r == pytest.approx(2 * SLIP / 0.0050)
        assert t.stop_at_exit == pytest.approx(1.0950)  # a stop still labelled SL was never moved
        assert t.gap_r == pytest.approx(0.2)
        assert t.outcome is Outcome.LOSS

    def test_moved_stop_is_unknown_for_backtests(self) -> None:
        trailed = closed_trade(exit_reason=ExitReason.TRAILING_STOP, exit_price=1.1060, profit=60.0)
        (t,) = trades_from_backtest([trailed]).trades
        assert t.stop_at_exit is None and t.gap_r is None

    def test_end_of_data_close_is_not_slipped(self) -> None:
        eod = closed_trade(exit_reason=ExitReason.END_OF_DATA, exit_price=1.1020, profit=20.0)
        (t,) = trades_from_backtest([eod], slippage={"EURUSD": SLIP}).trades
        assert t.slippage_price == pytest.approx(SLIP)

    def test_without_planned_risk_r_is_unknown_and_outcome_follows_net(self) -> None:
        (t,) = trades_from_backtest([closed_trade(risk_money=0.0)]).trades
        assert t.r_multiple is None and t.cost_r is None and t.risk_money is None
        assert t.outcome is Outcome.WIN
        (loss,) = trades_from_backtest([closed_trade(risk_money=0.0, profit=-5.0)]).trades
        assert loss.outcome is Outcome.LOSS

    def test_bars_held_from_the_entry_timeframe(self) -> None:
        (t,) = trades_from_backtest(
            [closed_trade()], contexts={"sig-1": EntryContext(timeframe=Timeframe.M15)}
        ).trades
        assert t.bars_held == 20
        assert trades_from_backtest([closed_trade()]).trades[0].bars_held is None

    def test_deterministic(self) -> None:
        trades = [closed_trade(ticket=i) for i in range(3)]
        assert trades_from_backtest(trades) == trades_from_backtest(trades)


class TestPaper:
    def test_initial_stop_and_risk_come_from_the_intent(self) -> None:
        ctx = EntryContext(timeframe=Timeframe.M15, spread=0.0002)
        result = trades_from_paper(
            [position_row()], {"intent-1": intent_row()}, contexts={"sig-1": ctx}, slippage={"EURUSD": SLIP}
        )
        (t,) = result.trades
        assert result.skipped == ()
        assert t.trade_id == "PAPER:paper:2" and t.scope is Scope.PAPER and t.hypothetical
        assert t.initial_sl == pytest.approx(1.0950)  # the row's stop moved to break-even
        assert t.stop_at_exit == pytest.approx(1.1000)
        assert t.exit_reason is ExitReason.BREAK_EVEN
        assert t.r_multiple == pytest.approx(-1.7 / 50.0)
        assert t.outcome is Outcome.SCRATCH
        assert t.bars_held == 12  # the engine's count, not the clock's
        assert t.context is ctx
        assert t.slippage_price == pytest.approx(2 * SLIP)
        assert t.gap_r == pytest.approx(0.0001 / 0.0050)

    def test_limit_entry_is_not_slipped(self) -> None:
        (t,) = trades_from_paper(
            [position_row()], {"intent-1": intent_row(entry_type="LIMIT")}, slippage={"EURUSD": SLIP}
        ).trades
        assert t.slippage_price == pytest.approx(SLIP)

    def test_open_positions_are_not_trades(self) -> None:
        assert trades_from_paper([position_row(status="OPEN")], {}).trades == ()

    def test_incomplete_or_unknown_rows_are_skipped_with_a_reason(self) -> None:
        result = trades_from_paper(
            [position_row(ticket=3, exit_price=None), position_row(ticket=4, exit_reason="WHATEVER")],
            {"intent-1": intent_row()},
        )
        assert result.trades == ()
        assert [s.source_id for s in result.skipped] == ["PAPER:paper:3", "PAPER:paper:4"]
        assert all(s.reason for s in result.skipped)

    def test_without_intent_a_moved_stop_leaves_the_risk_unknown(self) -> None:
        (t,) = trades_from_paper([position_row()], {}).trades
        assert t.initial_sl is None and t.r_multiple is None and t.mae_r is None
        assert t.strategy == "" and t.signal_id == ""

    def test_without_intent_an_unmoved_stop_is_the_initial_stop(self) -> None:
        row = position_row(sl=1.0950, stop_kind="SL", exit_reason="SL", exit_price=1.0950, profit=-50.0)
        (t,) = trades_from_paper([row], {}).trades
        assert t.initial_sl == pytest.approx(1.0950)
        assert t.r_multiple is None  # no planned risk money without the intent
        assert t.mae_r == pytest.approx(0.2)


class TestShadow:
    def test_closed_row_becomes_a_hypothetical_shadow_trade(self) -> None:
        (t,) = trades_from_shadow([shadow_row()]).trades
        assert t.trade_id == "SHADOW:opp-1:PLAN"
        assert t.scope is Scope.SHADOW and t.hypothetical
        assert t.signal_id == "opp-1"
        assert t.r_multiple == pytest.approx(1.986)
        assert t.risk_distance == pytest.approx(0.0050)
        assert t.mfe_r == pytest.approx(2.0)
        assert t.shadow is not None
        assert (t.shadow.source, t.shadow.variant, t.shadow.alerted, t.shadow.followed) == (
            "LIVE",
            "PLAN",
            True,
            False,
        )
        assert t.shadow.tradable

    def test_shadow_costs_in_money_and_r(self) -> None:
        (t,) = trades_from_shadow([shadow_row()]).trades
        assert t.costs.spread == pytest.approx(2.0)
        assert t.costs.slippage == pytest.approx(0.1)
        assert t.costs.commission == pytest.approx(0.7)
        assert t.costs.swap == pytest.approx(0.0)
        # spread 0.04R + entry slippage 0.002R + commission (2.0 - 1.986)R
        assert t.cost_r == pytest.approx(0.04 + 0.002 + 0.014)

    def test_context_from_the_stored_signal_facts(self) -> None:
        (t,) = trades_from_shadow([shadow_row()]).trades
        ctx = t.context
        assert ctx.session is Session.LONDON and ctx.regime is Regime.TRENDING
        assert ctx.timeframe is Timeframe.M15 and ctx.atr == pytest.approx(0.0030)
        assert ctx.htf_trend is Trend.BULLISH and t.alignment is Alignment.WITH
        assert t.bars_held == 24

    def test_not_aligned_is_not_claimed_counter_trend(self) -> None:
        row = shadow_row(features={"ctx:htf_aligned": 0.0})
        (t,) = trades_from_shadow([row]).trades
        assert t.context.htf_trend is None and t.alignment is Alignment.UNKNOWN
        assert t.context.regime is None

    def test_not_tradable_row_keeps_r_without_money(self) -> None:
        row = shadow_row(lot=None, gross_pnl=None, commission=None, swap=None, net_pnl=None, risk_money=None)
        (t,) = trades_from_shadow([row]).trades
        assert t.volume is None and t.net_pnl is None and t.risk_money is None
        assert t.costs.total == 0.0 and t.costs.spread is None
        assert t.r_multiple == pytest.approx(1.986)
        assert t.cost_r == pytest.approx(0.056)
        assert t.shadow is not None and not t.shadow.tradable

    def test_variant_and_source_kept(self) -> None:
        row = shadow_row(shadow_id="opp-1:MANAGED", variant="MANAGED", source="REPLAY")
        (t,) = trades_from_shadow([row]).trades
        assert t.shadow is not None and (t.shadow.variant, t.shadow.source) == ("MANAGED", "REPLAY")

    def test_entry_fallback_leaves_slippage_unknown(self) -> None:
        (t,) = trades_from_shadow([shadow_row(flags=["ENTRY_FALLBACK"])]).trades
        assert t.slippage_price is None and t.costs.slippage is None
        assert t.shadow is not None and t.shadow.flags == ("ENTRY_FALLBACK",)

    def test_stop_exit_slips_entry_and_exit(self) -> None:
        row = shadow_row(exit_reason="SL", exit_price=1.09520, r_multiple=-1.0002, r_net=-1.0142, win=False)
        (t,) = trades_from_shadow([row]).trades
        assert t.slippage_price == pytest.approx(2 * SLIP)
        assert t.outcome is Outcome.LOSS

    def test_open_and_void_rows_are_ignored(self) -> None:
        rows = [shadow_row(status="OPEN"), shadow_row(status="VOID")]
        assert trades_from_shadow(rows) == trades_from_shadow([])

    def test_closed_rows_without_a_result_or_geometry_are_skipped(self) -> None:
        result = trades_from_shadow(
            [
                shadow_row(shadow_id="a:PLAN", r_net=None),
                shadow_row(shadow_id="b:PLAN", initial_sl=1.10021),
                shadow_row(shadow_id="c:PLAN", side="HOLD"),
            ]
        )
        assert result.trades == ()
        assert result.skipped == (
            Skipped("SHADOW:a:PLAN", "closed without exit time, price, reason or R"),
            Skipped("SHADOW:b:PLAN", "no valid stop distance at the fill"),
            Skipped("SHADOW:c:PLAN", "'HOLD' is not a valid Side"),
        )


class TestContext:
    def test_from_decision_record(self) -> None:
        ctx = context_from_decision({"reason_codes": ["FIB_PULLBACK"]}, market_dict(), news_window=True)
        assert ctx.timeframe is Timeframe.M15
        assert ctx.htf_trend is Trend.BULLISH
        assert ctx.regime is Regime.TRENDING  # the entry timeframe's
        assert ctx.volatility is VolatilityState.NORMAL
        assert ctx.atr == pytest.approx(0.0020) and ctx.atr_percentile == pytest.approx(55.0)
        assert ctx.adx == pytest.approx(27.0)  # the higher timeframe's
        assert ctx.session is Session.LONDON
        assert ctx.spread == pytest.approx(0.0002)
        assert (ctx.support, ctx.resistance) == (pytest.approx(1.0960), pytest.approx(1.1060))
        assert ctx.reason_codes == ("FIB_PULLBACK",) and ctx.news_window is True

    def test_malformed_record_is_an_error(self) -> None:
        with pytest.raises(AnalyticsError):
            context_from_decision({}, {"symbol": "EURUSD"})

    def test_sr_distance_in_atr_toward_the_target(self) -> None:
        ctx = context_from_decision({}, market_dict())
        buy = trade(context=ctx)
        assert buy.sr_distance_atr == pytest.approx((1.1060 - 1.1000) / 0.0020)
        sell = trade(side=Side.SELL, context=ctx)
        assert sell.sr_distance_atr == pytest.approx((1.1000 - 1.0960) / 0.0020)


class TestOutcomeAndAlignment:
    @pytest.mark.parametrize(
        ("r", "expected"),
        [(0.2, Outcome.WIN), (0.19, Outcome.SCRATCH), (-0.19, Outcome.SCRATCH), (-0.2, Outcome.LOSS)],
    )
    def test_scratch_band(self, r: float, expected: Outcome) -> None:
        assert trade(r_multiple=r).outcome is expected

    @pytest.mark.parametrize(
        ("side", "trend", "expected"),
        [
            (Side.BUY, Trend.BULLISH, Alignment.WITH),
            (Side.SELL, Trend.BULLISH, Alignment.AGAINST),
            (Side.SELL, Trend.BEARISH, Alignment.WITH),
            (Side.BUY, Trend.NEUTRAL, Alignment.NEUTRAL),
            (Side.BUY, None, Alignment.UNKNOWN),
        ],
    )
    def test_alignment(self, side: Side, trend: Trend | None, expected: Alignment) -> None:
        assert trade(side=side, context=EntryContext(htf_trend=trend)).alignment is expected

    def test_single_trade_builder_takes_an_explicit_scope(self) -> None:
        t = from_closed_trade(closed_trade(), scope=Scope.PAPER, trade_id="PAPER:x")
        assert t.scope is Scope.PAPER and t.entry_time == T0
