#!/usr/bin/env bash
# The heavy family (chart patterns, harmonics) plus the candle reversal, two symbols at a time (commit memory).
cd "$(dirname "$0")/../.." || exit 1
STRATS="setup_pattern_breakout,setup_neckline_break,setup_harmonic_prz,setup_candle_reversal"
DET="chart.double,chart.triple,chart.head_shoulders,chart.triangle,chart.wedge,chart.rectangle,chart.flag,chart.cup_handle,harmonic.abcd,harmonic.bat,harmonic.butterfly,harmonic.crab,harmonic.cypher,harmonic.gartley,harmonic.shark,candle.engulfing,candle.hammer,candle.shooting_star,candle.doji,candle.inside_outside,candle.star,candle.harami,candle.tweezer"
SYMBOLS="EURUSD GBPUSD" bash research/2026-10-07-setup-review/run_family.sh heavy "$STRATS" "$DET"
SYMBOLS="USDJPY XAUUSD" bash research/2026-10-07-setup-review/run_family.sh heavy "$STRATS" "$DET"
