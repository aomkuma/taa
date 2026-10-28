"""sweep_detector by hand: the first minute's readings, the race (continued / faked / neither / quiet), the sweep, the
third leg, the pre-release range, the windows' edges, the event lists (New York time, the calendar, the exam refused),
the M1 candles from ticks, Thai time, the summary - and the owner's own example on the real ticks.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_sweep_detector.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sweep_detector as sd  # noqa: E402
from sweep_detector import (  # noqa: E402
    EXAM_START,
    ExamPeriodError,
    calendar_events,
    detect,
    first_minute,
    fixed_events,
    learning_ticks,
    m1_from_ticks,
    race,
    scan,
    summary,
    thai,
)

S = 10**9
T0 = 10_000  # the release, in seconds; ticks are given in seconds and turned into ns
REL = T0 * S


def path(rows):
    t, p = zip(*rows, strict=True)
    return np.array(t, np.int64) * S, np.array(p, float)


# --- the race: faked / continued / neither / quiet --------------------------------------------------------------


def test_the_owner_case_fake_drop_sweep_up_then_down():
    # p0 100 (the tick before the release); +10 s 97 (3 down: the first leg), +20 s 96.5 (its extreme, leg1 3.5);
    # +200 s 111 (10 up past p0 before a low 3 below 96.5: faked, decided at +200 s); +300 s 112 (the sweep's extreme,
    # 12 past p0 at minute 5.0); +600 s 95 (back 17 from 112, through p0: the third leg; 17 >= 0.5 x 12: came down)
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 97.0), (T0 + 20, 96.5), (T0 + 200, 111.0), (T0 + 300, 112.0),
                 (T0 + 600, 95.0)])
    x = detect(t, p, REL)
    assert x["first"] == -1 and x["leg1"] == pytest.approx(3.5) and x["outcome"] == "faked"
    assert x["t_leg"] == (T0 + 10) * S and x["t_ext"] == (T0 + 20) * S and x["t_decided"] == (T0 + 200) * S
    assert x["sweep"] == pytest.approx(12.0) and x["sweep_min"] == pytest.approx(5.0) and x["t_sweep"] == (T0 + 300) * S
    assert x["back"] == pytest.approx(17.0) and x["t_back"] == (T0 + 600) * S and x["came_down"] and x["third"]
    assert not x["two_sided"] and x["give_back"] == pytest.approx(0.0)  # the minute closed at its low (96.5)


def test_faked_without_the_third_leg_but_came_down():
    # the first leg up to 103.5; then 88 (12 below p0: faked); back to 95 = 7 from 88: >= 6 (half of 12), not past p0
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 103.5), (T0 + 200, 88.0), (T0 + 500, 95.0)])
    x = detect(t, p, REL)
    assert x["first"] == 1 and x["outcome"] == "faked" and x["sweep"] == pytest.approx(12.0)
    assert x["back"] == pytest.approx(7.0) and x["came_down"] and not x["third"]


@pytest.mark.parametrize(("back_to", "came"), [(93.9, False), (94.0, True)])
def test_came_down_needs_half_the_sweep(back_to, came):
    # the sweep 12 below p0 (88): back 5.9 is under 6 (half), back 6.0 is exactly half - counted
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 103.5), (T0 + 200, 88.0), (T0 + 500, back_to)])
    assert detect(t, p, REL)["came_down"] is came


def test_a_return_short_of_p0_is_not_the_third_leg():
    # the measurer's planted bug ("third = back >= 0.9 x sweep") passed: the sweep 12 (88), back to 99.0 = 11 = 0.917 x
    # the sweep - came down, but 1 short of p0: not the third leg
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 103.5), (T0 + 200, 88.0), (T0 + 500, 99.0)])
    x = detect(t, p, REL)
    assert x["back"] == pytest.approx(11.0) and x["came_down"] and not x["third"]


def test_the_third_leg_counts_a_return_exactly_to_p0():
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 103.5), (T0 + 200, 88.0), (T0 + 500, 100.0)])
    x = detect(t, p, REL)
    assert x["third"] and x["back"] == pytest.approx(12.0)


def test_faked_needs_exactly_run_past_p0():
    # the first leg down to 96; then 110.0 = exactly 10 past p0 -> faked; 109.99 -> not (neither)
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 96.0), (T0 + 200, 110.0)])
    assert detect(t, p, REL)["outcome"] == "faked"
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 96.0), (T0 + 200, 109.99)])
    assert detect(t, p, REL)["outcome"] == "neither"


def test_continued_needs_a_new_extreme_one_leg_beyond_the_first_minute():
    # the first minute down 5 (95); +100 s 92.1 (2.9 beyond: not yet); +200 s 91.9 (3.1 beyond: continued, decided
    # there); +250 s 90 (the window's most beyond leg1: cont = 10 - 5 = 5.0 at +250 s); +300 s 115 comes later
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 95.0), (T0 + 100, 92.1), (T0 + 200, 91.9), (T0 + 250, 90.0),
                 (T0 + 300, 115.0)])
    x = detect(t, p, REL)
    assert x["outcome"] == "continued" and x["t_decided"] == (T0 + 200) * S
    assert x["cont"] == pytest.approx(5.0) and x["t_cont"] == (T0 + 250) * S
    # the researcher's rule (any new extreme) decides it at +100 s already
    assert detect(t, p, REL, cont_extra=0.0)["t_decided"] == (T0 + 100) * S


def test_a_new_extreme_of_exactly_one_leg_is_not_yet_continued():
    # leg1 5 (95); 92.0 is exactly 3 beyond (8.0 = 5 + 3, not more); then 110 -> faked
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 95.0), (T0 + 100, 92.0), (T0 + 300, 110.0)])
    assert detect(t, p, REL)["outcome"] == "faked"


def test_a_small_new_extreme_then_the_sweep_is_faked_not_continued():
    # the first minute down 5 (95), +100 s 94.9 (0.1 beyond), +300 s 115: the owner's shape - faked (sweep 15 at
    # minute 5.0); the researcher's rule (any new extreme) calls it continued
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 95.0), (T0 + 100, 94.9), (T0 + 300, 115.0)])
    x = detect(t, p, REL)
    assert x["outcome"] == "faked" and x["sweep"] == pytest.approx(15.0) and x["sweep_min"] == pytest.approx(5.0)
    assert detect(t, p, REL, cont_extra=0.0)["outcome"] == "continued"


def test_neither_and_the_race_window_ends_at_15_minutes():
    # the first leg down 4; +200 s 108 (8 up only); a tick exactly at the release + 15 min (130) and one after it
    # (135) are outside the window -> neither
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 96.0), (T0 + 200, 108.0), (T0 + 900, 130.0), (T0 + 901, 135.0)])
    assert detect(t, p, REL)["outcome"] == "neither"


def test_the_race_starts_after_the_first_minute():
    # the first minute: up 11 (+5 s) then down 12 (+30 s): the larger move is down (leg1 12), the 11 up inside the
    # first minute is not a sweep; after it, +300 s 84.5 = 15.5 down (3.5 beyond 12): continued
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 111.0), (T0 + 30, 88.0), (T0 + 59, 95.0), (T0 + 300, 84.5)])
    x = detect(t, p, REL)
    assert x["first"] == -1 and x["leg1"] == pytest.approx(12.0) and x["outcome"] == "continued"


def test_the_sweep_is_the_extreme_inside_the_window_only():
    # faked at +200 s (111), the extreme in the window 113 (+800 s); 140 at +905 s is after the window
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 96.0), (T0 + 200, 111.0), (T0 + 800, 113.0), (T0 + 905, 140.0)])
    x = detect(t, p, REL)
    assert x["sweep"] == pytest.approx(13.0) and x["t_sweep"] == (T0 + 800) * S


def test_back_is_measured_for_15_minutes_after_the_sweeps_extreme():
    # the sweep's extreme 112 at +300 s; back to 104 at +1000 s (11.7 min after the extreme, after the release +15)
    # counts: back 8; 90 at +1201 s (15 min 1 s after the extreme) does not
    t, p = path([(T0 - 10, 100.0), (T0 + 10, 96.0), (T0 + 200, 111.0), (T0 + 300, 112.0), (T0 + 1000, 104.0),
                 (T0 + 1201, 90.0)])
    x = detect(t, p, REL)
    assert x["back"] == pytest.approx(8.0) and x["t_back"] == (T0 + 1000) * S and not x["third"]


def test_quiet_and_the_first_minutes_edges():
    # the first 3 USD after the first minute: quiet; a tick exactly at the release + 60 s is after the first minute
    t, p = path([(T0 - 10, 100.0), (T0 + 30, 102.9), (T0 + 60, 97.0), (T0 + 200, 85.0)])
    x = detect(t, p, REL)
    assert x["first"] == 0 and x["outcome"] == "quiet" and x["up1"] == pytest.approx(2.9)
    # exactly 3.0 inside the first minute is a first leg
    t, p = path([(T0 - 10, 100.0), (T0 + 30, 97.0), (T0 + 200, 99.0)])
    assert detect(t, p, REL)["first"] == -1


def test_p0_is_the_tick_before_the_release_not_at_it():
    # a tick AT the release (97) is the first leg's, not p0; none before the release -> None
    t, p = path([(T0 - 10, 100.0), (T0, 97.0), (T0 + 200, 111.0)])
    x = detect(t, p, REL)
    assert x["p0"] == 100.0 and x["first"] == -1 and x["outcome"] == "faked"
    t, p = path([(T0, 97.0), (T0 + 200, 111.0)])
    assert detect(t, p, REL) is None


def test_race_without_a_first_minute_reading():
    t, p = path([(T0 - 10, 100.0), (T0 + 30, 101.0)])
    assert race(t, p, REL, None) == {}
    assert race(t, p, REL, first_minute(t, p, REL)) == {"outcome": "quiet"}


# --- the first leg's side and the first minute's readings --------------------------------------------------------


def test_the_side_is_the_first_minutes_larger_move():
    # +5 s 104 (4 up, the first 3-USD move), +20 s 97 (3 down: t_leg), +30 s 88 (12 down: the extreme, t_ext),
    # +59 s 98 (the close: give_back 12 - 2 = 10); after: +200 s 84.9 (15.1 down = 3.1 beyond 12: continued)
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 104.0), (T0 + 20, 97.0), (T0 + 30, 88.0), (T0 + 59, 98.0), (T0 + 200, 84.9)])
    x = detect(t, p, REL)
    assert x["first"] == -1 and x["leg1"] == pytest.approx(12.0) and x["two_sided"]
    assert x["up1"] == pytest.approx(4.0) and x["dn1"] == pytest.approx(12.0) and x["c1"] == 98.0
    assert x["t_leg"] == (T0 + 20) * S and x["t_ext"] == (T0 + 30) * S and x["give_back"] == pytest.approx(10.0)
    assert x["outcome"] == "continued"
    # the researcher's side (the first 3-USD move): up 4, and the 15.1 down is then its 'sweep'
    y = detect(t, p, REL, side_rule="first")
    assert y["first"] == 1 and y["leg1"] == pytest.approx(4.0) and y["outcome"] == "faked"
    assert y["sweep"] == pytest.approx(15.1) and y["t_leg"] == (T0 + 5) * S


def test_a_tie_takes_the_side_that_reached_leg_first():
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 104.0), (T0 + 30, 96.0), (T0 + 200, 99.0)])
    x = first_minute(t, p, REL)
    assert x["first"] == 1 and x["leg1"] == pytest.approx(4.0) and x["two_sided"]
    # the measurer's planted bug ("always up on a tie") passed: the mirror - 3 down first (96 at +5 s), then 104
    t, p = path([(T0 - 10, 100.0), (T0 + 5, 96.0), (T0 + 30, 104.0), (T0 + 200, 99.0)])
    x = first_minute(t, p, REL)
    assert x["first"] == -1 and x["leg1"] == pytest.approx(4.0) and x["t_leg"] == (T0 + 5) * S
    with pytest.raises(ValueError, match="side_rule"):
        first_minute(t, p, REL, side_rule="close")


def test_the_pre_release_range_and_the_sweeps_through_it():
    # pre-release window = [release - 30 min, release): 150 at -30 min -1 s is outside; 104 (high) and 97 (low) in;
    # p0 100. The first leg to 96 goes below 97 (swept_pre); the sweep to 110 goes above 104 (swept_other)
    rows = [(T0 - 1801, 150.0), (T0 - 1700, 104.0), (T0 - 500, 97.0), (T0 - 10, 100.0), (T0 + 10, 96.0),
            (T0 + 300, 110.0)]
    x = detect(*path(rows), REL)
    assert x["pre_hi"] == 104.0 and x["pre_lo"] == 97.0
    assert x["swept_pre"] and x["outcome"] == "faked" and x["swept_other"]
    # the first leg only to 97.0 (equal to the pre-release low, not beyond): not swept_pre; the sweep reaches 104.0
    # (equal to the high) at +300 s and 110 at +400 s: faked (10.0 past p0), swept_other by the 110
    rows = [(T0 - 1700, 104.0), (T0 - 500, 97.0), (T0 - 10, 100.0), (T0 + 10, 97.0), (T0 + 300, 104.0),
            (T0 + 400, 110.0)]
    x = detect(*path(rows), REL)
    assert not x["swept_pre"] and x["outcome"] == "faked" and x["sweep"] == pytest.approx(10.0)
    assert x["swept_other"]  # the extreme 110 is above 104
    rows = [(T0 - 1700, 112.0), (T0 - 500, 97.0), (T0 - 10, 100.0), (T0 + 10, 97.0), (T0 + 300, 111.0)]
    assert not detect(*path(rows), REL)["swept_other"]  # 111 stays under the pre-release high 112
    # mirrored: the first leg up through the high, the sweep down through the low
    rows = [(T0 - 1700, 103.0), (T0 - 500, 95.0), (T0 - 10, 100.0), (T0 + 10, 103.5), (T0 + 300, 89.0)]
    x = detect(*path(rows), REL)
    assert x["first"] == 1 and x["swept_pre"] and x["swept_other"]
    # the measurer's planted bug (">=" on the up side) passed: the first leg up to exactly the pre-release high 103.0
    # is not beyond it; the sweep down to exactly the pre-release low 90.0 (10 past p0) is not beyond it either
    rows = [(T0 - 1700, 103.0), (T0 - 500, 90.0), (T0 - 10, 100.0), (T0 + 10, 103.0), (T0 + 300, 90.0), (T0 + 400, 95.0)]
    x = detect(*path(rows), REL)
    assert x["first"] == 1 and x["leg1"] == pytest.approx(3.0) and not x["swept_pre"]
    assert x["outcome"] == "faked" and x["sweep"] == pytest.approx(10.0) and not x["swept_other"]


def test_the_first_minutes_readings_do_not_see_after_the_decision():
    # replace every tick at / after the release + 60 s with other prices (another count, other times): every
    # first-minute reading stays equal; changing a tick before the decision does change them (the check has power)
    base = [(T0 - 1500, 101.0), (T0 - 10, 100.0), (T0 + 10, 97.0), (T0 + 20, 95.5), (T0 + 59, 96.2)]
    t, p = path([*base, (T0 + 60, 120.0), (T0 + 200, 80.0), (T0 + 400, 111.0)])
    rng = np.random.default_rng(7)
    t2, p2 = path([*base, *[(T0 + 60 + k, float(v)) for k, v in enumerate(rng.normal(100, 30, 500))]])
    for rule in ("larger", "first"):
        assert first_minute(t, p, REL, side_rule=rule) == first_minute(t2, p2, REL, side_rule=rule)
    t3, p3 = path([*base[:-1], (T0 + 59, 99.0), (T0 + 60, 120.0)])
    assert first_minute(t3, p3, REL) != first_minute(t, p, REL)


# --- the owner's own example on the real ticks ------------------------------------------------------------------


def test_the_owner_example_2026_01_09_on_the_real_ticks():
    # US jobs report 2026-01-09 13:30 UTC (20:30 Thai). From the tick mids (out_sweep_detector / DEV_LOG): p0 = 4473.34
    # (13:29:59); the first minute's low 4459.23 (13:30:12): 14.11 down; the high after it 4491.96 (13:40): the sweep
    # 18.6 past p0 at minute ~10.4; then 4479.08 (13:50): back 12.88 (>= half of 18.6), not through p0. The 30
    # minutes before: low 4462.14, high 4474.80 - the drop went below the low, the sweep above the high
    ev = pd.DataFrame(dict(t=[pd.Timestamp("2026-01-09 13:30", tz="UTC")], ny=["08:30"]))
    x = scan(ev).iloc[0]
    assert x["first"] == -1 and x["leg1"] == pytest.approx(14.11, abs=0.02) and x["outcome"] == "faked"
    assert x["sweep"] == pytest.approx(18.62, abs=0.02) and x["sweep_min"] == pytest.approx(10.4, abs=0.1)
    assert x["back"] == pytest.approx(12.88, abs=0.02) and x["came_down"] and not x["third"]
    assert x["pre_lo"] == pytest.approx(4462.14, abs=0.02) and x["pre_hi"] == pytest.approx(4474.80, abs=0.02)
    assert x["swept_pre"] and x["swept_other"] and not x["two_sided"]
    # the researcher's variants catch it too
    assert scan(ev, side_rule="first", cont_extra=0.0).iloc[0]["outcome"] == "faked"


# --- scan, the events, the exam refused --------------------------------------------------------------------------


def test_scan_uses_the_mid_and_keeps_the_event_columns(monkeypatch):
    # a synthetic day: the bid moves 3 down but the spread widens 2 -> the mid moves only 2: quiet on the mid, a
    # first leg on the bid
    day = pd.Timestamp("2026-01-09", tz="UTC")
    rel = pd.Timestamp("2026-01-09 13:30", tz="UTC").value
    t = np.array([rel - 10 * S, rel + 10 * S, rel + 200 * S], np.int64)
    bid, ask = np.array([100.0, 97.0, 97.0]), np.array([100.4, 99.4, 99.4])
    monkeypatch.setattr(sd, "learning_ticks", lambda d: (t, bid, ask) if pd.Timestamp(d) == day else None)
    ev = pd.DataFrame(dict(t=[pd.Timestamp(rel, tz="UTC"), pd.Timestamp("2026-01-12 13:30", tz="UTC")],
                           ny=["08:30", "08:30"], names=["NFP", ""]))
    x = scan(ev)
    assert len(x) == 1 and x.iloc[0]["names"] == "NFP" and x.iloc[0]["ny"] == "08:30"
    assert x.iloc[0]["p0"] == pytest.approx(100.2) and x.iloc[0]["outcome"] == "quiet"


def test_the_exam_is_refused():
    with pytest.raises(ExamPeriodError):
        learning_ticks(pd.Timestamp("2026-04-18", tz="UTC"))
    with pytest.raises(ExamPeriodError):
        learning_ticks(pd.Timestamp("2026-04-18 05:00"))  # naive = UTC
    assert learning_ticks(pd.Timestamp("2026-04-17", tz="UTC")) is not None  # the last learning day (a Friday)
    with pytest.raises(ExamPeriodError):
        fixed_events(end=EXAM_START + pd.Timedelta(days=1))
    with pytest.raises(ExamPeriodError):
        calendar_events(end=EXAM_START + pd.Timedelta(days=1))


def test_the_fixed_minutes_follow_new_york_time():
    ev = fixed_events(pd.Timestamp("2025-10-31", tz="UTC"), pd.Timestamp("2025-11-04", tz="UTC"))
    # Fri 31 Oct EDT (UTC-4): 12:30 / 14:00; Sat 1 and Sun 2 Nov none; Mon 3 Nov EST (UTC-5): 13:30 / 15:00
    assert [(e.strftime("%m-%d %H:%M"), n) for e, n in zip(ev.t, ev.ny, strict=True)] == [
        ("10-31 12:30", "08:30"), ("10-31 14:00", "10:00"), ("11-03 13:30", "08:30"), ("11-03 15:00", "10:00")]
    ev = fixed_events(pd.Timestamp("2026-03-13", tz="UTC"), pd.Timestamp("2026-03-17", tz="UTC"))
    # Fri 13 Mar 2026 is after the US switch (8 Mar): EDT, 12:30 / 14:00; Mon 16 Mar the same
    assert [e.strftime("%m-%d %H:%M") for e in ev.t] == ["03-13 12:30", "03-13 14:00", "03-16 12:30", "03-16 14:00"]
    ev = fixed_events()  # Mon 2025-10-20 .. Fri 2026-04-17: 26 weeks, 130 weekdays (holidays kept; scan skips no-tick days)
    assert ev.t.min() == pd.Timestamp("2025-10-20 12:30", tz="UTC") and ev.t.max() == pd.Timestamp("2026-04-17 14:00", tz="UTC")
    assert len(ev) == 2 * 130


def test_the_calendar_minutes():
    c = calendar_events().set_index("t")
    utc = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    assert c.loc[utc("2026-01-09 13:30"), "names"] == "NFP"
    assert c.loc[utc("2025-11-20 13:30"), "names"] == "CLM+NFP"  # the extra file's claims, merged by minute
    assert c.loc[utc("2026-02-20 13:30"), "names"] == "GDP+PCE"
    assert c.loc[utc("2026-01-28 19:00"), "names"] == "FOMC" and c.loc[utc("2026-01-28 19:00"), "ny"] == "14:00"
    assert c.loc[utc("2026-01-28 19:30"), "names"] == "PC"
    assert c.loc[utc("2026-03-18 18:00"), "ny"] == "14:00"  # EDT
    assert bool(c.loc[utc("2025-12-05 15:00"), "check"]) and not bool(c.loc[utc("2026-01-09 13:30"), "check"])
    # 62 release minutes in the learning parts (2026-04-03, NFP on Good Friday, has an empty tick file: scan skips it)
    assert c.index.min() == utc("2025-10-24 12:30") and c.index.max() == utc("2026-04-16 12:30") and len(c) == 62
    # the files do hold later releases - the filter removed them
    import gold

    assert (gold.releases().t >= EXAM_START).any()


# --- the chart helpers and the summary -----------------------------------------------------------------------------


def test_m1_candles_from_ticks():
    # minute 0: 10, 12, 9 -> O 10 H 12 L 9 C 9; minute 1: 11 (at 60 s exactly), 11.5 -> O 11 H 11.5 L 11 C 11.5;
    # minute 2 has no tick (left out); a tick at 180 s is outside [0, 180 s)
    t, p = path([(0, 10.0), (20, 12.0), (59, 9.0), (60, 11.0), (61, 11.5), (180, 30.0)])
    m = m1_from_ticks(t, p, 0, 180 * S)
    assert list(m.index) == [pd.Timestamp(0, tz="UTC"), pd.Timestamp(60 * S, tz="UTC")]
    assert m.iloc[0][["open", "high", "low", "close", "n"]].tolist() == [10.0, 12.0, 9.0, 9.0, 3]
    assert m.iloc[1][["open", "high", "low", "close", "n"]].tolist() == [11.0, 11.5, 11.0, 11.5, 2]


def test_thai_time():
    assert thai(pd.Timestamp("2026-01-09 13:30", tz="UTC").value) == "20:30"
    assert thai(pd.Timestamp("2025-10-20 18:05", tz="UTC").value) == "01:05"


def test_summary_by_hand():
    T = pd.DataFrame(dict(part=["P1"] * 4 + ["P2"], ny=["08:30"] * 5,
                          outcome=["faked", "faked", "continued", "quiet", "neither"],
                          sweep=[10.0, 20.0, np.nan, np.nan, np.nan], sweep_min=[2.0, 4.0, np.nan, np.nan, np.nan],
                          back=[5.0, 30.0, np.nan, np.nan, np.nan], came_down=[False, True, None, None, None],
                          third=[False, True, None, None, None]))
    s = summary(T).set_index("part")
    assert s.loc["P1", ["days", "faked", "continued", "neither", "quiet"]].tolist() == [4, 2, 1, 0, 1]
    assert s.loc["P1", "sweep_med"] == 15.0 and s.loc["P1", "min_med"] == 3.0 and s.loc["P1", "back_med"] == 17.5
    assert s.loc["P1", "came_down"] == 0.5 and s.loc["P1", "third"] == 0.5
    assert s.loc["P2", "neither"] == 1 and np.isnan(s.loc["P2", "sweep_med"])
