"""Position sizing (PLAN §A9) and entry-plan sizing (PLAN §A31, "แบ่งไม้").

Money and volumes are :class:`~decimal.Decimal`. Volumes are **floored** to the lot unit and never rounded up,
so the risk with every part filled never exceeds the budget (property-tested).

A single order is a one-part plan, so both paths share one implementation:

1. ``budget = min(basis · risk% / 100, max_risk_money_per_trade) × probation multiplier``, where the basis is
   ``min(equity, balance)`` by default (``risk.sizing_basis``).
2. Prices are aligned to ``trade_tick_size``; the stop is rounded *away* from the entry, which can only lower
   the volume.
3. ``loss_per_lot = −calc_profit(side, symbol, 1.0, entry, stop)`` (broker-computed, account currency).
   It must be > 0; ``None`` or a non-positive value means ``SYMBOL_SPEC_INCONSISTENT``.
4. Cross-check against ``ticks × tick_value_loss``; a difference above ``risk.tick_value_tolerance`` means
   ``SYMBOL_SPEC_INCONSISTENT``.
5. ``cost_per_lot = commission + slippage_allowance_points × (point / tick_size) × tick_value_loss``.
6. ``u = budget / Σ wᵢ(lossᵢ + costᵢ)``, capped so no order exceeds ``volume_max`` and the total stays within
   the symbol's lot limit; ``lotᵢ = floor_to_unit(wᵢ · u)``.
7. A part below ``volume_min`` (or ``risk.min_lot``) drops the deepest part and the plan is recomputed;
   a single part still below it means ``RISK_BELOW_MIN_LOT``.
8. Re-verify ``Σ lotᵢ(lossᵢ + costᵢ) ≤ budget``, then the margin: the plan's margin must fit within
   ``free margin × max_margin_utilization_percent`` and leave a margin level ≥ ``min_margin_level_percent``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal
from enum import StrEnum
from typing import Protocol

from app.config import RiskConfig
from app.core.decimal_utils import floor_to_step, is_multiple_of, round_to_tick, to_decimal
from app.core.enums import EntryType, Side
from app.market_data.data_models import SymbolSpec
from app.risk.reasons import Reason

ZERO = Decimal(0)
HUNDRED = Decimal(100)
MONEY_QUANTUM = Decimal("0.000001")


class ProfitCalculator(Protocol):
    """Broker-side P/L and margin (``MarketDataGateway`` and the simulated broker provide them)."""

    def calc_profit(
        self, side: Side, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None: ...

    def calc_margin(self, side: Side, symbol: str, volume: float, price: float) -> float | None: ...


@dataclass(frozen=True, slots=True)
class AccountFunds:
    equity: float
    balance: float
    margin: float  # margin already in use
    margin_free: float


class SplitMode(StrEnum):
    SINGLE = "SINGLE"
    SAME_PRICE = "SAME_PRICE"  # k orders at one price, staggered take-profits
    SCALE_IN = "SCALE_IN"  # entry 1 now, later limit entries toward the stop, one shared stop


class WeightScheme(StrEnum):
    EQUAL = "EQUAL"
    FRONT_LOADED = "FRONT_LOADED"  # 3:2:1
    BACK_LOADED = "BACK_LOADED"  # 1:2:3 (averages into an adverse move)


@dataclass(frozen=True, slots=True)
class PlanPart:
    entry: Decimal
    weight: Decimal
    order_type: EntryType = EntryType.MARKET
    take_profit: Decimal | None = None


@dataclass(frozen=True, slots=True)
class SizedPart:
    part: PlanPart
    volume: Decimal
    taps: int  # volume / lot unit: how many taps in the MT5 app
    loss_per_lot: Decimal
    cost_per_lot: Decimal

    @property
    def risk_money(self) -> Decimal:
        return self.volume * (self.loss_per_lot + self.cost_per_lot)


@dataclass(frozen=True, slots=True)
class SizingResult:
    ok: bool
    reason: Reason | None
    detail: str
    budget: Decimal
    stop_loss: Decimal | None = None
    lot_unit: Decimal | None = None
    parts: tuple[SizedPart, ...] = ()
    dropped_parts: int = 0
    margin_required: Decimal | None = None
    margin_level_after: Decimal | None = None
    over_budget: bool = False  # the minimum lot was taken although the budget buys less (min_lot_fallback)

    @property
    def volume(self) -> Decimal:
        return sum((p.volume for p in self.parts), ZERO)

    @property
    def risk_money(self) -> Decimal:
        """Loss at the stop, costs included, with **every** part filled."""
        return sum((p.risk_money for p in self.parts), ZERO)

    @property
    def entry(self) -> Decimal | None:
        return self.parts[0].part.entry if self.parts else None


@dataclass(slots=True)
class _Draft:
    """What is known so far; every exit of :meth:`PositionSizer.size_plan` reports it."""

    budget: Decimal
    stop_loss: Decimal | None = None
    lot_unit: Decimal | None = None
    parts: tuple[SizedPart, ...] = ()
    dropped_parts: int = 0
    margin_required: Decimal | None = None
    margin_level_after: Decimal | None = None
    over_budget: bool = False

    def done(self, reason: Reason | None = None, detail: str = "") -> SizingResult:
        return SizingResult(
            ok=reason is None,
            reason=reason,
            detail=detail,
            budget=self.budget,
            stop_loss=self.stop_loss,
            lot_unit=self.lot_unit,
            parts=self.parts,
            dropped_parts=self.dropped_parts,
            margin_required=self.margin_required,
            margin_level_after=self.margin_level_after,
            over_budget=self.over_budget,
        )


def weights(scheme: WeightScheme, k: int) -> list[Decimal]:
    if k < 1:
        raise ValueError("a plan needs at least one part")
    if scheme is WeightScheme.FRONT_LOADED:
        return [Decimal(k - i) for i in range(k)]
    if scheme is WeightScheme.BACK_LOADED:
        return [Decimal(i + 1) for i in range(k)]
    return [Decimal(1)] * k


def build_parts(
    mode: SplitMode,
    side: Side,
    entry: float,
    stop: float,
    take_profit: float | None,
    *,
    k: int = 1,
    scheme: WeightScheme = WeightScheme.EQUAL,
    atr: float | None = None,
    spacing_atr: float = 0.5,
) -> list[PlanPart]:
    """The orders of a plan (PLAN §A31), before sizing.

    - ``SAME_PRICE``: *k* market orders at *entry*; part *i* < *k* takes profit at *i* R (never beyond
      the final target), the last at *take_profit*.
    - ``SCALE_IN``: part 1 at market, part *i* a limit order ``i × spacing_atr × ATR`` toward the stop; levels
      that would reach the stop are dropped.
    """
    e, sl = to_decimal(entry), to_decimal(stop)
    tp = None if take_profit is None else to_decimal(take_profit)
    sign = Decimal(side.sign)
    if mode is SplitMode.SINGLE or k == 1:
        return [PlanPart(e, Decimal(1), EntryType.MARKET, tp)]
    w = weights(scheme, k)
    if mode is SplitMode.SAME_PRICE:
        risk = abs(e - sl)
        parts = []
        for i in range(k):
            target = tp
            if i < k - 1:
                staggered = e + sign * risk * (i + 1)
                target = staggered if tp is None or (tp - staggered) * sign > 0 else tp
            parts.append(PlanPart(e, w[i], EntryType.MARKET, target))
        return parts
    if atr is None or atr <= 0:
        raise ValueError("SCALE_IN needs a positive ATR for its spacing")
    step = to_decimal(spacing_atr) * to_decimal(atr)
    parts = [PlanPart(e, w[0], EntryType.MARKET, tp)]
    for i in range(1, k):
        level = e - sign * step * i
        if (level - sl) * sign <= 0:
            break
        parts.append(PlanPart(level, w[i], EntryType.LIMIT, tp))
    return parts


class PositionSizer:
    def __init__(
        self, risk: RiskConfig, calculator: ProfitCalculator, *, commission_per_lot: float = 0.0
    ) -> None:
        self.risk = risk
        self.calculator = calculator
        self.commission_per_lot = to_decimal(commission_per_lot)

    # budget ----------------------------------------------------------------------------------------------

    def risk_budget(
        self, funds: AccountFunds, *, probation: bool = False, risk_percent: float | None = None
    ) -> Decimal:
        """Step 1. *risk_percent* (a trading profile's value) can only lower the configured percent."""
        pct = to_decimal(self.risk.max_risk_per_trade_percent)
        if risk_percent is not None:
            pct = min(pct, to_decimal(risk_percent))
        basis = {
            "min_equity_balance": min(funds.equity, funds.balance),
            "equity": funds.equity,
            "balance": funds.balance,
        }[self.risk.sizing_basis]
        budget = max(ZERO, to_decimal(basis) * pct / HUNDRED)
        if self.risk.max_risk_money_per_trade is not None:
            budget = min(budget, to_decimal(self.risk.max_risk_money_per_trade))
        if probation:
            budget *= to_decimal(self.risk.probation_multiplier)
        return budget

    # per-lot loss ----------------------------------------------------------------------------------------

    def loss_per_lot(self, spec: SymbolSpec, side: Side, entry: Decimal, stop: Decimal) -> Decimal | str:
        """Steps 3–4: broker loss for 1 lot from *entry* to *stop*, or a problem description."""
        raw = self.calculator.calc_profit(side, spec.name, 1.0, float(entry), float(stop))
        if raw is None:
            return "order_calc_profit returned nothing"
        # broker floats carry noise (200.00000000000017); round up so the noise can only shrink the volume
        loss = (-to_decimal(raw)).quantize(MONEY_QUANTUM, rounding=ROUND_UP)
        if loss <= 0:
            return f"order_calc_profit gave a non-loss {raw} for a stop on the losing side"
        ticks = abs(entry - stop) / to_decimal(spec.tick_size)
        alt = ticks * to_decimal(spec.tick_value_loss)
        if alt <= 0:
            return "tick_value_loss is not positive"
        diff = abs(loss - alt) / max(loss, alt)
        if diff > to_decimal(self.risk.tick_value_tolerance):
            return f"broker loss {loss:.2f} vs tick-value loss {alt:.2f} differ by {diff:.0%}"
        return loss

    def cost_per_lot(self, spec: SymbolSpec) -> Decimal:
        """Step 5: commission plus the slippage allowance, per lot."""
        slip_ticks = (
            to_decimal(self.risk.slippage_allowance_points)
            * to_decimal(spec.point)
            / to_decimal(spec.tick_size)
        )
        return self.commission_per_lot + slip_ticks * to_decimal(spec.tick_value_loss)

    # sizing ----------------------------------------------------------------------------------------------

    def size(
        self,
        spec: SymbolSpec,
        side: Side,
        entry: float,
        stop: float,
        funds: AccountFunds,
        *,
        lot_limit: float,
        probation: bool = False,
        risk_percent: float | None = None,
        min_lot_fallback: bool = False,
    ) -> SizingResult:
        """A single market order."""
        parts = [PlanPart(to_decimal(entry), Decimal(1))]
        return self.size_plan(
            spec,
            side,
            parts,
            stop,
            funds,
            lot_limit=lot_limit,
            probation=probation,
            risk_percent=risk_percent,
            min_lot_fallback=min_lot_fallback,
        )

    def size_plan(
        self,
        spec: SymbolSpec,
        side: Side,
        parts: Sequence[PlanPart],
        stop: float,
        funds: AccountFunds,
        *,
        lot_limit: float,
        lot_unit: float | None = None,
        probation: bool = False,
        risk_percent: float | None = None,
        min_lot_fallback: bool = False,
    ) -> SizingResult:
        draft = _Draft(self.risk_budget(funds, probation=probation, risk_percent=risk_percent))
        problems = spec.validation_errors()
        if problems:
            return draft.done(Reason.SYMBOL_SPEC_INCONSISTENT, "; ".join(problems))
        if not parts:
            return draft.done(Reason.VOLUME_INVALID, "the plan has no orders")
        step = to_decimal(spec.volume_step)
        unit = step if lot_unit is None else to_decimal(lot_unit)
        if unit < step or not is_multiple_of(unit, step):
            return draft.done(
                Reason.VOLUME_INVALID, f"lot unit {unit} is not a multiple of the volume step {step}"
            )
        draft.lot_unit = unit
        if draft.budget <= 0:
            return draft.done(Reason.RISK_BELOW_MIN_LOT, "the risk budget is zero")

        tick = to_decimal(spec.tick_size)
        sl = round_to_tick(stop, tick, "down" if side is Side.BUY else "up")
        draft.stop_loss = sl
        aligned = [
            PlanPart(round_to_tick(p.entry, tick), p.weight, p.order_type, p.take_profit) for p in parts
        ]
        if any(p.weight <= 0 for p in aligned):
            return draft.done(Reason.VOLUME_INVALID, "plan weights must be positive")
        for p in aligned:
            if (p.entry - sl) * side.sign <= 0:
                return draft.done(
                    Reason.SL_WRONG_SIDE, f"stop {sl} is not on the losing side of entry {p.entry}"
                )
        cost = self.cost_per_lot(spec)
        losses: list[Decimal] = []
        for p in aligned:
            loss = self.loss_per_lot(spec, side, p.entry, sl)
            if isinstance(loss, str):
                return draft.done(Reason.SYMBOL_SPEC_INCONSISTENT, loss)
            losses.append(loss)

        v_min = to_decimal(spec.volume_min)
        if self.risk.min_lot is not None:
            v_min = max(v_min, to_decimal(self.risk.min_lot))
        v_max = to_decimal(spec.volume_max)
        total_cap = to_decimal(lot_limit)
        while True:
            n = len(aligned) - draft.dropped_parts
            w = [p.weight for p in aligned[:n]]
            denom = sum((wi * (li + cost) for wi, li in zip(w, losses, strict=False)), ZERO)
            # no single order above volume_max, and the plan's total within the symbol's lot limit
            u = min(draft.budget / denom, v_max / max(w), total_cap / sum(w, ZERO))
            lots = [floor_to_step(wi * u, unit) for wi in w]
            if all(lot >= v_min for lot in lots):
                break
            if n == 1 and min_lot_fallback and v_min <= min(v_max, total_cap):
                # the owner's choice: the minimum lot although its risk exceeds the budget; margin decides
                lots = [v_min]
                draft.over_budget = True
                break
            if n == 1:
                return draft.done(
                    Reason.RISK_BELOW_MIN_LOT,
                    f"budget {draft.budget:.2f} buys {lots[0]} lots; the minimum is {v_min}",
                )
            draft.dropped_parts += 1  # the deepest part goes first

        draft.parts = tuple(
            SizedPart(p, lot, int(lot / unit), loss, cost)
            for p, lot, loss in zip(aligned[:n], lots, losses[:n], strict=True)
        )
        total_risk = sum((s.risk_money for s in draft.parts), ZERO)
        if (total_risk > draft.budget and not draft.over_budget) or any(
            s.volume > v_max or not is_multiple_of(s.volume, step) for s in draft.parts
        ):
            return draft.done(
                Reason.VOLUME_INVALID, f"risk {total_risk:.2f} exceeds budget {draft.budget:.2f}"
            )
        return self._margin(spec, side, funds, draft)

    def _margin(self, spec: SymbolSpec, side: Side, funds: AccountFunds, draft: _Draft) -> SizingResult:
        """Step 8, for the whole plan as if every part were filled."""
        required = ZERO
        for s in draft.parts:
            m = self.calculator.calc_margin(side, spec.name, float(s.volume), float(s.part.entry))
            if m is None or m < 0:
                return draft.done(Reason.MARGIN_INSUFFICIENT, "order_calc_margin failed")
            required += to_decimal(m)
        allowed = (
            to_decimal(funds.margin_free) * to_decimal(self.risk.max_margin_utilization_percent) / HUNDRED
        )
        used = to_decimal(funds.margin) + required
        draft.margin_required = required
        draft.margin_level_after = to_decimal(funds.equity) / used * HUNDRED if used > 0 else None
        if required > allowed:
            cap = self.risk.max_margin_utilization_percent
            return draft.done(
                Reason.MARGIN_INSUFFICIENT,
                f"margin {required:.2f} > {cap:g}% of free margin {funds.margin_free:.2f}",
            )
        level = draft.margin_level_after
        if level is not None and level < to_decimal(self.risk.min_margin_level_percent):
            return draft.done(
                Reason.MARGIN_LEVEL_TOO_LOW,
                f"margin level after the trade {level:.0f}% < {self.risk.min_margin_level_percent:g}%",
            )
        return draft.done()
