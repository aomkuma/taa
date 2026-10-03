"""Broker order access (PLAN §A12; TAA-1201). The only module that builds and sends trade requests.

- :class:`ExecutionGateway` wraps ``order_check`` / ``order_send`` on a trading-enabled :class:`MT5Client`.
  It refuses to exist unless the mode is DEMO and the connected account is a DEMO account: LIVE stays
  disabled until Phase 14 wires the live gate (§A3). Every send and every result is logged.
- :class:`RequestBuilder` makes the three requests the engine needs: a market entry with SL and TP, an SL/TP
  change, and a (partial) close. Filling comes from the symbol (``filling.resolve_filling``), ``deviation`` is
  the slippage limit in points, orders are GTC, ``magic`` identifies the strategy and the comment is at most
  25 ASCII characters (brokers overwrite the tail of the 31-character field).
- ``order_send`` returning ``None`` means *unknown*: the order may exist. The result says so explicitly
  (``retcode=None``) and the caller must reconcile before anything else; nothing here retries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.broker import mt5_constants as c
from app.broker.filling import resolve_filling
from app.broker.models import BrokerPosition
from app.broker.mt5_client import MT5Client
from app.broker.retcodes import RetcodeClass, classify, describe
from app.core.decimal_utils import round_to_tick
from app.core.enums import Side, TradingMode
from app.core.errors import SafetyViolation, SymbolUnavailable
from app.market_data.data_models import SymbolSpec

log = logging.getLogger(__name__)

COMMENT_MAX = 25
_ASCII = re.compile(r"[^A-Za-z0-9 _.:\-]")


def safe_comment(text: str) -> str:
    """Printable ASCII, at most 25 characters (informational only: orders are matched by magic + ticket)."""
    return _ASCII.sub("", text)[:COMMENT_MAX]


@dataclass(frozen=True, slots=True)
class SendResult:
    retcode: int | None  # None: order_send returned nothing (outcome unknown)
    retcode_class: RetcodeClass
    description: str
    order: int = 0
    deal: int = 0
    volume: float = 0.0
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    comment: str = ""
    last_error: tuple[int, str] = (0, "")

    @property
    def ok(self) -> bool:
        return self.retcode_class in (RetcodeClass.SUCCESS, RetcodeClass.PARTIAL)


@dataclass(frozen=True, slots=True)
class CheckResult:
    retcode: int | None
    comment: str
    margin_free: float | None = None

    @property
    def ok(self) -> bool:
        return self.retcode == 0


class RequestBuilder:
    def __init__(self, deviation_points: int) -> None:
        if deviation_points < 0:
            raise ValueError("deviation must be >= 0")
        self.deviation = int(deviation_points)

    @staticmethod
    def _filling(spec: SymbolSpec) -> int:
        filling = resolve_filling(spec)
        if filling is None:
            raise SymbolUnavailable(f"{spec.name}: no filling mode is allowed for market orders")
        return filling

    @staticmethod
    def _price(spec: SymbolSpec, value: float) -> float:
        return float(round_to_tick(value, spec.tick_size))

    def market_entry(
        self,
        spec: SymbolSpec,
        side: Side,
        volume: float,
        price: float,
        sl: float,
        tp: float | None,
        *,
        magic: int,
        comment: str,
    ) -> dict[str, Any]:
        if sl <= 0:
            raise SafetyViolation("every entry needs a stop-loss")  # no "no SL" path exists (§A9)
        return {
            "action": c.TRADE_ACTION_DEAL,
            "symbol": spec.name,
            "volume": float(volume),
            "type": c.ORDER_TYPE_BUY if side is Side.BUY else c.ORDER_TYPE_SELL,
            "price": self._price(spec, price),
            "sl": self._price(spec, sl),
            "tp": 0.0 if tp is None else self._price(spec, tp),
            "deviation": self.deviation,
            "magic": int(magic),
            "comment": safe_comment(comment),
            "type_time": c.ORDER_TIME_GTC,
            "type_filling": self._filling(spec),
        }

    def modify_stops(
        self, spec: SymbolSpec, position: BrokerPosition, sl: float, tp: float | None
    ) -> dict[str, Any]:
        if sl <= 0:
            raise SafetyViolation("a stop-loss is never removed")
        return {
            "action": c.TRADE_ACTION_SLTP,
            "symbol": spec.name,
            "position": int(position.ticket),
            "sl": self._price(spec, sl),
            "tp": 0.0 if tp is None else self._price(spec, tp),
            "magic": int(position.magic),
        }

    def close(
        self,
        spec: SymbolSpec,
        position: BrokerPosition,
        price: float,
        *,
        volume: float | None = None,
        comment: str = "",
    ) -> dict[str, Any]:
        closing = c.ORDER_TYPE_SELL if position.side is Side.BUY else c.ORDER_TYPE_BUY
        return {
            "action": c.TRADE_ACTION_DEAL,
            "symbol": spec.name,
            "position": int(position.ticket),
            "volume": float(position.volume if volume is None else volume),
            "type": closing,
            "price": self._price(spec, price),
            "deviation": self.deviation,
            "magic": int(position.magic),
            "comment": safe_comment(comment or "taa:close"),
            "type_time": c.ORDER_TIME_GTC,
            "type_filling": self._filling(spec),
        }


class ExecutionGateway:
    """``order_check`` / ``order_send`` for the DEMO account. LIVE is refused until Phase 14."""

    def __init__(self, client: MT5Client) -> None:
        if not client.allow_trading:
            raise SafetyViolation("the execution gateway needs a trading-enabled client")
        if client.mode is not TradingMode.DEMO:
            raise SafetyViolation(f"broker orders are enabled for DEMO only (mode {client.mode.value})")
        self.client = client

    def _require_demo_account(self) -> None:
        report = self.client.last_report
        if report is None or report.account.trade_mode != c.ACCOUNT_TRADE_MODE_DEMO:
            raise SafetyViolation("broker orders need a verified DEMO account connection")

    def check(self, request: dict[str, Any]) -> CheckResult:
        self._require_demo_account()
        raw = self.client.call("order_check", request)
        if raw is None:
            return CheckResult(None, f"order_check returned nothing: {self.client.last_error()}")
        return CheckResult(
            int(raw.retcode), str(getattr(raw, "comment", "")), getattr(raw, "margin_free", None)
        )

    def send(self, request: dict[str, Any]) -> SendResult:
        self._require_demo_account()
        log.info(
            "order_send %s %s vol=%s price=%s sl=%s tp=%s magic=%s",
            request.get("action"),
            request.get("symbol"),
            request.get("volume"),
            request.get("price"),
            request.get("sl"),
            request.get("tp"),
            request.get("magic"),
        )
        raw = self.client.call("order_send", request)
        if raw is None:
            err = self.client.last_error()
            log.error("order_send returned nothing (outcome UNKNOWN): %s", err)
            return SendResult(None, RetcodeClass.UNKNOWN, describe(None), last_error=err)
        code = int(raw.retcode)
        result = SendResult(
            retcode=code,
            retcode_class=classify(code),
            description=describe(code),
            order=int(getattr(raw, "order", 0) or 0),
            deal=int(getattr(raw, "deal", 0) or 0),
            volume=float(getattr(raw, "volume", 0.0) or 0.0),
            price=float(getattr(raw, "price", 0.0) or 0.0),
            bid=float(getattr(raw, "bid", 0.0) or 0.0),
            ask=float(getattr(raw, "ask", 0.0) or 0.0),
            comment=str(getattr(raw, "comment", "")),
        )
        log.log(
            logging.INFO if result.ok else logging.WARNING,
            "order_send result %s order=%s deal=%s vol=%s price=%s",
            result.description,
            result.order,
            result.deal,
            result.volume,
            result.price,
        )
        return result
