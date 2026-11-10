"""The runner's start checks on the stored bars (eye/ZONE_LIVE.md L2): the store of the pinned server, a frame
missing, a frame starting later than the simulation's, the cut of a frame that starts earlier, and the overlap with
the broker's closed bars (it reaches back to the stored last bar; open time, then open / high / low / close within
one tick). Table-driven, on small constructed frames; one test reads the real ``FBS-Demo`` store."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.zone.core import load_bars
from app.zone.history_check import (
    REFERENCE_FIRST_BARS,
    check_overlap,
    check_stored_history,
    required_frames,
)

MINUTES = {"D1": 1440, "H4": 240, "H1": 60, "M15": 15, "M5": 5}
SERVER = "FBS-Demo"
ROOT = Path(__file__).resolve().parents[2]


def mk(tf: str, first: pd.Timestamp, n: int = 6, base: float = 100.0) -> pd.DataFrame:
    ot = [first + pd.Timedelta(minutes=MINUTES[tf] * k) for k in range(n)]
    return pd.DataFrame(
        {
            "open_time": ot,
            "close_time": [t + pd.Timedelta(minutes=MINUTES[tf]) for t in ot],
            "open": [base + k for k in range(n)],
            "high": [base + k + 2 for k in range(n)],
            "low": [base + k - 2 for k in range(n)],
            "close": [base + k + 1 for k in range(n)],
        }
    )


def bump(df: pd.DataFrame, i: int, col: str, delta: float) -> None:
    df.loc[df.index[i], col] = float(df[col].iloc[i]) + delta


def ref_frames(**shift: pd.Timedelta) -> dict[str, pd.DataFrame]:
    """Every frame starting at its reference first bar, shifted by ``shift[tf]`` (a positive shift is later)."""
    return {tf: mk(tf, REFERENCE_FIRST_BARS[tf] + shift.get(tf, pd.Timedelta(0))) for tf in MINUTES}


# --- the start checks ---------------------------------------------------------------------------------------------


def test_the_reference_is_the_measured_first_bars() -> None:
    assert {tf: t.strftime("%Y-%m-%d") for tf, t in REFERENCE_FIRST_BARS.items()} == {
        "D1": "2021-09-01",
        "H4": "2023-04-02",
        "H1": "2023-08-01",
        "M15": "2023-08-01",
        "M5": "2025-10-05",
    }
    assert all(t.tzinfo is not None for t in REFERENCE_FIRST_BARS.values())


def test_required_frames_follow_the_exec_frame() -> None:
    assert required_frames("M15") == ("D1", "H4", "H1", "M15")
    assert required_frames("M5") == ("D1", "H4", "H1", "M15", "M5")
    with pytest.raises(ValueError, match="exec_tf"):
        required_frames("H1")


def test_frames_at_the_reference_pass_uncut() -> None:
    fr = ref_frames()
    res = check_stored_history(SERVER, fr, "M5")
    assert res.ok and res.reasons == ()
    assert set(res.frames) == set(MINUTES)
    for tf, df in res.frames.items():
        assert len(df) == len(fr[tf]) and df["open_time"].iloc[0] == REFERENCE_FIRST_BARS[tf]


@pytest.mark.parametrize("store", [None, {}], ids=["none", "empty"])
def test_no_store_for_the_server_is_refused(store: dict[str, pd.DataFrame] | None) -> None:
    res = check_stored_history("Other-Server", store, "M15")
    assert not res.ok and res.frames == {}
    assert len(res.reasons) == 1 and "no stored bars" in res.reasons[0] and "Other-Server" in res.reasons[0]


@pytest.mark.parametrize(
    ("exec_tf", "drop", "named"),
    [
        ("M15", "D1", "D1"),
        ("M15", "H4", "H4"),
        ("M15", "H1", "H1"),
        ("M15", "M15", "M15"),
        ("M5", "M5", "M5"),
    ],
)
def test_a_missing_frame_is_refused_and_named(exec_tf: str, drop: str, named: str) -> None:
    fr = ref_frames()
    del fr[drop]
    res = check_stored_history(SERVER, fr, exec_tf)
    assert not res.ok and res.frames == {}
    assert len(res.reasons) == 1 and res.reasons[0].startswith(f"{named}:") and "missing" in res.reasons[0]


def test_an_empty_or_none_frame_counts_as_missing() -> None:
    fr: dict[str, pd.DataFrame | None] = dict(ref_frames())
    fr["H4"] = ref_frames()["H4"].iloc[0:0]
    fr["D1"] = None
    res = check_stored_history(SERVER, fr, "M15")
    assert not res.ok
    assert [r.split(":")[0] for r in res.reasons] == ["D1", "H4"]


def test_m5_is_not_required_when_the_exec_frame_is_m15() -> None:
    fr = ref_frames()
    del fr["M5"]
    assert check_stored_history(SERVER, fr, "M15").ok
    assert not check_stored_history(SERVER, fr, "M5").ok


@pytest.mark.parametrize("tf", ["D1", "H4", "H1", "M15", "M5"])
def test_a_frame_starting_later_than_the_reference_is_refused_and_named(tf: str) -> None:
    fr = ref_frames(**{tf: pd.Timedelta(minutes=MINUTES[tf])})  # one bar later
    res = check_stored_history(SERVER, fr, "M5")
    assert not res.ok and res.frames == {}
    assert len(res.reasons) == 1 and res.reasons[0].startswith(f"{tf}:") and "later" in res.reasons[0]


def test_every_refusal_found_is_listed() -> None:
    fr = ref_frames(H1=pd.Timedelta(hours=1), D1=pd.Timedelta(days=3))
    del fr["M15"]
    res = check_stored_history(SERVER, fr, "M15")
    assert [r.split(":")[0] for r in res.reasons] == ["D1", "H1", "M15"]


def test_a_frame_starting_earlier_is_cut_to_the_reference_first_bar() -> None:
    fr = {tf: mk(tf, REFERENCE_FIRST_BARS[tf] - pd.Timedelta(minutes=MINUTES[tf] * 3), n=9) for tf in MINUTES}
    res = check_stored_history(SERVER, fr, "M5")
    assert res.ok
    for tf, df in res.frames.items():
        assert df["open_time"].iloc[0] == REFERENCE_FIRST_BARS[tf]
        assert len(df) == 6 and list(df.index) == list(range(6))
        assert df["open"].iloc[0] == fr[tf]["open"].iloc[3]  # the dropped bars are the first three


def test_only_the_frames_that_start_earlier_are_cut() -> None:
    fr = ref_frames()
    fr["H1"] = mk("H1", REFERENCE_FIRST_BARS["H1"] - pd.Timedelta(hours=2), n=8)
    res = check_stored_history(SERVER, fr, "M15")
    assert res.ok
    assert len(res.frames["H1"]) == 6 and res.frames["H1"]["open_time"].iloc[0] == REFERENCE_FIRST_BARS["H1"]
    assert res.frames["D1"].equals(fr["D1"])
    assert "M5" in res.frames  # not required, but it reaches the reference: kept (cut)


def test_an_unneeded_late_m5_is_left_out_not_refused() -> None:
    fr = ref_frames(M5=pd.Timedelta(days=1))
    res = check_stored_history(SERVER, fr, "M15")
    assert res.ok and "M5" not in res.frames


# --- the overlap with the broker ----------------------------------------------------------------------------------

T0 = pd.Timestamp("2026-10-01 00:00", tz="UTC")
TICK = 0.01


def stored_h1() -> pd.DataFrame:
    return mk("H1", T0, n=10)


def broker_h1(first: int = 6, n: int = 8) -> pd.DataFrame:
    """The broker's closed bars from stored bar ``first``, running past the stored last bar (index 9)."""
    full = mk("H1", T0, n=first + n)
    return full.iloc[first:].reset_index(drop=True)


def test_the_overlap_that_agrees_passes() -> None:
    assert check_overlap("H1", stored_h1(), broker_h1(), TICK).ok


def test_the_broker_ending_at_the_stored_last_bar_passes() -> None:
    assert check_overlap("H1", stored_h1(), broker_h1(first=5, n=5), TICK).ok


def test_the_broker_starting_exactly_at_the_stored_last_bar_passes() -> None:
    assert check_overlap("H1", stored_h1(), broker_h1(first=9, n=3), TICK).ok


def test_a_difference_of_exactly_one_tick_is_within_the_tolerance() -> None:
    b = broker_h1()
    bump(b, 1, "high", TICK)
    bump(b, 2, "low", -TICK)
    assert check_overlap("H1", stored_h1(), b, TICK).ok


@pytest.mark.parametrize("col", ["open", "high", "low", "close"])
def test_a_price_differing_by_more_than_a_tick_is_refused_naming_frame_and_bar(col: str) -> None:
    b = broker_h1()
    bump(b, 2, col, 5 * TICK)
    res = check_overlap("H1", stored_h1(), b, TICK)
    bar = T0 + pd.Timedelta(hours=8)
    assert not res.ok and res.frame == "H1" and res.bar == bar
    assert "H1" in res.reason and str(bar) in res.reason and col in res.reason


def test_the_first_disagreeing_bar_is_the_one_named() -> None:
    b = broker_h1()
    bump(b, 3, "close", 1.0)
    bump(b, 1, "open", 1.0)
    assert check_overlap("H1", stored_h1(), b, TICK).bar == T0 + pd.Timedelta(hours=7)


def test_a_gap_between_the_stored_last_bar_and_the_broker_is_refused() -> None:
    res = check_overlap("M15", mk("M15", T0, n=4), mk("M15", T0 + pd.Timedelta(minutes=60), n=4), TICK)
    assert not res.ok and res.frame == "M15" and res.bar == T0 + pd.Timedelta(minutes=45)
    assert "gap" in res.reason and "M15" in res.reason


def test_a_broker_bar_the_stored_frame_lacks_is_refused() -> None:
    s = stored_h1().drop(index=7).reset_index(drop=True)  # the stored bar 7 missing
    res = check_overlap("H1", s, broker_h1(), TICK)
    assert not res.ok and res.bar == T0 + pd.Timedelta(hours=7) and "stored frame lacks" in res.reason


def test_a_stored_bar_the_broker_lacks_is_refused() -> None:
    b = broker_h1().drop(index=2).reset_index(drop=True)  # the broker lacks bar 8
    res = check_overlap("H1", stored_h1(), b, TICK)
    assert not res.ok and res.bar == T0 + pd.Timedelta(hours=8) and "broker lacks" in res.reason


def test_another_time_base_is_refused() -> None:
    b = broker_h1()
    b["open_time"] = b["open_time"] + pd.Timedelta(hours=2)  # the same prices, shifted two hours
    res = check_overlap("H1", stored_h1(), b, TICK)
    assert not res.ok and res.frame == "H1" and res.bar is not None


def test_empty_frames_are_refused() -> None:
    assert not check_overlap("H1", stored_h1(), broker_h1().iloc[0:0], TICK).ok
    assert not check_overlap("H1", stored_h1().iloc[0:0], broker_h1(), TICK).ok


def test_a_nan_price_is_a_disagreement() -> None:
    b = broker_h1()
    b.loc[1, "close"] = float("nan")
    assert not check_overlap("H1", stored_h1(), b, TICK).ok


# --- the real store -----------------------------------------------------------------------------------------------


def test_the_real_fbs_demo_store_passes() -> None:
    d = ROOT / "data" / "history" / SERVER / "XAUUSD"
    if not d.exists():
        pytest.skip("no stored bars on this machine")
    bars = load_bars("XAUUSD")
    frames = {tf: bars.frame(tf) for tf in MINUTES}
    for exec_tf in ("M15", "M5"):
        res = check_stored_history(SERVER, frames, exec_tf)
        assert res.ok, res.reasons
        for tf, df in res.frames.items():
            assert df["open_time"].iloc[0] == REFERENCE_FIRST_BARS[tf]
            assert len(df) == len(frames[tf])  # the store starts at the reference: nothing is cut
    # the store agrees with itself over a span: the overlap check passes on the last bars of each frame
    for tf, df in frames.items():
        assert check_overlap(tf, df, df.tail(50), bars.point).ok
