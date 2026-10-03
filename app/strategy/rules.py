"""Entry rules shared by the strategies: session window, Friday cutoff, costs, stop/target limits.

Each rule is a :class:`Condition` with a stable name, so every strategy explains itself the same way and the
decision engine sees the same reason codes (``REASONS``).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import datetime, time

import pandas as pd
from pydantic import Field, field_validator, model_validator

from app.strategy.base_strategy import StrategyParams
from app.strategy.signal_models import Condition, MarketContext, ReasonCode, StrategyContext


def hhmm(value: str) -> time:
    hours, _, minutes = value.partition(":")
    return time(int(hours), int(minutes))


def known(*values: float | None) -> bool:
    return all(v is not None and math.isfinite(v) for v in values)


def opt_float(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


class EntryRuleParams(StrategyParams):
    """Stop/target, cost and time rules every entry strategy applies."""

    rr_target: float = Field(default=2.0, gt=0, le=10, description="TP in R when no measured target is used")
    min_rr: float = Field(default=1.5, gt=0, le=10)
    max_sl_atr: float = Field(default=3.0, gt=0, le=20)
    max_spread_to_sl: float = Field(default=0.15, gt=0, le=1)
    session_start_utc: str = "07:00"
    session_end_utc: str = "20:00"
    friday_cutoff_utc: str | None = "20:00"

    @field_validator("session_start_utc", "session_end_utc", "friday_cutoff_utc")
    @classmethod
    def _check_hhmm(cls, value: str | None) -> str | None:
        if value is not None:
            hhmm(value)
        return value

    @model_validator(mode="after")
    def _coherent_rules(self) -> EntryRuleParams:
        if self.rr_target < self.min_rr:
            raise ValueError("rr_target must be >= min_rr")
        if hhmm(self.session_start_utc) >= hhmm(self.session_end_utc):
            raise ValueError("session_start_utc must be before session_end_utc")
        return self


REASONS: dict[str, ReasonCode] = {
    "sl_within_limit": ReasonCode.SL_TOO_FAR,
    "rr_ok": ReasonCode.RR_TOO_LOW,
    "spread_ok": ReasonCode.SPREAD_TOO_HIGH,
    "session_window": ReasonCode.OUTSIDE_SESSION,
    "before_friday_cutoff": ReasonCode.FRIDAY_CUTOFF,
}


def time_conditions(at: datetime, p: EntryRuleParams) -> list[Condition]:
    """Entry-bar close inside the weekday session window, and not after the Friday cutoff (UTC)."""
    now = at.time()
    weekday = at.weekday()
    in_session = weekday < 5 and hhmm(p.session_start_utc) <= now <= hhmm(p.session_end_utc)
    cutoff = p.friday_cutoff_utc is not None and (
        weekday > 4 or (weekday == 4 and now >= hhmm(p.friday_cutoff_utc))
    )
    return [
        Condition("session_window", in_session, 1.0, f"{at:%a %H:%M} UTC"),
        Condition("before_friday_cutoff", not cutoff, 1.0, f"cutoff {p.friday_cutoff_utc} UTC Friday"),
    ]


def spread_price(ctx: StrategyContext, last: pd.Series) -> tuple[float, float] | None:
    """(spread in points, spread in price): the live quote's, else the last bar's; None when unknown."""
    points = (
        ctx.market.spread_points if ctx.market.spread_points is not None else opt_float(last.get("spread"))
    )
    if points is None or ctx.spec is None:
        return None
    return points, points * ctx.spec.point


def entry_price(market: MarketContext, close: float, spread: float, buy: bool) -> float:
    """The live ask (BUY) or bid (SELL); bars are bid-based, so without a quote a BUY pays the spread."""
    quoted = market.ask if buy else market.bid
    if quoted is not None:
        return quoted
    return close + spread if buy else close


def risk_conditions(
    *,
    entry: float,
    stop: float,
    take_profit: float,
    atr: float,
    spread: float,
    spread_points: float,
    p: EntryRuleParams,
) -> list[Condition]:
    risk = abs(entry - stop)
    rr = abs(take_profit - entry) / risk if risk > 0 else 0.0
    return [
        Condition(
            "sl_within_limit",
            0 < risk <= p.max_sl_atr * atr,
            1.0,
            f"SL {risk / atr:.2f} ATR (max {p.max_sl_atr:g})",
        ),
        Condition("rr_ok", rr >= p.min_rr, 1.0, f"RR {rr:.2f} (min {p.min_rr:g})"),
        Condition(
            "spread_ok",
            risk > 0 and spread <= p.max_spread_to_sl * risk,
            1.0,
            f"spread {spread_points:g} pts = {spread / risk:.0%} of SL" if risk > 0 else "zero risk",
        ),
    ]


def failed_reasons(conditions: Iterable[Condition], extra: Mapping[str, ReasonCode]) -> list[ReasonCode]:
    """Reason codes of the failed conditions, ordered, without repeats (unknown names: ``NO_SETUP``)."""
    table = {**REASONS, **extra}
    return list(dict.fromkeys(table.get(c.name, ReasonCode.NO_SETUP) for c in conditions if not c.passed))


def explain(conditions: Iterable[Condition]) -> str:
    """One item per checklist entry: ``[x]`` passed, ``[ ]`` failed, with the measured value."""
    return "; ".join(f"[{'x' if c.passed else ' '}] {c.name}: {c.detail}" for c in conditions)
