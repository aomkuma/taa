"""Account profiles and cloud sizing (PLAN §A30 "Account profiles", §A31; TAA-8A3).

A user's alerts carry a lot and risk money only when they can be computed honestly for *that user's*
account:

- **LINKED_ENGINE** (an engine the user owns): the engine already sized the trade with MT5
  (``order_calc_profit``/``order_calc_margin``) on that account at signal time; its decision is used as is.
- **MANUAL** (everyone else): equity, balance, currency, leverage and an optional risk percent the user
  entered. The cloud sizes with the engine's own :class:`PositionSizer` over a :class:`SpecCalculator`: the
  replicated symbol spec plus conversion rates from the engine's newest closes (:class:`HistoryRates`).

Limits only tighten: the risk percent is the minimum of the profile's value, the trading profile's
``risk_per_signal_percent`` and ``config.yaml``'s ceiling. Missing data (no spec, no conversion series, no
recent close) refuses the sizing with a reason instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.advisory.preferences import EntryPlanPreferences
from app.config import CEILING_RISK_PER_TRADE_PCT, RiskConfig
from app.core.clock import ensure_utc
from app.core.enums import Side
from app.market_data.data_models import SymbolSpec
from app.risk.position_sizer import (
    AccountFunds,
    PositionSizer,
    SizingResult,
    SplitMode,
    WeightScheme,
    build_parts,
)
from app.risk.spec_calculator import SpecCalculator
from app.storage.database import Database
from app.storage.models import AccountProfileRow, EngineRow, HistoryCandle, SymbolCatalogRow
from app.sync.events import json_safe

MAX_RATE_AGE = timedelta(days=7)  # a close older than this is no conversion rate (fail closed)


class ProfileBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["LINKED_ENGINE", "MANUAL"]
    engine_id: str | None = Field(default=None, max_length=64)
    equity: float | None = Field(default=None, gt=0, le=1e9)
    balance: float | None = Field(default=None, gt=0, le=1e9)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    leverage: float | None = Field(default=None, gt=0, le=3000)
    risk_percent: float | None = Field(default=None, gt=0, le=CEILING_RISK_PER_TRADE_PCT)

    @model_validator(mode="after")
    def _source(self) -> ProfileBody:
        if self.source == "MANUAL":
            if self.equity is None or self.leverage is None:
                raise ValueError("a MANUAL profile needs equity and leverage")
            if self.engine_id is not None:
                raise ValueError("engine_id is for LINKED_ENGINE profiles")
        elif self.engine_id is None:
            raise ValueError("a LINKED_ENGINE profile names the engine")
        return self


def profile_dict(row: AccountProfileRow) -> dict[str, Any]:
    return {
        "source": row.source,
        "engine_id": row.engine_id,
        "equity": row.equity,
        "balance": row.balance,
        "currency": row.currency,
        "leverage": row.leverage,
        "risk_percent": row.risk_percent,
        "updated_at": json_safe(row.updated_at),
    }


class ProfileError(ValueError):
    pass


def save_profile(db: Database, user_id: str, body: ProfileBody, now: datetime) -> dict[str, Any]:
    with db.session() as sess:
        if body.source == "LINKED_ENGINE":
            engine = sess.get(EngineRow, body.engine_id)
            if engine is None or engine.owner_user_id != user_id or engine.status != "ACTIVE":
                raise ProfileError("engine_not_found")
        row = sess.get(AccountProfileRow, user_id)
        if row is None:
            row = AccountProfileRow(user_id=user_id, source=body.source, updated_at=now)
            sess.add(row)
        row.source, row.engine_id = body.source, body.engine_id
        row.equity, row.balance, row.currency = body.equity, body.balance or body.equity, body.currency
        row.leverage, row.risk_percent, row.updated_at = body.leverage, body.risk_percent, now
        return profile_dict(row)


def load_profile(db: Database, user_id: str) -> AccountProfileRow | None:
    with db.session() as sess:
        return sess.get(AccountProfileRow, user_id)


class HistoryRates:
    """Currency → account-currency rates from one engine's newest closes (any timeframe) of a pair holding
    both currencies, direct or inverse, or one hop through a common currency; cached per instance."""

    def __init__(
        self, db: Database, engine_id: str, server: str, account_currency: str, now: datetime
    ) -> None:
        self.db = db
        self.engine_id = engine_id
        self.server = server
        self.account = account_currency.upper()
        self.now = now
        self._cache: dict[str, float | None] = {}
        self._specs: dict[str, dict[str, Any]] | None = None

    def specs(self) -> dict[str, dict[str, Any]]:
        if self._specs is None:
            with self.db.session() as sess:
                rows = sess.scalars(
                    select(SymbolCatalogRow).where(
                        SymbolCatalogRow.engine_id == self.engine_id, SymbolCatalogRow.server == self.server
                    )
                ).all()
                self._specs = {r.symbol: dict(r.spec or {}) for r in rows}
        return self._specs

    def last_close(self, symbol: str) -> float | None:
        """The engine's newest close of *symbol* (any timeframe) no older than the rate age limit."""
        return self._last_close(symbol)

    def _last_close(self, symbol: str) -> float | None:
        with self.db.session() as sess:
            row = sess.execute(
                select(HistoryCandle.close, HistoryCandle.open_time)
                .where(
                    HistoryCandle.engine_id == self.engine_id,
                    HistoryCandle.server == self.server,
                    HistoryCandle.symbol == symbol,
                )
                .order_by(HistoryCandle.open_time.desc())
                .limit(1)
            ).first()
        if row is None or self.now - ensure_utc(row[1]) > MAX_RATE_AGE or row[0] <= 0:
            return None
        return float(row[0])

    def __call__(self, currency: str) -> float | None:
        if currency not in self._cache:
            self._cache[currency] = self._find(currency)
        return self._cache[currency]

    def _find(self, currency: str) -> float | None:
        direct = self._direct(currency, self.account)
        if direct is not None:
            return direct
        # one hop through a common currency (JPY → USD → EUR), like the backtester's conversion series
        middles = {
            str(v.get(k, "")).upper()
            for v in self.specs().values()
            for k in ("currency_base", "currency_profit")
        }
        for middle in sorted(middles - {currency, self.account, ""}):
            first = self._direct(currency, middle)
            second = None if first is None else self._direct(middle, self.account)
            if first is not None and second is not None:
                return first * second
        return None

    def _direct(self, currency: str, target: str) -> float | None:
        """Units of *target* per unit of *currency* from a pair holding both (direct or inverse)."""
        for symbol, spec in sorted(self.specs().items()):
            base, quote = (
                str(spec.get("currency_base", "")).upper(),
                str(spec.get("currency_profit", "")).upper(),
            )
            if base == currency and quote == target:
                close = self._last_close(symbol)
                if close is not None:
                    return close
            if base == target and quote == currency:
                close = self._last_close(symbol)
                if close is not None:
                    return 1.0 / close
        return None


@dataclass(frozen=True)
class CloudSizing:
    result: SizingResult | None
    reason: str = ""  # why there is no result


def size_manual(
    db: Database,
    profile: AccountProfileRow,
    *,
    engine_id: str,
    server: str,
    symbol: str,
    side: Side,
    entry: float,
    stop: float,
    risk: RiskConfig,
    risk_percent: float | None,
    now: datetime,
    take_profit: float | None = None,
    plan: EntryPlanPreferences | None = None,
    atr: float | None = None,
) -> CloudSizing:
    """Size a MANUAL profile's trade with the engine's sizer over the replicated spec: one market order, or
    the user's entry plan (rev. 3: SAME_PRICE / SCALE_IN parts, lot per tap) when *plan* is given."""
    if profile.source != "MANUAL" or profile.equity is None or profile.leverage is None:
        return CloudSizing(None, "not_manual")
    rates = HistoryRates(db, engine_id, server, profile.currency, now)
    raw = rates.specs().get(symbol)
    if not raw:
        return CloudSizing(None, "no_spec")
    try:
        spec = SymbolSpec(**raw)
    except TypeError:
        return CloudSizing(None, "no_spec")
    calc = SpecCalculator({symbol: spec}, profile.currency, profile.leverage, rates)
    converted = calc.spec_for(symbol)
    if converted is None:
        return CloudSizing(None, "no_conversion")
    pct = [p for p in (profile.risk_percent, risk_percent) if p is not None]
    equity = float(profile.equity)
    funds = AccountFunds(
        equity=equity, balance=float(profile.balance or equity), margin=0.0, margin_free=equity
    )
    sizer = PositionSizer(
        risk, SpecCalculator({symbol: converted}, profile.currency, profile.leverage, rates)
    )
    try:
        parts = build_parts(
            plan.mode if plan else SplitMode.SINGLE,
            side,
            entry,
            stop,
            take_profit,
            k=plan.parts if plan else 1,
            scheme=plan.weights if plan else WeightScheme.EQUAL,
            atr=atr,
            spacing_atr=plan.spacing_atr if plan else 0.5,
            tp_r=plan.take_profits_r if plan else (),
        )
    except ValueError:  # SCALE_IN without an ATR: no plan rather than a guessed spacing
        return CloudSizing(None, "no_atr")
    result = sizer.size_plan(
        converted,
        side,
        parts,
        stop,
        funds,
        lot_limit=converted.volume_max,
        lot_unit=plan.lot_unit if plan else None,
        risk_percent=min(pct) if pct else None,
    )
    return CloudSizing(
        result, "" if result.ok else (result.reason.value if result.reason else "sizing_failed")
    )


EXAMPLE_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD")
EXAMPLE_STOP_POINTS = 200  # 20 pips on a 5-digit pair
EXAMPLE_RR = 2.0


def preview_plan(
    db: Database,
    profile: AccountProfileRow,
    *,
    engine_id: str,
    server: str,
    plan: EntryPlanPreferences,
    risk: RiskConfig,
    risk_percent: float | None,
    now: datetime,
) -> dict[str, Any]:
    """An entry plan sized on an example trade (TAA-922): a BUY of the first of :data:`EXAMPLE_SYMBOLS` with a
    spec and a recent close, the stop :data:`EXAMPLE_STOP_POINTS` points below, the target at RR 2 and the ATR
    equal to the stop distance (SCALE_IN spacing). The same sizer as every alert's plan."""
    rates = HistoryRates(db, engine_id, server, profile.currency, now)
    specs = rates.specs()
    for symbol in EXAMPLE_SYMBOLS:
        point = (specs.get(symbol) or {}).get("point")
        close = rates.last_close(symbol)
        if point and close:
            break
    else:
        return {"available": False, "reason": "no_example"}
    distance = EXAMPLE_STOP_POINTS * float(point)
    entry, stop, target = close, close - distance, close + EXAMPLE_RR * distance
    sized = size_manual(
        db,
        profile,
        engine_id=engine_id,
        server=server,
        symbol=symbol,
        side=Side.BUY,
        entry=entry,
        stop=stop,
        risk=risk,
        risk_percent=risk_percent,
        now=now,
        take_profit=target,
        plan=plan,
        atr=distance,
    )
    example = {"symbol": symbol, "side": Side.BUY.value, "entry": entry, "stop": stop, "take_profit": target}
    if sized.result is None or not sized.result.ok:
        return {"available": False, "reason": sized.reason, "example": example}
    r = sized.result
    return {
        "available": True,
        "example": example,
        "currency": profile.currency,
        "equity": profile.equity,
        "budget": float(r.budget),
        "lot": float(r.volume),
        "risk_money": float(r.risk_money),
        "taps": sum(p.taps for p in r.parts),
        "plan": list(plan_of(r)),
    }


def plan_of(result: SizingResult) -> tuple[dict[str, Any], ...]:
    """The sized orders in the decision record's plan format (what the push and the app show)."""
    return tuple(
        {
            "entry": str(p.part.entry),
            "order_type": p.part.order_type.value,
            "take_profit": None if p.part.take_profit is None else str(p.part.take_profit),
            "volume": str(p.volume),
            "taps": p.taps,
            "risk_money": str(p.risk_money),
        }
        for p in result.parts
    )
