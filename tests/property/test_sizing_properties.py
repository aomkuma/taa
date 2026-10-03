"""Sizing invariants (PLAN §A9, §A31) over arbitrary accounts, prices, specs and entry plans (hypothesis)."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.config import RiskConfig
from app.core.decimal_utils import is_multiple_of, to_decimal
from app.core.enums import Side
from app.market_data.data_models import SymbolSpec
from app.risk.position_sizer import AccountFunds, PositionSizer, SplitMode, WeightScheme, build_parts
from app.risk.reasons import Reason
from tests.risk_data import TickCalculator
from tests.strategy_data import EURUSD_SPEC

STEPS = [("0.01", "0.01"), ("0.01", "0.1"), ("0.1", "0.1"), ("1", "1"), ("0.01", "0.05")]


@st.composite
def specs(draw: st.DrawFn) -> SymbolSpec:
    step, vmin = draw(st.sampled_from(STEPS))
    digits = draw(st.sampled_from([2, 3, 5]))
    tick = 10.0**-digits
    tick_value = draw(st.sampled_from([0.01, 0.1, 1.0, 10.0]))
    return dataclasses.replace(
        EURUSD_SPEC,
        digits=digits,
        point=tick,
        tick_size=tick,
        tick_value=tick_value,
        tick_value_profit=tick_value,
        tick_value_loss=tick_value,
        volume_step=float(step),
        volume_min=float(vmin),
        volume_max=draw(st.sampled_from([1.0, 5.0, 100.0])),
    )


def account(equity: float, balance: float) -> AccountFunds:
    return AccountFunds(equity=equity, balance=balance, margin=0.0, margin_free=equity)


common = {
    "equity": st.floats(50, 1_000_000),
    "balance": st.floats(50, 1_000_000),
    "risk_pct": st.floats(0.05, 2.0),
    "entry": st.floats(0.5, 5000),
    "stop_frac": st.floats(0.0005, 0.05),
    "side": st.sampled_from([Side.BUY, Side.SELL]),
    "lot_limit": st.floats(0.01, 50),
    "spec": specs(),
}


RELAXED = {"max_daily_loss_percent": 10, "max_weekly_loss_percent": 10, "max_total_open_risk_percent": 10}


def make(spec: SymbolSpec, risk_pct: float) -> PositionSizer:
    """Margin is made irrelevant (huge leverage): these properties are about volume and budget."""
    return PositionSizer(
        RiskConfig(max_risk_per_trade_percent=risk_pct, **RELAXED), TickCalculator(spec, leverage=1e9)
    )


@settings(max_examples=300, deadline=None)
@given(**common)
def test_single_order_invariants(
    equity: float,
    balance: float,
    risk_pct: float,
    entry: float,
    stop_frac: float,
    side: Side,
    lot_limit: float,
    spec: SymbolSpec,
) -> None:
    stop = entry * (1 - side.sign * stop_frac)
    assume(abs(entry - stop) > 2 * spec.tick_size)
    sizer = make(spec, risk_pct)
    r = sizer.size(spec, side, entry, stop, account(equity, balance), lot_limit=lot_limit)
    if not r.ok:
        assert r.reason in (Reason.RISK_BELOW_MIN_LOT, Reason.SL_WRONG_SIDE), r.detail
        return
    step = to_decimal(spec.volume_step)
    part = r.parts[0]
    assert r.risk_money <= r.budget  # never above budget
    assert is_multiple_of(r.volume, step)  # step-aligned
    assert r.volume >= to_decimal(spec.volume_min)  # never below the minimum
    assert r.volume <= min(to_decimal(spec.volume_max), to_decimal(lot_limit))
    # never rounded up: one more step would break the budget or a cap
    more = r.volume + step
    assert (
        more * (part.loss_per_lot + part.cost_per_lot) > r.budget
        or more > to_decimal(spec.volume_max)
        or more > to_decimal(lot_limit)
    )


@settings(max_examples=300, deadline=None)
@given(
    **common,
    mode=st.sampled_from([SplitMode.SAME_PRICE, SplitMode.SCALE_IN]),
    scheme=st.sampled_from(list(WeightScheme)),
    k=st.integers(1, 5),
    unit_multiple=st.integers(1, 4),
)
def test_entry_plan_invariants(
    equity: float,
    balance: float,
    risk_pct: float,
    entry: float,
    stop_frac: float,
    side: Side,
    lot_limit: float,
    spec: SymbolSpec,
    mode: SplitMode,
    scheme: WeightScheme,
    k: int,
    unit_multiple: int,
) -> None:
    stop = entry * (1 - side.sign * stop_frac)
    assume(abs(entry - stop) > 20 * spec.tick_size)
    atr = abs(entry - stop) / 3
    tp = entry + side.sign * 3 * abs(entry - stop)
    parts = build_parts(mode, side, entry, stop, tp, k=k, scheme=scheme, atr=atr, spacing_atr=0.5)
    unit = to_decimal(spec.volume_step) * unit_multiple
    r = make(spec, risk_pct).size_plan(
        spec, side, parts, stop, account(equity, balance), lot_limit=lot_limit, lot_unit=float(unit)
    )
    if not r.ok:
        assert r.reason in (Reason.RISK_BELOW_MIN_LOT, Reason.SL_WRONG_SIDE), r.detail
        return
    assert r.risk_money <= r.budget  # with every part filled
    assert r.volume <= to_decimal(lot_limit)
    assert len(r.parts) + r.dropped_parts == len(parts)
    for p in r.parts:
        assert is_multiple_of(p.volume, unit)  # whole taps
        assert p.taps * unit == p.volume
        assert p.volume >= to_decimal(spec.volume_min)
        assert p.volume <= to_decimal(spec.volume_max)
        assert (p.part.entry - r.stop_loss) * side.sign > 0  # type: ignore[operator]
    assert all(isinstance(p.volume, Decimal) for p in r.parts)
