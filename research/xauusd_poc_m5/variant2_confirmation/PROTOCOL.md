# Variant 2: edge-only confirmation and acceptance filter

**Status:** preregistered before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)
**Test window:** active-session UTC dates 2026-09-24 through 2026-10-06. Five fully covered sessions are expected from coverage metadata; sessions failing the prior coverage rule will be excluded. This window does not overlap the two earlier short samples.

## Hypothesis recorded before run

Requiring a second M5 close to hold back inside value and disabling a fade after two consecutive M5 closes outside that edge should remove some false reversals. It will likely reduce trade count; its effect on net P&L is uncertain. No positive result is assumed.

## Fixed rules

- Use only the previous completed broker session's profile. Same quote-midpoint, $0.10 bin, POC and contiguous 70% value-area method as the prior study.
- Test VAL long and VAH short only. Do not enter on the POC line. Target POC.
- Candidate long: M5 bar touches VAL zone and closes above VAL. Candidate short: M5 bar touches VAH zone and closes below VAH.
- Confirmation: the immediately following M5 bar must close back on the inside side of the same boundary (above VAL for long, below VAH for short). Enter at the first quote after that confirmation bar closes.
- Acceptance filter: after two consecutive M5 closes below VAL, disable VAL longs for the rest of that session. After two consecutive M5 closes above VAH, disable VAH shorts for the rest of that session.
- Stop remains beyond the confirmation bar's wick by max($0.05, one prior-session median spread). One open trade at a time, at most one trade per edge/direction/session. The target is the prior-session POC.
- If both edges qualify on one signal bar, skip the ambiguous signal. Skip entries unless target and stop are on the correct sides of entry.
- Use the existing coverage rule. Tick replay is chronological; buy at ask, sell at bid, stop/target at the executable quote. P&L includes spread through bid/ask, but excludes commission and extra slippage.
- Compare the unchanged edge-only baseline (one close back inside, no acceptance filter) and Variant 2 on the exact same covered sessions. Do not change parameters after viewing results.

## Interpretation limit

This short period is an exploratory comparison, not evidence of a durable edge. The profile uses broker quote-update activity as a volume proxy, not centralized executed XAUUSD volume.
