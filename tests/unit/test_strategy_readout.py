"""Hand-worked tests for app/strategy/readout.py's filter (TAA-1804); the full lines are checked byte for byte
against the research scripts in research/2026-10-23-entry/test_readout_parity.py."""

from __future__ import annotations

from app.strategy import readout as ro


def test_keep_takes_the_reading_lines_only_and_strips_them():
    lines = [
        "# Every timeframe at Fri 23 Oct 16:00 Thai",
        "M15 ATR  11.80 | big trend DOWN (LH 2, LL 6, HH 0, HL 0) | rhythm DOWN",
        "    swings: H 4102.8, L 4057.4",
        "    now 3995.64: running up from 3975.6",
        "  the last 6 bars: 3/5 higher lows, 3/5 higher highs (mixed)",
        "  the last 6 bars: 4/5 higher lows, 4/5 higher highs (UP steps)",
        "  the last 12 bars' range 2.1 ATR (a squeeze); last volume 0.7 x the mean",
        "  the last 12 bars' range 5.5 ATR; last volume 1.5 x the mean",
        "- 09:45 T1 re-test SELL 4019.16, stop 4035.90 (risk 16.7)",
        "- BOAR (yesterday strong down)",
        "## 3. Trend, phase, structure, volatility",
    ]
    assert ro.keep(lines) == [
        "M15 ATR  11.80 | big trend DOWN (LH 2, LL 6, HH 0, HL 0) | rhythm DOWN",
        "now 3995.64: running up from 3975.6",
        "the last 6 bars: 4/5 higher lows, 4/5 higher highs (UP steps)",
        "the last 12 bars' range 2.1 ATR (a squeeze); last volume 0.7 x the mean",
        "- 09:45 T1 re-test SELL 4019.16, stop 4035.90 (risk 16.7)",
        "- BOAR (yesterday strong down)",
    ]
