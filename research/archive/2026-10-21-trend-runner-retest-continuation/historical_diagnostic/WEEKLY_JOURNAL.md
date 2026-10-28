# RETEST-CONTINUATION V1 — weekly historical journal

**Status: descriptive, in-sample research only. No strategy rule changed.**

## Coverage and result

- Source cohort: 632 stopped-before-+1R opportunities across 129 calendar weeks.
- Completed candidate attempts: 108 across 70 active weeks; 1.54 attempts per active week.
- Candidate outcome: +28.25R total, +0.262R mean, 38.9% winners, -0.377R median.
- Top 3 attempts contributed 117.0% of total R; excluding them leaves -4.81R.
- Locked exam [2026-04-18, 2026-10-18) and later observations were excluded. Recorded spread is included; slippage is excluded.

## Yearly progression

| Year | Attempts | Total R | Mean R | Median R | Win rate |
|---:|---:|---:|---:|---:|---:|
| 2023 | 6 | -0.81 | -0.134 | -0.776 | 33.3% |
| 2024 | 42 | +3.39 | +0.081 | -0.274 | 40.5% |
| 2025 | 46 | +25.89 | +0.563 | -0.374 | 41.3% |
| 2026 | 14 | -0.23 | -0.016 | -0.736 | 28.6% |

## Chronological halves

| Half | Attempts | Total R | Mean R | Median R | Win rate |
|---|---:|---:|---:|---:|---:|
| first half | 54 | +4.80 | +0.089 | -0.274 | 40.7% |
| second half | 54 | +23.45 | +0.434 | -0.446 | 37.0% |

## Chronological direction transfer check

Choosing the side with higher mean R from only the first half selects BUY (first-half means: BUY +0.385R, SELL -0.167R). Applied to the next 54 attempts, BUY-only retains 30 trades and +34.03R (+1.134R/trade; 53.3% wins), versus all sides at +23.45R.
However, its top three later-half winners contribute +33.06R; without them the selected side retains only +0.98R. This chronological split is still already-seen development data, not independent validation; it is a lead to study, not a reason to disable SELL in the strategy.

## Weekly extremes (weeks with completed attempts)

Positive weeks:

| Week starts UTC | Attempts | Total R | Best R | Best trade |
|---|---:|---:|---:|---|
| 2025-06-02 | 1 | +13.36 | +13.36 | M1WF-00813 |
| 2025-05-05 | 1 | +10.08 | +10.08 | M1WF-00773 |
| 2025-09-22 | 3 | +8.44 | +9.62 | M1WF-00986 |
| 2024-03-18 | 1 | +6.18 | +6.18 | M1WF-00234 |
| 2026-02-09 | 2 | +3.46 | +4.33 | M1WF-01212 |

Negative weeks:

| Week starts UTC | Attempts | Total R | Best R | Most common event outcome |
|---|---:|---:|---:|---|
| 2026-04-06 | 3 | -3.00 | -1.00 | no retest (2) |
| 2024-08-12 | 3 | -2.16 | -0.16 | none; all other events completed or pending |
| 2024-07-29 | 2 | -1.93 | -0.93 | structure invalidated (3) |
| 2025-07-28 | 5 | -1.92 | +0.23 | structure invalidated (1) |
| 2023-11-20 | 2 | -1.76 | -0.76 | no reclaim (2) |

## Trade-path journal findings

- 632-event funnel: 108 COMPLETE, 221 NO_RETEST, 114 STRUCTURE_INVALIDATED, 114 NO_RECLAIM, 65 NO_CONTINUATION, and 10 pending horizon events.
- All 108 completed attempts ultimately exited by the structural trailing stop; median trade was negative even though total R was positive.
- Of 42 attempts that reached at least +1R MFE, 34 closed positive and 8 finished at or below zero. All 11 attempts that reached +3R MFE finished positive. This suggests the main weakness is the entry/continuation funnel, more than a general failure to retain a large move; the threshold cut is retrospective, not a deployable rule.
- The three largest winners occurred in separate 2025 weeks. Their removal turns the full result negative, so the positive total is not a stable weekly edge.
- The second chronological half gained +23.45R, but excluding its three largest winners it lost -9.61R. Improvement over time is therefore not established independently of outliers.

## Learning and next research action

Do not promote or retune this setup or the failed 52-week filter from these same outcomes. The first-half direction transfer chose BUY, but the next-half result falls to +0.98R after removing its three largest winners, so do not disable SELL based on this sample. The next historical question is the low completion rate (108/632): investigate one isolated entry-funnel hypothesis, preserve every skipped event, and measure it chronologically against the frozen candidate. Any positive development-sample result remains exploratory and does not replace a truly untouched validation period.

Reproduce with `.venv/Scripts/python.exe research/2026-10-21-trend-runner-retest-continuation/build_weekly_journal.py`. Weekly rows for all calendar weeks, including weeks with no source events, are in `weekly_journal.csv`.
