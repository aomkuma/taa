# RETEST-CONTINUATION V1 status

Checked: 2026-10-21 (Asia/Bangkok)

## Current evidence

- Historical diagnostic: **108 completed attempts from the 632-event cohort; +0.262R mean and +28.246R total**. It used M1 OHLC with recorded spread converted to price units, omitted slippage, and excluded the locked exam interval. This cohort had already been inspected, so it is in-sample exploratory evidence only, not independent validation. Median trade was -0.377R, win rate 38.9%, and the top 3 winners contributed 117% of total R; without those 3, total R was -4.810R.
- Weekly journal covers every source event across 129 UTC weeks: 108 attempts occurred in 70 weeks. 2025 contributed +25.89R; 2023 and 2026 were slightly negative. The top three trades occurred in separate 2025 weeks but removing them makes total R negative. See `historical_diagnostic/WEEKLY_JOURNAL.md` and `weekly_journal.csv`.
- Sequential replay report now records each of the 129 weeks individually: source/funnel counts, prior-only allow/block decisions, weekly and cumulative V1/filter R, blocked counterfactual outcomes, and weekly path notes. See `historical_diagnostic/WEEKLY_SEQUENTIAL_REPLAY.md` and `weekly_sequential_replay.csv`.
- A chronological side-transfer check selected BUY from the first 54 attempts (BUY mean +0.385R vs SELL -0.167R), then retained 30 BUY attempts for +34.03R in the next 54; however, its top three trades contributed +33.06R, leaving only +0.98R without them. This supports further study of the direction difference but does not justify disabling SELL.
- A single causal, past-only weekly side/session filter was replayed: trailing 52 weeks, minimum 5 previously allowed and settled attempts per cell, allow only if trailing mean R > 0, otherwise preserve baseline during warm-up. It selected 77 attempts for +26.28R (+0.341R mean), versus frozen V1's 108 for +28.25R. The 31 blocked attempts summed to +1.96R; filter total was lower, and chronological halves disagreed (-4.44R vs +1.24R in the first; +30.72R vs +27.00R in the second). **Do not adopt the filter.** Full findings: `historical_diagnostic/WEEKLY_REGIME_FILTER_RESULTS.md`.
- The 632-event ATR replay remains a source-stop-time state study: its source-stop screen result (+30.96R) is not an entry-time lock result. The trailing-mean learner selected 64 attempts for +25.02R vs baseline +28.25R; do not adopt it.
- The fixed gate was then frozen precisely and tested at the actual re-entry entry time on earlier XAUUSD history (2021-09 through 2023-10), while the reserved 2026 exam remained unopened. It selected 91/94 completed attempts for +2.325R vs V1 +2.193R; three blocked outcomes summed to -0.132R. The small +0.132R lift is not robust: baseline/gate counts 94/91 (<100), 85/84 days, fixed-gate second-half mean -0.049R, gate mean day-block 95% CI [-0.245,+0.402]R, paired lift CI [-0.036,+0.033]R. **Not passed; do not adopt or tune on this holdout.** This earlier period was used by other XAUUSD studies in the workspace, so it is not globally virgin market data. Details and weekly journal: `historical_holdout_2021_2023/HOLDOUT_RESULTS.md`, `HOLDOUT_WEEKLY_REPORT_TH.md`, and `holdout_trade_journal.csv`.
- Latest TR3 shadow cycle recorded 1 forward opportunity, 0 settled outcomes and 0 Champion-scored opportunities (cold start). The candidate observer therefore found 0 eligible source events and 0 terminal results. This is coverage only, not historical evidence or performance.

## Implementation

- `candidate.py`: frozen M5 reclaim → first retest → continuation close → next M1 entry; structural initial stop; confirmed M5-pivot trailing; 8-hour maximum.
- `journal.py`: isolated append-only SQLite journal with immutable hashes and prospective-date validation.
- `observer.py`: processes an already-settled, independently verified source event; pending candidate paths are not recorded as final outcomes.
- `source_adapter.py`: reads only new settled opportunities from the Champion journal using a read-only connection; checks ordered executable ticks through the source exit to classify stop-before-+1R; loads only post-boundary M1 bars.
- `run_observer.py`: repeatable command to advance only the isolated journal; pending horizons are not finalized.
- `historical_diagnostic.py`: separate replay path and outputs under `historical_diagnostic/`; never writes to the prospective journal.
- Candidate/journal/observer/source-adapter, historical-boundary, past-only ATR, and holdout source-classification tests: **27 pass**. Ruff checks pass for the new research scripts and tests.

## What remains before the first real observation

1. Run `run_observer.py` after new forward data/outcomes mature. The adapter determines `runner_stopped_before_plus1` from ordered executable ticks, not final RUNNER R alone.
2. Wait for new post-boundary TR1 opportunities and their fully matured 8-hour outcomes.
3. Candidate results go only to the isolated candidate journal, never to the Champion database.
4. Publish the first interim result only after 50 completed attempts across at least 30 trading days. Until then, report coverage/status only.

Historical output: `historical_diagnostic/DIAGNOSTIC_RESULTS.md`, with trade-level rows and machine-readable summary alongside it.
Weekly review: `historical_diagnostic/WEEKLY_JOURNAL.md`. Past-only filter replay: `historical_diagnostic/WEEKLY_REGIME_FILTER_RESULTS.md`; its implementation records a decision for all 632 events and does not feed blocked counterfactual labels into later training.
ATR-state sequential replay: `historical_diagnostic/ATR_WEEKLY_SEQUENTIAL_REPLAY.md` (129 weekly sections; 632 event-level decisions). Each settled allowed outcome updates only later decisions; blocked counterfactuals never enter training.
Thai weekly user-format summary: `historical_diagnostic/WEEKLY_LEARNING_REPORT_TH.md` (129 weeks; V1 R, fixed ATR-lock R, adaptive replay R, cumulative R, ATR context, standout trade, learning, and next-week research rule). USD/account equity is explicitly not modeled because the replay has no position sizing or compounding rule and the event paths overlap.
Entry-time ATR holdout: `historical_holdout_2021_2023/HOLDOUT_RESULTS.md` and `HOLDOUT_WEEKLY_REPORT_TH.md` (109 weeks, 474 source events); actual entry-time ATR gate did not pass the predeclared research criteria. It is not globally independent because the same earlier gold history supported other research.
