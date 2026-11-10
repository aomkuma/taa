# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 9 of the run-zone runner, the code-only findings (eye/ZONE_LIVE.md L2, L5 "The exits", L10).

A. One function classifies a setup's exit (`classify_exit`): a queued BE close never overrides a broker SL / TP deal.
B. The M5 start's arming comes from closed H1 bars alone (no exec_tf history is needed before the exec file's
   first bar); the start is complete only after the whole bootstrap succeeded.
C. `stop --now` behind an unacknowledged ordinary stop takes effect, its 60 s counted from the `now` request."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.broker import mt5_constants as c
from app.zone.trader import ZoneStartError, classify_exit
from tests.unit.test_zone_handsoff_causes import (
    REFUSED,
    Row,
    build,
    decide,
    fill_buy_p1,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import FILL, ts

# --- A: the exit's `how` -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "be_in_force", "own_close_at_be", "how"),
    [
        (c.DEAL_REASON_TP, False, False, "TP"),
        (c.DEAL_REASON_TP, True, True, "TP"),  # a broker TP deal is a TP whatever was queued
        (c.DEAL_REASON_SL, False, False, "SL"),
        (c.DEAL_REASON_SL, False, True, "SL"),  # a queued BE close that was refused: the original SL fired
        (c.DEAL_REASON_SL, True, False, "BE"),  # the BE stop was confirmed in force
        (c.DEAL_REASON_EXPERT, False, True, "BE"),  # L5's close at the BE price
        (c.DEAL_REASON_EXPERT, False, False, "close"),  # any other close of the runner
        (c.DEAL_REASON_CLIENT, False, False, "close"),
        (c.DEAL_REASON_SO, True, True, "close"),
    ],
)
def test_a_the_exit_is_classified_by_its_first_deal(
    reason: int, be_in_force: bool, own_close_at_be: bool, how: str
) -> None:
    assert classify_exit(reason, be_in_force=be_in_force, own_close_at_be=own_close_at_be) == how


BEYOND_ROWS: dict[int, list[Row]] = {130: [(103.0, 105.9, 100.9, 100.95), FILL, FILL, FILL]}


def beyond_the_be_stop(worlds: list, tmp_path: Path):  # type: ignore[no-untyped-def, type-arg]
    """The break-even is on at the 10:15 close with the price already beyond its stop (101.52): the runner owes a
    market close at the BE price."""
    w, ex = build(worlds, tmp_path, exec_rows=BEYOND_ROWS)
    decide(w)
    fill_buy_p1(w)
    w.step(60, 105.7)
    w.step(60, 100.95)
    return w, ex


def test_a_a_refused_be_close_then_the_original_sl_is_sl_at_the_sl_price(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = beyond_the_be_stop(worlds, tmp_path)
    ex.refuse_action[c.TRADE_ACTION_DEAL] = REFUSED  # the market close is refused
    w.to("2025-01-06 10:15:02", 100.95)
    assert w.runner.cands[1].close_reason  # the BE close is queued
    assert [p.sl for p in w.positions()] == [95.0]
    w.bid(94.0)  # the original SL fires at the broker
    w.fake.orders_get()
    w.step(2)
    w.step(2)
    row = w.store.setup(1)
    assert row.outcome == "traded" and row.exit_how == "SL"
    assert row.exit_price == pytest.approx(95.0)  # the logic SL price, not the BE stop 101.52


def test_a_the_runners_own_be_close_is_be_at_the_be_stop(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    w, _ = beyond_the_be_stop(worlds, tmp_path)
    w.to("2025-01-06 10:15:02", 100.95)
    w.step(2, 100.95)
    assert w.positions() == []
    row = w.store.setup(1)
    assert row.exit_how == "BE" and row.exit_price == pytest.approx(101.3158 + 0.2, abs=1e-3)


# --- B: the M5 start's arming -----------------------------------------------------------------------------------------


def m5_world(worlds: list, tmp_path: Path):  # type: ignore[no-untyped-def, type-arg]
    """An M5 world whose stored M5 history starts at 2025-01-06 20:00, after the arming epoch (2025-01-01) - and
    after the H1 bar of hour 135 (2025-01-06 15:00) that visited the BUY line 100 (the first hour that can make
    a visit is 130)."""
    dip: list[Row] = [(103.0, 104.0, 101.0, 103.0)] + [FILL] * 11
    w, ex = build(
        worlds,
        tmp_path,
        exec_tf="M5",
        exec_rows={135: dip},
        start=False,
        now="2025-01-07 09:59:58",
        last_hour=170,
    )
    frame = w.runner.live.frames["M5"]
    w.runner.live.frames["M5"] = frame[frame["open_time"] >= ts("2025-01-06 20:00")].reset_index(drop=True)
    return w, ex


def test_b_the_arming_needs_no_exec_history_before_the_exec_files_first_bar(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = m5_world(worlds, tmp_path)
    w.runner.start()
    r = w.runner
    assert r.initialized and r.hands_off is None
    assert (
        r.armed[(100.0, 10.0, 100.0)] is False
    )  # the visit of hour 135 disarmed the line, as the epoch's arming


def test_b_a_failed_bootstrap_refuses_the_start(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    from app.zone.core import ZoneError

    w, _ = build(worlds, tmp_path, start=False)

    def boom(upto: int) -> None:
        raise ZoneError("no history")

    w.runner._build_arming = boom  # type: ignore[method-assign]
    with pytest.raises(ZoneStartError, match="could not be completed"):
        w.runner.start()
    assert not w.runner.initialized and not w.runner.started


def test_b_a_failed_bootstrap_is_retried_and_not_cleared_by_a_flat_book(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    from app.zone.core import ZoneError

    w, _ = build(worlds, tmp_path, start=False)
    real_orders = w.runner.gw.orders
    state = {"read_fails": True}

    def orders(symbol: str | None = None) -> Any:
        if state["read_fails"]:
            raise OSError("no connection")
        return real_orders(symbol)

    w.runner.gw.orders = orders  # type: ignore[method-assign]
    w.runner.start()  # the first read fails: nothing is decided, no error
    assert not w.runner.initialized
    state["read_fails"] = False
    real_arming = w.runner._build_arming
    calls = {"n": 0}

    def boom(upto: int) -> None:
        calls["n"] += 1
        raise ZoneError("no history")

    w.runner._build_arming = boom  # type: ignore[method-assign]
    w.step(2)  # the bootstrap fails: hands-off (an uncaught error), not initialized
    assert not w.runner.initialized and w.runner.hands_off is not None
    w.step(2)  # the magic is flat - and still the bootstrap is retried, not skipped
    w.step(2)
    assert calls["n"] >= 3 and not w.runner.initialized
    w.runner._build_arming = real_arming  # type: ignore[method-assign]
    w.step(2)
    w.step(2)
    assert w.runner.initialized and w.runner.hands_off is None


# --- C: stop --now behind an unacknowledged ordinary stop -------------------------------------------------------------


def test_c_the_store_lists_every_unacknowledged_stop(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    w, _ = build(worlds, tmp_path)
    a = w.store.request_stop(w.clock.now_utc(), "a")
    b = w.store.request_stop(w.clock.now_utc(), "b", now_flag=True)
    assert [r.id for r in w.store.pending_stops()] == [a, b]
    assert w.store.pending_stop().id == a  # type: ignore[union-attr]


def test_c_stop_now_behind_an_unacknowledged_stop_exits_after_60_seconds(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED  # no removal is accepted: the ordinary stop stays open
    w.store.request_stop(w.clock.now_utc(), "ordinary")
    w.step(2)
    w.step(120)  # an ordinary stop never leaves early
    assert w.runner.stopping and not w.runner.exit_now and not w.runner.finished
    w.store.request_stop(w.clock.now_utc(), "owner", now_flag=True)
    w.step(2)
    assert w.runner.exit_now
    w.step(30)
    assert not w.runner.finished
    w.step(35)  # more than 60 s from the `now` request
    assert w.runner.finished


# --- D: one broker-read path, and the hour's first quote as the runner knows it ------------------------------------------


def place_requests(w: Any) -> list[Any]:
    return [r for r in w.store.requests() if r.kind == "place"]


def test_d_reads_failing_through_the_first_minutes_leave_the_hour_undecided(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    w.to("2025-01-06 09:59:58")  # the last healthy read before the hour
    w.fake.disconnect()
    w.to("2025-01-06 10:00:02")
    w.to("2025-01-06 10:01:00")
    w.to("2025-01-06 10:02:05")
    w.fake.reconnect()
    w.to("2025-01-06 10:02:10")  # recovered: a late recovery never opens a new 60 s
    assert w.runner.hour is not None and w.runner.hour.undecided and not w.runner.hour.decided
    assert w.names() == [] and place_requests(w) == []
    w.to("2025-01-06 11:00:03")  # the next hour decides as usual
    assert w.runner.hour.decided and len(w.names()) == 4


def test_d_a_pause_after_a_healthy_read_until_5_past_leaves_the_hour_undecided(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    w.to("2025-01-06 09:59:58")
    w.to("2025-01-06 10:05:00")  # the runner was not cycling in between
    assert w.runner.hour is not None and w.runner.hour.undecided
    assert w.names() == [] and place_requests(w) == []


def test_d_continuous_cycles_through_the_break_put_the_window_at_the_reopening(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    from tests.unit.test_zone_trader import reopening_at

    w, _ = build(worlds, tmp_path, start=False)
    reopening_at(w, "2025-01-06 10:05:00")  # the quote is the last one before the break (09:55) until then
    w.runner.start()
    t = ts("2025-01-06 09:59:58")
    while t < ts("2025-01-06 10:05:30"):
        w.to(t, 103)
        t += __import__("pandas").Timedelta(seconds=2)
    h = w.runner.hour
    assert h is not None and h.decided and len(w.names()) == 4
    assert ts("2025-01-06 10:04:56") <= h.first_quote_at <= ts("2025-01-06 10:05:00")


def test_d_a_failed_forming_h1_read_places_nothing_that_cycle(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    from app.zone.params import ZoneParams
    from tests.unit.test_zone_trader import bar, world

    rows129 = [
        bar(103, 104, 102, 103),
        bar(105, 106, 104, 105),
        bar(103, 104, 102, 103),
        bar(103, 104, 102, 103),
    ]
    w = world(worlds, tmp_path, exec_rows={129: rows129}, params=ZoneParams())
    w.step(2)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"]
    w.to("2025-01-06 10:14:50", 103)  # the coming bar blocks P1 and P2: removed ahead
    assert w.names() == []
    real = w.src.forming_h1

    def broken() -> Any:
        raise OSError("the forming bar cannot be read")

    w.src.forming_h1 = broken  # type: ignore[method-assign]
    w.to("2025-01-06 10:30:02", 103)  # bar 522 allows them again - but a read failed this cycle
    assert w.names() == [] and w.runner.stale_since is not None
    w.src.forming_h1 = real  # type: ignore[method-assign]
    w.step(2, 103)
    assert w.names() == ["Z1-P1-1", "Z1-P2-1"]


# --- F: a ticket becomes known through one function -----------------------------------------------------------------


def test_f_an_unknown_place_cancelled_by_hand_before_any_snapshot_is_hands_off(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_zone_handsoff_causes import hand_cancel
    from tests.unit.test_zone_trader import flaky, world

    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.no_reply_executed.add("Z1-P1-0")  # accepted at the broker, the reply lost
    w.runner.start()
    w.step(2)  # the decision: Z1-P1-0 is sent, its row is `unknown`
    hand_cancel(w, "Z1-P1-0")  # the owner cancels it before the runner has seen it once
    w.step(2)
    # the magic is flat, so the hands-off ends in the same cycle: it is seen in the log
    assert any(
        "was cancelled by hand" in r.getMessage() for r in caplog.records if "HANDS-OFF" in r.getMessage()
    )
    w.step(2)
    assert not any(r.comment == "Z1-P1-1" for r in w.store.requests(kinds=("place",)))  # never placed again


def test_f_an_unknown_place_found_filled_without_its_entry_deal_is_hands_off_after_a_bar(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_zone_trader import flaky, world

    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.no_reply_executed.add("Z1-P1-0")
    w.runner.start()
    w.step(2)
    o = next(o for o in w.fake.orders if o.comment == "Z1-P1-0")
    w.fake.orders.remove(o)
    w.fake.desk._archive(o, c.ORDER_STATE_FILLED)  # the history says filled; no position, no entry deal
    w.step(2)
    assert not any("HANDS-OFF" in r.getMessage() for r in caplog.records)  # within one bar it is waited for
    w.to("2025-01-06 10:16:10")
    w.step(2)
    assert any(
        "without its entry deal" in r.getMessage() for r in caplog.records if "HANDS-OFF" in r.getMessage()
    )


def test_f_an_unknown_place_found_expired_is_moot_and_not_hands_off(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    from tests.unit.test_zone_trader import flaky, world

    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.no_reply_executed.add("Z1-P1-0")
    w.runner.start()
    w.step(2)
    o = next(o for o in w.fake.orders if o.comment == "Z1-P1-0")
    w.fake.orders.remove(o)
    w.fake.desk._archive(o, c.ORDER_STATE_EXPIRED)
    w.step(2)
    assert w.runner.hands_off is None
    assert [r.state for r in place_requests(w) if r.comment == "Z1-P1-0"] == ["moot"]


# --- G: the in-bar touch order in the visit records -----------------------------------------------------------------


def test_g_sell_touched_first_then_buy_in_the_decision_bar_is_an_explained_difference(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    rows: dict[int, list[Row]] = {130: [(103.0, 109.5, 100.9, 103.0), FILL, FILL, FILL]}
    w, _ = build(worlds, tmp_path, exec_rows=rows)
    decide(w)
    w.step(2, 109.0)  # the SELL line is touched first: the SELL candidate is the hour's setup
    w.step(2, 101.0)  # then the BUY line, in the same bar
    assert w.runner.hour is not None and w.runner.hour.chosen is not None
    chosen = w.runner.hour.chosen
    assert chosen.side == "SELL"
    w.to("2025-01-06 11:00:05", 103)
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("in-bar touch order" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    rows_v = {v.side: v for v in w.store.visits(ts("2025-01-06 10:00").to_pydatetime())}
    assert set(rows_v) == {"BUY", "SELL"}
    assert (
        rows_v["SELL"].setup_id == chosen.id
    )  # the traded visit carries the hour's setup id, whatever its class
    assert rows_v["SELL"].classification == "busy" and rows_v["BUY"].classification == "setup"
    assert "in-bar touch order" in rows_v["SELL"].note and "in-bar touch order" in rows_v["BUY"].note


# --- E: the replay cycles through a long gap between ticks -----------------------------------------------------------


class _Stub:
    """Just what `Replay._fill_gap` touches."""

    def __init__(self, tick_s: float, seen_s: float) -> None:
        from types import SimpleNamespace

        self.broker = SimpleNamespace(tick_s=tick_s)
        self.cfg = SimpleNamespace(cycle_seconds=2.0)
        self.stale_seconds = 30.0
        self._seen_s = seen_s
        self.cycles: list[tuple[float, bool]] = []

    def _maybe_cycle(self, t_s: float, close_s: float, force: bool = False) -> None:
        self.cycles.append((t_s, force))


def test_e_a_gap_longer_than_the_stale_quote_is_cycled_every_cycle_seconds() -> None:
    from tests.zone_replay import Replay

    s = _Stub(tick_s=1000.0, seen_s=1000.0)
    Replay._fill_gap(s, 1100.0, 2000.0)  # type: ignore[arg-type]
    times = [t for t, _f in s.cycles]
    assert times[0] == 1002.0 and times[-1] == 1098.0 and len(times) == 49
    assert all(b - a == 2.0 for a, b in itertools.pairwise(times))
    assert [f for _t, f in s.cycles] == [False] * 48 + [True]  # the last one before the next tick is run


def test_e_a_short_gap_is_not_cycled_and_the_fill_starts_after_the_last_cycle() -> None:
    from tests.zone_replay import Replay

    s = _Stub(tick_s=1000.0, seen_s=1000.0)
    Replay._fill_gap(s, 1030.0, 2000.0)  # type: ignore[arg-type]
    assert s.cycles == []
    s = _Stub(tick_s=1000.0, seen_s=1090.0)  # a forced cycle at the bar's close already ran at 1090
    Replay._fill_gap(s, 1100.0, 2000.0)  # type: ignore[arg-type]
    assert [t for t, _f in s.cycles] == [1092.0, 1094.0, 1096.0, 1098.0]


def test_e_an_m5_replay_that_opens_the_week_decides_its_first_hour() -> None:
    """The span's first hour is the weekly reopening and the first M5 bar opens at 23:05: the replay broker serves
    the last tick before the span and the runner cycles through the gap, so the hour's first quote is the
    reopening (L2) - the visit of that hour is classified as the simulation does, never `undecided`."""
    from app.zone.core import load_bars
    from app.zone.params import load_params
    from tests.unit.zone_live_support import settings
    from tests.zone_replay import Replay, ReplayConfig
    from tests.zone_replay_compare import ROOT, plan_span

    if not (ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD").exists():
        pytest.skip("no stored bars")
    full = load_bars("XAUUSD")
    base, _v = load_params(ROOT / "data" / "bot_config.db", "XAUUSD", "default")
    plan = plan_span("2026-03-m5", full, base)
    end = plan.start + pd.Timedelta(minutes=90)
    rp = Replay(
        full,
        plan.params,
        settings("DEMO"),
        ReplayConfig(tf=plan.tf, mode="tick", epoch=plan.epoch),
        plan.start,
        end,
    )
    try:
        rp.run()
        visits = rp.runner.store.visits(plan.start.to_pydatetime())  # type: ignore[union-attr]
    finally:
        rp.close()
    assert [(v.side, v.classification) for v in visits] == [("BUY", "abnormal")]
    assert not [m for lvl, m in rp.collect.lines if "undecided" in m]
