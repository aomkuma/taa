# Setup TREND-RUNNER (TR1) - execution checklist

Started: 2026-10-20 13:48 Thai time (06:48 UTC).

Legend: `[ ]` not started, `[~]` in progress, `[x]` complete, `[!]` failed/blocked. A completed measurement is never
deleted; a failed rule keeps its result and lesson.

## 0. Scope and isolation

- [x] Create a dedicated TR1 research directory.
- [x] Write the detailed research plan before implementation or measurement.
- [x] Declare P1, P2 and exam boundaries.
- [x] Declare the spread-only primary cost and slippage parameter default 0.
- [x] Declare that PLAN-1, Setup OWN V3, engine code and configuration are read-only.
- [x] Limit round 1 to one entry family and four exit families.
- [x] Capture the initial git status for only this directory and note unrelated working-tree changes.
- [x] Add an automated import-boundary test that rejects setup-specific imports from the other research teams.

## 1. Data foundation - complete before measuring an outcome

- [x] Write a filtered M1 loader for P1 only.
- [x] Write a day tick reader that refuses to open a date outside its enabled period.
- [x] Add a disabled-by-default P2 switch; prove the P1 command cannot open P2.
- [x] Add a separate, locked exam switch; do not execute it.
- [x] Produce the bar/tick data manifest and gap/duplicate report (`FOUNDATION.md`).
- [x] Verify all internal timestamps are timezone-aware UTC.
- [x] Verify Asia/Thai time and New York DST anchors with hand cases.
- [x] Aggregate M5, M15 and H1 causally from M1.
- [x] Cross-check the aggregates against stored broker bars (all 23,962 bars exact).
- [x] Implement ATR and confirmed-fractal structure primitives with hand-worked tests.
- [x] Implement the spread-aware tick fill/exit simulator.
- [x] Preserve the ordered quotes inside one timestamp; a stop quote before a target quote wins.
- [x] Test gap fills, time exits, missing ticks and day boundaries.
- [x] Add truncation/no-look-ahead tests for every primitive (hand cases and three real-data cuts pass).
- [x] Plant material bugs in loaders, bars, ATR, structure and simulator; catch all 14.

## 2. P1 opportunity study - descriptive, no P2

- [x] Write the exact impulse-study definitions before computing.
- [x] Measure no more than three neighbouring impulse thresholds.
- [x] Report candidate counts separately for Asia, London and NY 08:30.
- [x] Measure the first pullback's depth, duration and risk in H1-ATR units.
- [x] Measure entry availability on M1, M5 and M15 without choosing the best after seeing P2.
- [x] Measure first passage to +1R, +2R, +3R and +5R.
- [x] Measure adverse excursion before each milestone.
- [x] Measure continuation after the fast target and subsequent giveback.
- [x] Measure time in market and collisions with the next session.
- [x] Save the complete candidate population and a reproducible text report.
- [x] Recompute the study with an independent implementation (364 rows, 16,016 field checks).
- [x] Plant outcome-label and future-bar leaks; catch all 8.

## 3. Freeze round 1 on P1

- [x] Choose one impulse rule and report every setting tried.
- [x] Freeze the entry timeframe selection.
- [x] Freeze the pullback and continuation-entry rules.
- [x] Freeze the initial stop and larger-TF level-space rules.
- [x] Freeze the FAST control exit.
- [x] Freeze the runner activation gate.
- [x] Freeze the SWING exit.
- [x] Freeze the SPLIT fraction and exit.
- [x] Freeze the STATE selector.
- [x] Write `FROZEN_ROUND_1.md` with exact rules, parameters and code/config hashes.
- [x] Draw twelve P1 trades: six winners and six losers.
- [x] Check those charts against the written rules, not against desired outcomes.
- [x] Re-run tests, mutants, look-ahead checks and independent replay.

## 4. P2 validation - one run of the frozen round

- [x] Confirm the frozen hashes before enabling P2.
- [x] Record the single validation command and start time.
- [x] Run P2 once without changing a parameter.
- [x] Report P1/P2 counts, trades/day, win rate, R, USD and 95% ranges.
- [x] Report weekly results, worst trade, losing streak and drawdown.
- [x] Report results by window, direction and fixed M1 timeframe; explicitly note no frozen entry state.
- [x] Report results without the best one and best three trades.
- [x] Compare FAST, SWING, SPLIT and STATE on exactly the same entries.
- [x] Mark the round FAIL: P2 SPLIT +0.088R/trade is below +0.15.
- [x] Write the next permitted hypothesis before any future rule modification (see final checkpoint).

## 5. Portfolio and robustness

- [x] Re-derive every frozen P1 and P2 trade from raw ticks independently.
- [x] Confirm spread is charged and slippage defaults to 0.
- [!] Do not run slippage sensitivities: the zero-slippage primary already fails and adverse slippage cannot rescue it.
- [x] Simulate TR1 standalone.
- [ ] Simulate TR1 beside PLAN-1 without editing either trade list.
- [ ] Report one-position-at-a-time collisions and foregone R for both setups.
- [x] Report TR1 one-position collisions, exposure hours and UTC-date crossing risk.
- [ ] Check neighbouring parameters for sign stability.
- [x] Verify concentration: P1 is London/outlier-led and P2 changes session/direction leadership.

## 6. Pre-exam gate

- [!] P1 and P2 are each at least +0.15 net R/trade: FAIL (+0.265 / +0.088).
- [x] Each part has at least 30 executed trades (138 / 142).
- [x] Removing the best trade leaves both parts non-negative (+0.147 / +0.004).
- [x] Full tests, mutants, no-look-ahead checks and independent replay pass.
- [x] The frozen source/config hashes are recorded and still match after validation.
- [x] The exam reader has not been invoked by any earlier command.
- [ ] The owner has seen the learning result and the frozen exam rule.
- [ ] Only the measurer is assigned the one exam run.

## 7. Exam and post-research work - locked

- [ ] Run the frozen exam exactly once.
- [ ] Report it week by week with R, USD, worst loss, streak and drawdown.
- [ ] Record PASS/PARTIAL/FAIL without modifying the exam result.
- [ ] If accepted, design a separate `app/strategy/` module and configuration lane.
- [ ] Run the engine test, lint, type and security gates before any DEMO proposal.
- [ ] Keep LIVE off until Phase 14 and explicit owner approval.

## Checkpoint log

### 2026-10-20 13:48 Thai - plan created

- No strategy implementation existed in this directory before the plan.
- No P1, P2 or exam outcome was read for TR1.
- Next checkpoint: finish section 0 and the data foundation through the exam guards and hand-worked loader tests.

### 2026-10-20 13:58 Thai - foundation checkpoint

- 30 tests passed; ruff format/check passed; 14 of 14 planted foundation bugs were caught.
- P1 M5/M15/H1 derived bars equal every stored broker OHLC value.
- The tick store contains 19,025 repeated millisecond timestamps; all quotes are retained in file order.
- No P2 or exam data was opened. Latest tick file opened: 2026-01-15.
- Next checkpoint: finish real-data truncation checks and write the P1 opportunity-study definitions before running
  them.

### 2026-10-20 15:00 Thai - round 1 frozen

- Selected entry: 0.25 H opening impulse, causal M1 first pullback/continuation, all three windows.
- Selected exit: one-third at +1R and two-thirds on the M5-to-M15 structure trail.
- P1 SPLIT: 138 trades, +0.265R/trade, +192.92 USD at 0.01 lot; best-one removal +0.147R.
- The common frozen runner reproduced 138 entries and 552 exit rows exactly.
- Frozen hashes, independent replay, 12 chart audits and 31/31 planted bugs passed. P2 and exam were not yet read.

### 2026-10-20 19:47 Thai - P2 validation and stop decision

- The one frozen P2 command began at 15:01:17 Thai; 142 entries and 568 control rows were generated.
- Frozen SPLIT P2: +0.088R/trade, +12.50R, +84.20 USD at 0.01 lot. Best-one removal is +0.004R; maximum
  drawdown is 20.24R; March is negative.
- Independent P2 replay passed 2,272 entry-field and 5,680 exit-field checks. Latest tick day opened was 2026-04-17.
- Round 1 is FAIL because P2 is below +0.15R/trade. Exam, engine, DEMO and PLAN-1 portfolio integration remain
  locked/skipped.
- Next permitted hypothesis (not tested here): retain the causal first-pullback entry, but treat persistence as a
  session-relative flow problem rather than a fixed partial/trail problem. A new round must predeclare a present-time
  higher-timeframe-flow plus open-space gate on a new design slice; P2 round-1 results may diagnose the idea but may
  not be reused as its validation set.
