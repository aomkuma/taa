# DEV_NOTES_3

Date: 2026-10-27

## Tasks A–C

- **A — `edge_side.py`:** Added a pure D1 regime reader from close-stamped H1 candles. It shifts the index back one hour, resamples daily closes, filters daily bars closed at `at`, and returns BUY/SELL only when close and the 50-day SMA slope agree. It rejects entry frames at or above D1 and returns `None` for missing/short data, mixed readings, and an incomplete D1 bar.
- **B — trend and range bots:** Added `require_edge_side=False` to both parameter models. The trend bots check it immediately after their session window and before reading other decision data; enabling it requests 1,200 H1 warmup bars. The range bot checks the break side against the D1 side after finding a break. A missing edge side holds every enabled bot with `AGAINST_EDGE_SIDE`. Default behavior remains off. The shared API sample fixture now records the two new `false` defaults.
- **C — `weighing.py`:** Added immutable `Weight` and `Scale` models and `score()`. Missing readings leave both parts of the ratio; numeric inputs are validated in `[0, 1]` and are not normalized by this module. The normalized score is weighted contribution / available weight. Boolean support means the value matches `wants`; numeric support means the contribution fraction is at least 0.5. `meets_threshold` uses `>=`; empty and zero-readable-weight scales do not meet even a zero threshold. No strategy calls the scorer yet.

## Tests and mutation proof

There are 26 new test cases. Each case was run against a targeted one-line production mutation; the default-off test has separate mutations for the trend and range parameter defaults. The 27 planted mutations caught all 26 cases. Full details are in [plant_bugs_3_output.txt](plant_bugs_3_output.txt).

| Test | Mutation used | Result |
|---|---|---|
| `edge_side`: rising mean + close above | Reverse the rising-SMA comparison | CAUGHT |
| `edge_side`: falling mean + close below | Reverse the falling-SMA comparison | CAUGHT |
| `edge_side`: close above falling mean | Ignore the SMA slope in the BUY condition | CAUGHT |
| `edge_side`: close below rising mean | Ignore the SMA slope in the SELL condition | CAUGHT |
| `edge_side`: exactly 50 closed D1 bars | Return BUY when only one full 50-day mean exists | CAUGHT |
| `edge_side`: 49 closed D1 bars | Admit 49 bars and force a side | CAUGHT |
| `edge_side`: unclosed D1 bar | Extend the closed-bar cutoff by one day | CAUGHT |
| `edge_side`: entry at D1 | Change the timeframe guard from `>=` to `>` | CAUGHT |
| `edge_side`: fewer than 1,200 H1 bars | Lower the H1 minimum to 1,199 | CAUGHT |
| `weighing`: all readings agree | Invert boolean agreement | CAUGHT |
| `weighing`: all readings disagree | Award full boolean weight on disagreement | CAUGHT |
| `weighing`: mixed weighted score | Complement a high reading instead of using it directly | CAUGHT |
| `weighing`: missing denominator | Add missing weight to the denominator | CAUGHT |
| `weighing`: `wants="low"` | Use the raw value instead of its complement | CAUGHT |
| `weighing`: empty scale | Give an empty denominator a score of 1 | CAUGHT |
| `weighing`: zero weight | Permit a zero denominator to meet threshold | CAUGHT |
| `weighing`: threshold equality | Change `>=` to `>` | CAUGHT |
| `weighing`: `None` reading | Let `None` continue as a present reading | CAUGHT |
| trend/range defaults | Set trend `require_edge_side` default to true | CAUGHT |
| trend/range defaults | Set range `require_edge_side` default to true | CAUGHT |
| trend down alignment | Invert the trend side check | CAUGHT |
| trend missing side | Let `None` pass the trend side check | CAUGHT |
| trend warmup | Ignore `require_edge_side` in the warmup count | CAUGHT |
| trend up alignment | Force the up bot to expect SELL | CAUGHT |
| range aligned break | Hold when the range side equals the edge | CAUGHT |
| range opposed break | Allow a SELL edge to pass a BUY break | CAUGHT |
| range missing edge | Hold only when the edge is BUY, letting `None` pass | CAUGHT |

The first harness iteration caught 23/25: two ineffective mutations did not change the tested branch. I corrected those definitions and reran it, then added mutations for the up-trend and missing-range-side tests that the final coverage review found unmapped. The final result is **27/27 caught, 0 missed**. The crash-safe harness keeps byte-for-byte backups and restores leftovers at the next invocation.

## Defaults and parity

- The prior round recorded the pre-this-round baseline as **3,948 passed, 9 skipped** (3,957 collected). This round adds 26 cases. After the API fixture update, the full suite passed: **3,974 passed, 9 skipped** (3,983 collected).
- Both new parameter defaults are `False`; `config.yaml` is unchanged. With the flag off, no edge-side calculation runs.
- Parity match rates were unchanged: `trend_box_down` **35/38 (92.1%)**, `trend_box_up` **21/23 (91.3%)**, `range_break` **39/41 (95.1%)**. The replay loaded only `config.yaml` via `load_app_config`, without environment settings.
- The first full pytest run exposed the expected API sample change from the new `false` fields. I regenerated `frontend/src/test/fixtures/api-samples.json`; its focused test passed. The rerun result is recorded below.

## Clarity and interpretation

No direct contradiction appeared within the detailed Task A–C requirements. Three scope details needed explicit treatment:

1. Exactly 50 closed daily closes produce one 50-day mean, but cannot establish whether that mean is rising or falling without a prior full 50-day window. I fail closed with `None` at 50 and classify only once 51 closes are available. This is covered by the 50-bar and 49-bar boundary tests.
2. The spec asks for supported/opposed lists for continuous numeric readings but does not define their dividing line. I classify the normalized contribution fraction at or above 0.5 as support and below 0.5 as opposition, documented in `score()`.
3. The owner’s rule says it applies to the AI trader too, while Task B specifies only `trend_box_down`, `trend_box_up`, and `range_break`, with a new opt-in parameter on those classes. I applied Task B to its three named strategies and did not add an AI-trader gate because no AI parameter or gate ordering is specified. The AI path therefore remains outside this implementation and needs an explicit follow-up decision to fulfill the wider statement.

## Checks

- Focused strategy tests: **73 passed**.
- `ruff format app tests`: **518 files already formatted**.
- `ruff check app tests`: passed.
- `mypy app`: passed (348 source files).
- `bandit -q -r app -c pyproject.toml`: passed.
- Full suite after API sample update: **3,974 passed, 9 skipped**, 3 existing warnings, 20m50s.

## What I did not do

I did not choose or tune research weights, connect the scorer to a strategy, change `config.yaml`, or edit `geometry*.py`, `edge_by_condition.py`, `JOURNAL.md`, or `weights*`. I did not commit, push, deploy, or change trading settings.

I did start the original parity script before checking its loader path. It calls `load_settings()` with the default `.env` path, so it likely read `.env` once before I stopped it; I did not inspect, display, or modify the file. The completed parity replay used a config-only wrapper instead. This was my mistake, and it is recorded here explicitly.
