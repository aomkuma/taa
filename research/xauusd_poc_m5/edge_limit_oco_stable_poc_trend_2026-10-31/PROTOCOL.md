# OCO in a stable value cluster, aligned with six-hour drift

**Status:** exploratory nested filter.
**Date:** 2026-10-31 (Asia/Bangkok)

## Question and rule

Does restricting the stable-POC, in-value, low-efficiency OCO to the side aligned with six-hour net drift improve robustness? Keep all conditions in `../edge_limit_oco_stable_poc_2026-10-31/PROTOCOL.md`. Add: prior 72 completed M5 closes net up -> allow buy VAL only; net down -> allow sell VAH only; unchanged -> allow both. The sign is known at the current bar open. Use the execution-audited bid/ask fill, immediate stop and planned-limit R accounting.

Exploratory only; the same historical validation block has been inspected in related experiments. Candidate criteria remain >=20 development trades, positive net R in at least two folds and positive validation net R.
