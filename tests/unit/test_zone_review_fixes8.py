# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 8 of the run-zone runner (eye/ZONE_LIVE.md L2 - L5, L7, L8, L10), finding by finding. Each test
reproduces the scenario of the finding on FakeMT5.

Normal case: 1 a marketable P2 only after P1's fill is read; 2 deal times keep their milliseconds; 3 P2 has no
fill-moment block of its own; 4 an exit at the original SL is `SL` while the BE modify was not confirmed; 5 an
M15 start needs no M5 file; 6 the live path never writes the stored history.
Safety net: 7 an exit of our position by a deal of magic 0 is seen; 8 the owner's hand is compared with the
latest accepted values (stop, expiry); 9 the 3-tries cap comes before the BE close; 10 placing permission is
judged before every request; 11 an accepted placement is tracked from its ticket; 12 an overdue stale removal
outlives the reconnection; 13 `stop --now` leaves after 60 s."""

from __future__ import annotations

import argparse
import ast
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.broker import mt5_constants as c
from app.zone.core import MARKET_DIRS
from app.zone.params import ZoneParams
from tests.unit.test_zone_handsoff_causes import (
    BUY_ROWS,
    HOUR0,
    REFUSED,
    assert_hands_off,
    build,
    decide,
    fill_buy_p1,
    hand_close,
    order,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import ts

ROOT = Path(__file__).resolve().parents[2]


def sent_comments(ex, prefix: str = "Z") -> list[str]:  # type: ignore[no-untyped-def]
    return [str(r.get("comment", "")) for r in ex.sent if str(r.get("comment", "")).startswith(prefix)]


# --- 1: a marketable P2 is sent only after its P1 has filled ----------------------------------------------------------


def test_1_a_marketable_p2_waits_for_the_p1_fill_to_be_read(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    w, ex = build(worlds, tmp_path)
    w.bid(97.5)  # the ask 97.7 is through both BUY prices (P1 101.32, P2 98.03)
    w.to(HOUR0)  # the hour's decision: P1 goes at market; its deal is not read yet
    assert sent_comments(ex) == ["Z1-P1-0"]  # P2 is not sent beside an unconfirmed P1
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]
    w.step(2)  # the fill is read: now P2 (marketable too) goes at market
    assert sent_comments(ex) == ["Z1-P1-0", "Z1-P2-0"]
    assert [p.comment for p in w.positions()] == ["Z1-P1-0", "Z1-P2-0"]
    w.step(2)
    assert sorted(w.runner.cands[1].fills) == ["P1", "P2"]


# --- 2: deal times keep their milliseconds ----------------------------------------------------------------------------


def test_2_the_gateway_keeps_the_milliseconds_of_a_deal(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    [d] = [d for d in w.fake.deals if d.entry == c.DEAL_ENTRY_IN]
    d.time_msc = int(d.time) * 1000 + 800
    got = {
        x.ticket: x
        for x in w.runner.gw.deals(
            ts("2025-01-06 09:00").to_pydatetime(), ts("2025-01-06 12:00").to_pydatetime()
        )
    }
    assert got[d.ticket].time_utc.microsecond == 800_000
    d.time_msc = 0  # a record without it keeps its whole second
    got = {
        x.ticket: x
        for x in w.runner.gw.deals(
            ts("2025-01-06 09:00").to_pydatetime(), ts("2025-01-06 12:00").to_pydatetime()
        )
    }
    assert got[d.ticket].time_utc.microsecond == 0


def test_2_an_exit_before_a_later_entry_in_the_same_second_is_judged_in_that_order(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    """P1's stop at .100 and P2's entry at .800 of one second: P2 filled after the setup ended (L5), so it is not the
    setup's fill."""
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    w.bid(94.0)  # a gap through P2 (98.03) and the SL (95)
    w.fake.orders_get()
    deals = {(d.comment, d.entry): d for d in w.fake.deals}
    p1_out = next(
        d
        for d in w.fake.deals
        if d.entry == c.DEAL_ENTRY_OUT and d.position_id == deals[("Z1-P1-0", c.DEAL_ENTRY_IN)].position_id
    )
    p2_in = deals[("Z1-P2-0", c.DEAL_ENTRY_IN)]
    p2_out = next(
        d for d in w.fake.deals if d.entry == c.DEAL_ENTRY_OUT and d.position_id == p2_in.position_id
    )
    base = int(p1_out.time) * 1000
    p1_out.time_msc, p2_in.time_msc, p2_out.time_msc = base + 100, base + 800, base + 900
    w.step(2)
    w.step(2)
    cand = w.runner.cands[1]
    assert sorted(cand.fills) == ["P1"]  # P2 came after P1's exit ended the setup
    assert cand.faults
    w.to("2025-01-06 10:15:05", 94.0)  # the outcome once the first fill's bar is judged on its close (L5)
    assert cand.outcome == "traded"


# --- 3: P2 has no fill-moment block of its own ------------------------------------------------------------------------


def test_3_p2_rests_when_only_its_own_price_would_be_blocked(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    # default parameters: the block is 3.33; the hour opened at 103: P1 101.32 is 1.68 away (open), P2 98.03 is
    # 4.97 away - blocked by a test of its own price, free by P1's (L5 rule 3: P1's block removes both)
    w, _ = build(worlds, tmp_path, params=ZoneParams())
    w.to(HOUR0)
    assert "Z1-P1-0" in w.names() and "Z1-P2-0" in w.names()


# --- 4: the exit's `how` is by the stop in force ----------------------------------------------------------------------


def test_4_an_exit_at_the_original_sl_is_sl_when_the_be_modify_was_refused(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    decide(w)
    fill_buy_p1(w)
    ex.refuse_action[c.TRADE_ACTION_SLTP] = 10016
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)  # the break-even is on; its modify is refused (try 1)
    assert w.runner.cands[1].be_on and [p.sl for p in w.positions()] == [95.0]
    w.bid(94.0)  # the original SL is hit
    w.fake.orders_get()
    w.step(2)
    w.step(2)
    row = w.store.setup(1)
    assert row.outcome == "traded" and row.exit_how == "SL"
    assert row.exit_price == pytest.approx(95.0)  # the logic price of the SL, not the BE stop


def test_4_control_an_exit_at_a_confirmed_be_stop_is_be(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    w, _ = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    decide(w)
    fill_buy_p1(w)
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)
    assert [p.sl for p in w.positions()] == [101.52]
    w.bid(101.0)
    w.fake.orders_get()
    w.step(2)
    w.step(2)
    assert w.store.setup(1).exit_how == "BE"


# --- 5 / 6: the start loads the frames it needs and never writes the stored history ----------------------------------


def _env(tmp_path: Path) -> Path:
    env = tmp_path / ".env"
    env.write_text(
        "TRADING_MODE=DEMO\nMT5_LOGIN=12345678\nMT5_PASSWORD=x\nMT5_SERVER=FBS-Demo\nMT5_TERMINAL_PATH=x\n"
        f"ENABLE_DEMO_TRADING=true\nENGINE_DB_URL=sqlite:///{(tmp_path / 'e.db').as_posix()}\n",
        encoding="utf-8",
    )
    return env


def _four_frame_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = MARKET_DIRS["XAUUSD"]
    if not src.exists():
        pytest.skip("no stored bars")
    dst = tmp_path / "history" / "FBS-Demo" / "XAUUSD"
    dst.mkdir(parents=True)
    for name in ("D1", "H4", "H1", "M15"):
        shutil.copy(src / f"{name}.parquet", dst / f"{name}.parquet")
    shutil.copy(src / "spec.json", dst / "spec.json")
    monkeypatch.setitem(MARKET_DIRS, "XAUUSD", dst)


def test_5_an_m15_start_needs_no_m5_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.cli.zone import build_runner
    from app.config import load_settings
    from app.zone.params import seed

    _four_frame_store(tmp_path, monkeypatch)
    db = tmp_path / "bot_config.db"
    seed(db, "XAUUSD", "default", "test", datetime(2025, 1, 1, tzinfo=UTC))
    args = argparse.Namespace(db=str(db), market="XAUUSD", set="default", fake=True)
    runner = build_runner(load_settings(env_file=str(_env(tmp_path))), args)
    assert runner.params.exec_tf == "M15" and runner.live.frames["M5"].empty
    runner.db.dispose()


def test_5_an_m5_start_without_the_m5_file_is_refused_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.cli.zone import build_runner
    from app.config import load_settings
    from app.core.errors import ConfigError
    from app.zone.params import seed, set_values

    _four_frame_store(tmp_path, monkeypatch)
    db = tmp_path / "bot_config.db"
    at = datetime(2025, 1, 1, tzinfo=UTC)
    seed(db, "XAUUSD", "default", "test", at)
    set_values(db, "XAUUSD", "default", "test", at, "m5", {"exec_tf": "M5"})
    args = argparse.Namespace(db=str(db), market="XAUUSD", set="default", fake=True)
    with pytest.raises(ConfigError, match="stored history refuses the start"):
        build_runner(load_settings(env_file=str(_env(tmp_path))), args)


def test_6_the_live_path_gives_the_runner_no_persistence_callback() -> None:
    tree = ast.parse((ROOT / "app" / "cli" / "zone.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names
    }
    assert "ParquetHistoryStore" not in names  # L2: the bars are kept in memory, never written back
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        assert "persist" not in {k.arg for k in call.keywords}


# --- 7: an exit of our position by a deal of magic 0 is the owner's hand --------------------------------------------


def test_7_a_manual_close_with_magic_zero_is_hands_off_at_once(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    hand_close(w, c.DEAL_REASON_CLIENT)
    for d in w.fake.deals:
        if d.entry == c.DEAL_ENTRY_OUT:
            d.magic = 0  # a close from the terminal carries no magic
    assert any(o.comment == "Z1-P2-0" for o in w.orders())
    w.step(2)
    w.step(2)
    assert_hands_off(w, caplog)  # P2 and the rest removed, the setup ended hands-off


# --- 8: the owner's hand is compared with the latest accepted values --------------------------------------------------


def test_8_restoring_the_original_sl_after_the_break_even_is_hands_off(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, _ = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    decide(w)
    fill_buy_p1(w)
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)
    [pos] = w.fake.positions
    assert pos.sl == 101.52  # the break-even stop was accepted
    pos.sl = 95.0  # the owner puts the original stop back
    w.step(2)
    w.step(2)
    kept = assert_hands_off(w, caplog)
    assert [t[2] for t in kept] == [95.0]  # left as the owner set it, not moved back to the BE stop


def test_8_restoring_the_old_expiry_after_an_extension_is_hands_off(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)  # the BUY candidate is the hour's setup; its P2 rests
    old = order(w, "Z1-P2-0").time_expiration
    w.to("2025-01-06 10:51:30", 101.0)  # the expiry extension of the hour's setup
    assert order(w, "Z1-P2-0").time_expiration == old + 3600
    order(w, "Z1-P2-0").time_expiration = old  # the owner restores the old expiry
    w.step(2)
    w.step(2)
    assert w.runner.hands_off is not None and "expiry" in w.runner.hands_off


# --- 9: the cap of 3 tries comes before the BE close ------------------------------------------------------------------


def test_9_three_refused_modifies_then_a_price_beyond_the_stop_is_hands_off_not_a_close(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, ex = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    decide(w)
    fill_buy_p1(w)
    ex.refuse_action[c.TRADE_ACTION_SLTP] = 10016
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)  # try 1
    w.step(2, 105.7)  # try 2
    w.step(2, 105.7)  # try 3
    w.step(2, 101.4)  # the price is beyond the BE stop (101.52), above the SL: the cap speaks first
    assert w.runner.hands_off is not None and "tries" in w.runner.hands_off
    closes = [r for r in ex.sent if r.get("action") == c.TRADE_ACTION_DEAL and r.get("position")]
    assert closes == []  # no market close
    kept = assert_hands_off(w, caplog)
    assert [t[2] for t in kept] == [95.0]


# --- 10: placing permission is judged before every request ------------------------------------------------------------


def test_10_an_unknown_place_stops_the_rest_of_the_placement_loop(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    ex.lose.add("Z1-P1-0")  # the BUY P1: no reply, may or may not exist
    w.to(HOUR0)
    assert sent_comments(ex) == ["Z1-P1-0"]  # the SELL candidate's P1 and P2 are not sent in the same cycle
    w.step(2)
    assert sent_comments(ex) == ["Z1-P1-0"]  # nor while the outcome is unknown


# --- 11: an accepted placement is tracked from its ticket -------------------------------------------------------------


def test_11_an_order_filled_before_any_snapshot_without_its_deal_is_hands_off(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, _ = build(worlds, tmp_path)
    w.to(HOUR0)  # the orders are placed; no cycle has read them back
    o = order(w, "Z1-P1-0")
    w.fake.orders.remove(o)
    w.fake.desk._archive(o, c.ORDER_STATE_FILLED)  # the history says filled; no position, no entry deal
    w.step(2)
    w.to("2025-01-06 10:16:10")
    w.step(2)
    assert_hands_off(w, caplog)


# --- 12: an overdue stale removal outlives the reconnection -----------------------------------------------------------


def test_12_orders_are_removed_once_the_connection_is_back_after_an_outage_over_one_bar(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    assert len(w.names()) == 4
    w.fake.disconnect()
    w.step(2)
    w.to("2025-01-06 10:16:30")  # 16 minutes without a successful read
    assert len(w.names()) == 4  # nothing can be done while it is down
    w.fake.reconnect()
    w.step(2)
    assert w.orders() == []  # L7: the removals owed are sent once it is back
    assert {r.outcome for r in w.store.setups()} == {"interrupted"}
    assert w.runner.hands_off is None


def test_12_a_short_outage_removes_nothing(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.fake.disconnect()
    w.step(2)
    w.step(60)
    w.fake.reconnect()
    w.step(2)
    assert len(w.names()) == 4


# --- 13: stop --now leaves after 60 s ---------------------------------------------------------------------------------


def test_13_stop_now_exits_after_60_seconds_with_the_outstanding_orders_logged(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED  # no removal is accepted
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(30)
    assert not w.runner.finished  # not yet: retried
    w.step(35)
    assert w.runner.finished
    text = "\n".join(r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)
    assert "stop --now" in text and "Z1-P1-0" in text


def test_13_a_stop_without_now_never_leaves_early(worlds: list, tmp_path: Path) -> None:  # type: ignore[type-arg]
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(120)
    assert not w.runner.finished


def test_13_stop_now_exits_after_60_seconds_even_when_the_broker_cannot_be_read(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.fake.disconnect()
    w.step(2)
    w.step(30)
    assert not w.runner.finished
    w.step(35)
    assert w.runner.finished


# --- 1 / 10 together: a market entry that never gets a deal ----------------------------------------------------------


def test_10_a_market_p1_without_a_deal_holds_back_p2_and_is_hands_off_after_a_bar(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The market P1 is answered DONE but no deal ever comes: L7 stops placing (nothing beside it, P2 included),
    L8 cause 6 turns hands-off after one bar. (The magic holds nothing, so the hands-off ends at once.)"""
    from tests.unit.test_zone_trader import NoDealMarket

    w, ex = build(worlds, tmp_path, fake_bid=100.9)  # the ask is through the BUY P1: a market entry
    w.runner.exe = NoDealMarket(ex)  # type: ignore[assignment]
    w.to(HOUR0, 100.9)
    assert [r.market for r in w.store.requests(kinds=("place",))] == [
        True
    ]  # P1 only; P2 is not placed beside it
    w.step(600, 100.9)
    assert not any(
        "made no deal in one bar" in r.getMessage() for r in caplog.records
    )  # within one bar: waited for
    w.step(400, 100.9)
    assert any("the market entry Z1-P1-0 made no deal in one bar" in r.getMessage() for r in caplog.records)
    assert not any(r.comment == "Z1-P2-0" for r in w.store.requests(kinds=("place",)))
