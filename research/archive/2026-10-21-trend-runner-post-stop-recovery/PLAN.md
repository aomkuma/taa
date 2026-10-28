# Post-stop recovery and one fixed re-entry hypothesis

## Objective

Follow up the trade journal's observation that many stopped-before-1R trades later moved favorably. Measure the timing/shape of that recovery, then evaluate one predeclared M5-confirmed re-entry rule as exploratory research. Do not edit or integrate TR1/TR3/TR4.

## Data and locked boundaries

- Source population: scored walk-forward journal rows classified `STOP_BEFORE_1R` (the initial RUNNER was stopped before a preceding +1R touch).
- Source M1 price rows: timestamps from 2023-09-01 UTC and strictly before 2026-04-18 UTC. Fail closed if any exam interval or post-shadow row enters.
- Any re-entry outcome must complete before 2026-04-18 UTC. The locked exam `[2026-04-18, 2026-10-18)` and post-shadow data on/after 2026-10-21 remain unused.
- Data are M1 OHLC with recorded spread, not tick sequence. No slippage, per user direction.

## Descriptive recovery measurements

- Time from first modeled stop to M5 close reclaiming the original entry price in the original setup direction.
- Fraction reaching original entry, +1R and +2R from the original entry within 15/30/60/120/240/480 minutes after stop.
- Favorable/adverse excursion after the reclaim; session, direction, H1 ATR, and calendar-year cuts.
- These are path descriptions, not a causal explanation or a tradable P&L result.

## One frozen exploratory re-entry candidate

1. Wait for the first completed M5 close after the initial stop that reclaims the original entry price in the original direction (`close >= original entry` for BUY, `close <= original entry` for SELL).
2. Enter at the next available M1 open, including recorded spread on the executable side.
3. Stop at one original initial-risk unit from the new entry; target +2R from the new entry; time exit after 120 minutes.
4. Resolve a same-M1-bar stop/target collision against the trade; gaps through stops fill at the observed open. One trigger and one re-entry maximum per initial setup.

Do not grid-search trigger, stop, target, or holding time. Report the event-level results by year and chronological half; trades are not portfolio-independent, so do not interpret summed R as an account curve.

## Decision criteria

- Report event counts/coverage first, then candidate R/trade, win rate, stop/target/time exits, holding time, and temporal cuts.
- If the candidate is negative, unstable, or concentrated in a single period, reject that exact frozen implementation. Audit trigger timing, side/spread conventions, bar-order ambiguity, data boundaries, and plausible mechanism before deciding whether a separate hypothesis merits study. Do not infer that a broader setup family is unusable from one failed implementation.
- If positive, label it **exploratory only**: the rule was motivated by previously viewed historical path behavior. Freeze it and collect fresh forward-shadow evidence before considering another optimization or any live/order-path change.

## Checklist

- [x] Create fail-closed, exam-safe M1 loader and validate source cohort.
- [x] Produce causal recovery and reclaim-time diagnostics.
- [x] Simulate only the predeclared M5 reclaim re-entry rule.
- [x] Report all eligible events, exits, chronological/year cuts, and limitations.
- [x] Test path chronology and exam boundary; do not alter existing strategy files/order paths.
- [x] Audit whether failure is explained by implementation ambiguity or by the tested rule's entry/stop behavior.
- [x] Run one explicitly post-hoc stop-width sensitivity to diagnose premature stop-outs; keep it labeled exploratory, not confirmation.

## Completion result

All 632 source events had a full recovery horizon before the exam boundary. A completed M5 reclaim appeared in 514 (81.3%); immediate re-entry with a 1R stop returned -64.32R total and -0.125R per attempt. Audit found no same-M1 stop/target collisions or evident mismatch from the written rule. A 1.5R-stop sensitivity improved to -0.049 original-risk-R per attempt but remained negative and both chronological halves remained negative. Reject both implementations for strategy use, but do not reject the wider re-entry/trend-continuation idea. The stop-width sensitivity was selected after inspecting baseline results, so it is diagnostic only. Next, freeze a distinct retest/continuation-plus-structure-stop hypothesis, then evaluate only on untouched forward-shadow data before any promotion. See `RESULTS.md`.

## Post-hoc audit note (2026-10-21)

After the original frozen 1R-stop candidate failed, the journal paths showed that 155 of 357 re-entry stop-outs later touched +2R within the observation horizon. This motivated exactly one 1.5R stop-width sensitivity. It is recorded transparently as post-hoc analysis; it is not part of the preregistered candidate and does not count as independent evidence. That sensitivity reduced the average loss materially, but stayed negative overall and in each chronological half. No parameter sweep was performed.
