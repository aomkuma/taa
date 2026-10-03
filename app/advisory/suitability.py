"""Suitability metrics and hard gates (PLAN §A25; TAA-6A3).

"Compute once, personalize per user": :func:`collect_facts` asks the broker once per symbol for the
account-independent facts (reference price, typical stop, loss/margin/1%-move of one lot); :func:`assess`
turns them into an account's metrics and gates without touching the broker again, so the cloud personalizer
can run it for every user from cached facts.

- **Typical stop** ``typical_SL = k × ATR(entry TF) + median spread`` (k = ``sl_atr_multiple``, default 1.5).
- **Min-lot risk** ``= min lot × (loss_per_lot + cost_per_lot)`` at the typical stop, the same terms the
  :class:`~app.risk.position_sizer.PositionSizer` floors against; **required equity** is the equity whose risk
  budget covers it (none when the per-trade money cap is below it).
- **Risk-sized lot** comes from the ``PositionSizer`` itself, fed by a calculator that scales the collected
  per-lot facts linearly.
- **Margin** of that lot (or the min lot) is checked × ``margin_buffer`` for temporary margin hikes (R24).
- **Effective leverage** (1%-move method) ``= |P/L of a 1% move| × 100 / equity``.
- **Cost ratio** ``= (median spread cost + commission) / loss at the typical stop``.

| Gate | Passes when |
|---|---|
| G1 Tradable | trading is enabled in a direction, the spec is valid and consistent, a filling mode exists |
| G2 Min-lot affordability | min-lot risk ≤ risk budget |
| G3 Margin | margin × buffer ≤ free margin × utilization cap, and the projected margin level ≥ minimum |
| G4 Cost | cost ratio ≤ ``risk.max_spread_to_sl_ratio`` |
| G5 Stops level | ``stops_level × point`` < ``stops_level_max_fraction`` × typical SL |
| G6 Data | ATR known, enough candles, a quote that is fresh while the market is open |

Each gate result carries an explanation key and parameters (:mod:`app.advisory.explanations`, TH/EN).
Gates that need the typical stop are ``NOT_EVALUATED`` when G1 or G6 leaves it unknown; a symbol is eligible
only when every gate passes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.advisory.asset_classes import AssetClass
from app.broker.filling import resolve_filling
from app.config import RiskConfig, SuitabilityConfig
from app.core.clock import ensure_utc
from app.core.decimal_utils import round_to_tick, to_decimal
from app.core.enums import Side
from app.market_data.data_models import SymbolSpec, Tick
from app.risk.position_sizer import AccountFunds, PositionSizer, ProfitCalculator

HUNDRED = Decimal(100)


class Gate(StrEnum):
    G1_TRADABLE = "G1_TRADABLE"
    G2_MIN_LOT = "G2_MIN_LOT"
    G3_MARGIN = "G3_MARGIN"
    G4_COST = "G4_COST"
    G5_STOPS_LEVEL = "G5_STOPS_LEVEL"
    G6_DATA = "G6_DATA"


class GateStatus(StrEnum):
    OK = "OK"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: Gate
    status: GateStatus
    key: str  # explanation key (app.advisory.explanations)
    params: Mapping[str, Any] = field(default_factory=dict)
    detail: str = ""  # English, for logs and the CLI

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.OK


def _pass(gate: Gate, key: str, **params: Any) -> GateResult:
    return GateResult(gate, GateStatus.OK, key, params)


def _fail(gate: Gate, key: str, detail: str = "", **params: Any) -> GateResult:
    return GateResult(gate, GateStatus.FAIL, key, params, detail)


def _skipped(gate: Gate) -> GateResult:
    return GateResult(gate, GateStatus.NOT_EVALUATED, "gate.not_evaluated", {"gate": gate.value})


# --- facts (broker side, once per symbol) ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SymbolFacts:
    spec: SymbolSpec
    asset_class: AssetClass
    side: Side  # reference direction: BUY unless the symbol is sell-only
    price: float | None  # the side's current quote
    atr: float | None
    median_spread: float  # price units
    typical_sl: float | None  # price distance
    loss_per_lot: float | None  # account currency, 1 lot over the typical stop
    margin_per_lot: float | None
    move_1pct_per_lot: float | None  # |P/L| of 1 lot for a 1% price move
    candles: int
    quote_age_seconds: float | None
    market_open: bool
    problems: tuple[tuple[str, str], ...] = ()  # G1: (explanation key, detail)

    @property
    def symbol(self) -> str:
        return self.spec.name


def tradability_problems(spec: SymbolSpec) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    if not spec.trading_enabled:
        problems.append(("g1.trade_disabled", "trade_mode is DISABLED"))
    elif not (spec.can_buy or spec.can_sell):
        problems.append(("g1.no_direction", "neither buying nor selling is allowed"))
    errors = spec.validation_errors()
    if errors:
        problems.append(("g1.spec_invalid", "; ".join(errors)))
    if resolve_filling(spec) is None:
        problems.append(("g1.no_filling", "no filling mode is allowed for market orders"))
    return problems


def collect_facts(
    spec: SymbolSpec,
    asset_class: AssetClass,
    calculator: ProfitCalculator,
    config: SuitabilityConfig,
    *,
    tick: Tick | None,
    atr: float | None,
    candles: int,
    now: datetime,
    market_open: bool,
    median_spread: float | None = None,
) -> SymbolFacts:
    """Broker calls: ``order_calc_profit`` twice and ``order_calc_margin`` once (when the inputs allow)."""
    problems = tradability_problems(spec)
    side = Side.SELL if spec.can_sell and not spec.can_buy else Side.BUY
    price = None if tick is None else (tick.ask if side is Side.BUY else tick.bid)
    if price is not None and price <= 0:
        price = None
    spread = median_spread if median_spread is not None else spec.spread_points * spec.point
    age = None if tick is None else max(0.0, (ensure_utc(now) - ensure_utc(tick.time_utc)).total_seconds())
    usable_atr = atr if atr is not None and atr > 0 else None
    typical = None if usable_atr is None else config.sl_atr_multiple * usable_atr + spread
    loss = margin = move = None
    if price is not None and not problems:
        if typical is not None:
            raw = calculator.calc_profit(side, spec.name, 1.0, price, price - side.sign * typical)
            loss = None if raw is None else -raw
        margin = calculator.calc_margin(side, spec.name, 1.0, price)
        raw_move = calculator.calc_profit(side, spec.name, 1.0, price, price * 1.01)
        move = None if raw_move is None else abs(raw_move)
        if (
            (typical is not None and (loss is None or loss <= 0))
            or margin is None
            or margin < 0
            or move is None
        ):
            problems.append(("g1.calc_failed", "order_calc_profit/order_calc_margin failed"))
    return SymbolFacts(
        spec=spec,
        asset_class=asset_class,
        side=side,
        price=price,
        atr=usable_atr,
        median_spread=spread,
        typical_sl=typical,
        loss_per_lot=loss,
        margin_per_lot=margin,
        move_1pct_per_lot=move,
        candles=candles,
        quote_age_seconds=age,
        market_open=market_open,
        problems=tuple(problems),
    )


class FactsCalculator:
    """A :class:`ProfitCalculator` scaling a symbol's collected per-lot facts linearly (no broker calls)."""

    def __init__(self, facts: SymbolFacts) -> None:
        if facts.loss_per_lot is None or not facts.typical_sl or facts.margin_per_lot is None:
            raise ValueError(f"{facts.symbol}: incomplete facts")
        self.per_price = facts.loss_per_lot / facts.typical_sl  # P/L of 1 lot per unit of price
        self.margin_per_lot = facts.margin_per_lot

    def calc_profit(
        self, side: Side, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None:
        return side.sign * (price_close - price_open) * self.per_price * volume

    def calc_margin(self, side: Side, symbol: str, volume: float, price: float) -> float | None:
        return self.margin_per_lot * volume


# --- assessment (per account, no broker calls) -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Suitability:
    symbol: str
    asset_class: AssetClass
    side: Side
    gates: tuple[GateResult, ...]
    typical_sl: float | None = None
    risk_budget: Decimal | None = None
    min_lot: Decimal | None = None
    min_lot_risk: Decimal | None = None
    required_equity: Decimal | None = None  # None: unknown, or no equity is enough under the money cap
    lot: Decimal | None = None  # risk-sized; None when below the minimum lot
    risk_money: Decimal | None = None
    margin: Decimal | None = None  # of the risk-sized lot (or the min lot), without the buffer
    margin_level_after: Decimal | None = None  # with the buffer
    margin_share: float | None = None  # margin x buffer / the margin G3 allows
    effective_leverage: float | None = None
    cost_ratio: float | None = None

    @property
    def eligible(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def failed(self) -> tuple[Gate, ...]:
        return tuple(g.gate for g in self.gates if g.status is GateStatus.FAIL)

    def gate(self, gate: Gate) -> GateResult:
        return next(g for g in self.gates if g.gate is gate)


def _money(value: Decimal | float) -> float:
    return round(float(value), 2)


def data_gate(facts: SymbolFacts, config: SuitabilityConfig) -> GateResult:
    g = Gate.G6_DATA
    if facts.price is None:
        return _fail(g, "g6.no_quote", "no current quote")
    age = facts.quote_age_seconds
    if facts.market_open and age is not None and age > config.max_quote_age_seconds:
        return _fail(g, "g6.stale_quote", f"last quote {age:.0f} s old", age=round(age))
    if facts.candles < config.min_candles:
        detail = f"{facts.candles} of {config.min_candles} candles"
        return _fail(g, "g6.few_candles", detail, candles=facts.candles, required=config.min_candles)
    if facts.atr is None:
        return _fail(g, "g6.no_atr", "ATR is not available")
    return _pass(g, "g6.ok")


def assess(
    facts: SymbolFacts,
    funds: AccountFunds,
    risk: RiskConfig,
    config: SuitabilityConfig,
    *,
    currency: str,
    risk_percent: float | None = None,
    commission_per_lot: float = 0.0,
) -> Suitability:
    """Metrics and gates G1–G6 of one symbol for one account; *risk_percent* can only lower the setting."""
    g6 = data_gate(facts, config)
    head = (facts.symbol, facts.asset_class, facts.side)
    later = (Gate.G2_MIN_LOT, Gate.G3_MARGIN, Gate.G4_COST, Gate.G5_STOPS_LEVEL)
    if facts.problems:
        key, detail = facts.problems[0]
        g1 = _fail(Gate.G1_TRADABLE, key, "; ".join(d for _, d in facts.problems))
        return Suitability(*head, gates=(g1, *map(_skipped, later), g6))
    if facts.typical_sl is None or facts.price is None or facts.loss_per_lot is None:
        g1 = _pass(Gate.G1_TRADABLE, "g1.ok")
        return Suitability(*head, gates=(g1, *map(_skipped, later), g6))

    spec, side, price, typical = facts.spec, facts.side, facts.price, facts.typical_sl
    sizer = PositionSizer(risk, FactsCalculator(facts), commission_per_lot=commission_per_lot)
    budget = sizer.risk_budget(funds, risk_percent=risk_percent)
    tick = to_decimal(spec.tick_size)
    entry = round_to_tick(price, tick)
    stop = round_to_tick(price - side.sign * typical, tick, "down" if side is Side.BUY else "up")
    loss = sizer.loss_per_lot(spec, side, entry, stop)
    if isinstance(loss, str):
        g1 = _fail(Gate.G1_TRADABLE, "g1.spec_inconsistent", loss)
        return Suitability(*head, gates=(g1, *map(_skipped, later), g6), typical_sl=typical)
    g1 = _pass(Gate.G1_TRADABLE, "g1.ok")

    # G2: the minimum lot against the risk budget
    cost = sizer.cost_per_lot(spec)
    v_min = to_decimal(spec.volume_min)
    if risk.min_lot is not None:
        v_min = max(v_min, to_decimal(risk.min_lot))
    min_lot_risk = v_min * (loss + cost)
    pct = to_decimal(risk.max_risk_per_trade_percent)
    if risk_percent is not None:
        pct = min(pct, to_decimal(risk_percent))
    cap = None if risk.max_risk_money_per_trade is None else to_decimal(risk.max_risk_money_per_trade)
    required = None if cap is not None and cap < min_lot_risk else (min_lot_risk * HUNDRED / pct)
    money = {"min_lot_risk": _money(min_lot_risk), "budget": _money(budget), "currency": currency}
    if budget >= min_lot_risk:
        g2 = _pass(Gate.G2_MIN_LOT, "g2.ok", **money)
    elif required is not None:
        detail = (
            f"minimum lot risks {min_lot_risk:.2f} vs budget {budget:.2f}; needs equity >= {required:.2f}"
        )
        g2 = _fail(Gate.G2_MIN_LOT, "g2.min_lot_risk", detail, **money, required_equity=_money(required))
    else:  # no equity is enough: the per-trade money cap is below the minimum lot's risk
        limit = cap if cap is not None else budget
        detail = f"minimum lot risks {min_lot_risk:.2f} above the per-trade cap {limit:.2f}"
        g2 = _fail(Gate.G2_MIN_LOT, "g2.cap", detail, **money, cap=_money(limit))

    # the risk-sized lot, by the same sizer the engine uses (its own margin verdict is replaced by G3)
    lot_limit = min(risk.max_lot, spec.volume_limit) if spec.volume_limit > 0 else risk.max_lot
    sized = sizer.size(
        spec, side, float(entry), float(stop), funds, lot_limit=lot_limit, risk_percent=risk_percent
    )
    lot = sized.volume if sized.parts else None
    reference_lot = lot if lot is not None else v_min

    # G3: margin with the hike buffer
    margin = to_decimal(facts.margin_per_lot or 0.0) * reference_lot
    buffered = margin * to_decimal(config.margin_buffer)
    allowed = to_decimal(funds.margin_free) * to_decimal(risk.max_margin_utilization_percent) / HUNDRED
    used = to_decimal(funds.margin) + buffered
    level = to_decimal(funds.equity) / used * HUNDRED if used > 0 else None
    minimum = to_decimal(risk.min_margin_level_percent)
    m = {"margin": _money(buffered), "available": _money(allowed), "currency": currency}
    if buffered > allowed:
        g3 = _fail(Gate.G3_MARGIN, "g3.margin", f"margin x buffer {buffered:.2f} > {allowed:.2f}", **m)
    elif level is not None and level < minimum:
        detail = f"margin level after the trade {level:.0f}% < {minimum:.0f}%"
        g3 = _fail(
            Gate.G3_MARGIN, "g3.margin_level", detail, level=round(float(level)), minimum=float(minimum)
        )
    else:
        g3 = _pass(Gate.G3_MARGIN, "g3.ok", **m)

    # G4: costs as a share of the stop
    spread_cost = facts.median_spread / spec.tick_size * spec.tick_value_loss
    cost_ratio = (spread_cost + commission_per_lot) / float(loss)
    c = {"cost_pct": round(cost_ratio * 100, 1), "max_pct": round(risk.max_spread_to_sl_ratio * 100, 1)}
    if cost_ratio <= risk.max_spread_to_sl_ratio:
        g4 = _pass(Gate.G4_COST, "g4.ok", **c)
    else:
        g4 = _fail(Gate.G4_COST, "g4.cost", f"cost {cost_ratio:.1%} of the stop", **c)

    # G5: the broker's minimum stop distance against the typical stop
    stops_distance = spec.stops_level * spec.point
    s = {"stops_distance": round(stops_distance, spec.digits), "typical_sl": round(typical, spec.digits)}
    if stops_distance < config.stops_level_max_fraction * typical:
        g5 = _pass(Gate.G5_STOPS_LEVEL, "g5.ok", **s)
    else:
        g5 = _fail(
            Gate.G5_STOPS_LEVEL, "g5.stops_level", f"stops level {stops_distance} vs stop {typical}", **s
        )

    leverage = None
    if facts.move_1pct_per_lot is not None and funds.equity > 0:
        leverage = facts.move_1pct_per_lot * float(reference_lot) * 100 / funds.equity
    return Suitability(
        *head,
        gates=(g1, g2, g3, g4, g5, g6),
        typical_sl=typical,
        risk_budget=budget,
        min_lot=v_min,
        min_lot_risk=min_lot_risk,
        required_equity=required,
        lot=lot,
        risk_money=sized.risk_money if lot is not None else None,
        margin=margin,
        margin_level_after=level,
        margin_share=float(buffered / allowed) if allowed > 0 else None,
        effective_leverage=leverage,
        cost_ratio=cost_ratio,
    )
