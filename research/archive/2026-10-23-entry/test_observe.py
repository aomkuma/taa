"""Hand-worked tests for observe.score() - the hour scored against the reading before it.

    .venv/Scripts/python -m pytest research/2026-10-23-entry/test_observe.py -q
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import observe as ob  # noqa: E402

T0 = pd.Timestamp("2026-10-21T06:00", tz="UTC")


def bars(rows: list[tuple[float, float, float]]) -> pd.DataFrame:
    """M1 bars from T0, one a minute: (high, low, close)."""
    idx = [T0 + pd.Timedelta(minutes=i) for i in range(len(rows))]
    return pd.DataFrame({"high": [r[0] for r in rows], "low": [r[1] for r in rows], "close": [r[2] for r in rows]}, index=idx)


def prev(rhythm: int, price: float = 100.0, atr: float = 4.0) -> dict:
    return {"as_of": T0.isoformat(), "price": price, "M15_rhythm": rhythm, "H1_atr": atr, "line_above": 106.0,
            "line_below": 95.0}


def test_down_rhythm_held_with_and_against_in_usd():
    # read DOWN at 100: high 101.5 (against 1.5), low 97 (with 3.0) -> held; no line reached (106 / 95)
    m1 = bars([(100.5, 99.0, 99.5), (101.5, 99.2, 101.0), (100.0, 97.0, 97.5)])
    s = ob.score(prev(-1), m1, T0 + pd.Timedelta(minutes=3))
    assert (s["bars"], s["high"], s["low"], s["last"]) == (3, 101.5, 97.0, 97.5)
    assert s["with"] == pytest.approx(3.0)
    assert s["against"] == pytest.approx(1.5)
    assert s["rhythm_held"] is True
    assert s["first_line"] == "neither"
    assert s["surprises"] == []


def test_against_the_rhythm_by_one_atr_is_a_surprise():
    # read UP at 100 (ATR 4): low 96 = 4.0 against (exactly 1 ATR -> flagged), high 101 = 1.0 with -> not held
    m1 = bars([(101.0, 99.0, 99.0), (99.5, 96.0, 96.5)])
    s = ob.score(prev(1), m1, T0 + pd.Timedelta(minutes=2))
    assert s["rhythm_held"] is False
    assert len(s["surprises"]) == 1
    assert "AGAINST the M15 rhythm (up)" in s["surprises"][0]


def test_just_under_one_atr_against_is_not_a_surprise():
    m1 = bars([(101.0, 96.1, 96.5)])
    assert ob.score(prev(1), m1, T0 + pd.Timedelta(minutes=1))["surprises"] == []


def test_a_run_with_no_rhythm_and_a_big_hour():
    # no rhythm read, ATR 4: up 6.0 = 1.5 ATR -> a run surprise; range 8.5 = 2.1 ATR -> a big hour too
    m1 = bars([(101.0, 97.5, 100.5), (106.0, 100.0, 105.5)])
    s = ob.score(prev(0), m1, T0 + pd.Timedelta(minutes=2))
    assert "rhythm_held" not in s
    assert len(s["surprises"]) == 2
    assert "ran up 6.0 USD (1.5 H1 ATR) with NO M15 rhythm" in s["surprises"][0]
    assert "range 8.5 USD = 2.1 H1 ATR" in s["surprises"][1]
    assert s["first_line"] == "above 106.00"  # the high touched the line above exactly


def test_first_line_is_the_earliest_bar_and_both_in_one_bar():
    m1 = bars([(100.0, 94.9, 95.5), (106.5, 95.0, 106.0)])
    assert ob.score(prev(0), m1, T0 + pd.Timedelta(minutes=2))["first_line"] == "below 95.00"
    m1 = bars([(106.0, 95.0, 100.0)])
    assert ob.score(prev(0), m1, T0 + pd.Timedelta(minutes=1))["first_line"] == "both in one bar"


def test_bars_at_or_after_as_of_are_not_scored():
    # the last bar opens at as_of -> outside the hour (no look-ahead into the next reading's hour)
    m1 = bars([(100.5, 99.5, 100.0), (120.0, 80.0, 100.0)])
    s = ob.score(prev(-1), m1, T0 + pd.Timedelta(minutes=1))
    assert (s["bars"], s["high"], s["low"]) == (1, 100.5, 99.5)
    assert ob.score(prev(-1), m1, T0)["bars"] == 0


def test_scorecard_counts_only_hours_with_a_rhythm():
    rows = [{"score": {"rhythm_held": True, "with": 3.0, "against": 1.0}},
            {"score": {"bars": 5}},
            {"score": {"rhythm_held": False, "with": 1.0, "against": 5.0}}]
    assert ob.scorecard(rows) == ("the last 2 hours read with an M15 rhythm: it held 1; mean move with it 2.0 USD, "
                                  "against it 3.0 USD")
    assert ob.scorecard([{}]) == "no hour with an M15 rhythm scored yet"


def test_a_tie_or_a_little_more_against_is_not_held():
    # read DOWN at 100: high 101.5 / low 98.5 -> with 1.5 = against 1.5 -> not held (it must go further WITH it)
    m1 = bars([(101.5, 98.5, 100.0)])
    assert ob.score(prev(-1), m1, T0 + pd.Timedelta(minutes=1))["rhythm_held"] is False
    # with 1.0, against 1.5 -> not held
    m1 = bars([(101.5, 99.0, 100.0)])
    assert ob.score(prev(-1), m1, T0 + pd.Timedelta(minutes=1))["rhythm_held"] is False


def test_a_no_rhythm_move_under_one_and_a_half_atr_is_not_a_surprise():
    # no rhythm, ATR 4: up 5.9 = 1.48 ATR, range 6.9 = 1.7 ATR -> nothing flagged
    m1 = bars([(105.9, 99.0, 105.0)])
    assert ob.score(prev(0), m1, T0 + pd.Timedelta(minutes=1))["surprises"] == []


def _row(as_of_utc, price, atr, behaviors, score=None):
    r = {"as_of": pd.Timestamp(as_of_utc, tz="UTC").isoformat(), "price": price, "H1_atr": atr, "behaviors": behaviors}
    if score is not None:
        r["score"] = score
    return r


def test_behavior_table_pairs_each_reading_with_the_next_hour():
    rows = [
        _row("2026-10-21T08:00", 100.0, 10.0, ["sweep", "chop"]),                      # 15:00 Thai
        _row("2026-10-21T09:00", 104.0, 8.0, ["sweep"], {"bars": 60, "high": 106.0, "low": 95.0, "last": 104.0}),
        _row("2026-10-21T10:00", 103.0, 8.0, ["chop"], {"bars": 60, "high": 108.0, "low": 100.0, "last": 103.0}),
        _row("2026-10-21T11:00", 99.0, 8.0, ["chop"], {"bars": 0}),                   # the hour had no bars
    ]
    text = ob.behavior_table(rows)
    # sweep: 15:00 -> up (106-100)/10 = 0.6, down (100-95)/10 = 0.5, net +0.4; 16:00 -> up (108-104)/8 = 0.5,
    # down (104-100)/8 = 0.5, net (103-104)/8 = -0.125 -> means 0.55 / 0.50 / +0.1375, net up 1 of 2
    assert "| sweep | 2 | 15h x1, 16h x1 | 0.55 | 0.50 | +0.14 | 1 / 2 |" in text
    # chop: only 15:00 is scored (17:00's next hour had no bars; 18:00 has no row after it)
    assert "| chop | 1 | 15h x1 | 0.60 | 0.50 | +0.40 | 1 / 1 |" in text
    assert text.index("| sweep |") < text.index("| chop |")  # the most seen first


def test_behavior_table_before_any_score():
    assert "(none scored yet)" in ob.behavior_table([_row("2026-10-21T08:00", 100.0, 10.0, ["sweep"])])


def test_behavior_table_a_flat_hour_is_not_net_up():
    rows = [_row("2026-10-21T08:00", 100.0, 10.0, ["grind"]),
            _row("2026-10-21T09:00", 100.0, 10.0, [], {"bars": 60, "high": 101.0, "low": 99.0, "last": 100.0})]
    assert "| grind | 1 | 15h x1 | 0.10 | 0.10 | +0.00 | 0 / 1 |" in ob.behavior_table(rows)


def _minutes(a, b):
    return pd.date_range(pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC"), freq="1min", inclusive="left")


def _ts(x):
    return pd.Timestamp(x, tz="UTC")


def test_missed_hours_after_the_pc_slept():
    # the last reading 19:05 Thai (12:05 UTC), woke at 21:29 Thai: 20:05 and 21:05 Thai were missed
    bars = _minutes("2026-10-23T10:00", "2026-10-23T14:29")
    got = ob.missed_hours(_ts("2026-10-23T12:05"), _ts("2026-10-23T14:29"), bars)
    assert got == [_ts("2026-10-23T13:05"), _ts("2026-10-23T14:05")]


def test_no_missed_hours_on_schedule():
    bars = _minutes("2026-10-23T10:00", "2026-10-23T14:05")
    assert ob.missed_hours(_ts("2026-10-23T13:05"), _ts("2026-10-23T14:05"), bars) == []
    assert ob.missed_hours(None, _ts("2026-10-23T14:05"), bars) == []


def test_missed_hours_after_an_off_schedule_reading():
    # the last reading at 21:29 Thai (14:29 UTC): its own hour's 14:05 is behind it; next 15:05, 16:05
    bars = _minutes("2026-10-23T14:00", "2026-10-23T16:40")
    got = ob.missed_hours(_ts("2026-10-23T14:29"), _ts("2026-10-23T16:40"), bars)
    assert got == [_ts("2026-10-23T15:05"), _ts("2026-10-23T16:05")]


def test_a_closed_market_hour_is_not_back_filled():
    # no bars between 13:05 and 14:05 UTC: the 14:05 mark is skipped, 13:05 and 15:05 are kept
    bars = _minutes("2026-10-23T12:00", "2026-10-23T13:05").append(_minutes("2026-10-23T14:30", "2026-10-23T15:40"))
    got = ob.missed_hours(_ts("2026-10-23T12:05"), _ts("2026-10-23T15:40"), bars)
    assert got == [_ts("2026-10-23T13:05"), _ts("2026-10-23T15:05")]


def test_missed_hours_are_capped():
    bars = _minutes("2026-10-01T00:00", "2026-10-10T00:00")
    assert len(ob.missed_hours(_ts("2026-10-01T00:05"), _ts("2026-10-10T00:00"), bars)) == 72
