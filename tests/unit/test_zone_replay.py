"""The replay of the runner against the simulation (eye/ZONE_LIVE.md L11.2).

The broker double's own behaviour is tested here always (quick). The replays themselves are slow (about 10 - 60
minutes a span and mode) and run only with ``ZONE_REPLAY=1``::

    ZONE_REPLAY=1 pytest tests/unit/test_zone_replay.py -k replay_span -s

Each prints its table (and every difference with its bar and a suggested cause); the gate fails on every
difference - it holds no list of accepted ones: accepting an explained difference is a record by hand in
eye/BOT_RESEARCH.md (L11)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from app.broker import mt5_constants as c
from app.core.clock import ManualClock
from app.zone.core import load_bars
from app.zone.params import load_params
from tests.unit.zone_live_support import settings
from tests.zone_replay import CENT, ReplayBroker, bar_path, snapshots_from_fake
from tests.zone_replay_compare import REQUIRED, ROOT, gate_failures, plan_span, run_span
from tests.zone_replay_explain import detail, explain_all, table

STORED = ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD"
REPLAY = pytest.mark.skipif(
    os.environ.get("ZONE_REPLAY") != "1" or not STORED.exists(),
    reason="replay: set ZONE_REPLAY=1 and have data/history/FBS-Demo/XAUUSD",
)


# --- the quote path ---------------------------------------------------------------------------------------------


def test_path_goes_open_nearer_extreme_other_extreme_close() -> None:
    bids, times = bar_path(100.0, 103.0, 98.0, 101.0, 1000.0, 1900.0, 15.0)
    assert bids[0] == 10000 and bids[-1] == 10100
    assert bids.max() == 10300 and bids.min() == 9800
    assert np.all(np.abs(np.diff(bids)) == 1)  # steps of one cent
    assert int(np.argmin(bids)) < int(np.argmax(bids))  # the low is nearer the open (2 < 3): first
    assert times[0] == 1000.0 and times[-1] == pytest.approx(1900.0 - 7.5)
    assert np.all(np.diff(times) > 0)


def test_path_high_first_when_it_is_nearer() -> None:
    bids, _t = bar_path(100.0, 101.0, 95.0, 96.0, 0.0, 300.0, 15.0)
    assert int(np.argmax(bids)) < int(np.argmin(bids))


def test_path_of_a_flat_bar_has_two_ticks() -> None:
    bids, times = bar_path(100.0, 100.0, 100.0, 100.0, 0.0, 300.0, 15.0)
    assert list(bids) == [10000, 10000] and times[1] == pytest.approx(292.5)


# --- the broker double ------------------------------------------------------------------------------------------


def broker(tmp_path: Path) -> tuple[ReplayBroker, ManualClock]:
    clock = ManualClock(datetime(2025, 1, 6, 10, 0, 0, tzinfo=UTC))
    account, terminal, spec, server_clock = snapshots_from_fake(settings("DEMO"), clock)
    return ReplayBroker(clock, account, terminal, spec, server_clock), clock


def pending(price: float, buy: bool, sl: float, tp: float, expiry_epoch: int | None = None) -> dict:  # type: ignore[type-arg]
    req = {
        "action": c.TRADE_ACTION_PENDING,
        "symbol": "XAUUSD",
        "volume": 0.01,
        "type": c.ORDER_TYPE_BUY_LIMIT if buy else c.ORDER_TYPE_SELL_LIMIT,
        "price": price,
        "sl": sl,
        "tp": tp,
        "magic": 1,
        "comment": "Z1-P1-0",
        "type_time": c.ORDER_TIME_GTC,
        "type_filling": c.ORDER_FILLING_RETURN,
    }
    if expiry_epoch is not None:
        req.update(type_time=c.ORDER_TIME_SPECIFIED, expiration=expiry_epoch)
    return req


def test_buy_limit_fills_at_its_price_when_the_ask_reaches_it(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)  # bid 101.00, ask 101.20
    assert b.send(pending(100.5, True, 95.0, 110.0)).ok
    b.on_tick(10051, 20, t0 + 1)  # ask 100.71: not yet
    assert len(b.orders_) == 1
    b.on_tick(10030, 20, t0 + 2)  # ask 100.50: fills
    assert not b.orders_ and len(b.positions_) == 1
    deal = b.deals_[-1]
    assert deal.entry == c.DEAL_ENTRY_IN and deal.price == 100.5 and deal.comment == "Z1-P1-0"
    assert b.history_[-1].state == c.ORDER_STATE_FILLED


def test_sell_limit_fills_on_the_bid(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10000, 20, t0)
    assert b.send(pending(101.0, False, 106.0, 90.0)).ok
    b.on_tick(10099, 20, t0 + 1)
    assert len(b.orders_) == 1
    b.on_tick(10100, 20, t0 + 2)
    assert len(b.positions_) == 1 and b.deals_[-1].price == 101.0


def test_buy_exits_on_the_bid_and_sell_on_the_ask(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)
    b.send(pending(100.5, True, 99.0, 103.0))
    b.on_tick(10030, 20, t0 + 1)  # filled
    b.on_tick(9900, 20, t0 + 2)  # the bid at the SL
    assert not b.positions_ and b.deals_[-1].reason == c.DEAL_REASON_SL and b.deals_[-1].price == 99.0

    b2, clock2 = broker(tmp_path)
    t1 = clock2.now_utc().timestamp()
    b2.on_tick(10000, 20, t1)
    b2.send(pending(101.0, False, 103.0, 99.0))
    b2.on_tick(10100, 20, t1 + 1)  # filled
    b2.on_tick(10279, 20, t1 + 2)  # ask 102.99
    assert len(b2.positions_) == 1
    b2.on_tick(10283, 20, t1 + 3)  # ask 103.03 >= the SL 103.00 (the bid is 102.83)
    assert not b2.positions_ and b2.deals_[-1].reason == c.DEAL_REASON_SL and b2.deals_[-1].price == 103.0


def test_a_take_profit_exits_at_its_price(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)
    b.send(pending(100.5, True, 99.0, 103.0))
    b.on_tick(10030, 20, t0 + 1)
    b.on_tick(10300, 20, t0 + 2)
    assert not b.positions_ and b.deals_[-1].reason == c.DEAL_REASON_TP and b.deals_[-1].price == 103.0


def test_an_order_expires_at_its_time_and_a_modify_moves_it(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)
    epoch = b.server_clock.utc_to_server_epoch(datetime.fromtimestamp(t0 + 600, UTC))
    res = b.send(pending(100.5, True, 95.0, 110.0, epoch))
    assert res.ok
    ticket = res.order
    later = b.server_clock.utc_to_server_epoch(datetime.fromtimestamp(t0 + 1200, UTC))
    mod = {
        "action": c.TRADE_ACTION_MODIFY,
        "order": ticket,
        "type_time": c.ORDER_TIME_SPECIFIED,
        "expiration": later,
    }
    assert b.send(mod).ok
    b.on_tick(10100, 20, t0 + 700)
    assert len(b.orders_) == 1  # moved on
    b.on_tick(10100, 20, t0 + 1201)
    assert not b.orders_ and b.history_[-1].state == c.ORDER_STATE_EXPIRED


def test_pending_orders_on_the_wrong_side_are_refused_and_a_remove_works(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)
    assert b.send(pending(101.5, True, 95.0, 110.0)).retcode == 10015  # a BUY limit above the ask
    res = b.send(pending(100.0, True, 95.0, 110.0))
    assert res.ok
    assert b.send({"action": c.TRADE_ACTION_REMOVE, "order": res.order}).ok
    assert not b.orders_ and b.history_[-1].state == c.ORDER_STATE_CANCELED
    assert b.send({"action": c.TRADE_ACTION_REMOVE, "order": res.order}).retcode == 10013


def test_market_entry_close_and_stops(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)
    entry = {
        "action": c.TRADE_ACTION_DEAL,
        "symbol": "XAUUSD",
        "volume": 0.01,
        "type": c.ORDER_TYPE_BUY,
        "price": 101.2,
        "sl": 99.0,
        "tp": 105.0,
        "magic": 1,
        "comment": "Z1-P1-0",
    }
    assert b.send(entry).ok
    (pos,) = b.positions_.values()
    assert pos.price_open == pytest.approx(101.2)  # the ask
    sltp = {"action": c.TRADE_ACTION_SLTP, "position": pos.ticket, "sl": 100.0, "tp": 105.0}
    assert b.send(sltp).ok and pos.sl == 100.0
    assert b.send({**sltp, "sl": 101.5}).retcode == 10016  # beyond the bid
    close = {
        "action": c.TRADE_ACTION_DEAL,
        "symbol": "XAUUSD",
        "position": pos.ticket,
        "type": c.ORDER_TYPE_SELL,
        "volume": 0.01,
    }
    assert b.send({**close, "symbol": "EURUSD"}).retcode == 10013  # as MT5: the symbol is the position's
    assert b.send({**close, "type": c.ORDER_TYPE_BUY}).retcode == 10013  # the opposite side only
    assert b.send({**close, "volume": 0.02}).retcode == 10014  # not above the position's volume
    assert b.send({**close, "volume": 0.005}).ok and b.positions_[pos.ticket].volume == pytest.approx(
        0.005
    )  # partial
    assert b.deals_[-1].volume == pytest.approx(0.005) and b.deals_[-1].entry == c.DEAL_ENTRY_OUT
    assert b.send({**close, "volume": 0.005}).ok and not b.positions_
    assert b.send({**close, "volume": 0.005}).retcode == 10036  # gone
    assert (
        b.deals_[-1].entry == c.DEAL_ENTRY_OUT and not b.positions_ and b.deals_[-1].entry == c.DEAL_ENTRY_OUT
    )
    assert CENT == 100


# --- the replays (ZONE_REPLAY=1) -------------------------------------------------------------------------------


@REPLAY
@pytest.mark.parametrize("mode", ["tick", "poll"])
@pytest.mark.parametrize("span", REQUIRED)
def test_replay_span(span: str, mode: str) -> None:
    full = load_bars("XAUUSD")
    base, _v = load_params(ROOT / "data" / "bot_config.db", "XAUUSD", "default")
    plan = plan_span(span, full, base)
    plan, rec = run_span(span, mode, full, base, plan=plan)
    diffs, ex = explain_all(plan, rec, full)
    print("\n" + table(plan, rec, diffs))
    if diffs:
        print(detail(diffs, ex))
    for lvl, msg in rec.log_lines:
        print(f"    runner {lvl}: {msg[:220]}")
    # THE GATE: zero raw differences and no ERROR log line. The suggested causes above are advisory only.
    failures = gate_failures(rec)
    assert not failures, f"{len(failures)} reasons; the first: {failures[0]}"


def test_a_modify_applies_price_sl_tp_and_time_like_mt5(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)
    res = b.send(pending(100.0, True, 95.0, 110.0))
    mod = {
        "action": c.TRADE_ACTION_MODIFY,
        "order": res.order,
        "price": 100.25,
        "sl": 96.0,
        "tp": 111.0,
        "type_time": c.ORDER_TIME_GTC,
    }
    assert b.send(mod).ok
    (o,) = b.orders_.values()
    assert (o.price, o.price_c, o.sl, o.tp, o.exp_s) == (100.25, 10025, 96.0, 111.0, None)
    assert b.send(mod).retcode == 10025  # no change
    assert b.send({**mod, "price": 101.5}).retcode == 10015  # a BUY limit above the ask


def test_the_quote_is_stamped_with_its_own_tick_time(tmp_path: Path) -> None:
    b, clock = broker(tmp_path)
    t0 = clock.now_utc().timestamp()
    b.on_tick(10100, 20, t0)
    clock.advance(600)
    tick = b.tick("XAUUSD")
    assert tick is not None and tick.time_utc.timestamp() == pytest.approx(t0)  # ten minutes old: stale


def test_snapshots_share_only_frozen_data_never_a_clock() -> None:
    """Two callers with the same start time but their own clocks stay independent; a different login gets its own
    account snapshot."""
    t = datetime(2025, 1, 6, 10, 0, 0, tzinfo=UTC)
    c1, c2 = ManualClock(t), ManualClock(t)
    a1, _t1, s1, sc1 = snapshots_from_fake(settings("DEMO"), c1)
    a2, _t2, s2, sc2 = snapshots_from_fake(settings("DEMO"), c2)
    assert sc1 is not sc2 and sc1.clock is c1 and sc2.clock is c2
    assert a1 == a2 and s1 == s2  # the same frozen values
    c1.advance(3600)
    assert sc2.clock.now_utc() == t and sc1.clock.now_utc() != t
    other, *_ = snapshots_from_fake(settings("DEMO", MT5_LOGIN="4242"), ManualClock(t))
    assert other.login != a1.login
