"""P/L attribution: one test per rule, ordering, the 3-code cap, fallbacks, texts and evidence (TAA-1003)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.analytics.attribution import MAX_CODES, RULES, TEMPLATES, Code, attribute, render
from app.analytics.trade_builder import Costs, EntryContext, Scope, Trade, trades_from_shadow
from app.core.enums import ExitReason, Side, Timeframe, Trend
from tests.analytics_data import shadow_row, trade

FRIDAY = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)
MONDAY_OPEN = datetime(2026, 10, 5, 0, 5, tzinfo=UTC)


def loss(**kw: Any) -> Trade:
    """A BUY stopped at its initial stop after 10 bars: -1.02R, MAE 1R, MFE 0.1R."""
    base: dict[str, Any] = {
        "exit_reason": ExitReason.STOP_LOSS,
        "exit_price": 1.0950,
        "stop_at_exit": 1.0950,
        "gross_pnl": -50.0,
        "net_pnl": -51.0,
        "r_multiple": -1.02,
        "costs": Costs(spread=0.0, slippage=0.0, commission=0.7, swap=0.3),
        "cost_r": 0.02,
        "mae": 0.0050,
        "mfe": 0.0005,
        "bars_held": 10,
    }
    base.update(kw)
    return trade(**base)


def codes(t: Trade) -> list[Code]:
    return [a.code for a in attribute(t)]


def evidence(t: Trade, code: Code) -> dict[str, Any]:
    (found,) = [a for a in attribute(t) if a.code is code]
    return dict(found.evidence)


class TestWins:
    def test_trailing_capture(self) -> None:
        t = trade(exit_reason=ExitReason.TRAILING_STOP, exit_price=1.1060, r_multiple=1.2, mfe=0.0080)
        (a,) = attribute(t)
        assert a.code is Code.WIN_TRAILING_CAPTURE
        assert a.evidence == {"r": 1.2, "mfe_r": pytest.approx(1.6), "exit_reason": "TRAIL"}
        assert a.text == "The trailing stop locked in +1.20R of a move that reached 1.60R."

    def test_trailing_stop_near_entry_is_a_scratch_not_a_capture(self) -> None:
        t = trade(exit_reason=ExitReason.TRAILING_STOP, r_multiple=0.1, cost_r=0.0)
        assert codes(t) == [Code.SCRATCH_BREAKEVEN]

    def test_trend_continuation(self) -> None:
        t = trade(context=EntryContext(htf_trend=Trend.BULLISH))
        (a,) = attribute(t)
        assert a.code is Code.WIN_TREND_CONTINUATION
        assert a.evidence == {"r": 1.98, "side": "BUY", "htf_trend": "BULLISH"}
        assert a.text == "A BUY with the higher-timeframe BULLISH trend made +1.98R."

    def test_win_in_a_neutral_trend_is_unexplained(self) -> None:
        (a,) = attribute(trade(context=EntryContext(htf_trend=Trend.NEUTRAL)))
        assert a.code is Code.WIN_OTHER
        assert a.text == "Made +1.98R; no specific pattern matched."


class TestScratch:
    def test_breakeven(self) -> None:
        t = trade(exit_reason=ExitReason.BREAK_EVEN, r_multiple=0.05, net_pnl=2.5, cost_r=0.0)
        (a,) = attribute(t)
        assert a.code is Code.SCRATCH_BREAKEVEN
        assert a.evidence == {"r": 0.05, "net_pnl": 2.5, "exit_reason": "BE"}
        assert a.text == "Closed near break-even at +0.05R (exit BE)."


class TestGaps:
    def test_gap_through_stop(self) -> None:
        t = loss(exit_price=1.0930, mae=0.0070)
        assert codes(t)[0] is Code.GAP_THROUGH_STOP
        assert evidence(t, Code.GAP_THROUGH_STOP) == {
            "gap_r": pytest.approx(0.4),
            "stop": 1.0950,
            "exit_price": 1.0930,
            "exit_reason": "SL",
        }

    def test_small_overshoot_is_slippage_not_a_gap(self) -> None:
        assert Code.GAP_THROUGH_STOP not in codes(loss(exit_price=1.0940))  # 0.2R

    def test_unknown_stop_at_exit_is_no_gap(self) -> None:
        assert Code.GAP_THROUGH_STOP not in codes(loss(exit_price=1.0930, stop_at_exit=None))

    def test_weekend_gap_instead_of_a_plain_gap(self) -> None:
        t = loss(entry_time=FRIDAY, exit_time=MONDAY_OPEN, exit_price=1.0930, mae=0.0070)
        found = codes(t)
        assert found[0] is Code.WEEKEND_GAP and Code.GAP_THROUGH_STOP not in found
        assert (
            attribute(t)[0].text
            == "Held over the weekend: the reopening gap filled the stop 0.40R beyond it."
        )

    def test_gapped_trailing_stop_on_a_win(self) -> None:
        t = trade(
            exit_reason=ExitReason.TRAILING_STOP, stop_at_exit=1.1060, exit_price=1.1040, r_multiple=0.8
        )
        assert codes(t) == [Code.WIN_TRAILING_CAPTURE, Code.GAP_THROUGH_STOP]


class TestLosses:
    def test_immediate_adverse(self) -> None:
        t = loss(bars_held=2)
        assert codes(t) == [Code.LOSS_IMMEDIATE_ADVERSE]
        assert evidence(t, Code.LOSS_IMMEDIATE_ADVERSE) == {
            "mae_r": pytest.approx(1.0),
            "mfe_r": pytest.approx(0.1),
            "bars_held": 2,
        }
        assert attribute(t)[0].text == (
            "Went against the entry at once: 1.00R adverse within 2 bars, at best 0.10R in favour."
        )

    @pytest.mark.parametrize(
        "kw",
        [
            {"bars_held": 4},
            {"bars_held": None},
            {"bars_held": 2, "mfe": 0.0015},  # 0.3R
            {"bars_held": 2, "mae": 0.0045},  # never reached -1R
        ],
    )
    def test_immediate_adverse_boundaries(self, kw: dict[str, Any]) -> None:
        assert Code.LOSS_IMMEDIATE_ADVERSE not in codes(loss(**kw))

    def test_gave_back_profit(self) -> None:
        t = loss(mfe=0.0060)
        assert codes(t) == [Code.LOSS_GAVE_BACK_PROFIT]
        assert attribute(t)[0].text == "Was 1.20R in profit before reversing to -1.02R."
        assert Code.LOSS_GAVE_BACK_PROFIT not in codes(loss(mfe=0.0045))

    def test_regime_shift(self) -> None:
        ctx = EntryContext(htf_trend=Trend.BULLISH, htf_trend_at_exit=Trend.BEARISH)
        t = loss(context=ctx)
        assert codes(t) == [Code.LOSS_REGIME_SHIFT]
        assert evidence(t, Code.LOSS_REGIME_SHIFT) == {
            "trend_at_entry": "BULLISH",
            "trend_at_exit": "BEARISH",
            "side": "BUY",
        }
        assert attribute(t)[0].text == "The higher-timeframe trend turned from BULLISH to BEARISH."

    @pytest.mark.parametrize(
        ("before", "after"),
        [(Trend.BULLISH, Trend.NEUTRAL), (Trend.BULLISH, None), (None, Trend.BEARISH)],
    )
    def test_no_regime_shift_without_a_flip_against_the_trade(
        self, before: Trend | None, after: Trend | None
    ) -> None:
        ctx = EntryContext(htf_trend=before, htf_trend_at_exit=after)
        assert Code.LOSS_REGIME_SHIFT not in codes(loss(context=ctx))

    def test_volatility_spike(self) -> None:
        t = loss(context=EntryContext(atr=0.0020, atr_at_exit=0.0032))
        assert codes(t) == [Code.LOSS_VOLATILITY_SPIKE]
        assert evidence(t, Code.LOSS_VOLATILITY_SPIKE)["atr_ratio"] == pytest.approx(1.6)
        assert attribute(t)[0].text == "Volatility expanded during the trade: ATR 1.6x its entry value."
        assert codes(loss(context=EntryContext(atr=0.0020, atr_at_exit=0.0028))) == [Code.LOSS_OTHER]

    def test_news_proximity(self) -> None:
        t = loss(context=EntryContext(news_window=True))
        assert codes(t) == [Code.LOSS_NEWS_PROXIMITY]
        assert attribute(t)[0].text == "A news window overlapped the trade."
        assert codes(loss(context=EntryContext(news_window=None))) == [Code.LOSS_OTHER]

    def test_counter_trend_entry(self) -> None:
        t = loss(context=EntryContext(htf_trend=Trend.BEARISH))
        assert codes(t) == [Code.COUNTER_TREND_ENTRY]
        assert evidence(t, Code.COUNTER_TREND_ENTRY) == {"side": "BUY", "htf_trend": "BEARISH"}
        assert attribute(t)[0].text == "A BUY against the higher-timeframe BEARISH trend."

    def test_counter_trend_win_is_not_blamed(self) -> None:
        t = trade(
            side=Side.SELL,
            entry_price=1.1000,
            initial_sl=1.1050,
            context=EntryContext(htf_trend=Trend.BULLISH),
        )
        assert Code.COUNTER_TREND_ENTRY not in codes(t)

    def test_unexplained_loss(self) -> None:
        (a,) = attribute(loss())
        assert a.code is Code.LOSS_OTHER
        assert a.evidence == {"r": -1.02, "net_pnl": -51.0}
        assert a.text == "Lost -1.02R; no specific pattern matched."


class TestCosts:
    def test_cost_dominated(self) -> None:
        t = loss(r_multiple=-0.3, cost_r=0.25, mae=0.0020)
        ev = evidence(t, Code.COST_DOMINATED)
        assert ev == {
            "cost_r": 0.25,
            "pre_cost_r": pytest.approx(-0.05),
            "cost_share": pytest.approx(5.0),
            "costs_complete": True,
        }
        assert render(Code.COST_DOMINATED, ev) == "Costs took 0.25R against a -0.05R result before costs."

    def test_costs_on_a_flat_result_have_no_share(self) -> None:
        t = trade(r_multiple=-0.1, cost_r=0.1)
        assert codes(t) == [Code.SCRATCH_BREAKEVEN, Code.COST_DOMINATED]
        assert evidence(t, Code.COST_DOMINATED)["cost_share"] is None

    def test_small_costs_do_not_dominate(self) -> None:
        assert Code.COST_DOMINATED not in codes(trade())  # 0.06R of +2.04R
        assert Code.COST_DOMINATED not in codes(trade(r_multiple=-0.3, cost_r=None))

    def test_high_slippage(self) -> None:
        t = loss(slippage_price=0.0006)
        assert codes(t) == [Code.HIGH_SLIPPAGE]
        assert evidence(t, Code.HIGH_SLIPPAGE) == {
            "slippage_r": pytest.approx(0.12),
            "slippage_price": 0.0006,
        }
        assert attribute(t)[0].text == "Slippage cost 0.12R of the initial risk."
        assert Code.HIGH_SLIPPAGE not in codes(loss(slippage_price=0.0004))
        assert Code.HIGH_SLIPPAGE not in codes(loss(slippage_price=None))


class TestSelection:
    def test_at_most_three_codes_in_rule_order(self) -> None:
        ctx = EntryContext(htf_trend=Trend.BEARISH, news_window=True)
        t = loss(bars_held=1, exit_price=1.0930, mae=0.0070, context=ctx, slippage_price=0.0010)
        assert codes(t) == [Code.GAP_THROUGH_STOP, Code.LOSS_IMMEDIATE_ADVERSE, Code.LOSS_NEWS_PROXIMITY]
        assert len(attribute(t)) == MAX_CODES

    def test_unknown_risk_disables_r_rules(self) -> None:
        t = loss(initial_sl=None, r_multiple=None, cost_r=None, bars_held=1, slippage_price=0.0010)
        assert t.outcome.value == "LOSS"
        assert codes(t) == [Code.LOSS_OTHER]
        assert attribute(t)[0].text == "Lost n/a; no specific pattern matched."

    def test_hypothetical_label_follows_the_scope(self) -> None:
        assert attribute(trade())[0].hypothetical
        assert not attribute(trade(scope=Scope.LIVE))[0].hypothetical

    def test_shadow_trade_is_attributed_and_labelled_hypothetical(self) -> None:
        (t,) = trades_from_shadow([shadow_row()]).trades
        (a,) = attribute(t)
        assert a.code is Code.WIN_TREND_CONTINUATION and a.hypothetical

    def test_every_code_has_a_template_and_a_translation_key(self) -> None:
        assert set(TEMPLATES) == set(Code)
        assert {code for code, _ in RULES} == set(Code) - {Code.WIN_OTHER, Code.LOSS_OTHER}
        (a,) = attribute(trade())
        assert a.text_key == "analytics.attribution.WIN_OTHER"

    def test_deterministic(self) -> None:
        t = loss(bars_held=2, context=EntryContext(timeframe=Timeframe.M15, news_window=True))
        assert attribute(t) == attribute(t)
        assert attribute(loss(entry_time=FRIDAY, exit_time=FRIDAY + timedelta(hours=2))) == attribute(
            loss(entry_time=FRIDAY, exit_time=FRIDAY + timedelta(hours=2))
        )
