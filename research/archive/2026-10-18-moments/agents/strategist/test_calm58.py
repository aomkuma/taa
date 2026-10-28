"""Hand-worked tests of row 58 (calm58.py): the LEARN / TEST guard, the ASIA_FADE event, the choice."""

import json

import numpy as np
import pandas as pd
import pytest

import calm58 as C

MIN = 60 * 10**9


def test_test_needs_the_frozen_file(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "FROZEN", tmp_path / "none.json")
    with pytest.raises(RuntimeError):
        C.period_of("test")
    assert C.period_of("learn") == C.LEARN
    (tmp_path / "f.json").write_text("{}")
    monkeypatch.setattr(C, "FROZEN", tmp_path / "f.json")
    assert C.period_of("test") == C.TEST
    with pytest.raises(ValueError):
        C.period_of("exam")


def test_ticks_never_at_or_after_the_phase_end(monkeypatch):
    calls = []
    monkeypatch.setattr(C, "TICKS", type("P", (), {"__truediv__": lambda s, f: calls.append(f) or s,
                                                     "exists": lambda s: False})())
    assert C.ticks(pd.Timestamp("2023-10-01", tz="UTC"), C.LEARN[1]) is None
    assert calls == []  # refused before any path is built
    C.ticks(pd.Timestamp("2023-09-29", tz="UTC"), C.LEARN[1])
    assert calls == ["2023-09-29.parquet"]


def test_asia_event_sell_after_close_back_inside():
    o = np.arange(5) * MIN
    hi = np.array([10.0, 12.0, 13.0, 11.5, 9.0])
    lo = np.array([9.0, 10.5, 11.0, 10.0, 8.0])
    cl = np.array([9.5, 11.8, 12.5, 10.5, 8.5])
    # Asia high 11, low 5: bar 1 trades above (12) and closes above; bar 2 extends to 13; bar 3 closes back inside (10.5)
    # -> a sell decided at bar 3's close (3 min + 1 min), the excursion's extreme 13
    assert C.asia_event(o, hi, lo, cl, 11.0, 5.0, 0, 5 * MIN) == (4 * MIN, -1, 13.0)


def test_asia_event_same_bar_and_buy_and_hour_limit():
    o = np.arange(3) * MIN
    hi = np.array([10.0, 10.0, 10.0])
    lo = np.array([6.0, 4.0, 6.0])
    cl = np.array([7.0, 5.5, 7.0])
    # bar 1 trades below 5 and closes back inside (5.5) on the same bar -> a buy, extreme 4
    assert C.asia_event(o, hi, lo, cl, 11.0, 5.0, 0, 3 * MIN) == (2 * MIN, 1, 4.0)
    # the hour ends before bar 1 -> nothing
    assert C.asia_event(o, hi, lo, cl, 11.0, 5.0, 0, 1 * MIN) is None
    # a bar that only closes outside never triggers
    assert C.asia_event(o[:1], np.array([12.0]), np.array([10.0]), np.array([11.5]), 11.0, 5.0, 0, MIN) is None


def test_choose_best_calm_learn_r():
    T = pd.DataFrame({"cand": ["ORB_FADE"] * 4, "setting": ["i stop d, target d", "i stop d, target d",
                                                            "ii stop d, target 0.5 d", "ii stop d, target 0.5 d"],
                      "atr": [5.0, 13.0, 5.0, 5.0], "R": [0.1, 9.0, 0.3, 0.3]})
    # setting i's calm R is +0.1 (the 13-ATR trade is not calm); ii's +0.3 -> ii
    assert C.choose(T)["ORB_FADE"] == "ii stop d, target 0.5 d"


def test_settings_count():
    assert sum(len(v) for v in C.SETTINGS.values()) == 15
    assert json.dumps(C.SETTINGS)  # serialisable names
