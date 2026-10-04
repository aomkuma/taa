"""P/L attribution (PLAN §A16 "Attribution"; TAA-1003): 1-3 reason codes per trade, each with a one-line
text and the evidence values behind it.

Deterministic rules over a :class:`~app.analytics.trade_builder.Trade`. The rules are checked in the order
of :data:`RULES` and the first :data:`MAX_CODES` that hold are kept. A trade no rule explains gets
``WIN_OTHER`` / ``LOSS_OTHER``; every scratch gets ``SCRATCH_BREAKEVEN``. A rule whose facts are unknown
(no initial stop, no exit-time trend, an unknown cost component) does not fire: attribution never guesses.

Fills store no price path, so ``LOSS_IMMEDIATE_ADVERSE`` reads "-1R within 3 bars" as a trade that reached
MAE >= 1R and was over within 3 entry-timeframe bars. The texts are English; the PWA renders the code's
translation key (``text_key``) with the same evidence values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.analytics.trade_builder import Alignment, Outcome, Trade, at_least
from app.core.enums import ExitReason


class Code(StrEnum):
    WIN_TRAILING_CAPTURE = "WIN_TRAILING_CAPTURE"
    WIN_TREND_CONTINUATION = "WIN_TREND_CONTINUATION"
    SCRATCH_BREAKEVEN = "SCRATCH_BREAKEVEN"
    WEEKEND_GAP = "WEEKEND_GAP"
    GAP_THROUGH_STOP = "GAP_THROUGH_STOP"
    LOSS_IMMEDIATE_ADVERSE = "LOSS_IMMEDIATE_ADVERSE"
    LOSS_GAVE_BACK_PROFIT = "LOSS_GAVE_BACK_PROFIT"
    LOSS_REGIME_SHIFT = "LOSS_REGIME_SHIFT"
    LOSS_VOLATILITY_SPIKE = "LOSS_VOLATILITY_SPIKE"
    LOSS_NEWS_PROXIMITY = "LOSS_NEWS_PROXIMITY"
    COUNTER_TREND_ENTRY = "COUNTER_TREND_ENTRY"
    COST_DOMINATED = "COST_DOMINATED"
    HIGH_SLIPPAGE = "HIGH_SLIPPAGE"
    WIN_OTHER = "WIN_OTHER"
    LOSS_OTHER = "LOSS_OTHER"


MAX_CODES = 3
IMMEDIATE_BARS = 3
IMMEDIATE_MFE_R = 0.3
GAVE_BACK_MFE_R = 1.0
GAP_R = 0.25  # a stop filled this far beyond its level (slippage included) is a gap
VOLATILITY_SPIKE_RATIO = 1.5  # ATR at the exit over ATR at the entry
COST_SHARE = 0.3  # costs above this share of the absolute result before costs
HIGH_SLIPPAGE_R = 0.1

Evidence = float | int | str | bool | None
Rule = Callable[[Trade], dict[str, Evidence] | None]

TEMPLATES: dict[Code, str] = {
    Code.WIN_TRAILING_CAPTURE: "The trailing stop locked in {r} of a move that reached {mfe_r}.",
    Code.WIN_TREND_CONTINUATION: "A {side} with the higher-timeframe {htf_trend} trend made {r}.",
    Code.SCRATCH_BREAKEVEN: "Closed near break-even at {r} (exit {exit_reason}).",
    Code.WEEKEND_GAP: "Held over the weekend: the reopening gap filled the stop {gap_r} beyond it.",
    Code.GAP_THROUGH_STOP: "Price gapped through the stop: the fill was {gap_r} beyond it.",
    Code.LOSS_IMMEDIATE_ADVERSE: (
        "Went against the entry at once: {mae_r} adverse within {bars_held} bars, at best {mfe_r} in favour."
    ),
    Code.LOSS_GAVE_BACK_PROFIT: "Was {mfe_r} in profit before reversing to {r}.",
    Code.LOSS_REGIME_SHIFT: "The higher-timeframe trend turned from {trend_at_entry} to {trend_at_exit}.",
    Code.LOSS_VOLATILITY_SPIKE: "Volatility expanded during the trade: ATR {atr_ratio}x its entry value.",
    Code.LOSS_NEWS_PROXIMITY: "A news window overlapped the trade.",
    Code.COUNTER_TREND_ENTRY: "A {side} against the higher-timeframe {htf_trend} trend.",
    Code.COST_DOMINATED: "Costs took {cost_r} against a {pre_cost_r} result before costs.",
    Code.HIGH_SLIPPAGE: "Slippage cost {slippage_r} of the initial risk.",
    Code.WIN_OTHER: "Made {r}; no specific pattern matched.",
    Code.LOSS_OTHER: "Lost {r}; no specific pattern matched.",
}


@dataclass(frozen=True, slots=True)
class Attribution:
    code: Code
    text: str
    evidence: Mapping[str, Evidence]
    hypothetical: bool  # from the trade's scope: backtest, paper and shadow results are not real fills

    @property
    def text_key(self) -> str:
        return f"analytics.attribution.{self.code.value}"


# --- rules --------------------------------------------------------------------------------------------------


def _win_trailing_capture(t: Trade) -> dict[str, Evidence] | None:
    if t.outcome is not Outcome.WIN or t.exit_reason is not ExitReason.TRAILING_STOP:
        return None
    return {"r": t.r_multiple, "mfe_r": t.mfe_r, "exit_reason": t.exit_reason.value}


def _win_trend_continuation(t: Trade) -> dict[str, Evidence] | None:
    trend = t.context.htf_trend
    if t.outcome is not Outcome.WIN or t.alignment is not Alignment.WITH or trend is None:
        return None
    return {"r": t.r_multiple, "side": t.side.value, "htf_trend": trend.value}


def _scratch_breakeven(t: Trade) -> dict[str, Evidence] | None:
    if t.outcome is not Outcome.SCRATCH:
        return None
    return {"r": t.r_multiple, "net_pnl": t.net_pnl, "exit_reason": t.exit_reason.value}


def _spans_weekend(entry: datetime, exit_: datetime) -> bool:
    """A Saturday (UTC) between the entry day and the exit day: held over a weekend close."""
    day, last = entry.date(), exit_.date()
    while day < last:
        if day.weekday() == 5:
            return True
        day += timedelta(days=1)
    return False


def _gap(t: Trade, *, weekend: bool) -> dict[str, Evidence] | None:
    gap = t.gap_r
    if gap is None or not at_least(gap, GAP_R) or _spans_weekend(t.entry_time, t.exit_time) is not weekend:
        return None
    return {
        "gap_r": gap,
        "stop": t.stop_at_exit,
        "exit_price": t.exit_price,
        "exit_reason": t.exit_reason.value,
    }


def _weekend_gap(t: Trade) -> dict[str, Evidence] | None:
    return _gap(t, weekend=True)


def _gap_through_stop(t: Trade) -> dict[str, Evidence] | None:
    return _gap(t, weekend=False)


def _loss_immediate_adverse(t: Trade) -> dict[str, Evidence] | None:
    mae, mfe, bars = t.mae_r, t.mfe_r, t.bars_held
    if t.outcome is not Outcome.LOSS or mae is None or mfe is None or bars is None:
        return None
    if bars > IMMEDIATE_BARS or not at_least(mae, 1.0) or at_least(mfe, IMMEDIATE_MFE_R):
        return None
    return {"mae_r": mae, "mfe_r": mfe, "bars_held": bars}


def _loss_gave_back_profit(t: Trade) -> dict[str, Evidence] | None:
    mfe = t.mfe_r
    if t.outcome is not Outcome.LOSS or mfe is None or not at_least(mfe, GAVE_BACK_MFE_R):
        return None
    return {"mfe_r": mfe, "r": t.r_multiple, "exit_reason": t.exit_reason.value}


def _loss_regime_shift(t: Trade) -> dict[str, Evidence] | None:
    before, after = t.context.htf_trend, t.context.htf_trend_at_exit
    if t.outcome is not Outcome.LOSS or before is None or after is None or before is after:
        return None
    if t.alignment_at_exit is not Alignment.AGAINST:
        return None
    return {"trend_at_entry": before.value, "trend_at_exit": after.value, "side": t.side.value}


def _loss_volatility_spike(t: Trade) -> dict[str, Evidence] | None:
    before, after = t.context.atr, t.context.atr_at_exit
    if t.outcome is not Outcome.LOSS or before is None or after is None or before <= 0:
        return None
    ratio = after / before
    if not at_least(ratio, VOLATILITY_SPIKE_RATIO):
        return None
    return {"atr_at_entry": before, "atr_at_exit": after, "atr_ratio": ratio}


def _loss_news_proximity(t: Trade) -> dict[str, Evidence] | None:
    if t.outcome is not Outcome.LOSS or t.context.news_window is not True:
        return None
    return {"news_window": True}


def _counter_trend_entry(t: Trade) -> dict[str, Evidence] | None:
    trend = t.context.htf_trend
    if t.outcome is not Outcome.LOSS or t.alignment is not Alignment.AGAINST or trend is None:
        return None
    return {"side": t.side.value, "htf_trend": trend.value}


def _cost_dominated(t: Trade) -> dict[str, Evidence] | None:
    cost, before = t.cost_r, t.pre_cost_r
    if cost is None or before is None or cost <= 0 or cost <= COST_SHARE * abs(before):
        return None
    return {
        "cost_r": cost,
        "pre_cost_r": before,
        "cost_share": None if before == 0 else cost / abs(before),
        "costs_complete": t.costs.complete,
    }


def _high_slippage(t: Trade) -> dict[str, Evidence] | None:
    slip = t.slippage_r
    if slip is None or not at_least(slip, HIGH_SLIPPAGE_R):
        return None
    return {"slippage_r": slip, "slippage_price": t.slippage_price}


RULES: tuple[tuple[Code, Rule], ...] = (
    (Code.WIN_TRAILING_CAPTURE, _win_trailing_capture),
    (Code.WIN_TREND_CONTINUATION, _win_trend_continuation),
    (Code.SCRATCH_BREAKEVEN, _scratch_breakeven),
    (Code.WEEKEND_GAP, _weekend_gap),
    (Code.GAP_THROUGH_STOP, _gap_through_stop),
    (Code.LOSS_IMMEDIATE_ADVERSE, _loss_immediate_adverse),
    (Code.LOSS_GAVE_BACK_PROFIT, _loss_gave_back_profit),
    (Code.LOSS_REGIME_SHIFT, _loss_regime_shift),
    (Code.LOSS_VOLATILITY_SPIKE, _loss_volatility_spike),
    (Code.LOSS_NEWS_PROXIMITY, _loss_news_proximity),
    (Code.COUNTER_TREND_ENTRY, _counter_trend_entry),
    (Code.COST_DOMINATED, _cost_dominated),
    (Code.HIGH_SLIPPAGE, _high_slippage),
)


# --- text ---------------------------------------------------------------------------------------------------

_SIGNED_R = frozenset({"r", "pre_cost_r"})


def _fmt(key: str, value: Evidence) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool | int | str):
        return str(value)
    if key in _SIGNED_R:
        return f"{value:+.2f}R"
    if key.endswith("_r"):
        return f"{value:.2f}R"
    if key == "atr_ratio":
        return f"{value:.1f}"
    return f"{value:.5g}"


def render(code: Code, evidence: Mapping[str, Evidence]) -> str:
    return TEMPLATES[code].format(**{k: _fmt(k, v) for k, v in evidence.items()})


def _make(code: Code, evidence: dict[str, Evidence], trade: Trade) -> Attribution:
    return Attribution(code, render(code, evidence), evidence, trade.hypothetical)


def attribute(trade: Trade) -> tuple[Attribution, ...]:
    """The trade's 1-3 reason codes, most specific first."""
    out: list[Attribution] = []
    for code, rule in RULES:
        evidence = rule(trade)
        if evidence is not None:
            out.append(_make(code, evidence, trade))
            if len(out) == MAX_CODES:
                break
    if not out:
        code = Code.WIN_OTHER if trade.outcome is Outcome.WIN else Code.LOSS_OTHER
        out.append(_make(code, {"r": trade.r_multiple, "net_pnl": trade.net_pnl}, trade))
    return tuple(out)
