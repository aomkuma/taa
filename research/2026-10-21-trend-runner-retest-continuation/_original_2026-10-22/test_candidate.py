# ruff: noqa: S101
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from candidate import COLLECTION_START, _tighten_stop, simulate_candidate


def _event(**updates):
    event = {
        "trade_key": "fwd-001",
        "stop_time_utc": (COLLECTION_START + pd.Timedelta(minutes=100)).isoformat(),
        "side": 1,
        "entry": 100.0,
        "stop": 99.0,
        "spread": 0.02,
        "runner_stopped_before_plus1": True,
    }
    event.update(updates)
    return event


def _bars(*, invalidate: bool = False, no_retest: bool = False, minutes: int = 620) -> pd.DataFrame:
    start = COLLECTION_START
    idx = pd.date_range(start, periods=minutes, freq="min", tz="UTC")
    close = np.full(minutes, 99.80)
    high = close + 0.02
    low = close - 0.02

    # M5 bar 20 reclaims; bar 22 retests; bar 23 confirms continuation.
    close[20 * 5 : 21 * 5] = 100.12
    high[20 * 5 : 21 * 5] = 100.16
    low[20 * 5 : 21 * 5] = 100.08

    close[21 * 5 : 22 * 5] = 100.08
    high[21 * 5 : 22 * 5] = 100.13
    low[21 * 5 : 22 * 5] = 100.02

    close[22 * 5 : 23 * 5] = 100.06
    high[22 * 5 : 23 * 5] = 100.14
    low[22 * 5 : 23 * 5] = 99.96  # retest touches original entry

    close[23 * 5 : 24 * 5] = 100.20
    high[23 * 5 : 24 * 5] = 100.22
    low[23 * 5 : 24 * 5] = 100.05

    # Post-entry path stays above the structural stop through the full 8h horizon.
    close[24 * 5 :] = 100.30
    high[24 * 5 :] = 100.34
    low[24 * 5 :] = 100.26
    if invalidate:
        # Post-retest, pre-confirmation M5 candle breaches the already-known structure.
        low[23 * 5] = 99.70
    if no_retest:
        low[21 * 5 : 24 * 5] = 100.02

    open_ = close.copy()
    # Preserve a plausible low/high range around each close on the flat sections.
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "spread": 2.0},
        index=idx,
    )


def test_candidate_is_causal_and_times_out_after_eight_hours():
    result = simulate_candidate(_event(), _bars())
    assert result["status"] == "COMPLETE"
    assert result["reason"] == "TIME"
    assert pd.Timestamp(result["entry_time_utc"]) == COLLECTION_START + pd.Timedelta(minutes=120)
    assert pd.Timestamp(result["reclaim_time_utc"]) == COLLECTION_START + pd.Timedelta(minutes=105)
    assert pd.Timestamp(result["retest_time_utc"]) == COLLECTION_START + pd.Timedelta(minutes=115)
    assert pd.Timestamp(result["confirmation_time_utc"]) == COLLECTION_START + pd.Timedelta(minutes=120)
    assert result["holding_minutes"] == 480
    assert result["initial_risk"] > 0
    assert result["mfe_r"] >= 0
    assert result["mae_r"] <= 0
    entry_bar = _bars().loc[pd.Timestamp(result["entry_time_utc"])]
    assert result["entry"] == pytest.approx(entry_bar["open"] + entry_bar["spread"] * 0.01)
    exit_bar = _bars().loc[pd.Timestamp(result["exit_time_utc"])]
    assert result["exit"] == pytest.approx(exit_bar["open"])


def test_gap_through_initial_stop_fills_at_adverse_open():
    bars = _bars()
    gap_time = COLLECTION_START + pd.Timedelta(minutes=121)
    bars.loc[gap_time, ["open", "high", "low", "close"]] = 90.0
    result = simulate_candidate(_event(), bars)
    assert result["status"] == "COMPLETE"
    assert result["reason"] == "STOP_GAP"
    assert result["exit"] == pytest.approx(90.0)


def test_short_side_mirrors_entry_and_uses_ask_for_exit():
    bars = _bars()
    mirrored = bars.copy()
    mirrored["open"] = 200.0 - bars["open"]
    mirrored["high"] = 200.0 - bars["low"]
    mirrored["low"] = 200.0 - bars["high"]
    mirrored["close"] = 200.0 - bars["close"]
    result = simulate_candidate(_event(side=-1, entry=100.03, stop=101.03), mirrored)
    assert result["status"] == "COMPLETE"
    assert result["reason"] == "TIME"
    assert result["entry"] == pytest.approx(mirrored.loc[pd.Timestamp(result["entry_time_utc"]), "open"])
    assert result["exit"] == pytest.approx(mirrored.loc[pd.Timestamp(result["exit_time_utc"]), "open"] + 0.02)


def test_protective_stop_can_only_tighten():
    assert _tighten_stop(1, 99.0, 100.0) == 100.0
    assert _tighten_stop(1, 100.0, 99.0) == 100.0
    assert _tighten_stop(-1, 101.0, 100.0) == 100.0
    assert _tighten_stop(-1, 100.0, 101.0) == 100.0


def test_nonqualifying_source_is_never_reentered():
    result = simulate_candidate(_event(runner_stopped_before_plus1=False), _bars())
    assert result["status"] == "INELIGIBLE_SOURCE"


def test_structural_stop_breach_before_confirmation_cancels_setup():
    result = simulate_candidate(_event(), _bars(invalidate=True))
    assert result["status"] == "STRUCTURE_INVALIDATED"


def test_no_retest_is_not_final_until_six_completed_bars_are_seen():
    pending = simulate_candidate(_event(), _bars(no_retest=True, minutes=120))
    assert pending["status"] == "PENDING_RETEST_WINDOW"
    complete = simulate_candidate(_event(), _bars(no_retest=True, minutes=620))
    assert complete["status"] == "NO_RETEST"


def test_preboundary_data_is_rejected():
    bars = _bars()
    bars.index = bars.index - pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match="pre-boundary"):
        simulate_candidate(_event(), bars)


def test_utc_and_duplicate_bar_validation():
    bars = _bars()
    bars.index = bars.index.tz_localize(None)
    with pytest.raises(ValueError, match="UTC"):
        simulate_candidate(_event(), bars)

    bars = _bars()
    bars.index = bars.index.where(np.arange(len(bars)) != 1, bars.index[0])
    with pytest.raises(ValueError, match="unique"):
        simulate_candidate(_event(), bars)
