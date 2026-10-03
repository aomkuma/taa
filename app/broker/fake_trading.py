"""Trade-server emulation for :class:`~app.broker.fake_mt5.FakeMT5` (tests and ``--fake`` runs; TAA-1201).

It validates requests the way the trade server does (market hours, trade mode, volume, filling, price
deviation, stops level, freeze level, margin), executes market deals, SL/TP changes and closes on the
fake account, and closes positions whose SL or TP the current price has reached. Fault injection:
:meth:`FakeTradeDesk.force` makes the next ``order_send`` return a chosen retcode (or ``None``), optionally
while still executing it: the "outcome unknown but the order exists" case a reconciler must handle.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import numpy as np

from app.broker import mt5_constants as c
from app.core.decimal_utils import is_multiple_of

if TYPE_CHECKING:
    from app.broker.fake_mt5 import FakeMT5, FakeSymbol

DONE, PLACED = 10009, 10008
FILLING_FLAG = {c.ORDER_FILLING_FOK: c.SYMBOL_FILLING_FOK, c.ORDER_FILLING_IOC: c.SYMBOL_FILLING_IOC}


@dataclass
class _Forced:
    retcode: int | None  # None: order_send returns None
    executes: bool


class FakeTradeDesk:
    def __init__(self, fake: FakeMT5) -> None:
        self.fake = fake
        self._forced: deque[_Forced] = deque()
        self._next_id = 5_000_000
        self.requests: list[dict[str, Any]] = []

    # --- test controls ------------------------------------------------------------------------------

    def force(self, retcode: int | None, *, executes: bool = False) -> None:
        """Force the next ``order_send`` result (``None``: no result); with *executes* it still runs."""
        self._forced.append(_Forced(retcode, executes))

    # --- helpers ------------------------------------------------------------------------------------

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _now_server(self) -> int:
        return int(self.fake.server_clock.utc_to_server_epoch(self.fake.clock.now_utc()))

    def _quote(self, symbol: str) -> tuple[float, float] | None:
        sym = self.fake.symbols.get(symbol)
        price = self.fake._current_price(symbol)
        if sym is None or price is None:
            return None
        bid = price[0]
        return bid, round(bid + price[1] * sym.point, sym.digits)

    def _market_open(self, sym: FakeSymbol) -> bool:
        from app.broker.fake_mt5 import market_open_mask

        now = int(self.fake.clock.now_utc().timestamp()) // 60 * 60
        return bool(market_open_mask(np.array([now]), sym.schedule)[0])

    def _result(self, retcode: int, request: dict[str, Any], **kw: Any) -> SimpleNamespace:
        quote = self._quote(str(request.get("symbol", ""))) or (0.0, 0.0)
        base = {
            "retcode": retcode,
            "deal": 0,
            "order": 0,
            "volume": 0.0,
            "price": 0.0,
            "bid": quote[0],
            "ask": quote[1],
            "comment": "Request executed" if retcode in (DONE, PLACED) else f"retcode {retcode}",
            "request_id": self._id(),
            "retcode_external": 0,
            "request": SimpleNamespace(**request),
        }
        base.update(kw)
        return SimpleNamespace(**base)

    # --- validation ---------------------------------------------------------------------------------

    def validate(self, request: dict[str, Any]) -> int:
        """0 when the request would be accepted, else the retcode the server would answer."""
        fake = self.fake
        if not fake.terminal.trade_allowed or fake.terminal.tradeapi_disabled:
            return 10027
        if fake.account.investor:
            return 10017
        action = request.get("action")
        symbol = str(request.get("symbol", ""))
        sym = fake.symbols.get(symbol)
        quote = self._quote(symbol)
        if sym is None or quote is None:
            return 10013
        if not self._market_open(sym):
            return 10018
        bid, ask = quote
        if action == c.TRADE_ACTION_SLTP:
            pos = self._position(request.get("position"))
            if pos is None:
                return 10036
            sl, tp = float(request.get("sl", 0.0)), float(request.get("tp", 0.0))
            if (sl, tp) == (pos.sl, pos.tp):
                return 10025
            mark = bid if pos.type == c.POSITION_TYPE_BUY else ask
            frozen = sym.freeze_level * sym.point
            for level in (pos.sl, pos.tp):
                if level and frozen and abs(mark - level) <= frozen:
                    return 10029
            return 0 if self._stops_ok(sym, pos.type, mark, sl, tp) else 10016
        if action != c.TRADE_ACTION_DEAL:
            return 10013
        order_type = request.get("type")
        if order_type not in (c.ORDER_TYPE_BUY, c.ORDER_TYPE_SELL):
            return 10013
        volume = float(request.get("volume", 0.0))
        position = request.get("position")
        if position:
            pos = self._position(position)
            if pos is None:
                return 10036
            closing_type = c.ORDER_TYPE_SELL if pos.type == c.POSITION_TYPE_BUY else c.ORDER_TYPE_BUY
            if order_type != closing_type or volume <= 0 or volume > pos.volume + 1e-12:
                return 10038
        else:
            if sym.trade_mode == c.SYMBOL_TRADE_MODE_DISABLED:
                return 10017
            if sym.trade_mode == c.SYMBOL_TRADE_MODE_CLOSEONLY:
                return 10044
            if sym.trade_mode == c.SYMBOL_TRADE_MODE_LONGONLY and order_type == c.ORDER_TYPE_SELL:
                return 10042
            if sym.trade_mode == c.SYMBOL_TRADE_MODE_SHORTONLY and order_type == c.ORDER_TYPE_BUY:
                return 10043
            if not (sym.volume_min <= volume <= sym.volume_max) or not is_multiple_of(
                volume, sym.volume_step
            ):
                return 10014
        flag = FILLING_FLAG.get(int(request.get("type_filling", -1)))
        if flag is None or not (sym.filling_mode & flag):
            return 10030
        market = ask if order_type == c.ORDER_TYPE_BUY else bid
        deviation = float(request.get("deviation", 0)) * sym.point
        if abs(float(request.get("price", 0.0)) - market) > deviation + 1e-12:
            return 10004
        if not position:
            mark = bid if order_type == c.ORDER_TYPE_BUY else ask
            pos_type = c.POSITION_TYPE_BUY if order_type == c.ORDER_TYPE_BUY else c.POSITION_TYPE_SELL
            if not self._stops_ok(
                sym, pos_type, mark, float(request.get("sl", 0.0)), float(request.get("tp", 0.0))
            ):
                return 10016
            margin = fake.order_calc_margin(order_type, symbol, volume, market) or 0.0
            account = fake.account_info()
            if account is None or margin > account.margin_free:
                return 10019
        return 0

    @staticmethod
    def _stops_ok(sym: FakeSymbol, pos_type: int, mark: float, sl: float, tp: float) -> bool:
        gap = sym.stops_level * sym.point
        if pos_type == c.POSITION_TYPE_BUY:
            return (not sl or sl < mark - gap) and (not tp or tp > mark + gap)
        return (not sl or sl > mark + gap) and (not tp or tp < mark - gap)

    def _position(self, ticket: Any) -> SimpleNamespace | None:
        return next((p for p in self.fake.positions if p.ticket == ticket), None)

    # --- module functions ---------------------------------------------------------------------------

    def order_check(self, request: dict[str, Any]) -> SimpleNamespace:
        code = self.validate(request)
        account = self.fake.account_info()
        return SimpleNamespace(
            retcode=code,
            comment="Done" if code == 0 else f"retcode {code}",
            balance=account.balance if account else 0.0,
            equity=account.equity if account else 0.0,
            margin_free=account.margin_free if account else 0.0,
            request=SimpleNamespace(**request),
        )

    def order_send(self, request: dict[str, Any]) -> SimpleNamespace | None:
        self.requests.append(dict(request))
        forced = self._forced.popleft() if self._forced else None
        if forced is not None and not forced.executes:
            if forced.retcode is None:
                self.fake._last_error = (-10004, "no connection with the trade server")
                return None
            return self._result(forced.retcode, request)
        code = self.validate(request)
        if code == 10025 and request.get("action") == c.TRADE_ACTION_SLTP:
            return self._result(10025, request)
        if code != 0:
            return self._result(code, request)
        result = self._execute(request)
        if forced is not None:  # executed, but the caller is told something else (or nothing)
            if forced.retcode is None:
                self.fake._last_error = (-10004, "no connection with the trade server")
                return None
            return self._result(forced.retcode, request)
        return result

    # --- execution ----------------------------------------------------------------------------------

    def _execute(self, request: dict[str, Any]) -> SimpleNamespace:
        action, symbol = request["action"], str(request["symbol"])
        bid, ask = self._quote(symbol) or (0.0, 0.0)
        if action == c.TRADE_ACTION_SLTP:
            pos = self._position(request["position"])
            if pos is None:
                return self._result(10036, request)
            pos.sl, pos.tp = float(request.get("sl", 0.0)), float(request.get("tp", 0.0))
            return self._result(DONE, request, order=self._id())
        order_type = request["type"]
        volume = float(request["volume"])
        price = ask if order_type == c.ORDER_TYPE_BUY else bid
        order = self._id()
        if request.get("position"):
            pos = self._position(request["position"])
            if pos is None:
                return self._result(10036, request)
            deal = self._close(
                pos, volume, price, order, str(request.get("comment", "")), c.DEAL_REASON_EXPERT
            )
            return self._result(DONE, request, deal=deal, order=order, volume=volume, price=price)
        ticket = order
        now = self._now_server()
        pos_type = c.POSITION_TYPE_BUY if order_type == c.ORDER_TYPE_BUY else c.POSITION_TYPE_SELL
        margin = self.fake.order_calc_margin(order_type, symbol, volume, price) or 0.0
        self.fake.positions.append(
            SimpleNamespace(
                ticket=ticket,
                symbol=symbol,
                type=pos_type,
                volume=volume,
                price_open=price,
                sl=float(request.get("sl", 0.0)),
                tp=float(request.get("tp", 0.0)),
                price_current=price,
                profit=0.0,
                swap=0.0,
                magic=int(request.get("magic", 0)),
                comment=str(request.get("comment", "")),
                time=now,
                identifier=ticket,
                margin=margin,
            )
        )
        deal = self._deal(
            symbol, order_type, c.DEAL_ENTRY_IN, volume, price, 0.0, ticket, order, request, now
        )
        return self._result(DONE, request, deal=deal, order=order, volume=volume, price=price)

    def _deal(
        self,
        symbol: str,
        order_type: int,
        entry: int,
        volume: float,
        price: float,
        profit: float,
        position: int,
        order: int,
        request: dict[str, Any] | None,
        now: int,
        magic: int | None = None,
        comment: str | None = None,
        reason: int = c.DEAL_REASON_EXPERT,
    ) -> int:
        deal = self._id()
        self.fake.deals.append(
            SimpleNamespace(
                ticket=deal,
                order=order,
                position_id=position,
                symbol=symbol,
                type=c.DEAL_TYPE_BUY if order_type == c.ORDER_TYPE_BUY else c.DEAL_TYPE_SELL,
                entry=entry,
                volume=volume,
                price=price,
                profit=profit,
                commission=0.0,
                swap=0.0,
                fee=0.0,
                magic=magic if magic is not None else int((request or {}).get("magic", 0)),
                comment=comment if comment is not None else str((request or {}).get("comment", "")),
                time=now,
                reason=reason,
            )
        )
        return deal

    def _close(
        self, pos: SimpleNamespace, volume: float, price: float, order: int, comment: str, reason: int
    ) -> int:
        direction = 1 if pos.type == c.POSITION_TYPE_BUY else -1
        closing_type = c.ORDER_TYPE_SELL if direction > 0 else c.ORDER_TYPE_BUY
        profit = self.fake.order_calc_profit(
            c.ORDER_TYPE_BUY if direction > 0 else c.ORDER_TYPE_SELL,
            pos.symbol,
            volume,
            pos.price_open,
            price,
        )
        profit = float(profit or 0.0)
        self.fake.account.balance += profit
        deal = self._deal(
            pos.symbol,
            closing_type,
            c.DEAL_ENTRY_OUT,
            volume,
            price,
            profit,
            pos.ticket,
            order,
            None,
            self._now_server(),
            magic=pos.magic,
            comment=comment or pos.comment,
            reason=reason,
        )
        remaining = round(pos.volume - volume, 8)
        if remaining <= 0:
            self.fake.positions.remove(pos)
        else:
            pos.volume = remaining
        return deal

    def refresh(self) -> None:
        """Mark positions to market and close those whose SL or TP the price has reached."""
        for pos in list(self.fake.positions):
            quote = self._quote(pos.symbol)
            if quote is None:
                continue
            bid, ask = quote
            buy = pos.type == c.POSITION_TYPE_BUY
            mark = bid if buy else ask
            if pos.sl and ((buy and mark <= pos.sl) or (not buy and mark >= pos.sl)):
                self._close(pos, pos.volume, mark, self._id(), "[sl]", c.DEAL_REASON_SL)
                continue
            if pos.tp and ((buy and mark >= pos.tp) or (not buy and mark <= pos.tp)):
                self._close(pos, pos.volume, pos.tp, self._id(), "[tp]", c.DEAL_REASON_TP)
                continue
            profit = self.fake.order_calc_profit(
                c.ORDER_TYPE_BUY if buy else c.ORDER_TYPE_SELL, pos.symbol, pos.volume, pos.price_open, mark
            )
            pos.price_current, pos.profit = mark, float(profit or 0.0)
