"""Portfolio exposure (PLAN §A9 "Exposure", §A31 portfolio heat; TAA-402).

:meth:`ExposureManager.snapshot` measures the open book; :meth:`ExposureManager.check` tests a candidate
trade against it. Rules:

- **Ownership.** A position is the bot's when its magic is in ``[magic_base, magic_base + MAGIC_RANGE)``.
  Anything else (manual trades have magic 0) is *foreign*. ``risk.foreign_positions_policy``: ``count`` makes
  foreign positions count toward every limit like the bot's own; ``halt`` blocks new entries while any exists.
- **Risk to stop** of a position = the broker loss from its open price to its stop (0 once the stop is
  past break-even). A position **without a stop**, or on a symbol whose spec or price is unusable, has
  *unknown* risk: the check ``UNKNOWN_POSITION_RISK`` fails (fail closed).
- **Portfolio heat** = Σ risk to stop + the candidate's risk with every part filled, as % of equity, within
  ``risk.max_total_open_risk_percent`` (or a lower trading-profile value).
- **Counts:** total open positions, positions per symbol, an opposite position on the symbol (never
  reversed automatically), correlation groups (at most one position per side within a group), and the
  number of positions long / short each currency (``max_same_direction_per_currency``).
- **Margin utilization** = (margin used + candidate margin) / equity; **effective leverage** = Σ |P/L of a
  1 % move| × 100 / equity, broker-computed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.broker.models import BrokerPosition
from app.config import RiskConfig
from app.core.enums import Side
from app.market_data.data_models import SymbolSpec
from app.risk.checks import Check, CheckKind
from app.risk.position_sizer import AccountFunds, ProfitCalculator
from app.risk.reasons import Reason

MAGIC_RANGE = 10_000
LEVERAGE_MOVE = 0.01  # the 1 % move behind effective leverage


@dataclass(frozen=True, slots=True)
class PositionRisk:
    position: BrokerPosition
    is_bot: bool
    risk_to_stop: float | None  # None: unknown (no stop, or no usable spec/price)
    move_value: float | None  # |P/L| of a 1 % move, for effective leverage

    @property
    def unknown(self) -> bool:
        return self.risk_to_stop is None


@dataclass(frozen=True, slots=True)
class Exposure:
    positions: tuple[PositionRisk, ...]
    equity: float
    margin: float
    counted: tuple[PositionRisk, ...] = field(default=())  # positions that count toward limits

    @property
    def open_risk(self) -> float:
        return sum(p.risk_to_stop or 0.0 for p in self.counted)

    @property
    def heat_percent(self) -> float:
        return 100.0 * self.open_risk / self.equity if self.equity > 0 else float("inf")

    @property
    def unknown_risk(self) -> tuple[PositionRisk, ...]:
        return tuple(p for p in self.counted if p.unknown)

    @property
    def foreign(self) -> tuple[PositionRisk, ...]:
        return tuple(p for p in self.positions if not p.is_bot)

    @property
    def effective_leverage(self) -> float:
        total = sum(p.move_value or 0.0 for p in self.counted)
        return 100.0 * total / self.equity if self.equity > 0 else float("inf")


@dataclass(frozen=True, slots=True)
class Candidate:
    symbol: str
    side: Side
    volume: float
    entry: float
    risk_money: float  # loss at the stop with every part filled, costs included
    margin_required: float


class ExposureManager:
    def __init__(self, risk: RiskConfig, calculator: ProfitCalculator, *, magic_base: int) -> None:
        self.risk = risk
        self.calculator = calculator
        self.magic_base = magic_base

    def is_bot(self, position: BrokerPosition) -> bool:
        return self.magic_base <= position.magic < self.magic_base + MAGIC_RANGE

    # measuring ---------------------------------------------------------------------------------------------

    def position_risk(self, position: BrokerPosition, spec: SymbolSpec | None) -> PositionRisk:
        bot = self.is_bot(position)
        price = position.price_current
        if spec is None or price <= 0:
            return PositionRisk(position, bot, None, None)
        move = self.calculator.calc_profit(
            position.side, position.symbol, position.volume, price, price * (1 + LEVERAGE_MOVE)
        )
        move_value = None if move is None else abs(move)
        if position.sl <= 0:
            return PositionRisk(position, bot, None, move_value)
        # capital at risk is measured from the open price: a stop past break-even risks nothing, and profit
        # that a trailing stop could give back is not counted as risk
        pnl = self.calculator.calc_profit(
            position.side, position.symbol, position.volume, position.price_open, position.sl
        )
        if pnl is None:
            return PositionRisk(position, bot, None, move_value)
        return PositionRisk(position, bot, max(0.0, -pnl), move_value)

    def snapshot(
        self, positions: Sequence[BrokerPosition], funds: AccountFunds, specs: Mapping[str, SymbolSpec]
    ) -> Exposure:
        measured = tuple(self.position_risk(p, specs.get(p.symbol)) for p in positions)
        counted = (
            measured
            if self.risk.foreign_positions_policy == "count"
            else tuple(m for m in measured if m.is_bot)
        )
        return Exposure(measured, funds.equity, funds.margin, counted)

    # checking ----------------------------------------------------------------------------------------------

    def check(
        self,
        candidate: Candidate,
        exposure: Exposure,
        specs: Mapping[str, SymbolSpec],
        *,
        max_heat_percent: float | None = None,
    ) -> list[Check]:
        r = self.risk
        acct = CheckKind.ACCOUNT
        book = [p.position for p in exposure.counted]
        on_symbol = [p for p in book if p.symbol == candidate.symbol]
        heat_limit = r.max_total_open_risk_percent
        if max_heat_percent is not None:
            heat_limit = min(heat_limit, max_heat_percent)
        equity = exposure.equity
        heat_after = (
            100.0 * (exposure.open_risk + candidate.risk_money) / equity if equity > 0 else float("inf")
        )
        margin_after = (
            100.0 * (exposure.margin + candidate.margin_required) / equity if equity > 0 else float("inf")
        )
        cand_move = self.calculator.calc_profit(
            candidate.side,
            candidate.symbol,
            candidate.volume,
            candidate.entry,
            candidate.entry * (1 + LEVERAGE_MOVE),
        )
        leverage_after = (
            float("inf")
            if cand_move is None or equity <= 0
            else exposure.effective_leverage + 100.0 * abs(cand_move) / equity
        )
        group_conflicts = self._group_conflicts(candidate, book)
        currency_counts = self._currency_counts(candidate, book, specs)
        worst_currency = max(currency_counts.items(), key=lambda kv: kv[1], default=("", 0))
        foreign = exposure.foreign
        return [
            Check(
                "foreign_positions",
                Reason.FOREIGN_POSITIONS,
                r.foreign_positions_policy == "count" or not foreign,
                acct,
                len(foreign),
                f"policy {r.foreign_positions_policy}",
            ),
            Check(
                "max_open_positions",
                Reason.MAX_OPEN_POSITIONS,
                len(book) + 1 <= r.max_open_positions,
                acct,
                len(book) + 1,
                r.max_open_positions,
            ),
            Check(
                "max_positions_per_symbol",
                Reason.MAX_POSITIONS_PER_SYMBOL,
                len(on_symbol) + 1 <= r.max_positions_per_symbol,
                acct,
                len(on_symbol) + 1,
                r.max_positions_per_symbol,
            ),
            Check(
                "conflicting_position",
                Reason.CONFLICTING_POSITION,
                not any(p.side is not candidate.side for p in on_symbol),
                acct,
                sum(p.side is not candidate.side for p in on_symbol),
                0,
                "an opposite position is open on the symbol; it is never reversed automatically",
            ),
            Check(
                "correlation_group",
                Reason.CORRELATION_LIMIT,
                not group_conflicts,
                acct,
                ",".join(group_conflicts),
                "1 per side per group",
            ),
            Check(
                "currency_direction",
                Reason.CURRENCY_EXPOSURE_LIMIT,
                worst_currency[1] <= r.max_same_direction_per_currency,
                acct,
                f"{worst_currency[0]}:{worst_currency[1]}" if worst_currency[0] else 0,
                r.max_same_direction_per_currency,
            ),
            Check(
                "unknown_position_risk",
                Reason.UNKNOWN_POSITION_RISK,
                not exposure.unknown_risk,
                acct,
                ",".join(f"{p.position.symbol}#{p.position.ticket}" for p in exposure.unknown_risk),
                "every open position has a measurable stop",
            ),
            Check(
                "max_total_open_risk",
                Reason.MAX_TOTAL_OPEN_RISK,
                heat_after <= heat_limit,
                acct,
                round(heat_after, 4),
                heat_limit,
                "portfolio heat after the trade, % of equity",
            ),
            Check(
                "margin_utilization",
                Reason.MARGIN_INSUFFICIENT,
                margin_after <= r.max_margin_utilization_percent,
                acct,
                round(margin_after, 4),
                r.max_margin_utilization_percent,
            ),
            Check(
                "effective_leverage",
                Reason.LEVERAGE_LIMIT,
                leverage_after <= r.max_effective_leverage,
                acct,
                round(leverage_after, 4),
                r.max_effective_leverage,
            ),
        ]

    def _group_conflicts(self, candidate: Candidate, book: Sequence[BrokerPosition]) -> list[str]:
        out = []
        for name, members in sorted(self.risk.correlation_groups.items()):
            if candidate.symbol not in members:
                continue
            # the same symbol is the per-symbol limit's business; a group limits *related* symbols
            if any(
                p.symbol in members and p.symbol != candidate.symbol and p.side is candidate.side
                for p in book
            ):
                out.append(name)
        return out

    def _currency_counts(
        self, candidate: Candidate, book: Sequence[BrokerPosition], specs: Mapping[str, SymbolSpec]
    ) -> dict[str, int]:
        """Positions on the candidate's own currency sides after the trade: long base, short quote (BUY)."""
        spec = specs.get(candidate.symbol)
        if spec is None:
            return {}
        counts: Counter[tuple[str, int]] = Counter()
        legs = [(p.symbol, p.side) for p in book] + [(candidate.symbol, candidate.side)]
        for symbol, side in legs:
            s = specs.get(symbol)
            if s is None:
                continue
            counts[(s.currency_base, side.sign)] += 1
            counts[(s.currency_profit, -side.sign)] += 1
        sign = candidate.side.sign
        return {
            f"{spec.currency_base}{'+' if sign > 0 else '-'}": counts[(spec.currency_base, sign)],
            f"{spec.currency_profit}{'-' if sign > 0 else '+'}": counts[(spec.currency_profit, -sign)],
        }
