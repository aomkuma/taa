# ruff: noqa: S101, PT018, E501
"""Hand-worked tests for the fixed RETEST-CONTINUATION V1 simulator (2026-10-22).

Common synthetic market (BUY unless stated). T0 = Monday 2025-11-03 00:00 UTC; E0 = 100.00, S0 = 99.00; the source
RUNNER stopped at T0+100 min. Every M5 bar k covers minutes 5k..5k+4 and each of its M1 bars has the same high/low
and open = close, except M5 bar 19 whose last minute (minute 99) is o 99.80 h 100.12 l 99.78 c 100.10.

    M5 bar   high     low      close    true range (MT5: max(h, prev c) - min(l, prev c))
    0..18    99.82    99.78    99.80    bar 0 none; 0.04 each
    19       100.12   99.78    100.10   0.34   (closes exactly at the stop time T0+100: not "after" the stop)
    20       100.16   100.08   100.12   0.08   reclaim: first close > 100.00 closing after T0+100 (at T0+105)
    21       100.13   100.02   100.08   0.11   no touch of 100.00
    22       100.14   99.96    100.06   0.18   retest: low 99.96 <= 100.00, close 100.06 >= 100.00
    23       100.22   100.05   100.20   ...    confirmation: close 100.20 > retest high 100.14; low 100.05 > stop
    24..     low = 100.06 + 0.01 (k - 24), high = low + 0.04, close = low + 0.02 (rising lows: no pivot low)

ATR(14) at the retest bar 22 = mean TR of bars 9..22 = (10 x 0.04 + 0.34 + 0.08 + 0.11 + 0.18) / 14 = 1.11 / 14
= 0.0792857. B = max(source spread 0.02, 0.1 x 0.0792857) = 0.02, provisional stop = 99.96 - 0.02 = 99.94.
Confirmation closes at T0+120 min. The entry quote at T0+120 min 0.5 s is bid 100.21 / ask 100.24: a BUY pays the
ask 100.24, entry spread 0.03, 1R = 100.24 - 99.94 = 0.30.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest
from candidate import (
    ENTRY_QUOTE_WINDOW,
    _tighten_stop,
    confirmed_pivots,
    find_signal,
    m5_bars,
    simulate_candidate,
    simulate_historical_diagnostic,
)
from ticks import EXAM_START, ExamLockedError

T0 = pd.Timestamp("2025-11-03 00:00", tz="UTC")
STOP_TIME = T0 + pd.Timedelta(minutes=100)
CONFIRM = T0 + pd.Timedelta(minutes=120)
ENTRY_T = CONFIRM + pd.Timedelta(milliseconds=500)
DEADLINE = ENTRY_T + pd.Timedelta(hours=8)
N_M5 = 126


def m(minutes: float) -> pd.Timestamp:
    return T0 + pd.Timedelta(minutes=minutes)


def bar_table(
    overrides: dict[int, tuple[float, float, float]] | None = None,
) -> list[tuple[float, float, float]]:
    table: list[tuple[float, float, float]] = []
    for k in range(N_M5):
        if k <= 19:
            table.append((99.82, 99.78, 99.80))
        elif k == 20:
            table.append((100.16, 100.08, 100.12))
        elif k == 21:
            table.append((100.13, 100.02, 100.08))
        elif k == 22:
            table.append((100.14, 99.96, 100.06))
        elif k == 23:
            table.append((100.22, 100.05, 100.20))
        else:
            low = 100.06 + 0.01 * (k - 24)
            table.append((low + 0.04, low, low + 0.02))
    for k, value in (overrides or {}).items():
        table[k] = value
    return table


def make_m1(
    overrides: dict[int, tuple[float, float, float]] | None = None, *, spread: int = 2, mirror: bool = False
) -> pd.DataFrame:
    rows = []
    for k, (high, low, close) in enumerate(bar_table(overrides)):
        for j in range(5):
            o, h, lo, c = close, high, low, close
            if k == 19 and j == 4:
                o, h, lo, c = 99.80, 100.12, 99.78, 100.10
            rows.append((o, h, lo, c))
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    if mirror:  # SELL world: p' = 200 - p, so highs and lows swap
        frame = pd.DataFrame(
            {
                "open": 200 - frame["open"],
                "high": 200 - frame["low"],
                "low": 200 - frame["high"],
                "close": 200 - frame["close"],
            }
        )
    frame["spread"] = spread
    frame.index = pd.date_range(T0, periods=len(frame), freq="min", tz="UTC", name="open_time")
    return frame


class FakeQuotes:
    """Test double for ticks.TickSource; ``splits`` cut iter_from into chunks (day files)."""

    def __init__(self, rows: list[tuple[pd.Timestamp, float, float]], splits: tuple[pd.Timestamp, ...] = ()):
        self.frame = pd.DataFrame(rows, columns=["time_utc", "bid", "ask"])
        self.splits = splits

    def span(self, start, end):
        f = self.frame
        return f.loc[(f["time_utc"] >= start) & (f["time_utc"] <= end)].reset_index(drop=True)

    def iter_from(self, start, *, max_days=10):
        f = self.frame.loc[self.frame["time_utc"] >= start]
        edges = [start, *[s for s in self.splits if s > start], pd.Timestamp.max.tz_localize("UTC")]
        for lo, hi in itertools.pairwise(edges):
            part = f.loc[(f["time_utc"] >= lo) & (f["time_utc"] < hi)]
            if len(part):
                yield part.reset_index(drop=True)


def event(**updates):
    base = {
        "trade_key": "T-1",
        "stop_time_utc": STOP_TIME,
        "side": 1,
        "entry": 100.00,
        "stop": 99.00,
        "spread": 0.02,
        "runner_stopped_before_plus1": True,
    }
    base.update(updates)
    return base


def run(m1, quotes, ev=None, **kw):
    return simulate_historical_diagnostic(
        ev or event(), m1, quotes, exam_start=EXAM_START, earliest_data=T0, **kw
    )


ENTRY_QUOTE = (ENTRY_T, 100.21, 100.24)


# --- M5 bars and ATR -------------------------------------------------------------------------------------------


def test_m5_bar_is_complete_at_its_clock_end_even_with_a_missing_minute():
    # Minutes 0-3 and 5-9; minute 4 has no M1 row. Bar 0 (00:00-00:05) still closes at 00:05 with the close of
    # minute 3 (99.80); bar 1 is complete because data reaches minute 9 (clock end 00:10).
    m1 = make_m1().iloc[:10].drop(index=m(4))
    bars = m5_bars(m1, 1)
    assert list(bars.index) == [m(0), m(5)]
    assert bars["close"].iloc[0] == 99.80 and bars["close_time"].iloc[0] == m(5)


def test_forming_m5_bar_is_never_a_signal():
    # Data ends at minute 7 (its clock end 00:08): bar 5-9 is still forming and must be absent.
    bars = m5_bars(make_m1().iloc[:8], 1)
    assert list(bars.index) == [m(0)]


def test_m5_atr_is_mt5_atr_first_value_at_bar_14():
    bars = m5_bars(make_m1(), 1)
    assert np.isnan(bars["atr14"].iloc[13])  # bars 0..13: TR[0] undefined, only 13 ranges
    assert bars["atr14"].iloc[14] == pytest.approx(0.04)  # TR 1..14 all 0.04
    assert bars["atr14"].iloc[22] == pytest.approx(1.11 / 14)


def test_m5_atr_true_range_uses_the_previous_close():
    # bar 21 gaps above bar 20's close 100.12: h 100.40 l 100.30 c 100.35 -> TR = 100.40 - 100.12 = 0.28 (h-l 0.10);
    # bar 22 (h 100.14, l 99.96) after close 100.35 -> TR = 100.35 - 99.96 = 0.39 (h-l 0.18).
    # ATR(14) at bar 22 = (10 x 0.04 + 0.34 + 0.08 + 0.28 + 0.39) / 14 = 1.49 / 14
    bars = m5_bars(make_m1({21: (100.40, 100.30, 100.35)}), 1)
    assert bars["atr14"].iloc[22] == pytest.approx(1.49 / 14)


def test_sell_bars_are_lifted_by_each_minutes_recorded_spread():
    # ambiguity A1 (kept from the original): SELL signal prices = bid + spread x 0.01. Spread 2 -> +0.02.
    bars = m5_bars(make_m1(spread=2), -1)
    assert bars["close"].iloc[0] == pytest.approx(99.82)
    assert bars["high"].iloc[20] == pytest.approx(100.18)


# --- reclaim / retest / invalidation / continuation ------------------------------------------------------------


def test_signal_hand_worked():
    s = find_signal(event(), make_m1())
    assert s["status"] == "SIGNAL"
    assert s["reclaim_time_utc"] == m(105)  # bar 20, not bar 19 that closes at the stop time itself
    assert s["retest_time_utc"] == m(115)
    assert s["confirmation_time_utc"] == m(120)
    assert s["retest_atr"] == pytest.approx(1.11 / 14)
    assert s["provisional_stop"] == pytest.approx(99.94)


def test_buffer_uses_atr_when_larger_than_source_spread():
    # spread 0.005 < 0.1 x 0.0792857 = 0.00792857 -> stop = 99.96 - 0.00792857 = 99.95207143
    s = find_signal(event(spread=0.005), make_m1())
    assert s["provisional_stop"] == pytest.approx(99.96 - 0.1 * 1.11 / 14)


def test_retest_close_below_entry_is_not_a_retest():
    # bar 22 closes 99.99 < 100.00 (touch but no hold); bars 23..26 never touch 100.00 (lows >= 100.05) -> NO_RETEST
    s = find_signal(event(), make_m1({22: (100.14, 99.96, 99.99)}))
    assert s["status"] == "NO_RETEST"


def test_retest_window_is_six_bars():
    # Push the touch from bar 22 to bar 26 (the 6th bar after reclaim bar 20) -> still a retest; bar 27 -> none.
    lifted = {22: (100.14, 100.03, 100.06)}
    # the bar-26 retest is confirmed by bar 27 closing 100.35 > 100.30
    sixth = find_signal(
        event(), make_m1({**lifted, 26: (100.30, 99.99, 100.05), 27: (100.40, 100.10, 100.35)})
    )
    assert sixth["status"] == "SIGNAL" and sixth["retest_time_utc"] == m(135)
    seventh = find_signal(event(), make_m1({**lifted, 27: (100.30, 99.99, 100.05)}))
    assert seventh["status"] == "NO_RETEST"


def test_bar_between_retest_and_confirmation_breaching_stop_cancels():
    # bar 23 does not confirm (close 100.10 <= 100.14) and bar 24 dips to 99.94 = stop -> invalidated
    s = find_signal(event(), make_m1({23: (100.15, 100.05, 100.10), 24: (100.30, 99.94, 100.25)}))
    assert s["status"] == "STRUCTURE_INVALIDATED"


def test_confirmation_bar_spanning_the_stop_cancels():
    s = find_signal(event(), make_m1({23: (100.22, 99.93, 100.20)}))
    assert s["status"] == "STRUCTURE_INVALIDATED"


def test_continuation_must_close_strictly_beyond():
    # bars 23 and 24 both close exactly at the retest high 100.14: not > 100.14 -> NO_CONTINUATION
    equal = find_signal(event(), make_m1({23: (100.16, 100.05, 100.14), 24: (100.16, 100.06, 100.14)}))
    assert equal["status"] == "NO_CONTINUATION"


def test_continuation_on_second_bar():
    s = find_signal(event(), make_m1({23: (100.16, 100.05, 100.10), 24: (100.20, 100.06, 100.15)}))
    assert s["status"] == "SIGNAL" and s["confirmation_time_utc"] == m(125)
    third = find_signal(
        event(),
        make_m1({23: (100.16, 100.05, 100.10), 24: (100.16, 100.06, 100.12), 25: (100.30, 100.10, 100.25)}),
    )
    assert third["status"] == "NO_CONTINUATION"


def test_reclaim_must_happen_within_8_hours_of_the_stop():
    # stop = T0+100 - 8 h: bar 19 (close 100.10 > 100.00) closes exactly at stop + 8 h -> inside, reclaim at T0+100.
    on_edge = find_signal(event(stop_time_utc=m(100) - pd.Timedelta(hours=8)), make_m1())
    assert on_edge["status"] == "SIGNAL" and on_edge["reclaim_time_utc"] == m(100)
    # one minute earlier the window ends at T0+99: bars 0..18 all close 99.80 <= 100.00 -> NO_RECLAIM
    late = find_signal(event(stop_time_utc=m(99) - pd.Timedelta(hours=8)), make_m1())
    assert late["status"] == "NO_RECLAIM"


def test_retest_and_confirmation_after_the_8_hour_reclaim_window_still_count():
    # Bug B3: the original expired the event when the retest/confirmation closed after stop + 8 h. Here the reclaim
    # (bar 19) closes exactly at stop + 8 h; retest bar 22 (T0+115) and confirmation (T0+120) close later and count.
    s = find_signal(event(stop_time_utc=m(100) - pd.Timedelta(hours=8)), make_m1())
    assert s["status"] == "SIGNAL"
    assert s["retest_time_utc"] == m(115) and s["confirmation_time_utc"] == m(120)


def test_signal_does_not_look_ahead():
    full = find_signal(event(), make_m1())
    upto = find_signal(event(), make_m1().loc[: m(119)])  # data through the confirmation bar's last minute
    assert upto["status"] == "SIGNAL" and upto["confirmation_time_utc"] == full["confirmation_time_utc"]
    early = find_signal(event(), make_m1().loc[: m(118)])  # confirmation bar still forming
    assert early["status"] == "PENDING_CONFIRMATION_WINDOW"
    future_changed = make_m1()
    future_changed.loc[m(121) :, ["high", "low", "close", "open"]] = 50.0
    assert find_signal(event(), future_changed)["provisional_stop"] == full["provisional_stop"]


# --- entry -----------------------------------------------------------------------------------------------------


def test_entry_buy_pays_ask_of_first_quote_at_or_after_confirmation():
    # the quote 1 s before the confirmation close is too early; the one 30 s after the entry quote is too late
    q = FakeQuotes(
        [
            (CONFIRM - pd.Timedelta(seconds=1), 100.0, 100.03),
            ENTRY_QUOTE,
            (ENTRY_T + pd.Timedelta(seconds=30), 100.30, 100.33),
            (m(300), 100.5, 100.53),
            (DEADLINE, 100.60, 100.63),
        ]
    )
    r = run(make_m1(), q)
    assert r["entry_time_utc"] == ENTRY_T.isoformat()
    assert r["entry"] == pytest.approx(100.24) and r["entry_spread"] == pytest.approx(0.03)
    assert r["initial_risk"] == pytest.approx(0.30)


def test_entry_slippage_is_adverse_and_defaults_to_zero():
    q = FakeQuotes([ENTRY_QUOTE, (DEADLINE, 100.60, 100.63)])
    r = run(make_m1(), q, slippage=0.05)
    assert r["entry"] == pytest.approx(100.29) and r["initial_risk"] == pytest.approx(0.35)


def test_entry_at_or_through_the_stop_is_cancelled():
    q = FakeQuotes([(ENTRY_T, 99.91, 99.94)])  # ask 99.94 = stop -> no positive risk
    assert run(make_m1(), q)["status"] == "ENTRY_THROUGH_STOP"


def test_no_quote_in_the_entry_minute_is_no_entry():
    q = FakeQuotes([(CONFIRM + ENTRY_QUOTE_WINDOW, 100.21, 100.24)])
    assert run(make_m1(), q)["status"] == "NO_ENTRY_QUOTE"


# --- stops, trail, time exit -----------------------------------------------------------------------------------


def test_stop_fills_at_the_worse_quote():
    # marks: 100.21 (R -0.1), 100.39 (R +0.5), 99.95 (above 99.94), 99.90 (through) -> exit 99.90
    # R = (99.90 - 100.24) / 0.30 = -1.133333; MFE +0.5; MAE -1.133333; held 131 - 120.00833 = 10.99167 min
    q = FakeQuotes([ENTRY_QUOTE, (m(125), 100.39, 100.42), (m(130), 99.95, 99.98), (m(131), 99.90, 99.93)])
    r = run(make_m1(), q)
    assert r["status"] == "COMPLETE" and r["reason"] == "STOP"
    assert r["exit"] == pytest.approx(99.90) and r["r"] == pytest.approx(-0.34 / 0.30)
    assert r["mfe_r"] == pytest.approx(0.5) and r["mae_r"] == pytest.approx(-0.34 / 0.30)
    assert r["holding_minutes"] == pytest.approx(11 - 0.5 / 60)  # T0+131:00 - T0+120:00.5


def test_stop_across_a_day_file_gap_fills_at_the_first_quote_of_the_next_chunk():
    split = m(200)
    q = FakeQuotes([ENTRY_QUOTE, (m(199), 100.30, 100.33), (m(201), 99.50, 99.53)], splits=(split,))
    r = run(make_m1(), q)
    assert r["reason"] == "STOP" and r["exit"] == pytest.approx(99.50)
    assert r["r"] == pytest.approx((99.50 - 100.24) / 0.30)


def test_trail_applies_only_from_the_pivot_confirmation_and_never_loosens():
    # bars 24 l 100.20, 25 l 100.15 (pivot low), 26 l 100.25 -> confirmed at bar 26 close = T0+135.
    # buffer = max(entry spread 0.03, 0.1 x ATR(<0.3)) = 0.03 -> trail stop 100.12.
    trail = {24: (100.24, 100.20, 100.22), 25: (100.19, 100.15, 100.17), 26: (100.29, 100.25, 100.27)}
    for k in range(27, N_M5):
        low = 100.26 + 0.01 * (k - 27)
        trail[k] = (low + 0.04, low, low + 0.02)
    m1 = make_m1(trail)
    pivots = confirmed_pivots(m5_bars(m1, 1), 1, 0.03, formed_from=CONFIRM)
    assert pivots == [(m(135), m(125), pytest.approx(100.12))]
    q = FakeQuotes(
        [ENTRY_QUOTE, (m(134), 100.11, 100.14), (m(135) + pd.Timedelta(seconds=1), 100.11, 100.14)]
    )
    r = run(m1, q)
    # 100.11 at T0+134 is above the active 99.94 (the pivot is not known yet); at T0+135:01 the 100.12 stop is.
    assert (
        r["reason"] == "TRAIL_STOP" and r["exit_time_utc"] == (m(135) + pd.Timedelta(seconds=1)).isoformat()
    )
    assert r["final_stop"] == pytest.approx(100.12) and r["r"] == pytest.approx((100.11 - 100.24) / 0.30)
    assert _tighten_stop(1, 100.12, 99.0) == 100.12 and _tighten_stop(-1, 100.12, 101.0) == 100.12


def test_pivot_formed_before_entry_is_ignored():
    # bar 22 (retest, low 99.96) is a pivot low confirmed at bar 23's close, but it formed before the entry.
    assert confirmed_pivots(m5_bars(make_m1(), 1), 1, 0.03, formed_from=CONFIRM) == []


def test_time_exit_at_first_quote_at_or_after_8_hours():
    # 100.55 one millisecond before the deadline is not an exit; 100.60 at the deadline is. R = 0.36 / 0.30 = 1.2;
    # MAE = entry quote (100.21 - 100.24) / 0.30 = -0.1
    q = FakeQuotes(
        [ENTRY_QUOTE, (DEADLINE - pd.Timedelta(milliseconds=1), 100.55, 100.58), (DEADLINE, 100.60, 100.63)]
    )
    r = run(make_m1(), q)
    assert r["reason"] == "TIME" and r["exit"] == pytest.approx(100.60) and r["r"] == pytest.approx(1.2)
    assert r["mfe_r"] == pytest.approx(1.2) and r["mae_r"] == pytest.approx(-0.1)


def test_stop_wins_over_time_on_the_same_quote():
    q = FakeQuotes([ENTRY_QUOTE, (DEADLINE, 99.80, 99.83)])
    assert run(make_m1(), q)["reason"] == "STOP"


def test_sell_mirror():
    # Mirror p' = 200 - p with zero bar spread: stop = 200 - 99.96 + 0.02 = 100.06; SELL enters at the bid 99.76
    # (mirror of ask 100.24); 1R = 0.30; marks on the ask: 100.10 >= 100.06 -> exit 100.10, R = -1.133333.
    m1 = make_m1(spread=0, mirror=True)
    ev = event(side=-1, stop=101.00)
    s = find_signal(ev, m1)
    assert s["status"] == "SIGNAL" and s["provisional_stop"] == pytest.approx(100.06)
    q = FakeQuotes([(ENTRY_T, 99.76, 99.79), (m(131), 100.07, 100.10)])
    r = run(m1, q, ev)
    assert r["entry"] == pytest.approx(99.76) and r["exit"] == pytest.approx(100.10)
    assert r["r"] == pytest.approx(-0.34 / 0.30)


def test_trade_past_the_supplied_bars_is_pending_not_guessed():
    q = FakeQuotes([ENTRY_QUOTE, (m(400), 100.5, 100.53)])
    assert run(make_m1().loc[: m(300)], q)["status"] == "PENDING_M1_COVERAGE"


# --- source / boundaries ---------------------------------------------------------------------------------------


def test_ineligible_source_is_not_traded():
    assert (
        run(make_m1(), FakeQuotes([]), event(runner_stopped_before_plus1=False))["status"]
        == "INELIGIBLE_SOURCE"
    )


def test_historical_replay_refuses_the_exam():
    ev = event(stop_time_utc=pd.Timestamp("2026-05-04", tz="UTC"))
    with pytest.raises(ValueError, match="exam"):
        run(make_m1(), FakeQuotes([]), ev)
    bars = make_m1()
    bars.index = pd.date_range("2026-04-17 23:00", periods=len(bars), freq="min", tz="UTC", name="open_time")
    with pytest.raises((ValueError, ExamLockedError)):
        simulate_historical_diagnostic(
            event(), bars, FakeQuotes([]), exam_start=EXAM_START, earliest_data=bars.index.min()
        )


def test_prospective_mode_refuses_pre_boundary_rows():
    with pytest.raises(ValueError, match="pre-boundary"):
        simulate_candidate(event(), make_m1(), FakeQuotes([]))


def prospective_case(minutes: int | None = None):
    """The TIME-exit case shifted to the prospective boundary (2026-10-21 00:00 UTC) for observer/adapter tests.

    ``minutes`` truncates the M1 bars (a shorter horizon leaves the trade pending).
    """
    from candidate import COLLECTION_START

    shift = COLLECTION_START - T0
    m1 = make_m1()
    if minutes is not None:
        m1 = m1.iloc[:minutes]
    m1.index = m1.index + shift
    q = FakeQuotes([(ENTRY_T + shift, 100.21, 100.24), (DEADLINE + shift, 100.60, 100.63)])
    return event(trade_key="fwd-001", stop_time_utc=STOP_TIME + shift), m1, q
