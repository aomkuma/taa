# TR3 frozen hypothesis

This hypothesis was frozen before the first TR3 measurement.

The causal TR1 entry and frozen SPLIT/RUNNER outcome remain unchanged. TR3 chooses only `RUNNER` or `SKIP` at entry.
It never chooses FAST. At each month start it fits three alpha-20 ridge regressions for clipped RUNNER R from the
preceding 60, 90 and 120 calendar days. Only outcomes completed before refit are eligible and every component needs
60 rows.

All components use the verified 11-feature TR2 entry vector. Each performs its own training-only median imputation,
standardization and z clipping. The ensemble median minus half the population standard deviation is its confidence
score. RUNNER requires score > +0.05R and at least two positive component predictions; otherwise SKIP.

The primary and four diagnostics are exactly those in `PLAN.md`. No post-result substitution is permitted. All data
through 2026-04-17 are seen development evidence, so a passing result can only justify new forward shadow collection.
