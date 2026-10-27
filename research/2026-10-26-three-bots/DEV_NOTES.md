# Three-bot development notes

## Implementation

- Added and registered `TrendBoxDown`, `TrendBoxUp`, and `RangeBreak`; all three are disabled in the new XAUUSD M5 `three_bots` lane.
- The lane requests only M1, M5, and H1. Its 1,200 H1 warm-up supplies the 300 H4 bars. Because app H1 frames are indexed by close time while the research data is indexed by open time, `range_break` shifts H1 indices back one hour before the exact `4h`/`first/max/min/last` resample, drops empty rows, then limits inputs to H4 bars closed by the M5 decision time.
- Kept the shared config and timeframe builder unchanged. Strategy rules use the values in the spec, including DST-aware sessions, confirmed ZigZag swings, the pre-decision 60-minute M1 run window, reward gates, daily flat, and ordered +0.5 R break-even management.
- Added hand-calculated tests for the entry plans, box selection, swing stepping, boundaries, session windows, closed-frame requirements, run gate, break-even order, and range resampling. Updated existing catalog, config-lane, API snapshot, and strategy API expectations for the three newly registered strategies and lane.
- `plant_bugs.py` contains 21 deliberate mutations. Its latest run caught all 21; the per-mutation output is in `plant_bugs_output.txt`.

## Verification

- Targeted strategy, catalog, API sample, strategy API, and architecture tests: 54 passed.
- Full `.venv\Scripts\python -m pytest -q`: 3,929 passed, 9 skipped, 3 existing warnings.
- `.venv\Scripts\ruff format app tests scripts` and `ruff check app tests scripts`: pass. `mypy app`: pass. `bandit -q -r app -c pyproject.toml`: pass (the repository's existing comment-word warnings remain).
- The 21-mutation run caught all 21 planted errors; see `plant_bugs_output.txt`.

## Parity

Ran `parity.py` on FBS-Demo XAUUSD over the specified 2025-10-20 through 2026-10-23 period. The table is also at the start of `parity_output.txt`; the file lists every unmatched decision with its engine reason.

| strategy | research trades | engine trades | research R/trade | research total R | engine R/trade | engine total R | decisions matched |
|---|---:|---:|---:|---:|---:|---:|---:|
| trend_box_down | 38 | 66 | +0.280 | +10.7 | +0.235 | +15.5 | 35/38 (92.1%) |
| trend_box_up | 23 | 39 | +0.133 | +3.0 | +0.051 | +2.0 | 21/23 (91.3%) |
| range_break | 41 | 46 | +0.488 | +20.0 | +0.339 | +15.6 | 39/41 (95.1%) |
| **all** | **102** | **151** | **+0.331** | **+33.7** | **+0.219** | **+33.1** | **95/102 (93.1%)** |

The seven research-only decisions were: three rejected for `SPREAD_TOO_HIGH`; one DOWN hold at `NO_BOX`; one UP hold at `RETRACE`; one RANGE decision lost when the lane arbiter accepted UP on the same close; and one RANGE rejection with `MAX_POSITIONS_PER_SYMBOL` plus `CURRENCY_EXPOSURE_LIMIT`. The 56 engine-only decisions are listed individually in `parity_output.txt`; each was an accepted engine signal with no research trade at that close. The engine uses native M5 bars and the next quote, while research resamples M1 into M5 and enters at the close with a flat $0.30 spread.

## Known limits

- The backtest engine advances fills and position management on the lane's M5 entry timeline. The reference settles stops and targets on every M1 bar. The strategy's manager replays closed M1 bars in order, but cannot make the current engine broker resolve fills at M1 granularity without a shared backtest-engine change, which §2.2 forbids here.
- The shared risk config defaults to one open position per symbol, and the app lane arbiter selects only one strategy signal per close. The reference allows one position per strategy and can accept a trend and range trade together. The parity runner's in-memory config uses the two-position upper bound and raises loss breakers to the existing safety cage so they do not truncate the sample. These overrides are backtest-only; the disabled lane inherits the shared one-position cap and single-signal arbitration in a normal app run. Changing those shared engine behaviors is outside this ticket.
