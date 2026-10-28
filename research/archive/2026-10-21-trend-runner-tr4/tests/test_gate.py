from datetime import datetime, timedelta, timezone

import pytest

from tr4.gate import apply_gate


UTC = timezone.utc


def row(key, minute, pct, action="RUNNER", *, available_minute=None):
    now = datetime(2026, 10, 21, 1, minute, tzinfo=UTC)
    available = now if available_minute is None else datetime(2026, 10, 21, 1, available_minute, tzinfo=UTC)
    return {
        "trade_key": key,
        "decision_time": now,
        "parent_action": action,
        "atr_m15_pct": pct,
        "atr_m30_pct": pct,
        "atr_h1_pct": pct,
        "atr_m15_available_at": available,
        "atr_m30_available_at": available,
        "atr_h1_available_at": available,
    }


def test_pause_is_strictly_above_80_and_resume_is_at_or_below_70():
    decisions = apply_gate([
        row("a", 0, 0.80),
        row("b", 1, 0.81),
        row("c", 2, 0.70),
        row("d", 3, 0.69),
    ])
    assert [d.transition for d in decisions] == ["NONE", "PAUSE", "RESUME", "NONE"]
    assert [d.tr4_action for d in decisions] == ["RUNNER", "SKIP", "RUNNER", "RUNNER"]


def test_paused_state_persists_between_thresholds_and_parent_skip_stays_skip():
    decisions = apply_gate([
        row("a", 0, 0.85),
        row("b", 1, 0.75, "SKIP"),
        row("c", 2, 0.71),
    ])
    assert [d.paused for d in decisions] == [True, True, True]
    assert [d.tr4_action for d in decisions] == ["SKIP", "SKIP", "SKIP"]


def test_uses_median_of_three_timeframe_percentiles():
    current = row("a", 0, 0.1)
    current["atr_m30_pct"] = 0.85
    current["atr_h1_pct"] = 0.81
    decision = apply_gate([current])[0]
    assert decision.composite_percentile == 0.81
    assert decision.transition == "PAUSE"


def test_rejects_future_atr_input():
    with pytest.raises(ValueError, match="not available"):
        apply_gate([row("a", 0, 0.8, available_minute=1)])


def test_rejects_nonchronological_rows_and_duplicate_keys():
    with pytest.raises(ValueError, match="nondecreasing"):
        apply_gate([row("a", 2, 0.2), row("b", 1, 0.2)])
    with pytest.raises(ValueError, match="unique"):
        apply_gate([row("a", 0, 0.2), row("a", 1, 0.2)])


def test_rejects_missing_or_invalid_percentile_and_non_utc_timestamp():
    bad_pct = row("a", 0, 1.01)
    with pytest.raises(ValueError, match="percentile"):
        apply_gate([bad_pct])
    bad_time = row("b", 0, 0.2)
    bad_time["decision_time"] = datetime(2026, 10, 21, 1, 0)
    with pytest.raises(ValueError, match="UTC"):
        apply_gate([bad_time])
