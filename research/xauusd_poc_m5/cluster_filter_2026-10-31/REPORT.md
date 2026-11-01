# Test: trade VAL/VAH only after prior value areas overlap

**Run date:** 2026-10-31 (Asia/Bangkok)
**Protocol:** preregistered in `PROTOCOL.md` before calculating outcomes.

## What ?price cluster? meant in this test

I interpreted it as repeated acceptance across two completed sessions: the prior two sessions' 70% Value Areas overlap by at least 50% of the narrower VA. For today's trades, levels still come from yesterday's profile; the overlap is only a gate. This is a past-data rule and does not use the rest of today's price path.

This definition may differ from a cluster forming inside the current session. The result below only answers this two-session value-area-overlap version.

## Sample and comparison

Require complete quote coverage for the current and preceding two sessions, leaving 104 common sessions (first 70%: 72 development sessions; last 30%: 32 validation sessions). The cluster condition passed on 44 of the 104 sessions. The baseline and filtered versions use the same eligible dates, same prior-day VAL/VAH/POC, same edge entry, same stop/target, and same tick replay.

| Version | Development trades | Dev net points/oz | Dev net R | Validation trades | Val net points/oz | Val net R | All net points/oz |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline, every common session | 86 | +62.39 | -30.60 | 41 | -22.07 | +3.56 | +40.32 |
| Only sessions passing cluster gate | 33 | +26.25 | -17.18 | 20 | -31.88 | -4.33 | -5.63 |

The filter reduced trades by 58% (127 to 53), but it did not improve performance. On validation, filtered cluster sessions lost 31.88 points while the 17 non-cluster sessions' baseline trades gained 9.81 points. Across all common sessions the filtered group ended at -5.63 points per oz, versus +40.32 for baseline. R-based returns were negative overall in both variants.

## Conclusion

This cluster definition did not help the VAL/VAH strategy in the tested data, especially in the later segment. It is not evidence that all forms of price clustering fail; it only rejects this specific gate (two prior value areas overlap at least 50%). Do not adopt it from this result.

The later segment is historical and not fully blind because some of its dates were examined in earlier work. Quote-update volume is broker-specific, not centralized executed volume; costs include the bid/ask spread but not commission or extra slippage.

## Files

- `PROTOCOL.md`: frozen rule and expectation
- `test_cluster_filter.py`: calculation and replay
- `summary.csv`: baseline and cluster-only totals by split
- `cluster_comparison.csv`: baseline results on cluster vs non-cluster sessions
- `trades.csv`: every trade for both groups, including overlap ratio
- `daily_levels_and_cluster.csv`: prior-day profile levels and cluster ratio
- `cluster_eligibility.csv`: coverage and cluster condition by candidate session
