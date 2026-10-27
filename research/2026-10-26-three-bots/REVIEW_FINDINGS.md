# Review findings — 2026-10-27

## 1. Is turning the take-profit floor off safe?

**Clean for division-by-zero and target-collapse in accepted entries; the floor is now genuinely off.**

- **What I checked:** `app/ai/plan.py` compares `abs(tp - entry) < MIN_TAKE_PROFIT`; `app/ai/trader.py` sets that constant to `0.0` and adds the same strict `< 0` C5 veto. Since absolute reward is nonnegative, neither comparison rejects a positive reward. A zero-distance plan is still rejected by the following directional check: `(entry - tp if sell else tp - entry) <= 0`. In `AITrader.recheck_plan_stops`, the zero floor leaves the independent `plan_min_rr * risk` gate. At the fill check, `max(p.min_take_profit, p.plan_min_rr * abs(order.stop - price))` becomes `max(0, 0.2 * risk)` with defaults; that is still a positive R gate when risk is positive.
- **Arithmetic:** `reach = abs(o.target - price) >= 0`; with `target_trim=0.10` and `min_take_profit=0`, `min(0, reach)=0` and `max(reach * (1 - 0.10), 0)=0.9 * reach`. There is no division. For every `reach > 0`, the trimmed target stays 90% of the way from fill to the target and cannot land on the fill. `target_trim < 1` is enforced by the parameter model. If `reach=0`, the expression yields zero and the target would equal the fill, but `AIOrder.geometry_ok(price)` rejects an order whose target is not strictly on its winning side before `entry_signal` applies this trim.
- **Strategy floors:** `TrendBox` and `RangeBreak` also use `reward < min_take_profit`, so a 0.0 default makes that part of the condition false for nonnegative reward. Their independent positive `min_r` checks remain; their targets are built beyond the entry, and TrendBox also checks target direction. No calculation divides by the floor.
- **Cost:** Sub-$5 targets can now pass the C5 distance checks. The AI lane still trims 10%, the AI path still applies its R checks, and the two strategies still apply their positive R floors. The claim that the floor rejected 1 of 496 signals is recorded in the research files; this review checked the changed arithmetic and call sites, not that historical count.

## 2. Are the three new tests honest?

**Yes. Each new test reaches the production behavior it claims to cover, and targeted mutations made each fail.**

- **Trend box cap:** `test_a_box_taller_than_the_cap_is_not_a_box` calls `TrendBoxDown.evaluate` with a 13 USD box against a 12 USD cap, then raises the configured cap and expects entry on the same bars. The test does not calculate or substitute the production filter. Removing the `box * leg` cap and inverting its comparison each failed this single test.
- **H1 close-to-open resampling:** `test_h4_is_built_from_h1_open_times_and_only_from_closed_bars` calls the production `RangeBreak._h4_from_h1` and checks exact H4 timestamps and aggregated highs. Replacing the one-hour shift with zero or replacing H4 maximum high with the first high failed this single test.
- **Forming H4 exclusion:** `test_an_unclosed_h4_bar_never_reaches_the_zigzag` calls `RangeBreak.evaluate`, captures the high array passed to the production `zigzag`, and asserts the forming bar's sentinel high is absent and that 300 bars remain. Filtering by H4 open time instead of H4 close time failed this single test.
- **Cost:** No flaw found in these tests' coverage of their stated production lines. The direct resampling test deliberately tests the helper rather than duplicating its grouping logic; the forming-bar test exercises the filter through `evaluate`.

## 3. Plant bugs against the new tests

**The six selected bugs were caught. One additional diagnostic mutation was missed (6/7 overall).** I added `research/2026-10-26-three-bots/review_plant_bugs.py`, which saves byte-for-byte backups before each mutation, restores in a `finally` block, and recovers leftover backups at the next invocation. The run output is in `research/2026-10-26-three-bots/review_plant_bugs_output.txt`.

| Mutation | Single test run | Result |
|---|---|---|
| Invert the trend box cap comparison | `test_a_box_taller_than_the_cap_is_not_a_box` | CAUGHT |
| Add the box share to the leg instead of multiplying | `test_a_box_taller_than_the_cap_is_not_a_box` | CAUGHT |
| Label H4 bins at their close rather than their open | `test_h4_is_built_from_h1_open_times_and_only_from_closed_bars` | CAUGHT |
| Aggregate H4 high with `first` instead of `max` | `test_h4_is_built_from_h1_open_times_and_only_from_closed_bars` | CAUGHT |
| Divide the box cap by the leg instead of multiplying | `test_a_box_taller_than_the_cap_is_not_a_box` | CAUGHT |
| Divide reward by the zero floor | `test_sell_break_plan_is_the_mirror_and_reward_floor_is_enforced` | CAUGHT |
| Exclude the latest already-closed H4 bar by filtering at `open + 5h` | `test_an_unclosed_h4_bar_never_reaches_the_zigzag` | MISSED |

The missed diagnostic changes the H4 close cutoff from four hours to five, which drops the most recent closed H4 bar. The test still sees 300 bars because older source data fills the tail slice; it checks that a forming bar is absent, but not that the latest closed bar is present. **Cost:** if production had this off-by-one cutoff, the range strategy would use an H4 box up to four hours older than intended. The production cutoff is currently four hours. The mutation run first passed both strategy test files, then ran each listed single test with only its corresponding production mutation. Every mutation was restored. No planted bug remains.

## 4. Anything else wrong?

**The range warmup and timeframe declarations line up, but daily flattening is unreachable for these extra-lane strategies. The lane items are currently disabled.**

- **Warmup and frames:** `RangeBreak.required_timeframes()` asks for M1, M5, and H1, and `warmup_bars()` returns 1,200. The `three_bots` lane enables those frames through `higher: H1`, `entry: M5`, and `refinement: M1`, has no extra context frames, and sets `warmup_bars: 1200`. `ContextBuilder.analyze` requests the configured warmup count for each enabled timeframe, so RangeBreak receives up to 1,200 closed H1 bars; it resamples those to 300 closed H4 bars. TrendBox only needs 400 H1 bars. The three configured strategy names match the strategy class names. All three `enabled` fields are `false`, so the lane currently builds no active strategies until enabled.
- **Daily close is unreachable in this lane:** M5 close timestamps can land exactly on 07:00 Bangkok, so the time comparison itself is representable. However, `Engine._evaluate` calls `backend.on_bar` only for the main lane. For every lane it calls `backend.on_lane_bar`; both paper and broker `on_lane_bar` implementations call `manage_position` but do not call `should_close`. The `should_close` calls are in `on_bar`. Since `three_bots` is an extra lane, enabling these strategies still will not invoke either `TrendBox.should_close` or `RangeBreak.should_close` through normal lane evaluation.
- **Separate risk config change:** The same visible `config.yaml` diff raises `max_account_drawdown_percent` from 10 to 50, raises `max_consecutive_losses` from 4 to 50, and sets `consecutive_loss_pause_hours` from 24 to 0. The comment calls these breakers deactivated, but the change materially allows a deeper account drawdown and a much longer losing streak before the streak limit, with no cooldown. I did not change these settings.
- **Cost:** If the three bots are enabled as configured, their stated daily flatten at 07:00 will not close their lane-owned positions via `should_close`; trades may remain open until another exit mechanism closes them. The higher drawdown and loss-streak limits increase exposure if those config changes are active.

## Verification

- `.venv\Scripts\python -m pytest -q tests/unit/test_strategy_trend_box.py tests/unit/test_strategy_range_break.py` — **36 passed**.
- `.venv\Scripts\python research\2026-10-26-three-bots\review_plant_bugs.py` — **6 caught, 1 missed**; source files restored. The nonzero status reports the test gap above.

---

## What the research session did with these findings (2026-10-27)

| finding | verdict | action |
|---|---|---|
| 1. the floor at 0.0 is arithmetically safe | accepted, re-checked | no change |
| 2. the three new tests are honest | accepted | no change |
| 3. a cutoff one bar too early passed `test_an_unclosed_h4_bar_never_reaches_the_zigzag` | **real gap** | split into two tests: the forming bar must be absent (01:05 decision) and the newest closed bar must be present (00:05 decision). The 5 h mutation now fails 4 tests. |
| 4a. `should_close` is unreachable from an extra lane | **real defect** | `on_lane_bar` now takes `close_check`; the orchestrator passes `lane.name != MAIN`. Three tests added (paper, broker, end to end on FakeMT5), each proven to fail when the wiring is removed. |
| 4b. the breakers in `config.yaml` are much wider | not a defect | the owner's decision, 2026-10-27: *"take the breakers out... or deactivate them... every trade already has its stop loss; these systems are designed for human traders, it affects their state of mind, but an AI and a bot are not affected by that."* |

### Left open, on purpose

`on_bar` asks **every** position's strategy to close, including one owned by an extra lane, using the
**main lane's** context - the wrong entry timeframe and the wrong decision bar for that strategy. Found
while proving the test above: a strategy that always says yes was closed by the main lane, so the first
version of the test passed even with the lane wiring removed.

For the three bots this is harmless (their `should_close` only asks whether it is 07:00 in Bangkok, which
is true on any lane's bar at that minute), so it is recorded rather than fixed. The clean fix is to take
`should_close` out of `on_bar` and let the orchestrator ask every lane through `on_lane_bar` with
`close_check=True`; that touches the backend protocol, both position managers and their tests, and buys
nothing for the work in hand.
