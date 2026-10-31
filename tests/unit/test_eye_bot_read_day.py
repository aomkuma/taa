"""Tests for the pure helpers of eye/research/bot_read_day.py (the drawing of what the bot reads on a day)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

day = importlib.import_module("eye.research.bot_read_day")
bot = importlib.import_module("eye.bot2e")


def seeded_db(tmp_path: Path) -> Path:
    cfg = importlib.import_module("eye.bot_config")
    db = tmp_path / "cfg" / "bot_config.db"
    at = pd.Timestamp("2026-10-31 10:00", tz="UTC").to_pydatetime()
    cfg.seed(db, "XAUUSD", "default", "t", at)
    cfg.set_values(db, "XAUUSD", "default", "t", at, "n", {"min_r": "1.5"})
    return db


def test_parse_overrides_types_and_unknown_names() -> None:
    got = day.parse_overrides(["fib_entry=0.382", "fib_count=on", "max_orders=2", "setup_days=2"])
    assert got == {"fib_entry": 0.382, "fib_count": "on", "max_orders": 2, "setup_days": 2}
    assert day.parse_overrides([]) == {}
    assert day.parse_overrides(["early_leg=off", "fade_min=off", "fib_early=0.1", "min_r=2"]) == {
        "early_leg": "off", "fade_min": "off", "fib_early": 0.1, "min_r": 2.0,
    }  # fmt: skip
    for bad in ("min_r=abc", "max_orders=1.5"):
        with pytest.raises(SystemExit):
            day.parse_overrides([bad])
    for bad in ("band_frac=0.1", "nonsense", "fib_entry"):
        with pytest.raises(SystemExit):
            day.parse_overrides([bad])


def test_day_bounds_are_06_00_to_midnight_thai() -> None:
    a, b = day.day_bounds("2026-10-07")
    assert a == pd.Timestamp("2026-10-06 23:00", tz="UTC") and b == pd.Timestamp("2026-10-07 17:00", tz="UTC")


def test_every_reason_the_bot_gives_has_a_style_and_the_order_is_green() -> None:
    for reason in bot.REASONS:
        if reason not in ("market closed", "outside window"):
            assert reason in day.STYLE_OF, reason
    assert day.reason_style("order written")[0] == "ORDER"
    assert day.reason_style("something new")[0] == "something new"  # an unknown reason is shown, not dropped


def test_trend_word_reads_the_view_in_real_terms() -> None:
    assert [day.trend_word(s, 1) for s in ("UP", "DOWN", "none")] == ["UP", "DOWN", "none"]
    assert [day.trend_word(s, -1) for s in ("UP", "DOWN", "none")] == ["DOWN", "UP", "none"]


def test_leg_from_log_and_fib_prices_buy_and_sell() -> None:
    t0, l0, t100, h100 = day.leg_from_log(
        "BUY|M5|2026-10-17 01:30:00+00:00", "L0 4155.81@17/10 08:30 H100 4198.73@17/10 11:25 leg 42.92"
    )
    assert (t0, l0, t100, h100) == (
        pd.Timestamp("2026-10-17 01:30", tz="UTC"), 4155.81, pd.Timestamp("2026-10-17 04:25", tz="UTC"), 4198.73,
    )  # fmt: skip
    lv = day.fib_prices(l0, h100)
    assert lv[0.0] == 4155.81 and lv[1.0] == 4198.73 and lv[0.382] == pytest.approx(4155.81 + 0.382 * 42.92)
    # a SELL: L0 is the start (the top), H100 the end (the low): the levels run down from the start
    _, s_l0, s_t100, s_h100 = day.leg_from_log(
        "SELL|M5|2026-10-07 19:00:00+00:00", "L0 4184.25@08/10 02:00 H100 4161.42@08/10 12:50 leg 22.83"
    )
    assert s_t100 == pd.Timestamp("2026-10-08 05:50", tz="UTC")
    sl = day.fib_prices(s_l0, s_h100)
    assert sl[0.0] == 4184.25 and sl[1.0] == 4161.42 and sl[0.382] == pytest.approx(4184.25 - 0.382 * 22.83)
    assert sl[1.618] == pytest.approx(4184.25 - 1.618 * 22.83)  # beyond the end, the same way
    with pytest.raises(ValueError):
        day.leg_from_log("a|b", "nothing")
    # an early leg's provisional end is marked H100?
    text = "L0 4161.42@07/10 06:40 H100? 4184.25@07/10 09:00 leg 22.83"
    e0, el0, e100, eh100 = day.leg_from_log("BUY|M5|2026-10-06 23:40:00+00:00", text)
    assert (e0, el0, e100, eh100) == (
        pd.Timestamp("2026-10-06 23:40", tz="UTC"), 4161.42, pd.Timestamp("2026-10-07 02:00", tz="UTC"), 4184.25,
    )  # fmt: skip
    assert day.is_early(text) and not day.is_early("L0 4161.42@07/10 06:40 H100 4184.25@07/10 09:00 leg 1")


def test_exit_bar_stop_first_on_the_fill_bar_and_a_double_touch_is_the_stop() -> None:
    idx = pd.date_range("2026-10-19 00:00", periods=5, freq="5min", tz="UTC")

    def frame(rows):
        return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx[: len(rows)])

    # a BUY: stop 100, target 110. The fill bar touches the target only: not an exit (the target counts later)
    rows = [(101, 111, 100.5, 105), (105, 106, 104, 105), (105, 111, 104, 110)]
    assert day.exit_bar(frame(rows), idx[0], True, 100.0, 110.0) == idx[2]
    # the fill bar touches the stop: exit on it
    assert (
        day.exit_bar(frame([(101, 102, 99, 100), (100, 111, 100, 105)]), idx[0], True, 100.0, 110.0) == idx[0]
    )
    # a later bar touching both: the stop's bar (the same bar either way); still open: None
    assert (
        day.exit_bar(frame([(101, 102, 100.5, 101), (101, 111, 99, 105)]), idx[0], True, 100.0, 110.0)
        == idx[1]
    )
    assert (
        day.exit_bar(frame([(101, 102, 100.5, 101), (101, 103, 101, 102)]), idx[0], True, 100.0, 110.0)
        is None
    )
    # a SELL: stop 110, target 100
    assert (
        day.exit_bar(frame([(105, 106, 104, 105), (105, 106, 99, 100)]), idx[0], False, 110.0, 100.0)
        == idx[1]
    )


def test_thai_stamp_round_trips_score_fill_text() -> None:
    assert day.thai_stamp("19/10 07:10", 2026) == pd.Timestamp("2026-10-19 00:10", tz="UTC")


def test_leg_from_log_reads_a_fade_leg_and_is_fade() -> None:
    text = "fade S 4154.21@06/10 23:55 E 4184.25@07/10 02:00 run 30.04"
    t0, l0, t100, h100 = day.leg_from_log("SELL|M5|2026-10-06 19:00:00+00:00", text)
    # 0 % at E (the key's time, 07/10 02:00 Thai), 100 % at S (the run's start, 06/10 23:55 Thai)
    assert (l0, h100) == (4184.25, 4154.21) and t0 == pd.Timestamp("2026-10-06 19:00", tz="UTC")
    assert t100 == pd.Timestamp("2026-10-06 16:55", tz="UTC") and day.is_fade(text)
    assert not day.is_fade("L0 4000.00@05/10 10:00 H100 4100.00@05/10 12:00 leg 100.00")
    lv = day.fib_prices(l0, h100)
    assert lv[0.0] == 4184.25 and lv[1.0] == 4154.21 and lv[1.618] == pytest.approx(4184.25 - 1.618 * 30.04)


def test_walk_day_lists_times_outside_the_windows_as_all_day(monkeypatch) -> None:
    """Rule 0: with ``windows`` off the day is walked at its 288 times, those outside the three windows under
    the name "all day"; with it on only the windows."""
    calls: list[pd.Timestamp] = []

    def fake(frames, now, p, used=frozenset(), pending=False, windowed=None):
        calls.append(now)
        log = dict.fromkeys(bot.LOG_COLUMNS, "")
        log["reason"] = "warm-up"
        return bot.Result(log)

    monkeypatch.setattr(bot, "cut", lambda full, now: {})
    monkeypatch.setattr(bot, "decide", fake)
    rows = day.walk_day("2026-04-07", bot.Params(), {})["rows"]
    assert len(calls) == len(rows) == 288
    names = [r["window"] for r in rows]
    assert names.count("all day") == 288 - 93
    assert {n for n in names if n != "all day"} == {"Asia", "London", "New York"}
    assert rows[0]["window"] == "all day" and rows[0]["close"] == pd.Timestamp("2026-04-06 17:00", tz="UTC")
    calls.clear()
    rows = day.walk_day("2026-04-07", bot.Params(windows="on"), {})["rows"]
    assert len(rows) == 93 and "all day" not in {r["window"] for r in rows}


def test_split_base_takes_market_set_and_db_out_of_the_overrides() -> None:
    base, rest = day.split_base(["fib_entry=0.382", "set=r3_off", "market=XAUUSD", "db=x.db", "min_r=1"])
    assert base == {"market": "XAUUSD", "set": "r3_off", "db": "x.db"} and rest == [
        "fib_entry=0.382",
        "min_r=1",
    ]
    base, rest = day.split_base([])
    assert base == {"market": "XAUUSD", "set": "default", "db": str(bot.CONFIG_DB)} and rest == []


def test_the_base_is_the_stored_set_with_the_overrides_on_top(tmp_path: Path) -> None:
    base = {"market": "XAUUSD", "set": "default", "db": str(seeded_db(tmp_path))}
    p, version = day.resolve_params(base, {})
    assert p == bot.Params(min_r=1.5) and version == 22
    p, version = day.resolve_params(base, {"fib_entry": 0.618, "early_leg": "off"})
    assert (p.min_r, p.fib_entry, p.early_leg) == (1.5, 0.618, "off") and version == 22
    line = day.config_line(base, version, {"fib_entry": 0.618, "early_leg": "off"})
    assert line == "config=XAUUSD/default@v22; overrides: fib_entry=0.618 early_leg=off"
    assert day.config_line(base, 22, {}) == "config=XAUUSD/default@v22; overrides: none"
    with pytest.raises(SystemExit, match="bad override"):
        day.resolve_params(base, {"fib_early": 0.1})  # a combination Params refuses
    with pytest.raises(SystemExit, match="no bars for EURUSD"):
        day.resolve_params({**base, "market": "EURUSD"}, {})
    with pytest.raises(SystemExit, match="seed --market XAUUSD --set nope"):
        day.resolve_params({**base, "set": "nope"}, {})


def test_main_reads_the_set_names_it_and_checks_the_market_before_bars(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    db = str(seeded_db(tmp_path))
    monkeypatch.setattr(bot, "load_frames", lambda: pytest.fail("bars loaded"))
    with pytest.raises(SystemExit, match="no bars for EURUSD"):
        day.main(["2026-10-07", f"db={db}", "market=EURUSD"])
    seen: dict = {}
    monkeypatch.setattr(bot, "load_frames", lambda: {"M5": None})
    monkeypatch.setattr(day, "draw", lambda d, p, o, full, config="": seen.update(p=p, o=o, c=config))
    day.main(["2026-10-07", f"db={db}", "fib_entry=0.618", "min_r=3"])
    assert seen["p"] == bot.Params(min_r=3.0, fib_entry=0.618) and seen["o"] == {
        "fib_entry": 0.618,
        "min_r": 3.0,
    }
    assert seen["c"] == "config=XAUUSD/default@v22; overrides: fib_entry=0.618 min_r=3.0"
    assert seen["c"] in capsys.readouterr().out
