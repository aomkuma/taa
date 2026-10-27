# DEV_NOTES_2

Date: 2026-10-27

## Implementation

- **Lever A (`require_big_tf`, default `False`)**: Added the shared parameter and increased H1 warmup to 1,200 only when enabled, enough to form 300 H4 bars. After the H1 stepping gate, the strategy calls `RangeBreak._h4_from_h1`, filters closed bars with `(index + 4h) <= decision time`, and checks confirmed swings via the existing `stepped()` helper. An opposing direction holds with `H4_AGAINST`; FLAT and aligned directions pass. The import is local to `evaluate()` because `range_break` already imports helpers from `trend_box`; this avoids a module import cycle and reuses the one resampling implementation.
- **Lever B (`min_stop_atr`, default `0.0`)**: Added a nonnegative shared parameter. When enabled, the strategy calls `app.indicators.volatility.atr` on closed H1 bars, using its existing 14 period Wilder smoothing. It widens only stops closer than the computed floor, before reward/risk checks, and adds `stop_floor` only when widening occurred. No duplicate ATR implementation was needed.
- No spec contradiction was found. The only integration detail was the existing `range_break`/`trend_box` import direction, handled by the local import above.

## New tests and mutation proof

Every new behavior test calls `evaluate()`; expected ATR distances are hand-worked from constant 2.00 H1 ranges. `plant_bugs_2.py` runs one targeted test per mutation and restores `trend_box.py` byte-for-byte in `finally`.

| New test | Mutation that proves it bites |
|---|---|
| `test_big_tf_off_keeps_an_opposing_h4_out_of_the_decision` | Set `require_big_tf` default to `True`. |
| `test_big_tf_down_blocks_up_h4_but_flat_and_down_keep_the_entry` | Let H4 UP pass; shorten H1 warmup to 400. |
| `test_big_tf_up_blocks_down_h4` | Let H4 DOWN pass. Also checks FLAT and UP entries. |
| `test_big_tf_requires_300_closed_h4_bars` | Lower the minimum to 299. |
| `test_big_tf_does_not_send_a_forming_h4_bar_to_zigzag` | Include an H4 bar whose close is four hours after the decision. |
| `test_min_stop_atr_off_leaves_a_tiny_box_stop_unchanged` | Set the `min_stop_atr` default to 1.0. |
| `test_min_stop_atr_widens_only_narrow_stops_and_reports_floor` | Halve the floor; omit the stop-floor condition. Checks an already-wide stop stays unchanged. |
| `test_min_stop_atr_mirrors_the_buy_stop_direction` | Move a BUY stop to `price + floor`. |
| `test_min_stop_atr_does_not_widen_a_stop_exactly_at_the_floor` | Change strict `<` to `<=`. |
| `test_min_stop_atr_widening_is_included_in_the_min_r_gate` | Check reward against box width instead of the widened risk. |

The final planted-bug run caught **12/12**; the full per-mutation results are in [plant_bugs_2_output.txt](plant_bugs_2_output.txt). An earlier mutation iteration missed the 299 bar boundary and widened-risk checks. I tightened those cases, and both mutations were caught in the final run. There were no final MISSED mutations.

## Default behavior proof

- Before adding the ten tests, the suite collected 3,947 cases: 3,937 passed, 9 skipped, and the API sample check failed because the public strategy response now includes the two new default parameters. I regenerated the shared response fixture; its focused test then passed.
- After implementation and fixture update, the full suite passed: **3,948 passed, 9 skipped** (3,957 collected). The strategy-focused files passed **47/47**. The two new fields default to `False` and `0.0`; existing parameter defaults and `config.yaml` are unchanged. With both levers off, no H4 resampling or ATR calculation runs.
- The parity script reported the same rates before and after the changes: `trend_box_down` 35/38 (92.1%), `trend_box_up` 21/23 (91.3%), and `range_break` 39/41 (95.1%). This confirms the default-off path retains the current parity match rates.

## Checks

- `ruff check app tests research/2026-10-26-three-bots/plant_bugs_2.py`: passed.
- `ruff format --check app tests research/2026-10-26-three-bots/plant_bugs_2.py`: passed.
- `mypy app`: passed (346 source files).
- `bandit -r app`: passed (no issues).
- A bare workspace-wide `ruff check` reports 16,055 existing findings in research scripts. The app, tests, and this task's harness all pass the scoped check above.

## What I did not do

I did not tune or judge either lever, run parameter sweeps, or change other defaults. I did not touch `geometry*.py`, `JOURNAL.md`, `.env`, `TRADING_MODE`, DEMO/LIVE settings, credentials, or `config.yaml`. I did not commit, push, or deploy.
