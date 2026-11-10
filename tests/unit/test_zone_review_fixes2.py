# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""The runner after Sol's second review of piece 2a (eye/ZONE_LIVE.md L1, L3, L4, L7, L8, L10): one test for each
fix, each failing on the code before the fix."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tests.unit.test_zone_trader import (
    cands,
    flaky,
    requests,
    restart,
    world,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import World

# --- 1: nothing new while an unwanted order is still open (L7) ---------------------------------------------------


def test_nothing_new_is_placed_while_an_unwanted_order_is_still_open(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    f.refuse_remove = 1000
    w.step(2)
    w.to("2025-01-06 10:59:50", 103)  # the end-of-hour removals are refused
    old = w.names()
    assert len(old) == 4
    w.to("2025-01-06 11:00:03", 103)  # the new hour's candidates exist, the old orders still rest
    assert w.names() == old and not any(o.comment.startswith(("Z3", "Z4")) for o in w.orders())
    f.refuse_remove = 0
    w.step(2)  # the removals go through (nothing new in this cycle)
    assert not any(o.comment.startswith(("Z1", "Z2")) for o in w.orders())
    w.step(2)
    assert w.names() == ["Z3-P1-0", "Z3-P2-0", "Z4-P1-0", "Z4-P2-0"]


# --- 2: a close is done only when the position is gone; the obligation survives a crash (L8) ---------------------


def test_a_partial_close_is_not_done_until_the_position_is_gone(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    [pos] = w.positions()
    f = flaky(w)
    f.partial_close = 2  # DONE_PARTIAL answers that close nothing
    w.runner.close_wanted[pos.ticket] = "required"
    w.step(2)
    assert [r.state for r in requests(w, "close")] == ["sent"] and len(w.positions()) == 1
    w.step(2)
    assert len(w.positions()) == 1
    w.step(2)  # the third send closes it
    assert w.positions() == []
    w.step(2)
    assert [(r.state, r.closed_at is not None) for r in requests(w, "close")] == [("sent", True)]


# --- 4: a second Ctrl+C does not leave with orders resting (L10) --------------------------------------------------


def test_a_second_ctrl_c_is_ignored_until_the_orders_are_removed(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    w.step(2)
    f.refuse_remove = 3
    calls = {"n": 0}

    def sleeper(seconds: float) -> None:
        calls["n"] += 1
        if calls["n"] in (1, 2):
            raise KeyboardInterrupt
        w.clock.advance(seconds)

    w.runner.run(sleep=sleeper)  # returns: the loop was not left by the second Ctrl+C
    assert w.orders() == [] and w.runner.finished and calls["n"] >= 3


# --- 6: every row of the hour comes back with its state (L3, L4) ---------------------------------------------------


def test_a_p1_refused_candidate_is_not_created_again_after_a_restart(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.refuse["Z1-P1-0"] = 10015
    w.runner.start()
    w.step(2)
    assert w.store.setup(1).outcome == "dropped" and "refused" in w.store.setup(1).note
    w2 = restart(w, worlds)
    w2.step(2)
    w2.step(2)
    assert len(w2.store.setups()) == 2  # no third row for the hour
    assert w2.store.setup(1).state == "dropped" and not any(o.comment.startswith("Z1") for o in w2.orders())
    assert not any(r.setup_id > 2 for r in requests(w2, "place"))


# --- 7: an interrupted candidate cannot become the hour's setup (L7) -----------------------------------------------


def test_a_touch_of_an_interrupted_candidate_is_recorded_and_reserves_nothing(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.kill.activate("test", "t", "test")
    w.step(2)
    w.kill.release("test", "t")
    w.step(2)
    with caplog.at_level(logging.WARNING, logger="app.zone.trader"):
        w.step(2, 101.2)  # the BUY line is touched after the interruption
    assert w.runner.hour is not None and w.runner.hour.chosen is None and w.orders() == []
    row = w.store.setup(1)
    assert row.outcome == "interrupted" and row.chosen is False
    assert any("ends interrupted" in r.message for r in caplog.records)
    w.to("2025-01-06 11:00:03", 103)
    assert w.runner.res_end is None and w.runner.hour.reserved is False  # it reserved nothing


def test_the_fill_of_an_interrupted_candidate_is_closed(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    f.refuse_remove = 1000
    w.step(2)
    w.kill.activate("test", "t", "test")
    w.step(2)
    w.step(2, 101.0)  # the order the kill switch could not remove fills
    assert w.positions() == [] and cands(w)["BUY"].fills == {}


def test_zone_run_pins_the_newest_version_of_the_set(tmp_path: Path) -> None:
    import argparse
    from datetime import UTC, datetime

    from app.cli.zone import build_runner
    from app.config import load_settings
    from app.zone.core import MARKET_DIRS
    from app.zone.params import seed, set_values

    if not MARKET_DIRS["XAUUSD"].exists():
        pytest.skip("no stored bars")
    env = tmp_path / ".env"
    env.write_text(
        "TRADING_MODE=DEMO\nMT5_LOGIN=12345678\nMT5_PASSWORD=x\nMT5_SERVER=FBS-Demo\nMT5_TERMINAL_PATH=x\n"
        f"ENABLE_DEMO_TRADING=true\nENGINE_DB_URL=sqlite:///{(tmp_path / 'e.db').as_posix()}\n",
        encoding="utf-8",
    )
    at = datetime(2025, 1, 1, tzinfo=UTC)
    db = tmp_path / "bot_config.db"
    v1 = seed(db, "XAUUSD", "default", "t", at)
    set_values(db, "XAUUSD", "default", "t", at, "why", {"away_frac": "0.3", "be_mode": "off"})
    args = argparse.Namespace(db=str(db), market="XAUUSD", set="default", fake=True)
    runner = build_runner(load_settings(env_file=str(env)), args)
    assert runner.persist is None and runner.cfg.set_version > v1 and runner.params.be_mode == "off"
    runner.db.dispose()
