# OCO limits during a six-hour balance cluster

**Status:** exploratory, execution-audited filter.
**Date:** 2026-10-31 (Asia/Bangkok)

## Question and protocol

Does restricting the buy-VAL / sell-VAH OCO to an objectively low-directional-efficiency six-hour market improve the in-value variant? Keep the prior completed M5 close inside the frozen VA, then require six-hour directional efficiency <=0.25. Efficiency is absolute net price change over the last 72 completed M5 close-to-close moves divided by the sum of absolute moves. This calculation uses data known at the bar open. The rest of the profile, OCO fills, spread-safe stops, planned-limit risk normalization, chronological split, and costs/limitations are identical to `../edge_limit_oco_execution_audited_2026-10-31/PROTOCOL.md`.

The gate is fixed at 0.25 for this exploratory run, consistent with the previously tested range threshold; this is not a newly optimized cutoff. A candidate still requires >=20 development trades, positive net R in >=2/3 development folds, and positive validation net R. Validation has been seen in related experiments and is not pristine.
