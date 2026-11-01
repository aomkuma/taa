# OCO limits restricted to an in-value rotation regime

**Status:** predeclared exploratory filter on the execution-audited OCO base.
**Date:** 2026-10-31 (Asia/Bangkok)

## Question

Does only working the user's buy-VAL / sell-VAH OCO while the last completed M5 close is inside frozen value avoid fills during an established move outside the cluster?

## Rules

Use the exact base profile, OCO, quote execution, spread-safe stop, planned-risk R normalization, order expiry and chronological 110/48 split in `../edge_limit_oco_execution_audited_2026-10-31/PROTOCOL.md`. The sole changed condition: a bar's OCO limits may be active only when the immediately prior completed M5 close is within frozen [VAL, VAH]. The prior close is known at the bar open, avoiding same-bar look-ahead. Use one first qualifying cluster per session and one fill max.

## Expectation

This should reduce trade count and may remove some trend-continuation fills. It may also miss valid edge tests. Test is exploratory; prior validation has been inspected in related studies and is not an untouched holdout.
