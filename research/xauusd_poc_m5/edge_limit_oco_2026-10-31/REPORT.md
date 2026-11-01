# OCO limit attempt (withdrawn)

**Status:** invalid for inference; retained as an execution-debug record.

This first backtest placed OCO limits at frozen VAL/VAH and set the stop only one median spread beyond the edge. It also invalidated at the M5 close before processing that bar's tick touches. It reported 66 development trades / -204.62R and 31 validation trades / -51.71R, all stopped. A later audit found the stop could already be crossed on the entry quote because spread was not fully allowed for. The timing also failed to process same-bar fills before close-based order expiry. Do not treat these metrics as strategy evidence.

See `../edge_limit_oco_execution_audited_2026-10-31/REPORT.md` for the corrected implementation.
