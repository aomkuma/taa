"""Tests for the pure helpers of eye/research/bot_view.py (the bot's MT5-style chart at a moment)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

view = importlib.import_module("eye.research.bot_view")
bot = importlib.import_module("eye.bot2e")


def seeded_db(tmp_path: Path) -> Path:
    cfg = importlib.import_module("eye.bot_config")
    db = tmp_path / "cfg" / "bot_config.db"
    at = pd.Timestamp("2026-10-31 10:00", tz="UTC").to_pydatetime()
    cfg.seed(db, "XAUUSD", "default", "t", at)
    cfg.set_values(db, "XAUUSD", "default", "t", at, "n", {"min_r": "1.5"})
    return db


SwingKind = importlib.import_module("app.indicators.price_action").SwingKind


def test_parse_args_defaults_and_overrides() -> None:
    got = view.parse_args(["2026-10-07", "07:00"])
    assert (got["tf"], got["before"], got["after"], got["overrides"]) == ("M5", 8.0, 8.0, {})
    got = view.parse_args(
        ["2026-10-07", "07:00", "tf=M15", "hours_before=4", "hours_after=2", "fib_entry=0.382"]
    )
    assert (got["tf"], got["before"], got["after"], got["overrides"]) == (
        "M15",
        4.0,
        2.0,
        {"fib_entry": 0.382},
    )
    for bad in (["2026-10-07"], ["2026-10-07", "07:00", "tf=H1"], ["2026-10-07", "07:00", "nonsense=1"]):
        with pytest.raises(SystemExit):
            view.parse_args(bad)


def test_view_bounds_are_thai_times_in_utc() -> None:
    now, start, end = view.view_bounds("2026-10-07", "07:00", 8, 6)
    assert now == pd.Timestamp("2026-10-07 00:00", tz="UTC")
    assert start == pd.Timestamp("2026-10-06 16:00", tz="UTC") and end == pd.Timestamp(
        "2026-10-07 06:00", tz="UTC"
    )


def test_ladder_levels_and_mt5_labels_buy_and_sell() -> None:
    lv = view.ladder(4000.0, 4100.0)  # a BUY: 0 % at the low, 100 % at the high
    assert list(lv) == [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]
    assert lv[0.0] == 4000.0 and lv[1.0] == 4100.0 and lv[0.618] == pytest.approx(4061.8)
    assert lv[1.618] == pytest.approx(4161.8) and lv[1.272] == pytest.approx(4127.2)
    sl = view.ladder(4100.0, 4000.0)  # a SELL: L0 the top, H100 the low: the mirror
    assert sl[0.0] == 4100.0 and sl[1.0] == 4000.0 and sl[0.618] == pytest.approx(4038.2)
    assert sl[1.618] == pytest.approx(3938.2)
    assert view.level_label(0.618, 4155.2) == "61.8 (4155.20)"
    assert (
        view.level_label(0.0, 4000.0) == "0 (4000.00)"
        and view.level_label(1.618, 4161.8) == "161.8 (4161.80)"
    )


def test_moving_point_follows_the_last_fixed_pivot() -> None:
    df = pd.DataFrame({"high": [10.0, 12.0, 11.0, 13.0, 12.5], "low": [9.0, 10.0, 8.0, 9.5, 9.0]})
    low = SimpleNamespace(kind=SwingKind.LOW, pivot_pos=0, price=9.0)
    assert view.moving_point(df, low) == (3, 13.0)  # after a LOW: the highest high since
    high = SimpleNamespace(kind=SwingKind.HIGH, pivot_pos=1, price=12.0)
    assert view.moving_point(df, high) == (2, 8.0)  # after a HIGH: the lowest low since
    last = SimpleNamespace(kind=SwingKind.LOW, pivot_pos=4, price=9.0)
    assert view.moving_point(df, last) == (4, 9.0)  # nothing after the pivot: the pivot itself


def leg_side(sign: int, look_lo: int = 0):
    """A BUY in the view: L0 4000 (a fixed LOW at 40), H100 4100 (the latest fixed HIGH at 60)."""
    pv = [bot.VPivot(True, 4000.0, 40), bot.VPivot(False, 4100.0, 60)]
    times = pd.date_range("2026-10-05", periods=90, freq="5min", tz="UTC")
    return SimpleNamespace(pv=pv, hi_v=np.full(90, 4090.0), lo_v=np.full(90, 4050.0), look_lo=look_lo,
                           sign=sign, times=times, h4="up" if sign > 0 else "down",
                           side="BUY" if sign > 0 else "SELL")  # fmt: skip


FIXED = bot.Params(early_leg="off")


def test_leg_geometry_buy_sell_and_the_setup_look() -> None:
    d = leg_side(1)
    t0, p0, t100, p100, early, key, fade = view.leg_geometry(d, FIXED)
    assert (
        (p0, p100, early, fade) == (4000.0, 4100.0, False, False)
        and t0 == d.times[40]
        and t100 == d.times[60]
    )
    assert key == d.times[40]  # one leg per start
    s0, sp0, _, sp100, *_ = view.leg_geometry(leg_side(-1), FIXED)  # the same view data as a SELL: negated
    assert (sp0, sp100) == (-4000.0, -4100.0) and s0 == d.times[40]
    assert view.leg_geometry(leg_side(1, look_lo=41), FIXED) is None  # L0 before the look: no leg
    assert view.leg_geometry(leg_side(1, look_lo=61), FIXED) is None  # H100 before it
    assert view.leg_geometry(leg_side(1, look_lo=40), FIXED) is not None


def test_leg_geometry_early_leg_is_marked_and_keyed_by_its_start() -> None:
    n = 90
    hi, lo = np.full(n, 4010.0), np.full(n, 4005.0)
    hi[40] = 4060.0  # a rally from Lf 4000 past 4000 + 0.382 x (4100 - 4000) = 4038.2
    d = leg_side(1)
    d.pv = [bot.VPivot(False, 4100.0, 20), bot.VPivot(True, 4000.0, 30)]
    d.hi_v, d.lo_v = hi, lo
    t0, p0, t100, p100, early, key, _ = view.leg_geometry(d, bot.Params(early_leg=0.382))
    assert early and (p0, p100) == (4000.0, 4060.0) and t0 == d.times[30] and t100 == d.times[40]
    assert key == d.times[30]  # the early leg and the fixed leg after it share the start
    off = view.leg_geometry(d, FIXED)  # off: the fixed leg of the HIGH 4100 has no low before it
    assert off is None


def test_side_sentence_leg_order_and_reasons_in_plain_words() -> None:
    t = pd.Timestamp("2026-10-06 16:55", tz="UTC")
    geo = (t, 4154.21, t, 4170.48, False)
    ordered = SimpleNamespace(
        reason="order written", setup=SimpleNamespace(order=4163.1, stop=4150.0, target=4190.0, r=2.1)
    )
    text = view.side_sentence("BUY", geo, ordered, "UP")
    assert "L0 4154.21 (06/10 23:55) -> H100 4170.48" in text and "M5 trend UP (a BUY needs UP)" in text
    assert "ORDER 4163.10, SL 4150.00, TP 4190.00, R 2.10" in text
    none = SimpleNamespace(reason="fib: leg has run (100 % traded)", setup=None)
    assert view.side_sentence("SELL", geo, none, "UP").endswith("no order: leg has run (rule 10)")
    assert "M5 trend UP (a SELL needs DOWN)" in view.side_sentence("SELL", geo, none, "UP")
    noleg = SimpleNamespace(reason="fib: no live leg", setup=None)
    assert view.side_sentence("SELL", None, noleg, "none").startswith("SELL: no leg (no live leg)")


def test_first_seen_keeps_the_first_moment_of_each_side_and_leg() -> None:
    ev = [
        (1, "BUY", "a"), (2, "BUY", "a"), (2, "SELL", "a"),  # the same key on the other side is new
        (3, "BUY", "b"), (4, "BUY", "a"), (5, "SELL", "a"), (6, "SELL", "c"),
    ]  # fmt: skip
    assert view.first_seen(ev) == [(1, "BUY", "a"), (2, "SELL", "a"), (3, "BUY", "b"), (6, "SELL", "c")]
    assert view.first_seen([]) == []


def test_parse_args_legs_mode_has_no_time() -> None:
    got = view.parse_args(["2026-10-07", "legs", "tf=M15"])
    assert got["hhmm"] is None and got["tf"] == "M15" and got["date"] == "2026-10-07"


def test_leg_geometry_fade_leg_has_0_percent_at_e_and_100_percent_at_s() -> None:
    n = 90
    times = pd.date_range("2026-10-05", periods=n, freq="5min", tz="UTC")
    pv = [bot.VPivot(True, 4050.0, 20), bot.VPivot(False, 4100.0, 40), bot.VPivot(True, 4000.0, 60)]
    d = SimpleNamespace(pv=pv, hi_v=np.full(n, 4060.0), lo_v=np.full(n, 4010.0), look_lo=0, sign=1, times=times,
                        h4="none", side="BUY")  # fmt: skip
    t0, p0, t100, p100, early, key, fade = view.leg_geometry(d, bot.Params())
    assert fade and not early and (p0, p100) == (4000.0, 4100.0)  # 0 % at E (the run's end), 100 % at S
    assert t0 == times[60] and t100 == times[40] and key == times[60]
    lv = view.ladder(p0, p100)
    assert lv[0.0] == 4000.0 and lv[1.0] == 4100.0 and lv[1.272] == pytest.approx(4127.2)
    assert lv[1.618] == pytest.approx(4161.8)  # beyond S, the way the run came back
    sentence = view.side_sentence(
        "BUY",
        (t0, p0, t100, p100, early, key, fade),
        SimpleNamespace(reason="order written", setup=None),
        "UP",
    )
    assert "fade leg S 4100.00" in sentence and "-> E 4000.00" in sentence
    # H4 clear and against this side: no leg for it
    against = SimpleNamespace(**{**vars(d), "h4": "down"})
    assert view.leg_geometry(against, bot.Params()) is None


def test_retest_sentence_order_and_reason() -> None:
    ordered = SimpleNamespace(reason="order written",
                              setup=SimpleNamespace(order=4161.42, stop=4170.39, target=4139.09, step="2", r=2.46))  # fmt: skip
    text = view.retest_sentence("SELL", ordered)
    assert "break and retest: ORDER limit 4161.42, SL 4170.39, TP 4139.09 (2), R 2.46" in text
    refused = SimpleNamespace(reason="fib: no M5 trend of its side", setup=None)
    assert view.retest_sentence("SELL", refused).endswith("no order: no M5 trend of its side")


def test_parse_args_takes_the_base_set() -> None:
    got = view.parse_args(["2026-10-07", "07:00"])
    assert got["base"] == {"market": "XAUUSD", "set": "default", "db": str(bot.CONFIG_DB)}
    got = view.parse_args(["2026-10-07", "legs", "set=r3_off", "market=EURUSD", "db=x.db", "min_r=1"])
    assert got["base"] == {"market": "EURUSD", "set": "r3_off", "db": "x.db"} and got["overrides"] == {
        "min_r": 1.0
    }


def test_params_are_the_stored_set_with_tf_and_overrides_on_top(tmp_path: Path) -> None:
    db = str(seeded_db(tmp_path))
    args = view.parse_args(["2026-10-07", "07:00", "tf=M15", f"db={db}", "fade_min=off"])
    p, version = view.params_of(args)
    assert (p.fib_tf, p.fade_min, p.min_r, version) == ("M15", "off", 1.5, 22)
    p, _ = view.params_of(view.parse_args(["2026-10-07", "07:00", f"db={db}", "fib_tf=M15"]))
    assert p.fib_tf == "M15"  # an explicit fib_tf override wins over tf


def test_another_market_stops_before_bars_load(tmp_path: Path, monkeypatch) -> None:
    db = str(seeded_db(tmp_path))
    monkeypatch.setattr(bot, "load_frames", lambda: pytest.fail("bars loaded"))
    one = view.parse_args(["2026-10-07", "07:00", f"db={db}", "market=EURUSD"])
    with pytest.raises(SystemExit, match="no bars for EURUSD"):
        view.draw(one)
    legs = view.parse_args(["2026-10-07", "legs", f"db={db}", "market=EURUSD"])
    with pytest.raises(SystemExit, match="no bars for EURUSD"):
        view.legs_mode(legs)
    missing = view.parse_args(["2026-10-07", "07:00", f"db={db}", "set=nope"])
    with pytest.raises(SystemExit, match="seed --market XAUUSD --set nope"):
        view.draw(missing)


def test_the_header_lists_a_tf_that_changes_the_sets_fib_tf(tmp_path: Path) -> None:
    db = str(seeded_db(tmp_path))
    _, _, line = view.config_of(view.parse_args(["2026-10-07", "07:00", "tf=M15", f"db={db}"]))
    assert line == "config=XAUUSD/default@v22; overrides: fib_tf=M15"
    _, _, line = view.config_of(view.parse_args(["2026-10-07", "07:00", "tf=M5", f"db={db}"]))
    assert line == "config=XAUUSD/default@v22; overrides: none"  # tf equal to the set's fib_tf adds nothing
    _, _, line = view.config_of(view.parse_args(["2026-10-07", "07:00", f"db={db}", "min_r=3"]))
    assert line.endswith("overrides: min_r=3.0")
    _, _, line = view.config_of(view.parse_args(["2026-10-07", "07:00", "tf=M15", f"db={db}", "fib_tf=M5"]))
    assert line.endswith("overrides: fib_tf=M5")  # an explicit fib_tf override is shown as given
    p, _, line = view.config_of(view.parse_args(["2026-10-07", "07:00", "tf=M15", f"db={db}", "min_r=3"]))
    assert p.fib_tf == "M15" and line.endswith("overrides: fib_tf=M15 min_r=3.0")


def test_each_tool_reads_the_set_once_per_drawing(tmp_path: Path, monkeypatch) -> None:
    cfg = importlib.import_module("eye.bot_config")
    day = importlib.import_module("eye.research.bot_read_day")
    db = str(seeded_db(tmp_path))
    calls: list[tuple] = []
    real = cfg.load_params

    def counting(*a, **k):
        calls.append(a)
        return real(*a, **k)

    monkeypatch.setattr(cfg, "load_params", counting)
    view.config_of(view.parse_args(["2026-10-07", "07:00", "tf=M15", f"db={db}", "min_r=3"]))
    assert len(calls) == 1
    calls.clear()
    base, rest = day.split_base([f"db={db}", "min_r=3"])
    day.resolve_params(base, day.parse_overrides(rest))
    assert len(calls) == 1


def test_a_legs_run_reads_the_set_once_for_all_its_images(tmp_path: Path, monkeypatch) -> None:
    cfg = importlib.import_module("eye.bot_config")
    db = str(seeded_db(tmp_path))
    calls: list[tuple] = []
    real = cfg.load_params
    monkeypatch.setattr(cfg, "load_params", lambda *a, **k: (calls.append(a), real(*a, **k))[1])
    t = [pd.Timestamp(f"2026-10-07 0{h}:00", tz="UTC") for h in (1, 2, 3)]
    seen: list = []
    monkeypatch.setattr(bot, "load_frames", lambda: {})
    monkeypatch.setattr(view, "new_leg_moments", lambda date, p, full: [(x, "BUY", None) for x in t])
    monkeypatch.setattr(view, "summary_line", lambda full, p, nu, side: "line")

    def fake_draw(one, full=None, only_side=None, resolved=None):
        seen.append(resolved)
        return Path("x.png")

    monkeypatch.setattr(view, "draw", fake_draw)
    view.legs_mode(view.parse_args(["2026-10-07", "legs", "tf=M15", f"db={db}"]))
    assert len(calls) == 1 and len(seen) == 3
    assert all(r is seen[0] and r[2].endswith("overrides: fib_tf=M15") for r in seen)
