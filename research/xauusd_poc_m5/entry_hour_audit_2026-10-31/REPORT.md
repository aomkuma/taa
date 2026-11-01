# Entry-hour diagnostic for full-range-stop VAL/VAH OCO

## Data and scope
This is an exploratory breakdown of the existing 158 trade full-range-stop OCO result. It does not change the strategy or select a rule. Entry timestamps are grouped by UTC clock hour; the three development folds remain chronological. All 24 hours were inspected after the outcomes were known, so any apparent best hour is subject to selection bias and needs a new preregistered sample.

## Observations

- 00:00 UTC: 38 development trades, +1.17R overall; fold results -4.11R (5), +0.57R (8), +4.71R (25). Validation had 34 trades and -1.65R.
- 04:00 UTC: 13 development trades, +0.89R; folds +0.41R (3), +2.14R (6), -1.66R (4). No validation trades.
- 06:00 UTC: 8 development trades, +4.12R; folds +0.13R (3), +1.58R (2), +2.41R (3). Validation had only 2 trades and -1.30R.
- Other UTC hours had too few observations or failed the same chronological/validation consistency check.

## Conclusion
No time-of-day filter is supported. 06:00 UTC looks positive in development but lacks a useful validation sample and its two observed validation trades lost. 00:00 UTC has a larger validation sample but is negative and development fold 1 is negative. These are diagnostics, not candidate strategies.

Source: `../edge_limit_oco_profile_extreme_stop_2026-10-31/trades.csv`; FBS-Demo quotes through 2026-10-28. Validation is historically reused; fees beyond spread are excluded.
