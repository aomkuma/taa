# DEV_SPEC_4 implementation notes

## Gap 1: H4 edge rule on PLAN-1

Added `require_edge_side: bool = False` to the ORB, NY straddle and B2 parameter models. Each enabled gate uses the existing `edge_lean()` and `behind()` functions, with the context's `entry_timeframe`. A missing reading or a `ValueError` is recorded as unreadable and refuses the entry. The rule is `behind(...) >= 0`, so a zero lean is allowed and a negative lean is refused. The condition is omitted when the option is off to preserve default signal output.

ORB and B2/B2M5 use M1 and M5 entries; the NY straddle enters from quotes and reads its context entry timeframe. None enters at H4 or above, so the gate was not forced onto an entry frame where no larger H4 frame exists. When enabled, each warmup requests at least 64 H4 bars (256 H1 bars, or 15,360 M1 bars).

## Gap 2: complete day plan

`DayPlan.check()` reads at most `READ_LIMIT` bytes, checks case-insensitive whole-word markers for condition, levels, the side with the edge, and scenarios, and returns a detail naming missing sections. `exists()` keeps its boolean API. The orchestrator passes the detailed check result into the DAY_PLAN gate. The AI markdown writer now emits an explicit `- scenarios:` marker, matching its `DayPlan.scenarios` field. Existing file, directory, empty, whitespace, unreadable, invalid UTF-8 and bounded-read refusals remain fail-closed.

The shared integration test plan and late-plan fixture now contain all four required sections. The API sample fixture includes the four new optional parameters with `false` defaults.

## Tests and mutations

Each mutant was planted against the production implementation, exercised by the named test, and restored by `plant_bugs_4.py`'s recovery journal and `finally` handler. The output is in `plant_bugs_4_output.txt`.

| Test | Planted change | Result |
|---|---|---|
| `test_plan_markers_are_case_insensitive_and_order_independent` | Remove condition marker | CAUGHT |
| `test_plan_markers_are_case_insensitive_and_order_independent` | Remove levels marker | CAUGHT |
| `test_plan_markers_are_case_insensitive_and_order_independent` | Remove edge-side marker | CAUGHT |
| `test_plan_markers_are_case_insensitive_and_order_independent` | Remove scenarios marker | CAUGHT |
| `test_a_partial_plan_names_the_missing_part` | Omit condition from refusal detail | CAUGHT |
| `test_a_partial_plan_names_the_missing_part` | Omit levels from refusal detail | CAUGHT |
| `test_a_partial_plan_names_the_missing_part` | Omit edge side from refusal detail | CAUGHT |
| `test_a_partial_plan_names_the_missing_part` | Omit scenarios from refusal detail | CAUGHT |
| `test_plan_markers_are_case_insensitive_and_order_independent` | Disable case-insensitive matching | CAUGHT |
| `test_a_one_character_plan_is_incomplete` | Allow a one-character plan | CAUGHT |
| `test_plan_check_reads_no_more_than_the_bound` | Remove the bounded read | CAUGHT |
| `TestPlan1Orb.test_edge_defaults_stay_off_and_warmup_grows_only_when_enabled` | Change ORB default to on | CAUGHT |
| `TestPlan1Orb.test_the_optional_edge_gate_refuses_an_opposing_or_unreadable_h4` | Bypass ORB's negative-lean refusal | CAUGHT |
| `TestPlan1Orb.test_the_optional_edge_gate_refuses_an_opposing_or_unreadable_h4` | Refuse a zero lean | CAUGHT |
| `TestPlan1Orb.test_edge_defaults_stay_off_and_warmup_grows_only_when_enabled` | Shorten enabled ORB warmup | CAUGHT |
| `TestPlan1Straddle.test_the_optional_edge_gate_refuses_a_buy_against_h4_and_reads_context_timeframe` | Bypass NY's negative-lean refusal | CAUGHT |
| `test_optional_edge_gate_uses_the_context_entry_frame_and_fails_closed` | Bypass B2/B2M5's negative-lean refusal | CAUGHT |
| `test_the_plan_goes_to_the_journal_and_the_store` | Remove the AI writer's scenario marker | CAUGHT |

Mutation result: **18 caught, 0 missed**. The first mutation-runner attempt reported one missed NY mutation because it changed a redundant downstream check. That check was removed; the mutation was retargeted to the journal gate. The final run also covered the missing-section details, case-insensitive matching, one-character refusal, bounded reads, zero-edge handling, warmup and AI scenario marker.

## Defaults and parity

All four new options default to `False`. Default strategy decisions do not add an edge condition, and warmups stay at their previous values when the option is off. Existing golden/parity tests passed in the first complete pytest run; no parity or golden-number files were edited. The API sample exposes the new optional fields as `false`. Regeneration also captured the currently returned strategy settings and environment values in that shared fixture (including existing trend-bot edge settings and `DAY_PLAN_DIR`); `config.yaml` was not edited.

## Validation

- Focused unit run after the final code changes: **94 passed**.
- Affected integration files after fixing their plan fixtures: **29 passed**.
- Combined focused rerun after the day-plan marker, `ValueError` handling and fixture fixes: **102 passed**.
- API sample test after fixture regeneration: **1 passed**.
- Scanner integration file: **12 passed**.
- Ruff format check: **520 files already formatted**.
- Ruff check: **passed**.
- Mypy: **349 source files, no issues**.
- Bandit: **no issues identified**.
- Full pytest first completed with **3,998 passed, 9 skipped, 19 failed**. Eighteen failures used intentionally incomplete generic plan fixtures; the other was the API sample now updated. The 29 affected integration tests and API sample test passed after those fixes.
- Two subsequent full-suite retries terminated with Windows native access violations during scanner/demo integration activity (one in the scanner test, one in the day-plan gate loop while pandas aggregated `fake_mt5` bars). Those tests pass in isolated runs. Therefore, the final full suite is **not recorded as green**.

## Conflict and scope

DEV_SPEC_4 asks for `plant_bugs_4_output.txt` to be committed, while the owner's instruction for this task says never commit. The output file was written, but no commit was made. No push was made. `.env`, `config.yaml`, `docs/`, and `research/2026-10-26-three-bots/weights*` were not edited. No PLAN-1 entry timeframe is H4 or higher.
