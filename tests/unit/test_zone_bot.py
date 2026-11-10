"""eye/zone_bot.py, the first half of the run-zone setup: the step, the grids and the visits (eye/ZONE_RULES.md,
rules 2 - 5 and 10; acceptance cases 1, 2 and the visit parts of 3, 4 and 5).

Unit tests use constructed bars. The acceptance tests read the stored bars and run only with ``ZONE_ACCEPT=1``
(``ZONE_ACCEPT=1 pytest tests/unit/test_zone_bot.py -k accept``)."""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eye import zone_bot as zb  # noqa: E402
from eye.zone_config import ZoneParams  # noqa: E402

TH = "Asia/Bangkok"
P = ZoneParams(be_mode="off")  # the unit tests of rules 6 - 7 below are written without the break-even
PB = ZoneParams()  # the defaults: the break-even on
STORED = ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD"
ACCEPT = pytest.mark.skipif(
    os.environ.get("ZONE_ACCEPT") != "1" or not STORED.exists(),
    reason="acceptance: set ZONE_ACCEPT=1 and have data/history/FBS-Demo/XAUUSD",
)
OUT = ROOT / "eye" / "research" / "zone_reference_out"

Row = tuple[float, float, float, float]


def ts(s: str, tz: str = "UTC") -> pd.Timestamp:
    return pd.Timestamp(s, tz=tz)


# --- constructed bars -------------------------------------------------------------------------------------


def frame(start: str, minutes: int, rows: list[Row]) -> pd.DataFrame:
    t0 = ts(start)
    ot = [t0 + pd.Timedelta(minutes=minutes * k) for k in range(len(rows))]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df["open_time"] = ot
    df["close_time"] = [t + pd.Timedelta(minutes=minutes) for t in ot]
    df["time_server"] = [int(t.timestamp()) for t in ot]
    df["spread"] = 0
    return zb.check_frame(df, "constructed")


FILL: Row = (105.0, 105.5, 104.5, 105.0)  # a quiet bar well away from the lines 100 and 110 (range 1.0)
START = "2025-01-06 00:00"
N_FILL = 130


def make_bars(
    h1_rows: list[Row],
    exec_rows: dict[int, list[Row]] | None = None,
    exec_tf: str = "M15",
    filler: list[Row] | None = None,
) -> zb.Bars:
    """H1 = 130 filler bars + ``h1_rows``; the exec frame has 4 (M15) or 12 (M5) flat bars per hour, an hour
    replaced by ``exec_rows[h1 row]``; the other frames are flat (no pivot: sideways)."""
    rows = (filler or [FILL] * N_FILL) + list(h1_rows)
    h1 = frame(START, 60, rows)
    per_h = zb.PER_H[exec_tf]
    ex_rows: list[Row] = []
    for k in range(len(rows)):
        ex_rows += (exec_rows or {}).get(k, [FILL] * per_h)
    ex = frame(START, 60 // per_h, ex_rows)
    flat = frame(START, 240, [FILL] * 20)
    m15 = ex if exec_tf == "M15" else frame(START, 15, [FILL] * 20)
    m5 = ex if exec_tf == "M5" else frame(START, 5, [FILL] * 20)
    return zb.Bars(flat, flat, h1, m15, m5, 0.01)


def row_time(k: int) -> pd.Timestamp:
    return ts(START) + pd.Timedelta(hours=N_FILL + k)


GRID = zb.Grid(ts("2025-01-01 00:00"), 100.0, 10.0, "test")  # lines 90, 100, 110; Z = 1.3158
FAR = ts("2030-01-01")


def visits(
    bars: zb.Bars,
    grids: list[zb.Grid] | None = None,
    params: ZoneParams = P,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp = FAR,
) -> list[zb.Visit]:
    return zb.find_visits(bars, [GRID] if grids is None else grids, params, start or ts("2025-01-01"), end)


BUY_100: Row = (105.0, 105.5, 100.5, 105.0)  # open above, low within Z of 100: a BUY visit on 100
UP: Row = (107.0, 108.0, 105.0, 107.0)  # wholly 5 above 100 (low >= 105): re-arms the line 100
STRADDLE: Row = (103.0, 107.0, 96.0, 103.0)  # reaches both sides of 100: touches but does not re-arm
SELL_100: Row = (95.0, 99.0, 94.5, 95.0)


# --- data (rule 10) ---------------------------------------------------------------------------------------


def test_no_bars_for_another_market_before_loading(tmp_path: Path) -> None:
    with pytest.raises(zb.ZoneError, match="no bars for EURUSD"):
        zb.load_bars("EURUSD", data_dir=tmp_path / "does_not_exist")


def test_frame_checks() -> None:
    t = ts("2025-01-06 00:00")
    h = pd.Timedelta(hours=1)
    ok = pd.DataFrame({"open_time": [t, t + h], "close_time": [t + h, t + 2 * h]})
    zb.check_frame(ok, "ok")
    with pytest.raises(zb.ZoneError, match="strictly increasing"):
        zb.check_frame(pd.DataFrame({"open_time": [t, t], "close_time": [t + h] * 2}), "dup")
    with pytest.raises(zb.ZoneError, match="strictly increasing"):
        zb.check_frame(ok.iloc[::-1], "back")
    with pytest.raises(zb.ZoneError, match="close_time"):
        zb.check_frame(pd.DataFrame({"open_time": [t], "close_time": [t]}), "bad")
    gap = pd.DataFrame({"open_time": [t, t + 3 * 24 * h], "close_time": [t + h, t + 3 * 24 * h + h]})
    zb.check_frame(gap, "gap")  # gaps are taken as they are
    # a bar closing exactly when the next opens is fine; one closing after it opens overlaps
    zb.check_frame(pd.DataFrame({"open_time": [t, t + h], "close_time": [t + h, t + h + h]}), "touching")
    overlap = pd.DataFrame({"open_time": [t, t + h / 2], "close_time": [t + h, t + 2 * h]})
    with pytest.raises(zb.ZoneError, match="overlaps"):
        zb.check_frame(overlap, "overlap")
    for col in ("open_time", "close_time"):
        nat = pd.DataFrame({"open_time": [t, t + h], "close_time": [t + h, t + 2 * h]})
        nat.loc[1, col] = pd.NaT
        with pytest.raises(zb.ZoneError, match="missing"):
            zb.check_frame(nat, "nat")


# --- rule 2: the weekly ATR and the step ------------------------------------------------------------------


def d1_weeks(highs: list[float]) -> pd.DataFrame:
    """Daily bars from Sunday 2025-01-05; per 7-day week: low 100, close 105, high ``highs[w]`` (on the 4th day)."""
    rows: list[Row] = []
    for h in highs:
        for d in range(7):
            rows.append((105.0, h if d == 3 else 106.0, 100.0 if d == 3 else 101.0, 105.0))
    return frame("2025-01-05 00:00", 1440, rows)


def test_weekly_atr_is_the_mean_of_14_true_ranges() -> None:
    wk = zb.weekly_atr(d1_weeks([110.0] * 15 + [130.0]))
    assert len(wk) == 16
    assert wk["atr"].iloc[:13].isna().all() and wk["atr"].iloc[13] == pytest.approx(10.0)
    # last week: TR = max(30, |130 - 105|, |100 - 105|) = 30; mean(13 x 10, 30) = 160 / 14
    assert wk["tr"].iloc[-1] == pytest.approx(30.0)
    assert wk["atr"].iloc[-1] == pytest.approx(160 / 14)
    assert wk.index[0] == pd.Timestamp("2025-01-05")  # weeks start Sunday 00:00
    assert wk["done"].iloc[0] == ts("2025-01-12 00:00")


def test_weekly_true_range_uses_the_gap_from_the_previous_close() -> None:
    rows: list[Row] = [(105.0, 106.0, 101.0, 105.0)] * 7 + [(200.0, 201.0, 199.0, 200.0)] * 7
    wk = zb.weekly_atr(frame("2025-01-05 00:00", 1440, rows))
    assert wk["tr"].iloc[1] == pytest.approx(201.0 - 105.0)  # |high - previous close| beats high - low


def test_month_steps_watr_and_fixed() -> None:
    d1 = d1_weeks([110.0] * 40)  # ATR 10 from the week starting 2025-04-06 (closed 2025-04-13)
    h4 = frame("2025-06-10 12:00", 240, [FILL] * 5)
    end = ts("2025-09-01", TH)
    m = zb.month_steps(d1, h4, P, end)
    assert m.starts[0] == ts("2025-05-01", TH)  # the month before the first H4 bar, 00:00 Thai
    assert m.at(ts("2025-08-15 03:00")) == pytest.approx(P.step_factor * 10.0)
    fixed = zb.month_steps(d1, h4, ZoneParams(step_mode="fixed", step_fixed=76.0), end)
    assert set(fixed.step.values()) == {76.0}
    assert fixed.starts[-1] == ts("2025-09-01", TH)  # a month starting exactly at end is included
    # a time is judged with the step of its Thai month: 17:00 UTC on 07-31 is already 08-01 in Bangkok
    two = zb.Months((), {"2025-07": 1.0, "2025-08": 2.0})
    assert two.at(ts("2025-07-31 16:59")) == 1.0 and two.at(ts("2025-07-31 17:00")) == 2.0


def test_months_start_the_month_before_the_first_h4_bar_at_midnight_thai() -> None:
    d1 = d1_weeks([110.0] * 40)
    p = ZoneParams(step_mode="fixed")
    end = ts("2025-08-01", TH)
    for first in ("2025-05-31 17:00", "2025-06-10 00:00", "2025-06-30 16:59"):  # all in Bangkok June
        m = zb.month_steps(d1, frame(first, 240, [FILL] * 3), p, end)
        assert m.starts[0] == ts("2025-05-01", TH)  # 00:00, not the first bar's clock time
        assert all(x.hour == 0 and x.day == 1 for x in m.starts)
    assert m.starts[-1] == ts("2025-08-01", TH)


def test_watr_without_a_closed_week_stops() -> None:
    with pytest.raises(zb.ZoneError, match="weekly ATR"):
        zb.month_steps(
            d1_weeks([110.0] * 5), frame("2025-02-03 12:00", 240, [FILL] * 3), P, ts("2025-03-01", TH)
        )


# --- rule 3: grids ----------------------------------------------------------------------------------------

S10 = ZoneParams(step_mode="fixed", step_fixed=10.0)


@pytest.mark.parametrize(
    ("d", "expect"),
    [
        (10.0, True), (11.0, True), (9.0, True), (11.0001, False), (8.9999, False),  # k = 1 and its edges
        (20.0, True), (21.0, True), (19.0, True), (21.01, False),  # k = 2
        (30.0, True), (31.0, True), (29.0, True), (31.01, False), (28.99, False),  # k = 3
        (14.0, False), (4.0, False), (41.0, False), (39.0, False),  # between, below, past k = 3 (no k = 4)
    ],
)  # fmt: skip
def test_pair_clusters_at_one_two_three_steps(d: float, expect: bool) -> None:
    got = zb.cluster_anchor(105.0, 105.0 - d, 10.0, S10)
    assert (got is not None) is expect
    if expect:
        assert got == 105.0 - d  # the anchor is the lower price
    assert zb.cluster_anchor(105.0 - d, 105.0, 10.0, S10) == got  # the order of the pair does not matter


def test_shift_and_no_shift_by_shift_tol() -> None:
    g = zb.Grid(ts("2025-01-01"), 100.0, 10.0, "t")
    cases = [(100.0, False), (102.0, False), (98.0, False), (112.0, False)]
    cases += [(102.0001, True), (97.9999, True), (107.0, True), (95.0, True)]
    for lo, shifts in cases:
        assert zb.new_grid_needed(g, lo, 10.0, S10) is shifts, lo
    assert zb.new_grid_needed(None, 100.0, 10.0, S10)  # no grid yet
    assert zb.off_lines(107.0, 100.0, 10.0) == pytest.approx(3.0)


def test_step_remake_by_step_remake() -> None:
    g = zb.Grid(ts("2025-01-01"), 100.0, 10.0, "t")
    assert not zb.new_grid_needed(g, 100.0, 12.0, S10) and not zb.new_grid_needed(g, 100.0, 8.0, S10)
    assert zb.new_grid_needed(g, 100.0, 12.01, S10) and zb.new_grid_needed(g, 100.0, 7.99, S10)
    assert not zb.month_remake_needed(g, 12.0, S10) and zb.month_remake_needed(g, 12.01, S10)
    assert not zb.month_remake_needed(None, 99.0, S10)


def months_of(steps: dict[str, float]) -> zb.Months:
    return zb.Months(tuple(ts(m + "-01", TH) for m in steps), steps)


def test_grid_events_pairs_shift_and_month_remake() -> None:
    months = months_of({"2025-01": 10.0, "2025-02": 10.0, "2025-03": 14.0, "2025-04": 14.0})
    pairs = [
        (ts("2025-01-10", TH), 120.0, 110.0),  # one step: the first grid, anchor 110
        (
            ts("2025-01-12", TH),
            132.0,
            111.0,
        ),  # d 21, two steps within the tolerance; 1 off the lines: no shift
        (ts("2025-01-14", TH), 141.0, 113.0),  # d 28: not a cluster
        (ts("2025-01-16", TH), 150.0, 115.0),  # d 35: not a cluster
        (ts("2025-01-20", TH), 130.0, 100.0),  # d 30, lo 100 on the lines: no shift
        (ts("2025-01-26", TH), 160.0, 130.0),  # d 30, lo 130 on the lines
        (ts("2025-01-28", TH), 148.0, 118.0),  # d 30, lo 118: exactly 2 = shift_tol x S off: no shift
        (ts("2025-01-30", TH), 147.0, 117.0),  # d 30, lo 117: 3 off: a new grid at 117
    ]
    g = zb.grids_from_events(pairs, months, S10, ts("2025-05-01", TH))
    assert [(x.start, x.anchor, x.step) for x in g[:2]] == [
        (ts("2025-01-10", TH), 110.0, 10.0),
        (ts("2025-01-30", TH), 117.0, 10.0),
    ]
    # March: the month's step 14 is 40 % from the grid's 10 -> the same anchor, the new step
    assert (g[2].start, g[2].anchor, g[2].step, g[2].cause) == (ts("2025-03-01", TH), 117.0, 14.0, "month")
    assert len(g) == 3  # February: equal step; April: 14 vs 14


def test_events_at_or_after_end_are_dropped_and_no_grid_before_a_pair() -> None:
    months = months_of({"2025-01": 10.0, "2025-02": 20.0})
    assert zb.grids_from_events([], months, S10, ts("2025-03-01", TH)) == []  # a month alone starts nothing
    pairs = [
        (ts("2025-01-10", TH), 120.0, 110.0),
        (ts("2025-01-20", TH), 155.0, 125.0),
    ]  # the 2nd shifts (5 off)
    assert (
        len(zb.grids_from_events(pairs, months, S10, ts("2025-01-20", TH))) == 1
    )  # the event at end is not used
    assert len(zb.grids_from_events(pairs, months, S10, ts("2025-01-21", TH))) == 2


def test_pairs_come_before_months_at_equal_times() -> None:
    months = months_of({"2025-01": 10.0, "2025-02": 20.0})
    pairs = [(ts("2025-01-10", TH), 120.0, 110.0), (ts("2025-02-01", TH), 140.0, 120.0)]
    # the February pair (step 20) comes first and starts the grid (120, 20); had the month come first it would
    # have remade (110, 20) and the pair would then have shifted: three grids
    g = zb.grids_from_events(pairs, months, S10, ts("2025-03-01", TH))
    assert [(x.anchor, x.step) for x in g] == [(110.0, 10.0), (120.0, 20.0)]
    assert g[1].cause.startswith("pair")


# --- rule 4: visits ---------------------------------------------------------------------------------------


def test_a_buy_visit_and_its_readings() -> None:
    (v,) = visits(make_bars([BUY_100]))
    assert (v.side, v.sgn, v.line, v.step, v.anchor, v.time, v.i) == (
        "BUY",
        1,
        100.0,
        10.0,
        100.0,
        row_time(0),
        N_FILL,
    )
    assert v.z == pytest.approx(P.near_frac * 10.0) and v.h1_open == 105.0
    assert v.share == pytest.approx(1.0) and v.trends == (False,) * 4  # flat frames have no pivot: sideways


def test_a_sell_visit() -> None:
    (v,) = visits(make_bars([SELL_100]))
    assert (v.side, v.sgn, v.line) == ("SELL", -1, 100.0)


def test_no_visit_when_the_bar_opens_on_the_line_or_stays_out_of_reach() -> None:
    assert visits(make_bars([(100.0, 100.5, 99.5, 100.0)])) == []  # open == line: neither side
    assert visits(make_bars([(105.0, 105.5, 101.4, 105.0)])) == []  # low 101.4 > 100 + Z (101.3158)
    assert len(visits(make_bars([(105.0, 105.5, 101.3, 105.0)]))) == 1


def test_arming_disarming_and_re_arming() -> None:
    assert [v.i for v in visits(make_bars([BUY_100, BUY_100]))] == [N_FILL]  # disarmed after the first visit
    # a bar that straddles the line does NOT re-arm it
    assert [v.i for v in visits(make_bars([BUY_100, STRADDLE, BUY_100]))] == [N_FILL]
    # a bar wholly 5 (away_frac x S) above re-arms it
    assert [v.i for v in visits(make_bars([BUY_100, UP, BUY_100]))] == [N_FILL, N_FILL + 2]
    # the edge: low == line + 5 re-arms (UP), 4.99 does not
    assert len(visits(make_bars([BUY_100, (107.0, 108.0, 104.99, 107.0), BUY_100]))) == 1


def test_re_arming_from_below_for_a_sell_line() -> None:
    down: Row = (93.0, 95.0, 92.0, 93.0)  # high <= 100 - 5: wholly away below
    assert len(visits(make_bars([SELL_100, down, SELL_100]))) == 2
    assert len(visits(make_bars([SELL_100, (93.0, 95.1, 92.0, 93.0), SELL_100]))) == 1


def test_a_new_grid_has_new_keys_all_armed() -> None:
    g2 = zb.Grid(row_time(1), 100.0, 20.0, "test")  # the same line 100 at another step: another key
    assert [v.i for v in visits(make_bars([BUY_100, BUY_100]), [GRID, g2])] == [N_FILL, N_FILL + 1]


def test_the_grid_in_force_is_the_last_one_started() -> None:
    late = zb.Grid(row_time(1), 100.0, 20.0, "test")
    vs = visits(make_bars([BUY_100, (105.0, 106.0, 100.0, 105.0)]), [GRID, late])
    assert [(v.i, v.step) for v in vs] == [(N_FILL, 10.0), (N_FILL + 1, 20.0)]
    assert (
        visits(make_bars([BUY_100]), [zb.Grid(row_time(5), 100.0, 10.0, "test")]) == []
    )  # not before the first grid
    assert visits(make_bars([BUY_100]), []) == []


def test_the_candidate_range_covers_a_very_long_bar() -> None:
    # A 100, S 10, open 102, high 105: with low 95 or low 65 the visit on 100 stays
    assert [v.line for v in visits(make_bars([(102.0, 105.0, 95.0, 102.0)]))] == [100.0]
    # with low 65 every line the bar reached is a visit, the nearest to the open first
    assert [v.line for v in visits(make_bars([(102.0, 105.0, 65.0, 102.0)]))] == [100.0, 90.0, 80.0, 70.0]


def test_the_rounded_line_edge() -> None:
    # A = 100.0049: the line is round(A, 2) = 100.00, below A. The bar's high + Z is under A, so without one more
    # candidate each side k = 0 would be missed; the visit test decides.
    g = zb.Grid(ts("2025-01-01"), 100.0049, 10.0, "test")
    z = P.near_frac * 10.0
    high = 100.0 - z + 0.0003  # >= 100.00 - Z, but high + Z < A
    assert high + z < 100.0049
    (v,) = visits(make_bars([(97.0, high, 96.5, 97.0)]), [g])
    assert (v.side, v.line) == ("SELL", 100.0)
    assert visits(make_bars([(97.0, 100.0 - z - 0.001, 96.5, 97.0)]), [g]) == []


def test_same_hour_order_is_the_order_price_reached_the_lines() -> None:
    # open 102: a BUY visit on 100 (low 99) and a SELL visit on 110 (high 111)
    h1: Row = (102.0, 111.0, 99.0, 102.0)
    up_first = [
        (102.0, 109.0, 102.0, 109.0),
        (109.0, 111.0, 108.0, 105.0),
        (105.0, 105.0, 105.0, 105.0),
        (105.0, 105.0, 99.0, 100.0),
    ]
    vs = visits(make_bars([h1], {N_FILL: up_first}))
    assert [v.line for v in vs] == [110.0, 100.0]
    assert [v.touch_j - v.j0 for v in vs] == [0, 3]
    down_first = [
        (102.0, 102.0, 99.0, 99.5),
        (99.5, 99.5, 99.5, 99.5),
        (99.5, 109.0, 99.5, 109.0),
        (109.0, 111.0, 109.0, 110.0),
    ]
    vs = visits(make_bars([h1], {N_FILL: down_first}))
    assert [v.line for v in vs] == [100.0, 110.0]
    assert [v.touch_j - v.j0 for v in vs] == [0, 2]


def test_same_bar_tie_goes_by_the_distance_from_the_open_then_the_line() -> None:
    both = [(102.0, 111.0, 99.0, 102.0), FILL, FILL, FILL]  # both lines in the first exec bar
    near_100 = visits(make_bars([(102.0, 111.0, 99.0, 102.0)], {N_FILL: both}))
    assert [v.line for v in near_100] == [100.0, 110.0]  # 2 before 8
    assert near_100[0].touch_j == near_100[1].touch_j
    near_110 = visits(make_bars([(108.0, 111.0, 99.0, 108.0)], {N_FILL: both}))
    assert [v.line for v in near_110] == [110.0, 100.0]  # 2 before 8, the other way
    mid = visits(
        make_bars([(105.0, 111.0, 99.0, 105.0)], {N_FILL: [(105.0, 111.0, 99.0, 105.0), FILL, FILL, FILL]})
    )
    assert [v.line for v in mid] == [100.0, 110.0]  # 5 and 5: the lower line
    assert mid[0].from_open == mid[1].from_open == 5.0


def test_no_exec_touch_in_the_hour_counts_as_after_the_last() -> None:
    (v,) = visits(make_bars([BUY_100], {N_FILL: [FILL] * 4}))
    assert v.touch_j == v.j0 + 4


def test_the_exec_frame_row_of_the_visit() -> None:
    assert visits(make_bars([BUY_100]))[0].j0 == 4 * N_FILL  # the exec bar opening at the visit's time
    vs5 = visits(make_bars([BUY_100], exec_tf="M5"), params=ZoneParams(exec_tf="M5"))
    assert vs5[0].j0 == 12 * N_FILL


def test_warm_up_index_and_the_run_start() -> None:
    assert zb.warmup_index(P) == 130
    assert zb.warmup_index(ZoneParams(mom_med_bars=200)) == 210
    # a touch on row 129 makes no visit (the loop starts at row 130); on row 130 it does
    early = [FILL] * N_FILL
    early[129] = BUY_100
    h1 = frame(START, 60, [*early, FILL])
    ex = frame(START, 15, [FILL] * (4 * (N_FILL + 1)))
    flat = frame(START, 240, [FILL] * 20)
    assert zb.find_visits(zb.Bars(flat, flat, h1, ex, ex, 0.01), [GRID], P, ts("2025-01-01"), FAR) == []
    assert len(visits(make_bars([BUY_100]))) == 1
    # not before the run's start
    assert visits(make_bars([BUY_100]), start=row_time(0) + pd.Timedelta(minutes=1)) == []
    assert len(visits(make_bars([BUY_100]), start=row_time(0))) == 1


def test_run_end_is_exclusive() -> None:
    bars = make_bars([BUY_100])
    assert visits(bars, end=row_time(0)) == []
    assert len(visits(bars, end=row_time(0) + pd.Timedelta(minutes=1))) == 1


def test_a_visit_without_an_hour_of_exec_history_stops_the_run() -> None:
    bars = make_bars([BUY_100])
    short = zb.Bars(
        bars.d1, bars.h4, bars.h1, bars.m15.iloc[4 * N_FILL - 3 :].reset_index(drop=True), bars.m5, 0.01
    )
    with pytest.raises(zb.ZoneError, match="no hour of history"):
        visits(short)


# --- rule 5: the readings and the decisions at their edges -----------------------------------------------


def test_momentum_reading_and_decision_on_constructed_bars() -> None:
    down: Row = (105.5, 105.5, 104.5, 104.5)  # a body of 1.0 toward a BUY line, range 1.0 = the median
    (v,) = visits(make_bars([down, FILL, BUY_100]))
    assert v.mom_body == pytest.approx(1.0) and v.mom_median == pytest.approx(1.0)
    assert zb.skip_momentum(v, P)  # body == median skips
    (w,) = visits(make_bars([(105.4, 105.5, 104.4, 104.41), BUY_100]))
    assert w.mom_body == pytest.approx(0.99) and not zb.skip_momentum(w, P)
    # toward the line means up for a SELL: the down bar is a body of -1, the max over the three bars is 0
    (s,) = visits(make_bars([down, FILL, SELL_100]))
    assert s.side == "SELL" and s.mom_body == pytest.approx(0.0) and not zb.skip_momentum(s, P)


def varied_filler(peak: int | None = None) -> list[Row]:
    """130 quiet bars whose ranges, opens and closes all differ (ranges grow with the row); the bar ``peak``
    has the biggest body toward a BUY line."""
    rows: list[Row] = []
    for k in range(N_FILL):
        o = 105.0 + (k % 7) * 0.01
        c = o - 0.45 if k == peak else o + 0.02 * ((k * 5) % 11) - 0.1
        rows.append((o, o + 0.5 + 0.001 * k, o - 0.5, c))
    return rows


@pytest.mark.parametrize("peak", [None, N_FILL - 3, N_FILL - 1])
def test_momentum_windows_are_exact_on_varying_bars(peak: int | None) -> None:
    bars = make_bars([BUY_100], filler=varied_filler(peak))
    (v,) = visits(bars)
    h1, i = bars.h1, v.i
    o, h, lo, c = (h1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    rng = h - lo
    med = float(np.median(rng[i - 120 : i]))
    assert v.mom_median == pytest.approx(med, abs=1e-12)
    assert v.mom_body == pytest.approx(float(((c - o) * -1)[i - 3 : i].max()), abs=1e-12)
    assert v.mom_run == pytest.approx(float((c[i - 1] - o[i - 6]) * -1), abs=1e-12)
    # the fixture tells the neighbouring windows apart, so an off-by-one cannot pass
    for a, b in ((i - 121, i - 1), (i - 119, i + 1), (i - 119, i), (i - 121, i)):
        assert abs(float(np.median(rng[a:b])) - med) > 1e-4, (a, b)
    assert abs(float((c[i - 1] - o[i - 5]) * -1) - v.mom_run) > 1e-3
    assert abs(float((c[i - 1] - o[i - 7]) * -1) - v.mom_run) > 1e-3
    if peak is not None:  # the biggest body sits on the oldest / newest bar of the window: a shift drops it
        assert v.mom_body == pytest.approx(0.45, abs=1e-12)
        assert float(((c - o) * -1)[i - 2 : i + 1].max()) < 0.4 if peak == N_FILL - 3 else True
        assert float(((c - o) * -1)[i - 4 : i - 1].max()) < 0.4 if peak == N_FILL - 1 else True


def test_first_touch_is_searched_only_in_the_visits_own_hour() -> None:
    bars = make_bars([BUY_100, FILL, FILL], {N_FILL + 1: [FILL, (105.0, 105.5, 100.5, 105.0), FILL, FILL]})
    j0 = 4 * N_FILL
    # the visit's hour keeps only its first exec bar (the other three are missing from the stored data)
    m15 = bars.m15.drop(index=[j0 + 1, j0 + 2, j0 + 3]).reset_index(drop=True)
    holey = zb.Bars(bars.d1, bars.h4, bars.h1, m15, bars.m5, bars.point)
    (v,) = visits(holey)
    # j0 + 1 is the 01:00 bar (no touch), j0 + 2 the 01:15 bar that touches: outside the hour, so not a first touch
    assert v.j0 == j0 and v.touch_j == j0 + 1


def test_skip_busy_is_at_or_before_the_reservation_end() -> None:
    t = ts("2025-03-03 10:00")
    assert not zb.skip_busy(t, None)
    assert zb.skip_busy(t, t) and zb.skip_busy(t, t + pd.Timedelta(minutes=1))
    assert not zb.skip_busy(t + pd.Timedelta(minutes=1), t)


def test_momentum_looks_back_only_mom_bars() -> None:
    down: Row = (105.5, 105.5, 104.5, 104.5)
    (far,) = visits(make_bars([down, FILL, FILL, FILL, BUY_100]))  # 4 bars before: outside i-3 .. i-1
    assert far.mom_body == pytest.approx(0.0)
    (near,) = visits(make_bars([down, FILL, FILL, BUY_100]))
    assert near.mom_body == pytest.approx(1.0)


def test_momentum_run_reading_and_decision_edge() -> None:
    (v,) = visits(make_bars([FILL] * 5 + [(105.0, 105.5, 103.9, 104.0), BUY_100]))
    assert v.mom_run == pytest.approx(1.0)  # (close_{i-1} - open_{i-6}) x -sgn = (104 - 105) x -1
    edge = replace(v, mom_body=0.0, mom_median=1.0, mom_run=10.0, step=10.0)
    assert zb.skip_momentum(edge, P) and not zb.skip_momentum(replace(edge, mom_run=9.999), P)
    assert zb.skip_momentum(replace(edge, mom_run=0.0, mom_body=1.0), P)
    assert not zb.skip_momentum(replace(edge, mom_run=0.0, mom_body=0.999), P)


def test_abnormal_reading_and_decision_edge() -> None:
    bars = make_bars([FILL, (105.0, 108.0, 105.0, 107.9), BUY_100])
    (v,) = visits(bars)
    h1 = bars.h1
    ema = h1["close"].ewm(span=50, adjust=False).mean()
    tr = pd.concat(
        [h1.high - h1.low, (h1.high - h1.close.shift()).abs(), (h1.low - h1.close.shift()).abs()], axis=1
    ).max(axis=1)
    atr = tr.rolling(14).mean()
    assert v.ema_dist == pytest.approx(abs(h1.close[v.i - 1] - ema[v.i - 1]))
    assert v.atr == pytest.approx(atr[v.i - 1])
    edge = replace(v, ema_dist=3.0 * 2.0, atr=2.0)
    assert zb.skip_abnormal(edge, P) and not zb.skip_abnormal(replace(edge, ema_dist=5.999), P)
    assert not zb.skip_abnormal(replace(edge, atr=float("nan")), P)
    assert not zb.skip_abnormal(edge, ZoneParams(abn_atr=1e9))


def test_trend_reading() -> None:
    a = np.array
    assert zb.is_trend(a([2.0, 3.0]), a([1.0, 2.0])) and zb.is_trend(a([3.0, 2.0]), a([2.0, 1.0]))
    assert not zb.is_trend(a([2.0, 3.0]), a([2.0, 1.0]))  # a rising high with a falling low: sideways
    assert not zb.is_trend(a([2.0, 2.0]), a([1.0, 2.0]))  # equal highs: sideways
    assert not zb.is_trend(a([3.0]), a([1.0, 2.0])) and not zb.is_trend(a([]), a([]))
    assert zb.is_trend(
        a([1.0, 2.0, 3.0]), a([5.0, 1.0, 2.0])
    )  # only the last two of each count: highs up, lows up


def test_frame_trends_use_only_pivots_known_by_t() -> None:
    def pv(known: list[int], high: list[bool], price: list[float]) -> zb.PivotSet:
        return zb.PivotSet(np.array(known, dtype="int64"), np.array(high, dtype=bool), np.array(price))

    up = pv(
        [1, 2, 3, 4], [True, False, True, False], [10.0, 5.0, 12.0, 6.0]
    )  # highs 10, 12; lows 5, 6: a trend
    flat = pv([], [], [])
    st = {"D1": up, "H4": flat, "H1": flat, "M15": flat}
    assert zb.frame_trends(st, 4) == (True, False, False, False)
    assert zb.frame_trends(st, 3) == (False, False, False, False)  # the second low is not yet known


def test_each_frames_trend_reading_in_order_d1_h4_h1_m15() -> None:
    def pv(trending: bool) -> zb.PivotSet:
        lows = (
            [5.0, 6.0] if trending else [6.0, 5.0]
        )  # highs 10, 12 always: rising lows trend, falling do not
        return zb.PivotSet(
            np.array([1, 2, 3, 4], dtype="int64"),
            np.array([True, False, True, False]),
            np.array([10.0, lows[0], 12.0, lows[1]]),
        )

    frames = ("D1", "H4", "H1", "M15")
    bars = make_bars([BUY_100])
    for k, alone in enumerate(frames):  # each frame trending alone: every frame differs from every other
        st = {tf: pv(tf == alone) for tf in frames}
        expect = tuple(j == k for j in range(4))
        assert zb.frame_trends(st, 4) == expect
        # through find_visits: the visit carries each frame's reading; the share is the weight of the other three
        (v,) = zb.find_visits(bars, [GRID], P, ts("2025-01-01"), FAR, state=st)
        assert v.trends == expect
        assert v.share == pytest.approx(1.0 - P.gate_w[k])  # 0.6, 0.7, 0.8, 0.9
    # and the opposite pattern: everything trends but one frame
    st = {tf: pv(tf != "H1") for tf in frames}
    assert zb.frame_trends(st, 4) == (True, True, False, True)


def test_sideways_share_and_the_gate_edge() -> None:
    w = (0.4, 0.3, 0.2, 0.1)
    assert zb.sideways_share((False,) * 4, w) == pytest.approx(1.0)
    assert zb.sideways_share((True, True, True, False), w) == pytest.approx(0.1)
    assert zb.sideways_share((True, False, True, False), w) == pytest.approx(0.4)
    (v,) = visits(make_bars([BUY_100]))
    eq = ZoneParams(gate_w=(0.25, 0.25, 0.25, 0.25))
    one = replace(v, share=zb.sideways_share((True, True, True, False), eq.gate_w))
    assert one.share == 0.25 and zb.skip_trend(one, eq)  # <= gate_min skips
    two = replace(v, share=zb.sideways_share((True, True, False, False), eq.gate_w))
    assert two.share == 0.5 and not zb.skip_trend(two, eq)
    assert not zb.skip_trend(replace(v, share=0.3), P) and zb.skip_trend(replace(v, share=0.25), P)


# --- independence (rule 0) --------------------------------------------------------------------------------


def test_zone_bot_imports_nothing_of_the_fibonacci_bot() -> None:
    names: set[str] = set()
    for node in ast.walk(ast.parse((ROOT / "eye" / "zone_bot.py").read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.update(a.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            names.update((node.module or "").split("."))
            names.update(a.name for a in node.names)
    assert names & {"bot2e", "bot_config", "bot_research"} == set()


# --- acceptance on the stored bars ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def stored() -> zb.Bars:
    return zb.load_bars("XAUUSD")


@ACCEPT
def test_accept_case_1_weekly_atr(stored: zb.Bars) -> None:
    wk = zb.weekly_atr(stored.d1)
    assert round(float(wk.loc[pd.Timestamp("2026-10-25"), "atr"]), 2) == 195.99


FIXED76 = ZoneParams(step_mode="fixed", exec_tf="M5", abn_atr=1e9, be_mode="off")
RUNS = {
    "defaults": (ZoneParams(be_mode="off"), "2023-10-01", "2026-11-01"),
    "defaults_be": (ZoneParams(), "2023-10-01", "2026-11-01"),
    "fixed76": (FIXED76, "2025-11-01", "2026-11-01"),
}


@ACCEPT
def test_accept_case_2_grids_of_rule_3(stored: zb.Bars) -> None:
    end = ts("2026-11-01", TH)
    g = zb.build_grids(
        stored.h4, zb.month_steps(stored.d1, stored.h4, FIXED76, end), FIXED76, stored.point, end
    )
    on = [x for x in g if x.start <= ts("2025-08-01", TH)][-1]
    assert (on.start, round(on.anchor, 2)) == (ts("2025-06-18 12:00", TH), 3293.39)
    later = [(x.start, round(x.anchor, 2)) for x in g if x.start > ts("2025-08-01", TH)]
    expect = [
        ("2025-08-14 20:00", 3331.04),
        ("2025-11-05 13:00", 3886.43),
        ("2026-05-05 12:00", 4510.20),
        ("2026-07-02 12:00", 3942.95),
        ("2026-09-09 20:00", 4282.45),
        ("2026-09-22 12:00", 4253.59),
        ("2026-10-14 00:00", 4066.42),
    ]
    assert later == [(ts(a, TH), p) for a, p in expect]


def run(
    stored: zb.Bars,
    tag: str,
    bars: zb.Bars | None = None,
    end: pd.Timestamp | None = None,
) -> tuple[list[zb.Grid], list[zb.Visit]]:
    p, a, b = RUNS[tag]
    bars = bars or stored
    end = end or ts(b, TH)
    months = zb.month_steps(bars.d1, bars.h4, p, end)
    g = zb.build_grids(bars.h4, months, p, bars.point, end)
    return g, zb.find_visits(bars, g, p, ts(a, TH), end)


def reference_pivots(stored: zb.Bars) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """The reference's ``PIV`` (close time of the confirm bar, kind, price), recomputed from scratch."""
    from app.indicators.chart_read import zigzag_pivots

    out = {}
    for tf in zb.STATE_FRAMES:
        df = stored.frame(tf)
        z = zigzag_pivots(df.high.to_numpy(float), df.low.to_numpy(float), stored.point)
        out[tf] = (
            np.array([df.close_time.iloc[p.confirm_pos].value for p in z]),
            np.array([p.kind.name for p in z]),
            np.array([p.price for p in z]),
        )
    return out


def reference_share(piv: dict[str, Any], t: pd.Timestamp, weights: tuple[float, ...]) -> float:
    """The reference's ``side_share`` (the mask form)."""
    tot = 0.0
    for tf, w in zip(zb.STATE_FRAMES, weights, strict=True):
        ct, kd, pr = piv[tf]
        m = ct <= t.value
        hs, ls = pr[m & (kd == "HIGH")][-2:], pr[m & (kd == "LOW")][-2:]
        trend = (
            len(hs) == 2
            and len(ls) == 2
            and ((hs[1] > hs[0] and ls[1] > ls[0]) or (hs[1] < hs[0] and ls[1] < ls[0]))
        )
        tot += 0 if trend else w
    return tot


@ACCEPT
@pytest.mark.parametrize("tag", ["defaults", "defaults_be", "fixed76"])
def test_accept_case_3_grids_and_visits_equal_the_reference(stored: zb.Bars, tag: str) -> None:
    p = RUNS[tag][0]
    g, v = run(stored, tag)
    tol = 1e-9
    rg = pd.read_csv(OUT / f"grids_accept_{tag}.csv")
    assert len(g) == len(rg)
    for r, x in zip(rg.itertuples(), g, strict=True):
        assert (
            pd.Timestamp(r.start) == x.start and abs(r.anchor - x.anchor) < tol and abs(r.step - x.step) < tol
        )
    rv = pd.read_csv(OUT / f"visits_accept_{tag}.csv")
    assert len(v) == len(rv)
    for r, x in zip(rv.itertuples(), v, strict=True):
        assert pd.Timestamp(r.visit) == x.time and r.side == x.side
        pairs = [
            (r.line, x.line), (r.S, x.step), (r.Z, x.z), (r.h1_open, x.h1_open), (r.from_open, x.from_open),
            (r.anchor, x.anchor), (r.mom_body, x.mom_body), (r.mom_median, x.mom_median),
            (r.mom_run, x.mom_run), (r.ema_dist, x.ema_dist), (r.atr, x.atr), (r.share, x.share),
        ]  # fmt: skip
        assert all(abs(a - b) < tol for a, b in pairs), (r.visit, pairs)
        assert bool(r.momentum) is zb.skip_momentum(x, p) and bool(r.abn) is zb.skip_abnormal(x, p)
        assert int(r.touch_j) == x.touch_j
        assert (bool(r.trend_D1), bool(r.trend_H4), bool(r.trend_H1), bool(r.trend_M15)) == x.trends, r.visit
    # the state gate is not in the reference's file: recompute its side_share for every visit
    piv = reference_pivots(stored)
    for x in v:
        assert x.share == pytest.approx(reference_share(piv, x.time, p.gate_w)), x.time


def visit_key(v: zb.Visit) -> tuple[Any, ...]:
    return (
        v.time,
        v.side,
        v.line,
        v.step,
        v.anchor,
        v.touch_j,
        v.j0,
        v.mom_body,
        v.mom_median,
        v.mom_run,
        v.ema_dist,
        v.atr,
        v.trends,
        v.share,
    )


@ACCEPT
@pytest.mark.parametrize("cut", ["2024-06-01 00:00", "2025-12-15 00:00", "2026-08-01 00:00"])
def test_accept_case_4_visits_and_grids_are_the_same_on_bars_cut_at_t(stored: zb.Bars, cut: str) -> None:
    t = ts(cut)
    g_full, v_full = run(stored, "defaults")
    g_cut, v_cut = run(stored, "defaults", bars=zb.cut_bars(stored, t), end=t)
    assert [x for x in g_full if x.start < t] == g_cut
    before = [visit_key(x) for x in v_full if x.time < t]
    assert before and before == [visit_key(x) for x in v_cut]


def test_the_rounded_line_edge_on_the_low_side() -> None:
    # A = 99.9951: the line round(A, 2) = 100.00 lies ABOVE the unrounded A. The bar's low - Z is just above A, so
    # without one more candidate below, the first candidate would be k = 1 and the visit on 100.00 would be missed.
    g = zb.Grid(ts("2025-01-01"), 99.9951, 10.0, "test")
    z = P.near_frac * 10.0
    low = 100.0 + z - 0.0001  # low <= 100.00 + Z, but low - Z > A
    assert low - z > 99.9951
    (v,) = visits(make_bars([(105.0, 105.5, low, 105.0)]), [g])
    assert (v.side, v.line) == ("BUY", 100.0)


def test_a_far_away_bar_re_arms_a_line_it_cannot_visit() -> None:
    # the bar (low 123) is wholly >= 5 above 100 but its candidate lines do not include 100: the re-arm still
    # covers every disarmed line of the grid, before the candidates are looked at
    far: Row = (125.0, 126.0, 123.0, 125.0)
    assert [v.i for v in visits(make_bars([BUY_100, far, BUY_100]))] == [N_FILL, N_FILL + 2]
    assert [v.i for v in visits(make_bars([BUY_100, far]))] == [N_FILL]  # the far bar itself visits nothing


# --- rules 6 and 7: the setup, its fills and its exit (constructed bars) ---------------------------------

T0 = ts("2025-02-03 00:00")
Q = pd.Timedelta(minutes=15)
J0 = 8  # the visit is at exec row 8, after 8 flat bars of history (2 hours)


def flat(p: float) -> Row:
    return (p, p, p, p)


HIST: list[Row] = [flat(102.0)] * 8


def ebars(rows: list[Row], spreads: list[float] | None = None) -> zb.ExecBars:
    sp = np.array(spreads if spreads is not None else [0.0] * len(rows))
    arr = np.array(rows, dtype=float)
    return zb.ExecBars(
        arr[:, 0],
        arr[:, 1],
        arr[:, 2],
        arr[:, 3],
        sp,
        pd.Series([T0 + Q * (k + 1) for k in range(len(rows))]),
    )


def mk_visit(side: str = "BUY", line: float = 100.0, step: float = 10.0, j0: int = J0, **kw: Any) -> zb.Visit:
    base: dict[str, Any] = {
        "time": T0 + Q * j0, "i": 0, "side": side, "sgn": 1 if side == "BUY" else -1, "line": line, "step": step,
        "anchor": line, "z": 1.3158, "h1_open": line + 2, "mom_body": 0.0, "mom_median": 1.0, "mom_run": 0.0,
        "ema_dist": 0.0, "atr": 1.0, "trends": (False,) * 4, "share": 1.0, "j0": j0, "touch_j": j0, "from_open": 2.0,
    }  # fmt: skip
    base.update(kw)
    return zb.Visit(**base)


def mirror(rows: list[Row]) -> list[Row]:
    """The same bars seen from the other side: price p becomes 200 - p (a BUY on line 100 becomes a SELL on 100)."""
    return [(200 - o, 200 - lo, 200 - h, 200 - c) for o, h, lo, c in rows]


def sim(
    side: str,
    rows: list[Row],
    hist: list[Row] | None = None,
    spreads: list[float] | None = None,
) -> zb.Setup:
    """Simulate a visit on line 100 (step 10) at exec row 8; ``rows`` and ``hist`` are written for a BUY and
    mirrored for a SELL."""
    allrows = (hist if hist is not None else HIST) + rows
    if side == "SELL":
        allrows = mirror(allrows)
    return zb.simulate_setup(mk_visit(side), ebars(allrows, spreads), P, 0.01)


def px(side: str, p: float) -> float:
    return p if side == "BUY" else 200.0 - p


SIDES = ["BUY", "SELL"]
P1B, P2B, SLB, TPB = (
    100 + P.p1_frac * 10,
    100 - P.p2_frac * 10,
    95.0,
    110.0,
)  # the BUY prices on line 100, S 10
QUIET: Row = (102.0, 102.4, 101.6, 102.0)


@pytest.mark.parametrize("side", SIDES)
def test_prices_of_p1_p2_sl_tp(side: str) -> None:
    s = sim(side, [(102.0, 102.5, 101.2, 102.0)])
    sg = 1 if side == "BUY" else -1
    assert s.p1 == pytest.approx(100 + sg * 1.3157894736842106)
    assert s.p2 == pytest.approx(100 - sg * 1.9736842105263157)
    assert s.sl == pytest.approx(100 - sg * 5.0) and s.tp == pytest.approx(100 + sg * 10.0)


@pytest.mark.parametrize("side", SIDES)
def test_p1_fill_then_tp_on_a_later_bar(side: str) -> None:
    s = sim(side, [(102.0, 102.5, 101.2, 102.0), (102.0, 111.0, 101.0, 110.5)])
    assert (s.outcome, s.how, s.exit_j, s.end_j) == ("traded", "TP", J0 + 1, J0 + 1)
    assert [(f.name, f.j) for f in s.fills] == [("P1", J0)]
    assert s.fills[0].price == pytest.approx(px(side, P1B)) and s.exit_price == pytest.approx(px(side, TPB))
    (p,) = zb.positions_of(s)
    assert p.pnl == pytest.approx(TPB - P1B) and p.risk == pytest.approx(P1B - SLB)
    assert zb.setup_r(s) == pytest.approx((TPB - P1B) / (P1B - SLB))
    assert s.end_time == T0 + Q * (J0 + 2)  # the close of the exit bar


@pytest.mark.parametrize("side", SIDES)
def test_no_tp_on_the_fill_bar_but_the_next_bar_takes_it(side: str) -> None:
    s = sim(side, [(102.0, 111.0, 101.2, 110.0), (110.0, 110.5, 109.0, 110.0)])
    assert (s.how, s.exit_j) == ("TP", J0 + 1)  # the fill bar reached the TP price and did not exit


@pytest.mark.parametrize("side", SIDES)
def test_no_tp_on_the_bar_that_fills_p2_either(side: str) -> None:
    # P1 filled earlier; a later bar fills P2 and also reaches the TP (not the SL): no TP on that bar
    rows = [(102.0, 102.5, 101.2, 102.0), (102.0, 111.0, 97.5, 110.0), (110.0, 110.5, 109.0, 110.0)]
    s = sim(side, rows)
    assert [(f.name, f.j) for f in s.fills] == [("P1", J0), ("P2", J0 + 1)]
    assert (s.how, s.exit_j) == ("TP", J0 + 2)


@pytest.mark.parametrize("side", SIDES)
def test_sl_first_in_a_bar_holding_both(side: str) -> None:
    s = sim(side, [(102.0, 102.5, 101.2, 102.0), (102.0, 111.0, 94.0, 100.0)])
    assert (s.how, s.exit_price) == ("SL", pytest.approx(px(side, SLB)))
    assert all(p.pnl < 0 for p in zb.positions_of(s))


@pytest.mark.parametrize("side", SIDES)
def test_sl_first_when_both_positions_filled_earlier_and_a_later_bar_holds_sl_and_tp(side: str) -> None:
    # P1 and P2 filled on earlier bars, so the TP is allowed: a bar holding both the SL and the TP exits on the SL
    rows = [(102.0, 102.5, 101.2, 102.0), (102.0, 102.0, 97.5, 98.0), (98.0, 111.0, 94.0, 100.0)]
    s = sim(side, rows)
    assert [f.j for f in s.fills] == [J0, J0 + 1]
    assert (s.how, s.exit_j, s.exit_price) == ("SL", J0 + 2, pytest.approx(px(side, SLB)))
    # the control: the same later bar without the SL reaches the TP and takes it
    tp = sim(side, [*rows[:2], (98.0, 111.0, 96.0, 100.0)])
    assert (tp.how, tp.exit_price) == ("TP", pytest.approx(px(side, TPB)))


@pytest.mark.parametrize("side", SIDES)
def test_a_bar_filling_both_positions_and_stopping_out_on_the_fill_bar(side: str) -> None:
    s = sim(side, [(102.0, 102.5, 94.0, 100.0)])
    assert [(f.name, f.j) for f in s.fills] == [("P1", J0), ("P2", J0)]
    assert (s.how, s.exit_j) == ("SL", J0)  # on a fill bar only the SL counts
    ps = zb.positions_of(s)
    assert [p.pnl for p in ps] == [pytest.approx(SLB - P1B), pytest.approx(SLB - P2B)]
    assert zb.setup_r(s) == pytest.approx(-1.0)  # an SL exit loses exactly the risk


@pytest.mark.parametrize("side", SIDES)
def test_both_positions_exit_together_and_r_is_the_sum_ratio(side: str) -> None:
    s = sim(side, [(102.0, 102.5, 101.2, 102.0), (102.0, 102.0, 97.0, 98.0), (98.0, 111.0, 98.0, 110.0)])
    assert [f.j for f in s.fills] == [J0, J0 + 1] and (s.how, s.exit_j) == ("TP", J0 + 2)
    pnl, risk = (TPB - P1B) + (TPB - P2B), (P1B - SLB) + (P2B - SLB)
    assert zb.setup_r(s) == pytest.approx(pnl / risk)
    assert sum(p.pnl for p in zb.positions_of(s)) == pytest.approx(pnl)


@pytest.mark.parametrize("side", SIDES)
def test_orders_stay_after_the_first_fill_even_past_the_withdrawal_level(side: str) -> None:
    rows = [(102.0, 102.5, 101.2, 102.0), (102.0, 106.0, 101.5, 105.0), (105.0, 105.0, 97.5, 98.0)]
    s = sim(side, [*rows, (98.0, 111.0, 98.0, 110.0)])
    assert [f.name for f in s.fills] == ["P1", "P2"] and s.how == "TP"  # high - L 6 >= 5 did not withdraw P2


def test_the_spread_on_each_side() -> None:
    sp8 = [0.0] * 8
    # BUY: a fill needs the ASK (low + spread) at the price; the SL and TP read the bid
    assert (
        sim("BUY", [(102.0, 102.5, 101.2, 102.0)], spreads=[*sp8, 0.2 / 0.01]).outcome == "pending"
    )  # 101.4
    assert sim("BUY", [(102.0, 102.5, 101.1, 102.0)], spreads=[*sp8, 0.2 / 0.01]).outcome == "traded"  # 101.3
    held = [(102.0, 102.5, 101.1, 102.0), (102.0, 103.0, 95.1, 102.0)]  # the SL reads the bid low: 95.1 > 95
    assert sim("BUY", held, spreads=[*sp8, 20.0, 50.0]).how == "open"
    hit = [(102.0, 102.5, 101.1, 102.0), (102.0, 103.0, 94.9, 102.0)]  # the bid low 94.9 <= 95: stopped
    assert sim("BUY", hit, spreads=[*sp8, 20.0, 50.0]).how == "SL"
    # SELL: a fill reads the bid high, no spread; the SL is the ASK (high + spread), the TP too (low + spread)
    v = mk_visit("SELL")
    h = mirror(HIST)
    no_fill = zb.simulate_setup(v, ebars([*h, (98.0, 98.6, 97.5, 98.0)], [*sp8, 50.0]), P, 0.01)
    assert no_fill.outcome == "pending"  # 98.6 < 98.6842: a spread added to the bid would have filled it
    fill = zb.simulate_setup(v, ebars([*h, (98.0, 98.69, 97.5, 98.0)], [*sp8, 50.0]), P, 0.01)
    assert [f.name for f in fill.fills] == ["P1"]
    sl = [(98.0, 98.69, 97.5, 98.0), (98.0, 104.6, 98.0, 100.0)]
    with_sp = zb.simulate_setup(v, ebars(h + sl, [*sp8, 0.0, 50.0]), P, 0.01)
    assert with_sp.how == "SL"  # 104.6 + 0.5 >= 105
    assert zb.simulate_setup(v, ebars(h + sl, [0.0] * 10), P, 0.01).how == "open"
    tp = [(98.0, 98.69, 97.5, 98.0), (98.0, 98.0, 89.6, 90.0), (90.0, 90.0, 89.4, 90.0)]
    t1 = zb.simulate_setup(v, ebars(h + tp, [*sp8, 0.0, 50.0, 50.0]), P, 0.01)
    assert (t1.how, t1.exit_j) == (
        "TP",
        J0 + 2,
    )  # 89.6 + 0.5 = 90.1 > 90 on bar 9; 89.4 + 0.5 <= 90 on bar 10


@pytest.mark.parametrize("side", SIDES)
def test_withdrawal_at_the_edge_and_inside_it(side: str) -> None:
    at = sim(side, [QUIET, (102.0, 105.0, 101.6, 104.0)])  # high - L == 5 == away_frac x S: withdrawn
    assert (at.outcome, at.end_j) == ("no fill", J0 + 1) and at.end_time == T0 + Q * (J0 + 2)
    inside = sim(side, [QUIET, (102.0, 104.99, 101.6, 104.0), QUIET, QUIET])
    assert inside.outcome == "pending"  # not withdrawn: the data ends
    first = sim(side, [(102.0, 110.0, 101.6, 104.0), QUIET])  # the first bar (j0) is never a withdrawal
    assert first.outcome == "pending"


@pytest.mark.parametrize("side", SIDES)
def test_expiry_counts_exec_bars_and_pending_at_the_end_of_the_data(side: str) -> None:
    life = P.order_life_h * zb.PER_H["M15"]
    s = sim(side, [QUIET] * (life + 1))  # j0 + 192: expired on that bar when the data goes on past it
    assert (s.outcome, s.end_j) == ("no fill", J0 + life)
    p = sim(side, [QUIET] * life)  # ... and pending when the data ends right before it
    assert (p.outcome, p.end_j) == ("pending", J0 + life - 1) and p.end_time == T0 + Q * (J0 + life)
    assert sim(side, [QUIET] * 3).outcome == "pending"


@pytest.mark.parametrize("side", SIDES)
def test_open_at_the_end_of_the_data_exits_at_the_last_close(side: str) -> None:
    s = sim(side, [(102.0, 102.5, 101.2, 102.0), (102.0, 103.0, 101.0, 103.0)])
    assert (s.outcome, s.how, s.exit_j, s.end_j) == ("traded", "open", J0 + 1, J0 + 1)
    assert s.exit_price == pytest.approx(px(side, 103.0))
    assert zb.positions_of(s)[0].pnl == pytest.approx(103.0 - P1B)


def cold_hist(last_close: float) -> list[Row]:
    """Row 4 opens at 105 and row 7 closes at ``last_close``: the closed-hour run toward a BUY line."""
    return [*[flat(102.0)] * 4, flat(105.0), flat(102.0), flat(102.0), flat(last_close)]


@pytest.mark.parametrize("side", SIDES)
def test_the_closed_hour_cancel_at_its_edge(side: str) -> None:
    # open_{j-4} = 105, close_{j-1} = 101.6: ran 3.4 toward the line >= cancel_frac x S = 3.3333
    s = sim(side, [(102.0, 102.5, 101.2, 102.0)], hist=cold_hist(101.6))
    assert (s.outcome, s.end_j, s.fills) == ("cancel", J0, ())
    assert sim(side, [flat(102.0)], hist=cold_hist(101.67)).outcome == "pending"  # 3.33 < 3.3333: no cancel


@pytest.mark.parametrize("side", SIDES)
def test_the_fill_moment_cancel_stops_the_whole_setup_p2_is_not_tested(side: str) -> None:
    # the hour before ran 3 toward the line (no closed-hour cancel); a fill at P1 would be 3.68 away from
    # open_{j-4} = 105: the fill-moment cancel; the bar also reaches P2, which must not fill
    hist = [*[flat(102.0)] * 4, flat(105.0), *[flat(102.0)] * 3]
    bar = (102.0, 102.5, 97.0, 100.0)
    s = sim(side, [bar], hist=hist)
    assert (s.outcome, s.fills, s.end_j) == ("cancel", (), J0)
    assert [f.name for f in sim(side, [bar]).fills] == ["P1", "P2"]  # without the 105 open the bar fills both


@pytest.mark.parametrize("side", SIDES)
def test_no_cancel_once_a_position_has_filled(side: str) -> None:
    hist = [
        *[flat(102.0)] * 5,
        flat(105.0),
        flat(102.0),
        flat(102.0),
    ]  # open_5 = 105: from j = 9 a run of 3.8
    filled = [(102.0, 102.5, 101.2, 101.6), (101.6, 102.0, 101.2, 101.5), (101.5, 111.0, 101.5, 110.5)]
    s = sim(side, filled, hist=hist)
    assert [f.name for f in s.fills] == ["P1"] and (s.how, s.exit_j) == ("TP", J0 + 2)
    # the control: nothing filled, and the same run cancels the setup on bar 9
    c = sim(side, [(102.0, 102.5, 101.6, 101.6), QUIET], hist=hist)
    assert (c.outcome, c.end_j) == ("cancel", J0 + 1)


@pytest.mark.parametrize("side", SIDES)
def test_exec_history_guard(side: str) -> None:
    with pytest.raises(zb.ZoneError, match="no hour of history"):
        zb.simulate_setup(mk_visit(side, j0=3), ebars([*HIST, flat(102.0)]), P, 0.01)


# --- every comparison of rules 6 - 7 at its exact edge (binary-representable numbers) -----------------------
# line 1000, step 64, point 0.25 (one spread point = 0.25): P1 = 1008, P2 = 984, SL = 968, TP = 1064,
# withdrawal at 32 beyond the line, both cancels at a run of 16 toward it

EXP = ZoneParams(
    near_frac=0.125,
    p1_frac=0.125,
    p2_frac=0.25,
    sl_frac=0.5,
    away_frac=0.5,
    cancel_frac=0.25,
    tp_steps=1,
    be_mode="off",
)
HX: list[Row] = [flat(1020.0)] * 8  # 8 flat bars well above the line (a BUY comes down to 1000)
PT = 0.25


def mirror2(rows: list[Row]) -> list[Row]:
    return [(2000 - o, 2000 - lo, 2000 - h, 2000 - c) for o, h, lo, c in rows]


def simx(
    side: str,
    rows: list[Row],
    hist: list[Row] | None = None,
    spreads: list[float] | None = None,
    direct: bool = False,
) -> zb.Setup:
    """A visit on line 1000, S 64 at exec row 8. ``rows``/``hist`` are for a BUY and mirrored (p -> 2000 - p)
    for a SELL, unless ``direct`` (written for the SELL as it is)."""
    allrows = (hist if hist is not None else HX) + rows
    if side == "SELL" and not direct:
        allrows = mirror2(allrows)
    v = mk_visit(side, line=1000.0, step=64.0)
    return zb.simulate_setup(v, ebars(allrows, spreads), EXP, PT)


@pytest.mark.parametrize("side", SIDES)
def test_edge_withdrawal_exactly_away_frac_beyond_the_line(side: str) -> None:
    quiet: Row = (1020.0, 1020.0, 1020.0, 1020.0)
    assert simx(side, [quiet, (1020.0, 1032.0, 1020.0, 1020.0)]).outcome == "no fill"  # 32 == away: withdrawn
    assert simx(side, [quiet, (1020.0, 1031.75, 1020.0, 1020.0)]).outcome == "pending"
    assert simx(side, [(1020.0, 1032.0, 1020.0, 1020.0), quiet]).outcome == "pending"  # j0 itself never


@pytest.mark.parametrize("side", SIDES)
def test_edge_the_closed_hour_cancel_at_exactly_cancel_frac(side: str) -> None:
    def hist(last: float) -> list[Row]:  # open_{j-4} = 1036, close_{j-1} = last
        return [*[flat(1020.0)] * 4, flat(1036.0), flat(1020.0), flat(1020.0), flat(last)]

    quiet = [flat(1020.0)]
    assert simx(side, quiet, hist=hist(1020.0)).outcome == "cancel"  # run 16 == cancel_frac x S
    assert simx(side, quiet, hist=hist(1020.25)).outcome == "pending"  # 15.75


@pytest.mark.parametrize("side", SIDES)
def test_edge_the_fill_moment_cancel_at_exactly_cancel_frac(side: str) -> None:
    def hist(open4: float) -> list[Row]:
        return [*[flat(1020.0)] * 4, flat(open4), *[flat(1020.0)] * 3]

    bar: Row = (1020.0, 1020.0, 1008.0, 1010.0)  # low == P1
    assert simx(side, [bar], hist=hist(1024.0)).outcome == "cancel"  # (1008 - 1024) toward = 16 == cancel
    s = simx(side, [bar], hist=hist(1023.75))  # 15.75: no cancel, P1 fills
    assert [f.name for f in s.fills] == ["P1"]


@pytest.mark.parametrize("side", SIDES)
def test_edge_fills_at_exactly_the_price(side: str) -> None:
    assert [f.name for f in simx(side, [(1020.0, 1020.0, 1008.0, 1010.0)]).fills] == ["P1"]  # low == P1
    assert simx(side, [(1020.0, 1020.0, 1008.25, 1010.0)]).fills == ()
    two = simx(side, [(1020.0, 1020.0, 984.0, 990.0)])  # low == P2 (the same bar reaches P1 too)
    assert [f.name for f in two.fills] == ["P1", "P2"]
    one = simx(side, [(1020.0, 1020.0, 984.25, 990.0)])
    assert [f.name for f in one.fills] == ["P1"]


def test_edge_a_buy_fills_on_the_ask_exactly_at_the_price() -> None:
    bar: Row = (1020.0, 1020.0, 1007.75, 1010.0)
    assert simx("BUY", [bar], spreads=[*[0.0] * 8, 1.0]).fills[0].name == "P1"  # 1007.75 + 0.25 == 1008
    assert simx("BUY", [(1020.0, 1020.0, 1008.0, 1010.0)], spreads=[*[0.0] * 8, 1.0]).fills == ()


FILL_BAR: Row = (1020.0, 1020.0, 1008.0, 1010.0)  # fills P1 only (BUY frame)


@pytest.mark.parametrize("side", SIDES)
def test_edge_sl_exactly_at_the_price_and_one_tick_short(side: str) -> None:
    s = simx(side, [FILL_BAR, (1010.0, 1010.0, 968.0, 970.0)])
    assert (s.how, s.exit_j) == ("SL", J0 + 1)  # low == SL
    assert simx(side, [FILL_BAR, (1010.0, 1010.0, 968.25, 970.0)]).how == "open"


@pytest.mark.parametrize("side", SIDES)
def test_edge_tp_exactly_at_the_price_and_one_tick_short(side: str) -> None:
    s = simx(side, [FILL_BAR, (1010.0, 1064.0, 1010.0, 1010.0)])
    assert (s.how, s.exit_j) == ("TP", J0 + 1)  # high == TP
    assert simx(side, [FILL_BAR, (1010.0, 1063.75, 1010.0, 1010.0)]).how == "open"


def test_edge_a_sell_stop_and_target_on_the_ask() -> None:
    base = mirror2(HX)
    fill: Row = (980.0, 992.0, 980.0, 990.0)  # high == P1 (992)
    sp = [0.0] * 8
    # SL 1032: high + spread >= SL
    hit = simx(
        "SELL", [fill, (990.0, 1031.75, 990.0, 990.0)], hist=base, spreads=[*sp, 0.0, 1.0], direct=True
    )
    assert (hit.how, hit.exit_j) == ("SL", J0 + 1)  # 1031.75 + 0.25 == 1032
    miss = simx(
        "SELL", [fill, (990.0, 1031.5, 990.0, 990.0)], hist=base, spreads=[*sp, 0.0, 1.0], direct=True
    )
    assert miss.how == "open"
    # TP 936: low + spread <= TP
    tp = simx("SELL", [fill, (990.0, 990.0, 935.75, 940.0)], hist=base, spreads=[*sp, 0.0, 1.0], direct=True)
    assert (tp.how, tp.exit_j) == ("TP", J0 + 1)  # 935.75 + 0.25 == 936
    no = simx("SELL", [fill, (990.0, 990.0, 936.0, 940.0)], hist=base, spreads=[*sp, 0.0, 1.0], direct=True)
    assert no.how == "open"


@pytest.mark.parametrize("side", SIDES)
def test_edge_the_tp_waits_for_a_bar_after_every_fill(side: str) -> None:
    s = simx(side, [(1020.0, 1064.0, 1008.0, 1030.0), (1030.0, 1064.0, 1030.0, 1030.0)])
    assert (s.how, s.exit_j) == ("TP", J0 + 1)  # the fill bar reaches the TP price and does not exit


def test_edge_the_exec_history_guard_at_exactly_one_hour() -> None:
    rows = [*[flat(1020.0)] * 5, flat(1020.0)]
    ok = zb.simulate_setup(mk_visit("BUY", line=1000.0, step=64.0, j0=4), ebars(rows), EXP, PT)  # j0 == per_h
    assert ok.outcome == "pending"
    with pytest.raises(zb.ZoneError, match="no hour of history"):
        zb.simulate_setup(mk_visit("BUY", line=1000.0, step=64.0, j0=3), ebars(rows), EXP, PT)


@pytest.mark.parametrize("side", SIDES)
def test_edge_pending_when_the_loop_runs_exactly_to_the_end(side: str) -> None:
    quiet = [flat(1020.0)] * 3
    s = simx(side, quiet)
    assert (s.outcome, s.end_j) == ("pending", J0 + 2)


def test_edge_an_sl_exit_must_lose_strictly() -> None:
    v = mk_visit("BUY", line=1000.0, step=64.0)
    flat_sl = zb.Setup(
        v, 1008.0, 984.0, 968.0, 1064.0, "traded", (zb.Fill("P1", 0, 968.0),), 0, 968.0, "SL", 0, T0
    )
    with pytest.raises(zb.ZoneError, match="SL exit"):
        zb.positions_of(flat_sl)  # pnl == 0 exactly
    ok = zb.Setup(
        v, 1008.0, 984.0, 968.0, 1064.0, "traded", (zb.Fill("P1", 0, 968.25),), 0, 968.0, "SL", 0, T0
    )
    assert zb.positions_of(ok)[0].pnl == -0.25
    tp = zb.Setup(
        v, 1008.0, 984.0, 968.0, 1064.0, "traded", (zb.Fill("P1", 0, 1064.0),), 0, 1064.0, "TP", 0, T0
    )
    assert zb.positions_of(tp)[0].pnl == 0.0  # only an SL exit is checked


def test_edge_a_chart_with_zero_usd_is_a_loss() -> None:
    s = fake_setup("2025-01-05 10:00", 0.0)
    assert zb.chart_name(1, s, 0.0) == "01_loss_20250105.png"
    assert zb.chart_name(1, s, 0.25) == "01_win_20250105.png"
    assert zb.chart_name(1, s, -0.25) == "01_loss_20250105.png"


# --- the break-even (rule 7) at its exact edges: line 1000, S 64, point 0.25 -------------------------------
# BUY: P1 1008, P2 984, SL 968, TP 1064. With only P1 filled: avg 1008, mid = 1008 + 0.5 x 56 = 1036.
# With P1 and P2 filled: avg 996, mid = 996 + 0.5 x 68 = 1030.

EXB = replace(EXP, be_mode="entry", be_frac=0.5)
SP8 = [0.0] * 8


def px2(side: str, p: float) -> float:
    return p if side == "BUY" else 2000.0 - p


def simb(
    side: str,
    rows: list[Row],
    spreads: list[float] | None = None,
    params: ZoneParams = EXB,
    direct: bool = False,
    hist: list[Row] | None = None,
) -> zb.Setup:
    allrows = (hist if hist is not None else (mirror2(HX) if direct else HX)) + rows
    if side == "SELL" and not direct:
        allrows = mirror2(allrows)
    v = mk_visit(side, line=1000.0, step=64.0)
    return zb.simulate_setup(v, ebars(allrows, spreads), params, PT)


F1: Row = (1020.0, 1020.0, 1008.0, 1010.0)  # fills P1 only, no trigger (high 1020 < 1036)
QB: Row = (1030.0, 1030.0, 1030.0, 1030.0)  # a quiet bar above the break-even SL


@pytest.mark.parametrize("side", SIDES)
def test_be_triggers_exactly_at_mid_on_the_fill_bar_and_works_from_the_next_bar(side: str) -> None:
    trig: Row = (1020.0, 1036.0, 1008.0, 1030.0)  # fills P1, high == mid: the break-even goes on
    s = simb(side, [trig, (1030.0, 1030.0, 1008.0, 1010.0)])  # the next bar's low == avg (the new SL)
    assert (s.how, s.exit_j, s.exit_price) == ("BE", J0 + 1, pytest.approx(px2(side, 1008.0)))
    assert (s.be_sl, s.be_j) == (pytest.approx(px2(side, 1008.0)), J0)
    assert zb.positions_of(s)[0].pnl == pytest.approx(0.0)
    short = simb(side, [(1020.0, 1035.75, 1008.0, 1030.0), (1030.0, 1030.0, 1008.0, 1010.0)])
    assert (short.how, short.be_sl) == (
        "open",
        None,
    )  # one tick short of mid: no break-even, the SL stays at 968
    assert simb(side, [trig, (1030.0, 1030.0, 1008.25, 1010.0)]).how == "open"  # the new SL is not reached


@pytest.mark.parametrize("side", SIDES)
def test_be_triggers_on_a_later_bar_at_mid_exactly(side: str) -> None:
    s = simb(side, [F1, (1020.0, 1036.0, 1020.0, 1030.0), (1030.0, 1030.0, 1008.0, 1010.0)])
    assert (s.be_j, s.how, s.exit_j) == (J0 + 1, "BE", J0 + 2)
    assert simb(side, [F1, (1020.0, 1035.75, 1020.0, 1030.0), (1030.0, 1030.0, 1008.0, 1010.0)]).be_sl is None


@pytest.mark.parametrize("side", SIDES)
def test_the_sl_does_not_move_on_the_trigger_bar_itself(side: str) -> None:
    # the trigger bar also trades down to the new SL (1008): no exit on it - the SL moves from the next bar
    s = simb(side, [(1020.0, 1036.0, 1008.0, 1030.0), QB])
    assert (s.be_j, s.how) == (J0, "open")


@pytest.mark.parametrize("side", SIDES)
def test_a_bar_with_an_exit_does_not_trigger_the_break_even(side: str) -> None:
    s = simb(side, [F1, (1020.0, 1040.0, 960.0, 1000.0)])  # holds the SL (968) and a high above mid
    assert (s.how, s.exit_price, s.be_sl) == ("SL", pytest.approx(px2(side, 968.0)), None)


@pytest.mark.parametrize("side", SIDES)
def test_an_unfilled_p2_is_cancelled_by_the_break_even_and_never_fills_after(side: str) -> None:
    s = simb(side, [(1020.0, 1036.0, 1008.0, 1030.0), QB, (1030.0, 1030.0, 984.0, 990.0)])
    assert [f.name for f in s.fills] == ["P1"] and (s.how, s.exit_j) == (
        "BE",
        J0 + 2,
    )  # P2's price was reached
    off = simb(side, [(1020.0, 1036.0, 1008.0, 1030.0), QB, (1030.0, 1030.0, 984.0, 990.0)], params=EXP)
    assert [f.name for f in off.fills] == ["P1", "P2"]  # without the break-even P2 fills on that bar


@pytest.mark.parametrize("side", SIDES)
def test_a_p2_that_filled_before_the_trigger_is_kept_and_the_average_uses_both(side: str) -> None:
    both: Row = (1020.0, 1020.0, 984.0, 1000.0)  # P1 and P2 fill; avg 996, mid 1030
    s = simb(side, [both, (1000.0, 1029.75, 1000.0, 1020.0), (1020.0, 1020.0, 1000.0, 1010.0)])
    assert [f.name for f in s.fills] == ["P1", "P2"] and s.be_sl is None  # one tick short of mid
    s = simb(side, [both, (1000.0, 1030.0, 1000.0, 1020.0), (1020.0, 1020.0, 996.0, 1000.0)])
    assert (s.be_j, s.be_sl, s.how) == (J0 + 1, pytest.approx(px2(side, 996.0)), "BE")
    ps = zb.positions_of(s)
    assert [p.pnl for p in ps] == [
        pytest.approx(-12.0),
        pytest.approx(12.0),
    ]  # exit at avg 996: P1 -12, P2 +12
    assert [p.risk for p in ps] == [pytest.approx(40.0), pytest.approx(16.0)]  # risk on the ORIGINAL SL 968
    assert zb.setup_r(s) == pytest.approx(0.0)


@pytest.mark.parametrize("side", SIDES)
def test_the_break_even_does_not_move_once_on_and_the_tp_stays(side: str) -> None:
    rows = [(1020.0, 1036.0, 1008.0, 1030.0), (1030.0, 1040.0, 1030.0, 1040.0), QB]
    s = simb(side, rows, spreads=[*SP8, 0.0, 8.0, 0.0])
    assert (
        s.be_sl == pytest.approx(px2(side, 1008.0)) and s.be_j == J0
    )  # set once: a later bar reaching mid again changes nothing
    tp = simb(side, [(1020.0, 1036.0, 1008.0, 1030.0), (1030.0, 1064.0, 1030.0, 1060.0)])
    assert (tp.how, tp.exit_price) == ("TP", pytest.approx(px2(side, 1064.0)))  # the TP still takes it


def test_be_buy_sl_carries_the_trigger_bars_spread_and_exits_on_the_bid() -> None:
    trig: Row = (1020.0, 1036.0, 1007.5, 1030.0)
    s = simb(
        "BUY", [trig, (1030.0, 1030.0, 1008.5, 1010.0)], spreads=[*SP8, 2.0, 8.0]
    )  # 2 points on the trigger
    assert (s.be_sl, s.how, s.exit_price) == (
        1008.5,
        "BE",
        1008.5,
    )  # avg + 2 x 0.25; the exit reads the bid low
    assert zb.positions_of(s)[0].pnl == pytest.approx(0.5)  # a BE exit may be above 0: no assertion
    assert simb("BUY", [trig, (1030.0, 1030.0, 1008.75, 1010.0)], spreads=[*SP8, 2.0, 0.0]).how == "open"
    # the trigger is judged on the bid: the spread does not help a BUY reach mid
    near: Row = (1020.0, 1035.75, 1007.0, 1030.0)
    assert simb("BUY", [near, QB], spreads=[*SP8, 4.0, 0.0]).be_sl is None


def test_be_sell_trigger_is_judged_on_the_ask_and_the_sl_on_the_ask_too() -> None:
    h = mirror2(HX)
    fill: Row = (980.0, 992.0, 980.0, 990.0)  # SELL: P1 992 (high == P1); avg 992; TP 936; mid 964
    sp = [*SP8, 0.0]

    def run(trigger_low: float, trigger_sp: float, nxt: Row, nxt_sp: float) -> zb.Setup:
        rows = [fill, (990.0, 990.0, trigger_low, 970.0), nxt]
        return simb("SELL", rows, spreads=[*sp, trigger_sp, nxt_sp], direct=True, hist=h)

    s = run(963.5, 2.0, (970.0, 991.25, 970.0, 980.0), 1.0)  # low + spread = 964 == mid: triggered
    assert s.be_j == J0 + 1 and s.be_sl == 991.5  # avg + sgn x spread = 992 - 0.5
    assert (s.how, s.exit_price) == ("BE", 991.5)  # next bar: high 991.25 + 0.25 == 991.5
    assert run(963.75, 2.0, (970.0, 991.25, 970.0, 980.0), 1.0).be_sl is None  # 964.25 > mid: no trigger
    assert run(963.5, 2.0, (970.0, 991.0, 970.0, 980.0), 1.0).how == "open"  # 991 + 0.25 < 991.5


@pytest.mark.parametrize("side", SIDES)
def test_p2_filling_on_the_trigger_bar_is_in_the_average(side: str) -> None:
    # P1 fills first (avg 1008, mid 1036 would not be reached). A later bar fills P2 (984) and reaches 1030: with
    # both fills avg = 996 and mid = 1030, so the break-even goes on that very bar, at the average of both
    s = simb(side, [F1, (1020.0, 1030.0, 984.0, 1000.0), (1020.0, 1020.0, 996.0, 1000.0)])
    assert [(f.name, f.j) for f in s.fills] == [("P1", J0), ("P2", J0 + 1)]
    assert (s.be_j, s.be_sl) == (J0 + 1, pytest.approx(px2(side, 996.0)))
    assert (s.how, s.exit_j, s.exit_price) == ("BE", J0 + 2, pytest.approx(px2(side, 996.0)))


def test_be_frac_sets_the_trigger_price_and_off_changes_nothing() -> None:
    quarter = replace(EXB, be_frac=0.25)  # mid = 1008 + 0.25 x 56 = 1022
    assert simb("BUY", [F1, (1020.0, 1022.0, 1020.0, 1020.0)], params=quarter).be_j == J0 + 1
    assert simb("BUY", [F1, (1020.0, 1021.75, 1020.0, 1020.0)], params=quarter).be_sl is None
    off = simb("BUY", [(1020.0, 1036.0, 1008.0, 1030.0), (1030.0, 1030.0, 1008.0, 1010.0)], params=EXP)
    assert (off.how, off.be_sl, off.be_j) == ("open", None, None)  # be_mode off: the current behaviour


def test_be_columns_in_the_positions_rows() -> None:
    s = simb("BUY", [(1020.0, 1036.0, 1008.0, 1030.0), (1030.0, 1030.0, 1008.0, 1010.0)])
    ex = ebars([*HX, (1020.0, 1036.0, 1008.0, 1030.0), (1030.0, 1030.0, 1008.0, 1010.0)])
    (row,) = zb.position_rows([zb.Outcome(s.visit, "traded", s)], ex)
    assert row["sl"] == 968.0 and row["be_sl"] == 1008.0 and row["how"] == "BE"
    assert row["be_time"] == zb.thai(ex.close_time.iloc[J0])  # the close of the bar that turned it on
    none = simb("BUY", [F1, QB])
    (r2,) = zb.position_rows([zb.Outcome(none.visit, "traded", none)], ebars([*HX, F1, QB]))
    assert r2["be_time"] == "" and r2["be_sl"] is None
    assert "be_sl" in zb.POSITION_COLUMNS and "be_time" in zb.POSITION_COLUMNS
    stats = zb.summary_stats([zb.Outcome(s.visit, "traded", s)])
    assert stats["be_exits"] == 1 and stats["setups"] == 1


def constructed_be_run() -> tuple[zb.Bars, zb.RunResult]:
    exec_rows = {
        N_FILL - 1: [flat(102.0)] * 4,
        # bar 0 fills P1 (101.3158); bar 1 reaches mid (105.66): break-even on; bar 2 trades down to it: BE exit
        N_FILL: [
            (102.0, 102.5, 100.5, 101.0),
            (101.0, 106.0, 100.9, 105.0),
            (105.0, 105.0, 101.3, 101.5),
            FILL,
        ],
    }
    bars = make_bars([BUY_100, FILL, FILL], exec_rows)
    vs = visits(bars)
    ex = zb.ExecBars.from_frame(bars.m15)
    return bars, zb.RunResult([GRID], vs, zb.apply_rules(vs, ex, PB, bars.point), ex)


def test_the_chart_draws_the_be_sl_dashed_from_the_next_bar_and_the_title_says_be(tmp_path: Path) -> None:
    bars, res = constructed_be_run()
    s = zb.traded(res.outcomes)[0]
    assert (s.how, s.be_j, s.exit_j) == ("BE", 4 * N_FILL + 1, 4 * N_FILL + 2)
    seen: dict[str, Any] = {}

    def read(fig: Any) -> None:
        seen["title"] = fig.get_suptitle()
        for i, ax in enumerate(fig.axes):
            seen[f"be{i}"] = ax.collections[3]  # after the wicks, SL and TP: the dashed BE SL
            seen[f"x{i}"] = ax.collections[3].get_segments()[0][0][0]
            seen[f"dash{i}"] = ax.collections[3].get_linestyle()
            seen[f"text{i}"] = [t.get_text() for t in ax.texts if "BE SL" in t.get_text()]

    zb.draw_chart(tmp_path / "c.png", s, GRID, bars, PB, 0.0, on_figure=read)
    assert "BE" in seen["title"].split("|")[-2]  # the title gives how
    first, last = bars.m15["close_time"].iloc[s.fills[0].j], bars.m15["close_time"].iloc[s.exit_j]
    wins = [
        zb.chart_window(bars.h1, first - pd.Timedelta(days=6), last + pd.Timedelta(days=1)),
        zb.chart_window(bars.m15, first - pd.Timedelta(hours=10), last + pd.Timedelta(hours=3)),
    ]
    # the dashed segment starts at the bar after the trigger: exec row +2 in the exec panel; the H1 panel bar of it
    assert seen["x1"] == wins[1].index.get_loc(4 * N_FILL + 2)
    assert seen["x0"] == wins[0].index.get_loc(N_FILL)
    assert seen["text0"] == seen["text1"] and len(seen["text1"]) == 1 and "from the line" in seen["text1"][0]
    assert seen["dash0"][0][1] is not None and seen["dash1"][0][1] is not None  # dashed, not solid
    assert f"{s.be_sl:.2f}" in seen["text1"][0]


def test_a_chart_whose_be_trigger_is_the_last_bar_draws_no_dashed_segment(tmp_path: Path) -> None:
    bars, res = constructed_be_run()
    cut_rows = 4 * N_FILL + 2  # the data ends on the trigger bar (exec row 4 N + 1)
    m15 = bars.m15.iloc[:cut_rows].reset_index(drop=True)
    short = zb.Bars(bars.d1, bars.h4, bars.h1, m15, bars.m5, bars.point)
    ex = zb.ExecBars.from_frame(m15)
    outs = zb.apply_rules(res.visits, ex, PB, bars.point)
    s = zb.traded(outs)[0]
    assert (s.how, s.be_j, s.exit_j) == ("open", cut_rows - 1, cut_rows - 1)
    counts: list[int] = []
    zb.draw_chart(
        tmp_path / "c.png",
        s,
        GRID,
        short,
        PB,
        0.0,
        on_figure=lambda f: counts.extend(len(a.collections) for a in f.axes),
    )
    assert counts == [3, 3]  # wicks, SL and TP only: no segment from a bar that does not exist


# --- rule 8: the order of the skips and the busy reference ------------------------------------------------


def run_apply(visits: list[zb.Visit], rows: list[Row]) -> list[zb.Outcome]:
    return zb.apply_rules(visits, ebars(rows), P, 0.01)


def test_skip_order_momentum_busy_abnormal_trend() -> None:
    v, rows = mk_visit(), [*HIST, QUIET, QUIET, QUIET]
    assert run_apply([replace(v, mom_body=2.0, ema_dist=9.0, share=0.0)], rows)[0].reason == "momentum"
    assert run_apply([replace(v, ema_dist=9.0, share=0.0)], rows)[0].reason == "abnormal"
    assert run_apply([replace(v, share=0.0)], rows)[0].reason == "trend"
    # busy comes before abnormal and trend: a pending first setup, then a visit that is abnormal AND trend
    first, later = mk_visit(j0=8), mk_visit(j0=9, ema_dist=9.0, share=0.0)
    assert [o.reason for o in run_apply([first, later], rows)] == ["pending", "busy"]


def test_busy_reserves_through_withdrawn_cancelled_and_pending_setups_and_the_equality_edge() -> None:
    rows = [*HIST, QUIET, (102.0, 105.0, 101.6, 104.0), *[QUIET] * 6]  # v1 is withdrawn on row 9
    v1, v2, v3 = mk_visit(j0=8), mk_visit(j0=10), mk_visit(j0=11)
    out = run_apply([v1, v2, v3], rows)
    assert [o.reason for o in out] == ["no fill", "busy", "pending"]
    assert out[1].visit.time == out[0].setup.end_time  # type: ignore[union-attr]  # equal to the end: busy
    # a skipped visit reserves nothing: a momentum skip between does not stop the next
    vm = replace(mk_visit(j0=9), mom_body=2.0)
    assert [o.reason for o in run_apply([v1, vm, v3], rows)] == ["no fill", "momentum", "pending"]
    # cancelled setups reserve to the cancel bar's close
    c = run_apply([mk_visit(j0=8), mk_visit(j0=8)], [*cold_hist(101.6), *[(102.0, 102.5, 101.2, 102.0)] * 2])
    assert [o.reason for o in c] == ["cancel", "busy"]
    # pending reserves to the last bar
    p = run_apply([mk_visit(j0=8), mk_visit(j0=10)], [*HIST, *[QUIET] * 4])
    assert [o.reason for o in p] == ["pending", "busy"]


# --- rule 11: the numbers ------------------------------------------------------------------------------


def fake_setup(when: str, usd: float, how: str = "TP") -> zb.Setup:
    v = mk_visit(time=ts(when, TH), line=100.0)
    f = zb.Fill("P1", 0, 100.0)
    return zb.Setup(v, 100.0, 98.0, 95.0, 110.0, "traded", (f,), 0, 100.0 + usd, how, 0, ts("2025-01-01"))


def test_summary_drawdown_negative_months_and_open_apart() -> None:
    setups = [
        fake_setup("2025-01-05 10:00", +10.0),
        fake_setup("2025-01-20 10:00", -4.0, "SL"),
        fake_setup("2025-02-03 10:00", -8.0, "SL"),
        fake_setup("2025-02-10 10:00", +3.0),
        fake_setup("2025-03-04 10:00", +20.0),
        fake_setup("2025-04-02 10:00", +5.0),
        fake_setup("2025-04-09 10:00", -5.0, "SL"),
        fake_setup("2025-03-10 10:00", +99.0, "open"),
    ]
    outs = [zb.Outcome(s.visit, "traded", s) for s in setups] + [zb.Outcome(mk_visit(), "pending", None)]
    st = zb.summary_stats(outs)
    # cumulative 10, 6, -2, 1, 21 against the peaks 10, 10, 10, 10, 21: the deepest is -12
    assert st["setups"] == 7 and st["open"] == 1 and st["pending"] == 1
    assert st["drawdown"] == pytest.approx(-12.0) and st["usd"] == pytest.approx(21.0)
    assert st["months"] == 4 and st["negative_months"] == 1  # February: -8 + 3 = -5; April sums to 0
    assert st["by_month"]["2025-02"] == pytest.approx(-5.0)
    assert st["tp_share"] == pytest.approx(4 / 7)  # the open one is not counted
    assert st["r_per_setup"] == pytest.approx(
        (2.0 - 0.8 - 1.6 + 0.6 + 4.0 + 1.0 - 1.0) / 7
    )  # usd / a risk of 5 each
    assert zb.chart_name(3, setups[0], 10.0) == "03_win_20250105.png"
    assert zb.chart_name(4, setups[1], -4.0) == "04_loss_20250120.png"
    assert zb.chart_name(5, setups[7], 99.0) == "05_open_20250310.png"


def test_the_summary_rows_name_the_zone_and_every_parameter() -> None:
    from eye.zone_config import FIELD_NAMES

    rows = dict(
        zb.summary_rows(
            "zone=XAUUSD/default@v1", P, ts("2023-10-01", TH), ts("2026-11-01", TH), zb.summary_stats([])
        )
    )
    assert rows["zone"] == "zone=XAUUSD/default@v1"
    assert all(f"param.{n}" in rows for n in FIELD_NAMES)
    assert rows["setups"] == 0 and rows["open"] == 0 and rows["pending"] == 0


# --- the charts and the command line --------------------------------------------------------------------


def constructed_run() -> tuple[zb.Bars, zb.RunResult]:
    exec_rows = {
        N_FILL - 1: [flat(102.0)] * 4,
        N_FILL: [(102.0, 102.5, 100.5, 101.0), (101.0, 111.0, 100.9, 110.5), FILL, FILL],
    }
    bars = make_bars([BUY_100, FILL, FILL], exec_rows)
    vs = visits(bars)
    ex = zb.ExecBars.from_frame(bars.m15)
    return bars, zb.RunResult([GRID], vs, zb.apply_rules(vs, ex, P, bars.point), ex)


def test_one_png_per_setup_with_the_expected_name(tmp_path: Path) -> None:
    bars, res = constructed_run()
    assert [o.reason for o in res.outcomes] == ["traded"]
    paths = zb.write_charts(tmp_path, res, bars, P)
    assert [p.name for p in paths] == ["01_win_20250111.png"]  # the visit's Thai date
    assert all(p.exists() and p.stat().st_size > 1000 for p in paths)
    assert [p.name for p in (tmp_path / "charts").iterdir()] == ["01_win_20250111.png"]


def test_the_outputs_of_a_run_are_written(tmp_path: Path) -> None:
    _, res = constructed_run()
    stats = zb.write_outputs(tmp_path, "zone=T/x@v1", P, ts("2025-01-01", TH), ts("2025-03-01", TH), res)
    assert stats["setups"] == 1
    pos = pd.read_csv(tmp_path / "positions.csv")
    assert list(pos["pos"]) == ["P1"] and pos["how"][0] == "TP"
    assert pos["pnl"][0] == pytest.approx(TPB - P1B, abs=1e-6) and pos["visit"][0].endswith("+07:00")
    vis = pd.read_csv(tmp_path / "visits.csv")
    assert list(vis["outcome"]) == ["traded"] and "trend_D1" in vis.columns and "share" in vis.columns
    assert list(pd.read_csv(tmp_path / "grids.csv").columns) == ["start", "anchor", "step", "cause"]
    summary = pd.read_csv(tmp_path / "summary.csv").set_index("name")["value"]
    assert summary["zone"] == "zone=T/x@v1" and summary["setups"] == "1"


def empty_result() -> zb.RunResult:
    ex = zb.ExecBars.from_frame(make_bars([FILL]).m15)
    return zb.RunResult([], [], [], ex)


def test_an_empty_run_still_writes_every_header(tmp_path: Path) -> None:
    zb.write_outputs(tmp_path, "zone=T/x@v1", P, ts("2025-01-01", TH), ts("2025-03-01", TH), empty_result())
    for name, cols in (
        ("positions.csv", zb.POSITION_COLUMNS),
        ("visits.csv", zb.VISIT_COLUMNS),
        ("grids.csv", zb.GRID_COLUMNS),
    ):
        df = pd.read_csv(tmp_path / name)
        assert list(df.columns) == cols and len(df) == 0, name
    assert (tmp_path / "positions.csv").read_text().strip() == ",".join(zb.POSITION_COLUMNS)
    summary = pd.read_csv(tmp_path / "summary.csv").set_index("name")["value"]
    assert summary["setups"] == "0" and summary["zone"] == "zone=T/x@v1"


def test_summary_floats_are_written_to_six_decimals(tmp_path: Path) -> None:
    _, res = constructed_run()
    zb.write_outputs(tmp_path, "zone=T/x@v1", P, ts("2025-01-01", TH), ts("2025-03-01", TH), res)
    text = (tmp_path / "summary.csv").read_text()
    lines = dict(line.split(",", 1) for line in text.splitlines()[1:])
    assert lines["usd"] == f"{TPB - P1B:.6f}" and lines["drawdown"] == "0.000000" and lines["setups"] == "1"
    assert lines["param.step_factor"] == "0.3333333333333333"  # parameters are text, exactly as stored


def test_a_new_run_removes_the_old_pngs_and_nothing_else(tmp_path: Path) -> None:
    bars, res = constructed_run()
    charts = tmp_path / "charts"
    charts.mkdir()
    (charts / "99_loss_20200101.png").write_bytes(b"old")
    (charts / "notes.txt").write_text("keep")
    paths = zb.write_charts(tmp_path, res, bars, P)
    assert (
        sorted(p.name for p in charts.iterdir()) == ["01_win_20250111.png", "notes.txt"] and len(paths) == 1
    )
    zb.write_charts(tmp_path, empty_result(), bars, P)  # a second run with no setups: no old chart is left
    assert [p.name for p in charts.iterdir()] == ["notes.txt"]


def test_the_drawn_artists_sit_on_bar_indices_across_closures_with_thai_tick_labels(tmp_path: Path) -> None:
    bars, res = constructed_run()
    shift = pd.Timedelta(hours=3)  # a closure: three clock hours with no bars

    def with_gap(df: pd.DataFrame, k: int) -> pd.DataFrame:
        d = df.copy()
        for col in ("open_time", "close_time"):
            d.loc[d.index >= k, col] = d.loc[d.index >= k, col] + shift
        return d

    # one closure 5 hours before the visit's hour, one right before it: the first fill is the first exec bar
    # after the reopening, and it opens the H1 bar of the visit
    h1, m15 = (
        with_gap(with_gap(bars.h1, N_FILL - 5), N_FILL),
        with_gap(with_gap(bars.m15, 4 * (N_FILL - 5)), 4 * N_FILL),
    )
    gapped = zb.Bars(bars.d1, bars.h4, h1, m15, bars.m5, bars.point)
    s = zb.traded(res.outcomes)[0]
    assert [(f.name, f.j) for f in s.fills] == [("P1", 4 * N_FILL)] and s.exit_j == 4 * N_FILL + 1
    first, last = m15["close_time"].iloc[s.fills[0].j], m15["close_time"].iloc[s.exit_j]
    windows = [
        zb.chart_window(h1, first - pd.Timedelta(days=6), last + pd.Timedelta(days=1)),
        zb.chart_window(m15, first - pd.Timedelta(hours=10), last + pd.Timedelta(hours=3)),
    ]
    fill_pos = [
        windows[0].index.get_loc(N_FILL),
        windows[1].index.get_loc(4 * N_FILL),
    ]  # the bar of each fill
    exit_pos = [windows[0].index.get_loc(N_FILL), windows[1].index.get_loc(4 * N_FILL + 1)]
    seen: dict[str, Any] = {}

    def read(fig: Any) -> None:
        for i, ax in enumerate(fig.axes):
            wicks, sl, tp = ax.collections[:3]
            seen[f"wick{i}"] = [seg[0][0] for seg in wicks.get_segments()]
            seen[f"body{i}"] = [r.get_x() + r.get_width() / 2 for r in ax.patches]
            seen[f"fill{i}"] = [ln.get_xdata()[0] for ln in ax.lines if ln.get_marker() in ("^", "v")]
            seen[f"exit{i}"] = [ln.get_xdata()[0] for ln in ax.lines if ln.get_marker() == "X"]
            seen[f"seg{i}"] = [sl.get_segments()[0][0][0], tp.get_segments()[0][0][0]]
            fig.canvas.draw()
            seen[f"ticks{i}"] = list(ax.get_xticks())
            seen[f"labels{i}"] = [t.get_text() for t in ax.get_xticklabels()]

    zb.draw_chart(tmp_path / "c.png", s, GRID, gapped, P, 1.0, on_figure=read)
    for i, (w, step) in enumerate(zip(windows, (pd.Timedelta(hours=1), Q), strict=True)):
        assert (w["open_time"].diff().dropna() > step).any()  # the closures really are in the panel's bars
        assert seen[f"wick{i}"] == list(range(len(w))) and seen[f"body{i}"] == list(range(len(w)))
        assert seen[f"fill{i}"] == [fill_pos[i]] and seen[f"exit{i}"] == [exit_pos[i]]
        assert seen[f"seg{i}"] == [fill_pos[i], fill_pos[i]]  # the SL and TP segments start at the fill's bar
        # tick labels: the Thai time of the bar at each tick (a known bar: the first one of the window)
        for x, text in zip(seen[f"ticks{i}"], seen[f"labels{i}"], strict=True):
            assert text == w["open_time"].iloc[int(x)].tz_convert(TH).strftime("%m-%d %H:%M")
        first_bar = w["open_time"].iloc[0]
        assert seen[f"labels{i}"][0] == first_bar.tz_convert(TH).strftime("%m-%d %H:%M")
        assert seen[f"labels{i}"][0] != first_bar.strftime("%m-%d %H:%M")  # not the UTC time (Thai is +7 h)


def test_sl_and_tp_segments_are_at_least_a_sixth_of_each_panel(tmp_path: Path) -> None:
    bars, res = constructed_run()
    shares: list[float] = []
    zb.write_charts(tmp_path, res, bars, P, fractions=shares)
    assert len(shares) == 4 and min(shares) >= 1 / 6  # SL and TP in each of the two panels


def test_command_line_stops_on_a_missing_db_or_an_unknown_market(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert zb.main(["--db", str(tmp_path / "none.db"), "--out", str(tmp_path / "o")]) == 1
    err = capsys.readouterr().err
    assert "seed" in err and "none.db" in err
    assert zb.main(["--market", "EURUSD", "--db", str(tmp_path / "none.db")]) == 1
    assert "no bars for EURUSD" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


# --- acceptance: setups against the reference positions --------------------------------------------------

_CACHE: dict[str, zb.RunResult] = {}


def zone_run(stored: zb.Bars, tag: str) -> zb.RunResult:
    if tag not in _CACHE:
        p, a, b = RUNS[tag]
        _CACHE[tag] = zb.run_zone(stored, p, ts(a, TH), ts(b, TH))
    return _CACHE[tag]


EXPECT: dict[str, dict[str, Any]] = {
    "defaults": {
        "setups": 104, "r": 0.433, "tp": 0.53, "usd": 1761.8, "dd": -617.5, "neg": 11, "months": 36,
        "reasons": {"momentum": 530, "trend": 131, "busy": 59, "cancel": 61, "no fill": 72, "abnormal": 130, "traded": 104},
    },
    "defaults_be": {
        "setups": 109, "r": 0.392, "tp": 0.41, "usd": 1868.9, "dd": -280.0, "neg": 13, "months": 36,
        "reasons": {"momentum": 530, "trend": 133, "busy": 48, "cancel": 62, "no fill": 75, "abnormal": 130, "traded": 109},
    },
    "fixed76": {"setups": 41, "r": 0.615, "usd": 1378.0},
}  # fmt: skip


@ACCEPT
@pytest.mark.parametrize("tag", ["defaults", "defaults_be", "fixed76"])
def test_accept_case_3_setups_equal_the_reference_positions(stored: zb.Bars, tag: str) -> None:
    res = zone_run(stored, tag)
    ref = pd.read_csv(OUT / f"long_accept_{tag}.csv")
    rows = zb.position_rows(res.outcomes, res.ex)
    assert len(rows) == len(ref)
    tol = 1e-9
    for r, x in zip(ref.itertuples(), rows, strict=True):
        assert pd.Timestamp(r.visit) == pd.Timestamp(x["visit"]) and r.pos == x["pos"] and r.side == x["side"]
        assert pd.Timestamp(r.entry_t) == pd.Timestamp(x["entry_t"])
        assert pd.Timestamp(r.exit_t) == pd.Timestamp(x["exit_t"]) and r.how == x["how"]
        assert abs(r.S - round(x["S"], 2)) < tol and abs(r.line - x["line"]) < tol
        for a, b in (
            (r.entry, x["entry"]),
            (r.sl, x["sl"]),
            (r.tp, x["tp"]),
            (r.risk, x["risk"]),
            (r.pnl, x["pnl"]),
        ):
            assert abs(a - b) < tol, (r.visit, r.pos)
    st = zb.summary_stats(res.outcomes)
    e = EXPECT[tag]
    assert st["setups"] == e["setups"] and st["open"] == 0 and st["pending"] == 0
    assert round(st["r_per_setup"], 3) == e["r"] and round(st["usd"], 1) == e["usd"]
    if tag != "fixed76":
        assert round(st["tp_share"], 2) == e["tp"] and round(st["drawdown"], 1) == e["dd"]
        assert (st["negative_months"], st["months"]) == (e["neg"], e["months"])
        assert st["reasons"] == e["reasons"]
    assert (st["be_exits"] > 0) is (tag == "defaults_be")


@ACCEPT
def test_accept_case_3a_charts_draw_sl_and_tp_at_least_a_sixth_wide(stored: zb.Bars, tmp_path: Path) -> None:
    res = zone_run(stored, "defaults_be")
    shares: list[float] = []
    paths = zb.write_charts(tmp_path, res, stored, RUNS["defaults_be"][0], fractions=shares)
    assert len(paths) == 109 and len(shares) == 4 * 109
    assert min(shares) >= 1 / 6, min(shares)


@ACCEPT
def test_accept_run_writes_every_file_and_one_chart_per_setup(tmp_path: Path) -> None:
    from eye import zone_config as zc

    db = tmp_path / "cfg.db"
    now = pd.Timestamp("2026-11-01", tz="UTC").to_pydatetime()
    zc.seed(db, "XAUUSD", "fx", "test", now)
    zc.set_values(
        db,
        "XAUUSD",
        "fx",
        "test",
        now,
        "acceptance",
        {"step_mode": "fixed", "exec_tf": "M5", "abn_atr": "1e9", "be_mode": "off"},
    )
    out = tmp_path / "out"
    args = ["--db", str(db), "--set", "fx", "--start", "2025-11-01", "--end", "2026-11-01", "--out", str(out)]
    assert zb.main(args) == 0
    for f in ("positions.csv", "visits.csv", "grids.csv", "summary.csv"):
        assert (out / f).exists()
    summary = pd.read_csv(out / "summary.csv").set_index("name")["value"]
    assert summary["zone"].startswith("zone=XAUUSD/fx@v") and summary["setups"] == "41"
    pos = pd.read_csv(out / "positions.csv")
    first = pos.groupby("setup").first()
    usd = pos.groupby("setup")["pnl"].sum()
    expected = sorted(
        f"{k:02d}_{'open' if r.how == 'open' else ('win' if usd[k] > 0 else 'loss')}_{r.visit[:10].replace('-', '')}.png"
        for k, r in first.iterrows()
    )
    assert sorted(p.name for p in (out / "charts").iterdir()) == expected and len(expected) == 41


def setup_key(o: zb.Outcome) -> tuple[Any, ...]:
    s = o.setup
    if s is None:
        return (o.visit.time, o.visit.line, o.reason)
    fills = tuple((f.name, f.j, f.price) for f in s.fills)
    return (
        o.visit.time,
        o.visit.line,
        o.reason,
        fills,
        s.exit_j,
        s.exit_price,
        s.how,
        s.end_j,
        s.be_j,
        s.be_sl,
    )


@ACCEPT
@pytest.mark.parametrize("cut", ["2024-06-01 00:00", "2025-12-15 00:00", "2026-08-01 00:00"])
def test_accept_case_4_setups_are_the_same_on_bars_cut_at_t(stored: zb.Bars, cut: str) -> None:
    t = ts(cut)
    full = zone_run(stored, "defaults_be")  # the break-even on
    p, a, _ = RUNS["defaults_be"]
    part = zb.run_zone(zb.cut_bars(stored, t), p, ts(a, TH), t)
    by_cut = {(o.visit.time, o.visit.line): o for o in part.outcomes}
    before = [o for o in full.outcomes if o.visit.time < t]
    assert before and len(before) == len(part.outcomes)
    for o in before:
        c = by_cut[(o.visit.time, o.visit.line)]
        s = o.setup
        if s is None or s.end_time <= t:
            assert setup_key(o) == setup_key(c)  # everything known by T is the same
        else:  # not resolved at T: left pending (nothing filled) or open (filled, still running)
            known = tuple((f.name, f.j, f.price) for f in s.fills if full.ex.close_time.iloc[f.j] <= t)
            assert c.setup is not None and tuple((f.name, f.j, f.price) for f in c.setup.fills) == known
            assert (c.reason, c.setup.how) in (("pending", None), ("traded", "open"))
            if s.be_j is not None and full.ex.close_time.iloc[s.be_j] <= t:  # the break-even went on before T
                assert (c.setup.be_j, c.setup.be_sl) == (s.be_j, s.be_sl)
            else:  # it went on after T (or never): not yet known at T
                assert (c.setup.be_j, c.setup.be_sl) == (None, None)


# --- the step function: one copy of a setup's bar-by-bar life (ZONE_LIVE L0) ---------------------------------


def _life_loop(v: zb.Visit, ex: zb.ExecBars, params: ZoneParams, point: float) -> zb.Setup:
    """The step function looped by hand, then the Setup assembled from the final state, with nothing of
    ``simulate_setup`` in it: the two must give the same Setup."""
    plan = zb.plan_setup(v, params)
    life = zb.start_life(plan)
    j = v.j0
    while j < len(ex):
        life = zb.step_setup(plan, life, j, zb.bar_values(ex, j, plan.per_h, point))
        if life.status != "live":
            break
        j += 1
    n = len(ex)
    be_sl = life.cur_sl if life.be_on else None

    def mk(o: str, end_j: int, xj: int | None, xp: float | None, how: str | None) -> zb.Setup:
        return zb.Setup(
            v, plan.p1, plan.p2, plan.sl, plan.tp, o, life.fills, xj, xp, how, end_j,
            ex.close_time.iloc[end_j], be_sl, life.be_j,
        )  # fmt: skip

    if life.status == "cancel":
        return mk("cancel", j, None, None, None)
    if life.status == "exit":
        return mk("traded", j, j, life.exit_price, life.how)
    if life.status == "withdrawn":
        return mk("no fill", j, None, None, None)
    if not life.fills:
        return mk("pending", n - 1, None, None, None)
    return mk("traded", n - 1, n - 1, float(ex.close[n - 1]), "open")


def _bars_for_steps(
    rows: list[tuple[float, float, float, float]], per_h: int, hist: tuple[float, float, float, float]
) -> zb.ExecBars:
    """per_h bars of ``hist`` (the hour before the visit) then the given (open, high, low, close) rows."""
    allr = [hist] * per_h + rows
    n = len(allr)
    ct = pd.Series(pd.date_range("2025-01-06", periods=n, freq="15min", tz="UTC") + pd.Timedelta(minutes=15))
    return zb.ExecBars(
        np.array([r[0] for r in allr]),
        np.array([r[1] for r in allr]),
        np.array([r[2] for r in allr]),
        np.array([r[3] for r in allr]),
        np.array([10.0] * n),
        ct,
    )


def _visit_for_steps(sgn: int, j0: int) -> zb.Visit:
    return zb.Visit(
        pd.Timestamp("2025-01-06", tz="UTC"), 0, "BUY" if sgn > 0 else "SELL", sgn, 100.0, 10.0, 90.0, 1.3,
        100.0, 0.0, 1.0, 0.0, 0.0, 1.0, (False,) * 4, 1.0, j0, j0, 0.0,
    )  # fmt: skip


@pytest.mark.parametrize("params", [ZoneParams(be_mode="off", exec_tf="M15"), ZoneParams(exec_tf="M15")])
@pytest.mark.parametrize("sgn", [1, -1])
def test_the_step_function_looped_equals_simulate_setup(sgn: int, params: ZoneParams) -> None:
    per_h = zb.PER_H["M15"]  # 4: the visit's bar j0 is row 4
    # a BUY line at 100, S = 10: P1 = 100 + 100/76 (above the line), P2 = 100 - 150/76, SL 95, TP 110; a SELL
    # mirrors them around 100. The spread of every bar is 10 points x 0.01 = 0.1.
    m = float(sgn)
    j0 = per_h
    p1, p2 = 100.0 + m * 100 / 76, 100.0 - m * 150 / 76

    def px(x: float) -> float:
        return 100.0 + m * (x - 100.0)

    def bar(o: float, h: float, lo: float, c: float) -> tuple[float, float, float, float]:
        a, b, c1, d = (px(x) for x in (o, h, lo, c))
        return (a, max(b, c1), min(b, c1), d)

    base = bar(103.0, 103.4, 102.6, 103.0)  # above P1 and under the away distance: nothing happens
    touch = bar(103.0, 103.4, 101.0, 102.0)  # P1 fills here
    # name: (rows, history bar, fills [(name, row offset from j0, price)], exit (offset, price) | None,
    #        how, outcome, end row offset)
    cases: dict[str, tuple[Any, ...]] = {
        "expired": ([base] * (params.order_life_h * per_h + 3), base, [], None, None, "no fill", 192),
        "moved away": ([base, bar(103.0, 106.0, 102.6, 104.0), base], base, [], None, None, "no fill", 1),
        "P1 then the TP": (
            [base, touch, bar(102.0, 111.0, 101.5, 110.5), base],
            base,
            [("P1", 1, p1)],
            (2, px(110.0)),
            "TP",
            "traded",
            2,
        ),
        "P1 and P2 on later bars, then the SL": (
            [touch, bar(102.0, 102.0, 97.9, 98.0), bar(98.0, 98.2, 94.0, 94.5), base],
            base,
            [("P1", 0, p1), ("P2", 1, p2)],
            (2, px(95.0)),
            "SL",
            "traded",
            2,
        ),
        "P1 and P2 in one bar": (
            [bar(103.0, 103.4, 97.9, 98.0), bar(98.0, 98.2, 94.0, 94.5), base],
            base,
            [("P1", 0, p1), ("P2", 0, p2)],
            (1, px(95.0)),
            "SL",
            "traded",
            1,
        ),
        "open at the end": ([touch, base, base], base, [("P1", 0, p1)], (2, px(103.0)), "open", "traded", 2),
        "the TP not on the fill bar": (
            [bar(103.0, 111.0, 101.0, 110.5), bar(110.5, 111.0, 109.0, 110.5), base],
            base,
            [("P1", 0, p1)],
            (1, px(110.0)),
            "TP",
            "traded",
            1,
        ),
        "fill-moment cancel": (
            [base, touch, base],
            bar(105.5, 105.9, 105.1, 105.5),
            [],
            None,
            None,
            "cancel",
            1,
        ),
        "closed-hour cancel": ([base, base], bar(107.0, 107.4, 102.6, 103.0), [], None, None, "cancel", 0),
    }
    if params.be_mode == "entry":
        # the break-even goes on at row 1 (the bar after the fill reaches half way to the TP, 105.66); its stop
        # is the average fill + the spread of that bar; row 2 reaches P2 but it is cancelled, then the stop
        cases["break-even then its stop"] = (
            [touch, bar(102.0, 106.0, 101.5, 105.0), bar(105.0, 105.0, 97.9, 100.0), base],
            base,
            [("P1", 0, p1)],
            (2, p1 + m * 0.1),
            "BE",
            "traded",
            2,
        )
    for name, (rows, hist, fills, ext, how, outcome, end_off) in cases.items():
        ex = _bars_for_steps(rows, per_h, hist)
        v = _visit_for_steps(sgn, j0)
        a = zb.simulate_setup(v, ex, params, 0.01)
        b = _life_loop(v, ex, params, 0.01)
        assert a == b, name
        assert a.outcome == outcome and a.how == how, (name, a.outcome, a.how)
        assert [(f.name, f.j, f.price) for f in a.fills] == [
            (n, j0 + o, pytest.approx(pr, abs=1e-9)) for n, o, pr in fills
        ], name
        assert a.end_j == j0 + end_off, name
        if ext is None:
            assert a.exit_j is None and a.exit_price is None, name
        else:
            assert a.exit_j == j0 + ext[0] and a.exit_price == pytest.approx(ext[1], abs=1e-9), name
        # the break-even: only with be_mode "entry", and only where a bar reaches half way to the TP after a
        # fill (105.66 for P1 alone) - on the fill bar itself in one case, a bar later in the other
        be_row = {"the TP not on the fill bar": 0, "break-even then its stop": 1}.get(name)
        if params.be_mode == "entry" and be_row is not None:
            assert a.be_j == j0 + be_row, name
            assert a.be_sl == pytest.approx(p1 + m * 0.1, abs=1e-9), name
        else:
            assert a.be_j is None and a.be_sl is None, name


def test_the_step_function_returns_a_finished_state_unchanged() -> None:
    plan = zb.plan_setup(_visit_for_steps(1, 4), P)
    life = zb.SetupLife("cancel", (), plan.sl)
    b = zb.BarValues(1.0, 0.0, 0.0, 0.0, 0.0)
    assert zb.step_setup(plan, life, 5, b) is life
