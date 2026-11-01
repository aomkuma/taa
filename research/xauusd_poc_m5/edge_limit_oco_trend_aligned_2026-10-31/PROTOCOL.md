# OCO boundary entries aligned with the six-hour drift

**Status:** exploratory nested filter following the low-efficiency test.
**Date:** 2026-10-31 (Asia/Bangkok)

## Question and rule

Does aligning the boundary side with the prior six-hour net drift help the in-value, low-efficiency OCO? Keep the exact `../edge_limit_oco_cluster_efficiency_2026-10-31/PROTOCOL.md` rules, including prior M5 close inside frozen value and six-hour efficiency <=0.25. Add one rule: if the prior 72 completed M5 close-to-close path is net up, permit buy-VAL only; if net down, permit sell-VAH only; if unchanged, allow both. The path and side are known at the current bar open. All fills/stops/targets use audited bid/ask execution and planned-limit risk units.

This is exploratory; the historical validation block is not an untouched holdout due to previous related research. Same candidate rule: >=20 development trades, positive net R in at least two development folds, and positive validation net R.
