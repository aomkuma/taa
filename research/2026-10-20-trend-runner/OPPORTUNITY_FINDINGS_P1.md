# TR1 P1 opportunity findings and entry selection

Computed: 2026-10-20 after the predeclared study, independent replay and real-data truncation checks. This document
uses P1 only. P2 and the exam were still locked.

## Measurement result

The study saved 364 spread-aware candidate paths across all predeclared cells. The independent implementation
replayed all 364 rows exactly: 4,732 candidate-field checks, 2,912 entry/stop checks and 8,372 raw-tick path checks.

For M1 entries, the three impulse thresholds produced:

- 0.25 H: 138 candidates; 52.9% reached 1R, 34.1% reached 2R, 29.7% reached 3R and 18.1% reached 5R;
- 0.50 H: 103 candidates; 47.6% reached 1R, 31.1% reached 2R, 25.2% reached 3R and 17.5% reached 5R;
- 0.75 H: 67 candidates; 43.3% reached 1R, 31.3% reached 2R, 28.4% reached 3R and 16.4% reached 5R.

M5 produced only 32, 17 and 6 candidates at those thresholds. M15 produced one candidate in total. Most otherwise
valid slower-timeframe entries breached the predeclared maximum initial risk of 0.50 H. They do not provide a viable
2-3 trades/day entry lane.

At 0.25 H on M1, Asia/London/New York contributed 51/46/41 candidates. The respective 2R passage rates were
37.3%/39.1%/24.4%, so New York is visibly weaker but is retained: dropping it after seeing P1 would be an undeclared
session filter. The three windows together produce 138 opportunities over 64 scheduled weekdays, or 2.16 per
weekday before portfolio collisions.

For the selected population, median initial risk was 0.270 H, median pullback depth was 0.191 H, median pullback
confirmation took 5 minutes, and median entry time was 31 minutes after the anchor. Median MFE was 1.11R. Of the
138 paths, 135 had a complete stop-or-eight-hour observation inside P1; the three boundary/closure-censored paths
remain in the saved population but will be reported separately from complete-path exit metrics.

The long-tail premise is present but not yet an edge: 41 paths reached 3R and 25 reached 5R, while median giveback
after first reaching 1R was 3.71R. That combination is the reason to test structure-based exits; it is not evidence
that a particular exit will be profitable.

## Entry selection for round 1

Round 1 selects `0.25 H + M1 + all three windows` because it is the only predeclared neighbouring setting that both
meets the intended frequency and has the strongest pooled 1R/2R passage rates. The choice is made on P1 only.

No additional state, direction or session filter is selected. The selected entry population is the subset of
`opportunities_p1.parquet` with `threshold == 0.25` and `timeframe == M1`.

This fixes the entry side of round 1 before exit outcomes are calculated. Exit definitions are written separately in
`EXIT_DESIGN_P1.md` before their P1 results are generated.
