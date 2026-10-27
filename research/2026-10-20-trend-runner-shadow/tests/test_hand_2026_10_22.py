# ruff: noqa: S101, PT018
"""Hand-worked tests for the shadow TR1 fill and RUNNER (= SPLIT) outcome (audit 2026-10-22).

Common trade: BUY entry 100.00 at T, initial stop 99.00 (1R = 1.00); marks are bids (ask = bid + 0.03).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shadow.detector import Detection, atr, fill_and_risk
from shadow.outcomes import StructureEvent, run_exit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "2026-10-18-moments" / "agents" / "precursors"))
from foundation import atr as mt5_atr

T = pd.Timestamp("2025-11-05 10:00", tz="UTC")


def q(*rows):
    """(minutes after T, bid) rows."""
    return pd.DataFrame(
        {
            "time_utc": [T + pd.Timedelta(minutes=m) for m, _ in rows],
            "bid": [b for _, b in rows],
            "ask": [b + 0.03 for _, b in rows],
        }
    )


def ev(minutes, tf, stop):
    return StructureEvent(
        T + pd.Timedelta(minutes=minutes), tf, T + pd.Timedelta(minutes=minutes - 2), stop, stop
    )


def runner(ticks, events=(), family="RUNNER"):
    return run_exit(family, ticks, 1, 100.00, 99.00, T, list(events))


def test_atr_is_mt5():
    rng = np.random.default_rng(7)
    c = 100 + rng.normal(0, 1, 60).cumsum()
    h, lo = c + rng.uniform(0, 1, 60), c - rng.uniform(0, 1, 60)
    assert np.allclose(atr(h, lo, c), mt5_atr(h, lo, c), equal_nan=True)


def test_stop_fills_at_the_worse_quote():
    r = runner(q((0, 99.97), (1, 99.50), (2, 98.80)))
    assert r.reason.value == "STOP" and r.exit_price == pytest.approx(98.80)
    assert r.r == pytest.approx(-1.2) and not r.partial_taken


def test_partial_then_stop_at_the_initial_stop():
    # 101.00 = +1R books 1/3; then 98.90: R = 1/3 + 2/3 x (-1.10) = -0.40
    r = runner(q((0, 99.97), (1, 101.00), (2, 98.90)))
    assert r.partial_taken and r.r == pytest.approx(-0.40)


def test_m5_trail_after_partial():
    # M5 stop 100.50 available at T+5; bid 100.40 at T+6 -> exit 100.40: R = 1/3 + 2/3 x 0.40 = 0.60
    r = runner(q((0, 99.97), (1, 101.20), (6, 100.40)), [ev(5, "M5", 100.50)])
    assert r.final_stop == pytest.approx(100.50) and r.r == pytest.approx(0.60)


def test_trail_never_loosens():
    r = runner(q((0, 99.97), (11, 100.30)), [ev(5, "M5", 100.50), ev(10, "M5", 100.20)])
    assert r.reason.value == "STOP" and r.final_stop == pytest.approx(100.50)


def test_graduation_at_3r_switches_to_m15_confirmed_afterwards():
    # 103.00 = +3R at T+2 -> graduated. M5 101.50 (T+5) is ignored, so 101.45 at T+6 is no exit; M15 99.50
    # confirmed at T+1 (before graduation) is ignored; M15 102.00 (T+15) applies; bid 101.90 at T+16 exits:
    # R = 1/3 + 2/3 x 1.90 = 1.60
    events = [ev(1, "M15", 99.50), ev(5, "M5", 101.50), ev(15, "M15", 102.00)]
    r = runner(q((0, 99.97), (2, 103.00), (6, 101.45), (16, 101.90)), events)
    assert r.graduated and r.exit_time == T + pd.Timedelta(minutes=16)
    assert r.final_stop == pytest.approx(102.00) and r.r == pytest.approx(1.60)


def test_no_graduation_below_3r():
    # 102.50 = +2.5R (partial taken, not graduated); M5 101.50 at T+5 applies; 101.40 at T+6 exits:
    # R = 1/3 + 2/3 x 1.40 = 1.2667
    r = runner(q((0, 99.97), (1, 102.50), (6, 101.40)), [ev(5, "M5", 101.50)])
    assert not r.graduated and r.exit_time == T + pd.Timedelta(minutes=6)
    assert r.r == pytest.approx(1 / 3 + 2 / 3 * 1.40)


def test_time_exit_at_first_quote_at_or_after_8_hours():
    ticks = pd.concat([q((0, 99.97)), q((480, 100.50))], ignore_index=True)
    ticks.loc[2] = [T + pd.Timedelta(hours=8) - pd.Timedelta(milliseconds=1), 100.40, 100.43]
    ticks = ticks.sort_values("time_utc", kind="stable").reset_index(drop=True)
    r = runner(ticks)
    assert r.reason.value == "TIME" and r.exit_price == pytest.approx(100.50) and r.r == pytest.approx(0.50)


def test_censored_when_data_ends():
    assert runner(q((0, 99.97), (60, 99.50))).reason.value == "CENSORED"


def test_fast_target_books_the_declared_price_on_a_gap():
    r = runner(q((0, 99.97), (3, 102.50)), family="FAST")
    assert r.reason.value == "TARGET" and r.exit_price == pytest.approx(102.00) and r.r == pytest.approx(2.0)


def _detection(side, pivot, h1):
    return Detection("LONDON", T, 100.0, h1, side, T, T, pivot, T, 0.5, T + pd.Timedelta(minutes=10), 1.0)


def test_fill_buy_at_ask_with_spread_buffer():
    # first quote at/after the decision: bid 100.00 / ask 100.30 -> entry 100.30, spread 0.30,
    # buffer max(0.30, 0.10 x 1.0) = 0.30 -> stop 99.00 - 0.30 = 98.70, risk 1.60, risk/H = 1.60 / 10 = 0.16
    ticks = pd.DataFrame(
        {
            "time_utc": [
                T + pd.Timedelta(minutes=10) - pd.Timedelta(seconds=1),
                T + pd.Timedelta(minutes=10, milliseconds=200),
            ],
            "bid": [99.0, 100.0],
            "ask": [99.3, 100.3],
        }
    )
    f = fill_and_risk(_detection(1, 99.0, 10.0), ticks)
    assert f["entry"] == pytest.approx(100.30) and f["stop"] == pytest.approx(98.70)
    assert f["risk"] == pytest.approx(1.60) and f["risk_h1"] == pytest.approx(0.16)
    # SELL pivot 101.00: entry at the bid 100.00, stop 101.30, risk 1.30
    s = fill_and_risk(_detection(-1, 101.0, 10.0), ticks)
    assert s["entry"] == pytest.approx(100.00) and s["stop"] == pytest.approx(101.30)
    # H = 2.0 -> risk/H = 0.80 > 0.50 -> rejected
    assert fill_and_risk(_detection(1, 99.0, 2.0), ticks) is None
