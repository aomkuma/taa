# OCO in a stationary value cluster using normalized POC drift

**Status:** exploratory, execution-audited filter.
**Date:** 2026-10-31 (Asia/Bangkok)

Keep the corrected stationary-cluster rules: prior completed M5 close inside the frozen VA, six-hour efficiency <=0.25, activate only when all conditions are simultaneously met, quote-side limit/stop/target simulation, and 72-bar/two-close expiry. Replace the absolute POC-shift cutoff with a scale-normalized condition: older/recent-half POC distance <=5% of current six-hour VA width, measured at the activation bar and maintained while the OCO is active. The 5% value is fixed in this run and is not optimized on validation.

Same 158 chronological sessions (110 development / 48 validation), three development folds. Candidate rule is >=20 development trades, positive net R in >=2 folds and positive validation net R. Historical validation is not pristine after related experiments.
