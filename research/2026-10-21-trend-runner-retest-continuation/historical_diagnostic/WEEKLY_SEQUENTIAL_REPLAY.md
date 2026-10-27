# Historical weekly walk-forward reports — RETEST-CONTINUATION V1

**This is a retrospective, in-sample replay on pre-exam development data, not live trading or independent validation.** Every week is processed in chronological order. The weekly adaptive decision uses only prior allowed, completed candidate attempts in the same side/session cell over 52 weeks; it needs five prior settled attempts, otherwise the frozen V1 is allowed during warm-up. A result can update later weeks only after its exit time. No result is used to choose its own week's action.

Coverage: 129 UTC weeks, 632 source events, 108 completed V1 attempts. Frozen V1 total +28.25R; past-only weekly filter +26.28R on 77 attempts. R is event-level and overlapping attempts are not portfolio equity. Recorded spread is included; slippage is excluded. Locked exam [2026-04-18, 2026-10-18) was excluded.

## Week-by-week sequence

### Week 2023-10-30 to 2023-11-05 UTC

- Source events: 2. Funnel outcomes: no retest 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +0.00R; adaptive +0.00R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2023-11-06 to 2023-11-12 UTC

- Source events: 4. Funnel outcomes: structure invalidated 1, no reclaim 2, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +0.00R; adaptive +0.00R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2023-11-13 to 2023-11-19 UTC

- Source events: 5. Funnel outcomes: no retest 2, no continuation 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 5.
- Weekly result: V1 -0.60R on 2 attempts; adaptive -0.60R on 2. Cumulative: V1 -0.60R; adaptive -0.60R.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +0.57R / median MAE -0.67R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2023-11-20 to 2023-11-26 UTC

- Source events: 7. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 2, no continuation 1; completed V1 attempts: 2 (0 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 7.
- Weekly result: V1 -1.76R on 2 attempts; adaptive -1.76R on 2. Cumulative: V1 -2.36R; adaptive -2.36R.
- Weekly learning: 0 positive and 2 non-positive attempts; median MFE +0.00R / median MAE -1.17R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2023-11-27 to 2023-12-03 UTC

- Source events: 5. Funnel outcomes: no retest 5; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 5.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -2.36R; adaptive -2.36R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2023-12-04 to 2023-12-10 UTC

- Source events: 5. Funnel outcomes: no retest 3, no continuation 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 5.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -2.36R; adaptive -2.36R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2023-12-11 to 2023-12-17 UTC

- Source events: 4. Funnel outcomes: structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 +2.35R on 1 attempts; adaptive +2.35R on 1. Cumulative: V1 -0.01R; adaptive -0.01R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +2.81R / median MAE -0.63R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2023-12-18 to 2023-12-24 UTC

- Source events: 7. Funnel outcomes: no retest 2, structure invalidated 2, no reclaim 1, no continuation 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 7.
- Weekly result: V1 -0.79R on 1 attempts; adaptive -0.79R on 1. Cumulative: V1 -0.81R; adaptive -0.81R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.06R / median MAE -0.92R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2023-12-25 to 2023-12-31 UTC

- Source events: 5. Funnel outcomes: no retest 2, no reclaim 2, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 5.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -0.81R; adaptive -0.81R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-01-01 to 2024-01-07 UTC

- Source events: 2. Funnel outcomes: no retest 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -0.81R; adaptive -0.81R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-01-08 to 2024-01-14 UTC

- Source events: 4. Funnel outcomes: no retest 1, no reclaim 3; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -0.81R; adaptive -0.81R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-01-15 to 2024-01-21 UTC

- Source events: 4. Funnel outcomes: structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 -0.35R on 1 attempts; adaptive -0.35R on 1. Cumulative: V1 -1.15R; adaptive -1.15R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.31R / median MAE -0.38R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-01-22 to 2024-01-28 UTC

- Source events: 6. Funnel outcomes: no retest 4, structure invalidated 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 6.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -1.15R; adaptive -1.15R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-01-29 to 2024-02-04 UTC

- Source events: 7. Funnel outcomes: no retest 4, structure invalidated 1, no reclaim 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 7.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -1.15R; adaptive -1.15R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-02-05 to 2024-02-11 UTC

- Source events: 4. Funnel outcomes: no retest 2, no reclaim 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 -0.26R on 1 attempts; adaptive -0.26R on 1. Cumulative: V1 -1.42R; adaptive -1.42R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +1.28R / median MAE -0.37R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-02-12 to 2024-02-18 UTC

- Source events: 3. Funnel outcomes: no reclaim 1, no continuation 1, pending 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -1.42R; adaptive -1.42R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-02-19 to 2024-02-25 UTC

- Source events: 8. Funnel outcomes: no retest 2, no reclaim 3, no continuation 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 8.
- Weekly result: V1 +0.86R on 1 attempts; adaptive +0.86R on 1. Cumulative: V1 -0.56R; adaptive -0.56R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +2.50R / median MAE -0.30R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-02-26 to 2024-03-03 UTC

- Source events: 4. Funnel outcomes: no reclaim 1; completed V1 attempts: 3 (1 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 -0.85R on 3 attempts; adaptive -0.85R on 3. Cumulative: V1 -1.41R; adaptive -1.41R.
- Weekly learning: 1 positive and 2 non-positive attempts; median MFE +0.76R / median MAE -0.98R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-03-04 to 2024-03-10 UTC

- Source events: 2. Funnel outcomes: no retest 1, structure invalidated 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -1.41R; adaptive -1.41R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-03-11 to 2024-03-17 UTC

- Source events: 7. Funnel outcomes: no retest 2, structure invalidated 1, no continuation 1; completed V1 attempts: 3 (1 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 5, non-positive-history block: 2.
- Weekly result: V1 -1.54R on 3 attempts; adaptive -1.54R on 3. Cumulative: V1 -2.95R; adaptive -2.95R.
- Weekly learning: 1 positive and 2 non-positive attempts; median MFE +0.56R / median MAE -0.77R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-03-18 to 2024-03-24 UTC

- Source events: 9. Funnel outcomes: no retest 6, no reclaim 1, no continuation 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 6.
- Weekly result: V1 +6.18R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.23R; adaptive -2.95R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +6.18R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +7.22R / median MAE -0.54R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-03-25 to 2024-03-31 UTC

- Source events: 8. Funnel outcomes: no retest 3, structure invalidated 3, no reclaim 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4, non-positive-history block: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.23R; adaptive -2.95R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-04-01 to 2024-04-07 UTC

- Source events: 7. Funnel outcomes: no retest 5, structure invalidated 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4, non-positive-history block: 3.
- Weekly result: V1 +1.01R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +4.24R; adaptive -2.95R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +1.01R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +2.47R / median MAE -0.05R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-04-08 to 2024-04-14 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1, no continuation 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 2.
- Weekly result: V1 -0.01R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +4.23R; adaptive -2.95R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.01R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.98R / median MAE -0.17R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-04-15 to 2024-04-21 UTC

- Source events: 5. Funnel outcomes: no retest 2, no reclaim 2; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 2.
- Weekly result: V1 -0.79R on 1 attempts; adaptive -0.79R on 1. Cumulative: V1 +3.44R; adaptive -3.73R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.00R / median MAE -1.02R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-04-22 to 2024-04-28 UTC

- Source events: 3. Funnel outcomes: no retest 2, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.44R; adaptive -3.73R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-04-29 to 2024-05-05 UTC

- Source events: 6. Funnel outcomes: no retest 1, no reclaim 2, no continuation 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 4.
- Weekly result: V1 +0.13R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.57R; adaptive -3.73R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +0.13R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +0.89R / median MAE -0.44R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-05-06 to 2024-05-12 UTC

- Source events: 3. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.57R; adaptive -3.73R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-05-13 to 2024-05-19 UTC

- Source events: 2. Funnel outcomes: no reclaim 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.57R; adaptive -3.73R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-05-20 to 2024-05-26 UTC

- Source events: 5. Funnel outcomes: no retest 3, structure invalidated 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.57R; adaptive -3.73R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-05-27 to 2024-06-02 UTC

- Source events: 3. Funnel outcomes: no retest 1, structure invalidated 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 1.
- Weekly result: V1 -0.66R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.91R; adaptive -3.73R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.66R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.01R / median MAE -0.68R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-06-03 to 2024-06-09 UTC

- Source events: 5. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4, non-positive-history block: 1.
- Weekly result: V1 +1.45R on 1 attempts; adaptive +1.45R on 1. Cumulative: V1 +4.36R; adaptive -2.28R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +2.88R / median MAE -0.77R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-06-10 to 2024-06-16 UTC

- Source events: 4. Funnel outcomes: no retest 2, structure invalidated 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 3.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +4.36R; adaptive -2.28R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-06-17 to 2024-06-23 UTC

- Source events: 8. Funnel outcomes: no retest 3, structure invalidated 1, no reclaim 2, no continuation 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 6, non-positive-history block: 2.
- Weekly result: V1 +0.27R on 1 attempts; adaptive +0.27R on 1. Cumulative: V1 +4.62R; adaptive -2.02R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +2.06R / median MAE -0.21R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-06-24 to 2024-06-30 UTC

- Source events: 4. Funnel outcomes: no retest 2, no continuation 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 3.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +4.62R; adaptive -2.02R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-07-01 to 2024-07-07 UTC

- Source events: 6. Funnel outcomes: no retest 2, structure invalidated 2, no continuation 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +4.62R; adaptive -2.02R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-07-08 to 2024-07-14 UTC

- Source events: 6. Funnel outcomes: no retest 4; completed V1 attempts: 2 (0 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 5, non-positive-history block: 1.
- Weekly result: V1 -1.29R on 2 attempts; adaptive -1.00R on 1. Cumulative: V1 +3.34R; adaptive -3.02R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.29R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 2 non-positive attempts; median MFE +0.30R / median MAE -0.72R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-07-15 to 2024-07-21 UTC

- Source events: 5. Funnel outcomes: no retest 2, structure invalidated 1, no reclaim 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.34R; adaptive -3.02R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-07-22 to 2024-07-28 UTC

- Source events: 5. Funnel outcomes: no retest 2, structure invalidated 1, no reclaim 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 2.
- Weekly result: V1 -1.00R on 1 attempts; adaptive -1.00R on 1. Cumulative: V1 +2.34R; adaptive -4.02R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +1.88R / median MAE -1.02R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-07-29 to 2024-08-04 UTC

- Source events: 7. Funnel outcomes: no retest 2, structure invalidated 3; completed V1 attempts: 2 (0 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 5.
- Weekly result: V1 -1.93R on 2 attempts; adaptive -0.93R on 1. Cumulative: V1 +0.40R; adaptive -4.95R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -1.00R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 2 non-positive attempts; median MFE +0.81R / median MAE -1.16R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-08-05 to 2024-08-11 UTC

- Source events: 4. Funnel outcomes: structure invalidated 1, no reclaim 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 3.
- Weekly result: V1 +0.63R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +1.04R; adaptive -4.95R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +0.63R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +2.53R / median MAE -0.66R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-08-12 to 2024-08-18 UTC

- Source events: 3. Funnel outcomes: none; completed V1 attempts: 3 (0 positive, 3 non-positive).
- Past-only decisions this week: non-positive-history block: 3.
- Weekly result: V1 -2.16R on 3 attempts; adaptive +0.00R on 0. Cumulative: V1 -1.12R; adaptive -4.95R.
- Filter review: blocked 3 completed counterfactual attempt(s), worth -2.16R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 3 non-positive attempts; median MFE +0.16R / median MAE -1.13R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-08-19 to 2024-08-25 UTC

- Source events: 6. Funnel outcomes: no retest 4; completed V1 attempts: 2 (2 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 3.
- Weekly result: V1 +0.64R on 2 attempts; adaptive +0.64R on 2. Cumulative: V1 -0.48R; adaptive -4.31R.
- Weekly learning: 2 positive and 0 non-positive attempts; median MFE +1.97R / median MAE -0.77R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-08-26 to 2024-09-01 UTC

- Source events: 5. Funnel outcomes: no retest 2, structure invalidated 2, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -0.48R; adaptive -4.31R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-09-02 to 2024-09-08 UTC

- Source events: 2. Funnel outcomes: no reclaim 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 1.
- Weekly result: V1 -1.00R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 -1.48R; adaptive -4.31R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -1.00R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.25R / median MAE -1.07R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-09-09 to 2024-09-15 UTC

- Source events: 6. Funnel outcomes: no retest 3, no reclaim 2, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 5.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 -1.48R; adaptive -4.31R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-09-16 to 2024-09-22 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 3.
- Weekly result: V1 +1.65R on 2 attempts; adaptive -0.41R on 1. Cumulative: V1 +0.16R; adaptive -4.72R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +2.06R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +1.55R / median MAE -0.62R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-09-23 to 2024-09-29 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 3.
- Weekly result: V1 +1.84R on 2 attempts; adaptive -0.18R on 1. Cumulative: V1 +2.00R; adaptive -4.91R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +2.02R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +2.71R / median MAE -0.39R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-09-30 to 2024-10-06 UTC

- Source events: 3. Funnel outcomes: structure invalidated 1; completed V1 attempts: 2 (0 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 1.
- Weekly result: V1 -1.60R on 2 attempts; adaptive -1.00R on 1. Cumulative: V1 +0.40R; adaptive -5.91R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.60R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 2 non-positive attempts; median MFE +0.54R / median MAE -0.87R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-10-07 to 2024-10-13 UTC

- Source events: 3. Funnel outcomes: no retest 1, no reclaim 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: non-positive-history block: 3.
- Weekly result: V1 +2.17R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.57R; adaptive -5.91R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +2.17R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +3.93R / median MAE -0.28R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-10-14 to 2024-10-20 UTC

- Source events: 4. Funnel outcomes: no retest 2, structure invalidated 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: positive-history allow: 1, non-positive-history block: 3.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.57R; adaptive -5.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-10-21 to 2024-10-27 UTC

- Source events: 4. Funnel outcomes: no retest 3, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: non-positive-history block: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.57R; adaptive -5.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-10-28 to 2024-11-03 UTC

- Source events: 5. Funnel outcomes: no retest 4, structure invalidated 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: non-positive-history block: 5.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.57R; adaptive -5.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-11-04 to 2024-11-10 UTC

- Source events: 6. Funnel outcomes: no retest 3, structure invalidated 1, no reclaim 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 1, non-positive-history block: 4.
- Weekly result: V1 -1.00R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +1.57R; adaptive -5.91R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -1.00R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.00R / median MAE -1.26R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-11-11 to 2024-11-17 UTC

- Source events: 6. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 3, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 2, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +1.57R; adaptive -5.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-11-18 to 2024-11-24 UTC

- Source events: 2. Funnel outcomes: no reclaim 1, pending 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +1.57R; adaptive -5.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-11-25 to 2024-12-01 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 2.
- Weekly result: V1 +2.61R on 1 attempts; adaptive +2.61R on 1. Cumulative: V1 +4.19R; adaptive -3.29R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +3.41R / median MAE -0.28R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-12-02 to 2024-12-08 UTC

- Source events: 3. Funnel outcomes: no retest 1, pending 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 1.
- Weekly result: V1 -0.88R on 1 attempts; adaptive -0.88R on 1. Cumulative: V1 +3.31R; adaptive -4.17R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.65R / median MAE -1.02R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-12-09 to 2024-12-15 UTC

- Source events: 4. Funnel outcomes: no retest 2, structure invalidated 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.31R; adaptive -4.17R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2024-12-16 to 2024-12-22 UTC

- Source events: 7. Funnel outcomes: no retest 2, no reclaim 1, no continuation 3; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 5, positive-history allow: 1, non-positive-history block: 1.
- Weekly result: V1 +0.08R on 1 attempts; adaptive +0.08R on 1. Cumulative: V1 +3.38R; adaptive -4.09R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +1.22R / median MAE -0.93R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-12-23 to 2024-12-29 UTC

- Source events: 5. Funnel outcomes: no reclaim 1, no continuation 1, pending 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 3.
- Weekly result: V1 -0.80R on 2 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.59R; adaptive -4.09R.
- Filter review: blocked 2 completed counterfactual attempt(s), worth -0.80R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +0.44R / median MAE -0.72R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2024-12-30 to 2025-01-05 UTC

- Source events: 3. Funnel outcomes: no retest 1, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.59R; adaptive -4.09R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-01-06 to 2025-01-12 UTC

- Source events: 3. Funnel outcomes: no continuation 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 1.
- Weekly result: V1 +0.51R on 1 attempts; adaptive +0.51R on 1. Cumulative: V1 +3.09R; adaptive -3.59R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +1.40R / median MAE -0.80R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-01-13 to 2025-01-19 UTC

- Source events: 5. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 3; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.09R; adaptive -3.59R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-01-20 to 2025-01-26 UTC

- Source events: 2. Funnel outcomes: no retest 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.09R; adaptive -3.59R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-01-27 to 2025-02-02 UTC

- Source events: 7. Funnel outcomes: no retest 3, structure invalidated 2; completed V1 attempts: 2 (0 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 5, non-positive-history block: 2.
- Weekly result: V1 -1.16R on 2 attempts; adaptive -0.16R on 1. Cumulative: V1 +1.93R; adaptive -3.75R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -1.00R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 2 non-positive attempts; median MFE +0.77R / median MAE -0.79R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-02-03 to 2025-02-09 UTC

- Source events: 4. Funnel outcomes: no retest 2, structure invalidated 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +1.93R; adaptive -3.75R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-02-10 to 2025-02-16 UTC

- Source events: 4. Funnel outcomes: structure invalidated 3; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 -0.69R on 1 attempts; adaptive -0.69R on 1. Cumulative: V1 +1.24R; adaptive -4.44R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.09R / median MAE -0.72R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-02-17 to 2025-02-23 UTC

- Source events: 7. Funnel outcomes: no retest 1, structure invalidated 4, no continuation 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 6, non-positive-history block: 1.
- Weekly result: V1 +2.85R on 1 attempts; adaptive +2.85R on 1. Cumulative: V1 +4.09R; adaptive -1.59R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +3.35R / median MAE -0.42R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-02-24 to 2025-03-02 UTC

- Source events: 3. Funnel outcomes: structure invalidated 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3.
- Weekly result: V1 +0.70R on 1 attempts; adaptive +0.70R on 1. Cumulative: V1 +4.80R; adaptive -0.88R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +2.82R / median MAE -0.12R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-03-03 to 2025-03-09 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +4.80R; adaptive -0.88R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-03-10 to 2025-03-16 UTC

- Source events: 4. Funnel outcomes: structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 4.
- Weekly result: V1 -1.00R on 1 attempts; adaptive -1.00R on 1. Cumulative: V1 +3.80R; adaptive -1.88R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.99R / median MAE -1.46R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-03-17 to 2025-03-23 UTC

- Source events: 6. Funnel outcomes: no retest 2, structure invalidated 2, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 5, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +3.80R; adaptive -1.88R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-03-24 to 2025-03-30 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 -0.91R on 1 attempts; adaptive -0.91R on 1. Cumulative: V1 +2.89R; adaptive -2.79R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.92R / median MAE -0.96R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-03-31 to 2025-04-06 UTC

- Source events: 4. Funnel outcomes: no retest 3, structure invalidated 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.89R; adaptive -2.79R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-04-07 to 2025-04-13 UTC

- Source events: 5. Funnel outcomes: no retest 3, structure invalidated 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4, non-positive-history block: 1.
- Weekly result: V1 +0.38R on 1 attempts; adaptive +0.38R on 1. Cumulative: V1 +3.27R; adaptive -2.42R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +1.26R / median MAE -0.37R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-04-14 to 2025-04-20 UTC

- Source events: 6. Funnel outcomes: no retest 3, structure invalidated 2; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 5, non-positive-history block: 1.
- Weekly result: V1 -0.54R on 1 attempts; adaptive -0.54R on 1. Cumulative: V1 +2.73R; adaptive -2.96R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.68R / median MAE -0.92R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-04-21 to 2025-04-27 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.73R; adaptive -2.96R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-04-28 to 2025-05-04 UTC

- Source events: 6. Funnel outcomes: no retest 3, no reclaim 1, no continuation 2; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +2.73R; adaptive -2.96R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-05-05 to 2025-05-11 UTC

- Source events: 5. Funnel outcomes: no retest 2, structure invalidated 1, no reclaim 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 5.
- Weekly result: V1 +10.08R on 1 attempts; adaptive +10.08R on 1. Cumulative: V1 +12.80R; adaptive +7.12R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +11.44R / median MAE -0.89R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-05-12 to 2025-05-18 UTC

- Source events: 8. Funnel outcomes: no retest 4, structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 8.
- Weekly result: V1 -1.00R on 1 attempts; adaptive -1.00R on 1. Cumulative: V1 +11.80R; adaptive +6.12R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.02R / median MAE -1.04R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-05-19 to 2025-05-25 UTC

- Source events: 9. Funnel outcomes: no retest 2, structure invalidated 2, no reclaim 3; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 5, non-positive-history block: 4.
- Weekly result: V1 +1.00R on 2 attempts; adaptive +1.48R on 1. Cumulative: V1 +12.80R; adaptive +7.60R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.48R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +1.41R / median MAE -0.35R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-05-26 to 2025-06-01 UTC

- Source events: 8. Funnel outcomes: no retest 2, structure invalidated 2, no reclaim 3, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 6, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +12.80R; adaptive +7.60R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-06-02 to 2025-06-08 UTC

- Source events: 5. Funnel outcomes: no retest 2, no reclaim 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 4, non-positive-history block: 1.
- Weekly result: V1 +13.36R on 1 attempts; adaptive +13.36R on 1. Cumulative: V1 +26.16R; adaptive +20.96R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +15.57R / median MAE -0.47R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-06-09 to 2025-06-15 UTC

- Source events: 5. Funnel outcomes: no retest 2, structure invalidated 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 5.
- Weekly result: V1 -0.36R on 2 attempts; adaptive -0.36R on 2. Cumulative: V1 +25.81R; adaptive +20.60R.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +0.79R / median MAE -0.70R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-06-16 to 2025-06-22 UTC

- Source events: 6. Funnel outcomes: no retest 2, structure invalidated 1, no continuation 1, pending 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: non-positive-history block: 6.
- Weekly result: V1 -1.00R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +24.81R; adaptive +20.60R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -1.00R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.14R / median MAE -1.26R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-06-23 to 2025-06-29 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: non-positive-history block: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +24.81R; adaptive +20.60R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-06-30 to 2025-07-06 UTC

- Source events: 7. Funnel outcomes: no retest 5, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 1, non-positive-history block: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +24.81R; adaptive +20.60R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-07-07 to 2025-07-13 UTC

- Source events: 6. Funnel outcomes: no retest 3, structure invalidated 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 2, non-positive-history block: 2.
- Weekly result: V1 -0.45R on 2 attempts; adaptive -0.45R on 2. Cumulative: V1 +24.36R; adaptive +20.15R.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +0.67R / median MAE -0.88R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-07-14 to 2025-07-20 UTC

- Source events: 7. Funnel outcomes: no retest 1, structure invalidated 3, no continuation 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 3, positive-history allow: 1, non-positive-history block: 3.
- Weekly result: V1 -0.02R on 2 attempts; adaptive -0.02R on 2. Cumulative: V1 +24.34R; adaptive +20.13R.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +1.30R / median MAE -0.67R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-07-21 to 2025-07-27 UTC

- Source events: 6. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1, no continuation 1, pending 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 3, non-positive-history block: 2.
- Weekly result: V1 -0.41R on 1 attempts; adaptive -0.41R on 1. Cumulative: V1 +23.92R; adaptive +19.72R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +1.28R / median MAE -0.63R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-07-28 to 2025-08-03 UTC

- Source events: 7. Funnel outcomes: structure invalidated 1, no reclaim 1; completed V1 attempts: 5 (2 positive, 3 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 4, non-positive-history block: 1.
- Weekly result: V1 -1.92R on 5 attempts; adaptive -2.12R on 4. Cumulative: V1 +22.00R; adaptive +17.60R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +0.20R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 2 positive and 3 non-positive attempts; median MFE +0.42R / median MAE -0.49R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-08-04 to 2025-08-10 UTC

- Source events: 4. Funnel outcomes: no retest 3; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 2, non-positive-history block: 1.
- Weekly result: V1 -0.69R on 1 attempts; adaptive -0.69R on 1. Cumulative: V1 +21.31R; adaptive +16.91R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.03R / median MAE -0.72R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-08-11 to 2025-08-17 UTC

- Source events: 3. Funnel outcomes: no retest 1, no continuation 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: non-positive-history block: 3.
- Weekly result: V1 +1.85R on 1 attempts; adaptive +0.00R on 0. Cumulative: V1 +23.17R; adaptive +16.91R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth +1.85R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +4.24R / median MAE -0.29R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-08-18 to 2025-08-24 UTC

- Source events: 6. Funnel outcomes: no retest 2, structure invalidated 4; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 2, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +23.17R; adaptive +16.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-08-25 to 2025-08-31 UTC

- Source events: 3. Funnel outcomes: structure invalidated 1, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +23.17R; adaptive +16.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-09-01 to 2025-09-07 UTC

- Source events: 5. Funnel outcomes: no retest 4, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +23.17R; adaptive +16.91R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-09-08 to 2025-09-14 UTC

- Source events: 6. Funnel outcomes: no retest 4, no reclaim 1; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 2, non-positive-history block: 2.
- Weekly result: V1 +0.85R on 1 attempts; adaptive +0.85R on 1. Cumulative: V1 +24.02R; adaptive +17.76R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +1.44R / median MAE -0.32R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-09-15 to 2025-09-21 UTC

- Source events: 1. Funnel outcomes: no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +24.02R; adaptive +17.76R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-09-22 to 2025-09-28 UTC

- Source events: 9. Funnel outcomes: structure invalidated 4, no continuation 1, pending 1; completed V1 attempts: 3 (1 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 5, positive-history allow: 3, non-positive-history block: 1.
- Weekly result: V1 +8.44R on 3 attempts; adaptive +8.44R on 3. Cumulative: V1 +32.45R; adaptive +26.20R.
- Weekly learning: 1 positive and 2 non-positive attempts; median MFE +0.90R / median MAE -0.48R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-09-29 to 2025-10-05 UTC

- Source events: 4. Funnel outcomes: no retest 2, structure invalidated 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +32.45R; adaptive +26.20R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-10-06 to 2025-10-12 UTC

- Source events: 7. Funnel outcomes: no retest 1, no reclaim 3, no continuation 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 3, non-positive-history block: 2.
- Weekly result: V1 -0.08R on 2 attempts; adaptive +0.56R on 1. Cumulative: V1 +32.37R; adaptive +26.76R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.64R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +0.91R / median MAE -0.53R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-10-13 to 2025-10-19 UTC

- Source events: 7. Funnel outcomes: no retest 2, structure invalidated 1, no reclaim 1; completed V1 attempts: 3 (1 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 3, positive-history allow: 2, non-positive-history block: 2.
- Weekly result: V1 -0.52R on 3 attempts; adaptive +0.07R on 1. Cumulative: V1 +31.86R; adaptive +26.83R.
- Filter review: blocked 2 completed counterfactual attempt(s), worth -0.59R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 2 non-positive attempts; median MFE +0.50R / median MAE -0.20R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-10-20 to 2025-10-26 UTC

- Source events: 7. Funnel outcomes: no retest 2, no reclaim 4, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 3, non-positive-history block: 3.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +31.86R; adaptive +26.83R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-10-27 to 2025-11-02 UTC

- Source events: 6. Funnel outcomes: no retest 2, structure invalidated 1, no reclaim 2; completed V1 attempts: 1 (1 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 4.
- Weekly result: V1 +0.01R on 1 attempts; adaptive +0.01R on 1. Cumulative: V1 +31.87R; adaptive +26.84R.
- Weekly learning: 1 positive and 0 non-positive attempts; median MFE +0.76R / median MAE -0.55R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-11-03 to 2025-11-09 UTC

- Source events: 3. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +31.87R; adaptive +26.84R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-11-10 to 2025-11-16 UTC

- Source events: 5. Funnel outcomes: no retest 1, structure invalidated 2, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: positive-history allow: 1, non-positive-history block: 4.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +31.87R; adaptive +26.84R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-11-17 to 2025-11-23 UTC

- Source events: 6. Funnel outcomes: no retest 4, structure invalidated 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 1, non-positive-history block: 3.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +31.87R; adaptive +26.84R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-11-24 to 2025-11-30 UTC

- Source events: 5. Funnel outcomes: no retest 2, structure invalidated 1; completed V1 attempts: 2 (0 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 3.
- Weekly result: V1 -1.31R on 2 attempts; adaptive -1.31R on 2. Cumulative: V1 +30.56R; adaptive +25.53R.
- Weekly learning: 0 positive and 2 non-positive attempts; median MFE +0.40R / median MAE -0.74R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-12-01 to 2025-12-07 UTC

- Source events: 5. Funnel outcomes: no retest 4, structure invalidated 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +30.56R; adaptive +25.53R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2025-12-08 to 2025-12-14 UTC

- Source events: 6. Funnel outcomes: no retest 2, structure invalidated 2, no reclaim 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 3, positive-history allow: 1, non-positive-history block: 2.
- Weekly result: V1 -1.00R on 1 attempts; adaptive -1.00R on 1. Cumulative: V1 +29.56R; adaptive +24.53R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.16R / median MAE -1.10R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-12-15 to 2025-12-21 UTC

- Source events: 4. Funnel outcomes: structure invalidated 1, no continuation 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: positive-history allow: 2, non-positive-history block: 2.
- Weekly result: V1 -0.09R on 2 attempts; adaptive +0.50R on 1. Cumulative: V1 +29.47R; adaptive +25.04R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.59R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +1.00R / median MAE -0.80R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-12-22 to 2025-12-28 UTC

- Source events: 5. Funnel outcomes: no retest 3, structure invalidated 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 3, non-positive-history block: 1.
- Weekly result: V1 -1.00R on 1 attempts; adaptive -1.00R on 1. Cumulative: V1 +28.47R; adaptive +24.04R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.01R / median MAE -1.26R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2025-12-29 to 2026-01-04 UTC

- Source events: 3. Funnel outcomes: no retest 1, structure invalidated 1, pending 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +28.47R; adaptive +24.04R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-01-05 to 2026-01-11 UTC

- Source events: 4. Funnel outcomes: no retest 2, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, non-positive-history block: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +28.47R; adaptive +24.04R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-01-12 to 2026-01-18 UTC

- Source events: 1. Funnel outcomes: structure invalidated 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: positive-history allow: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +28.47R; adaptive +24.04R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-01-19 to 2026-01-25 UTC

- Source events: 6. Funnel outcomes: no reclaim 4, no continuation 1; completed V1 attempts: 1 (0 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 2, non-positive-history block: 2.
- Weekly result: V1 -1.00R on 1 attempts; adaptive -1.00R on 1. Cumulative: V1 +27.47R; adaptive +23.04R.
- Weekly learning: 0 positive and 1 non-positive attempts; median MFE +0.00R / median MAE -1.11R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2026-01-26 to 2026-02-01 UTC

- Source events: 7. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 2, no continuation 1; completed V1 attempts: 2 (0 positive, 2 non-positive).
- Past-only decisions this week: warm-up allow: 4, positive-history allow: 2, non-positive-history block: 1.
- Weekly result: V1 -1.21R on 2 attempts; adaptive -0.21R on 1. Cumulative: V1 +26.26R; adaptive +22.83R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -1.00R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 0 positive and 2 non-positive attempts; median MFE +0.85R / median MAE -0.67R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2026-02-02 to 2026-02-08 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1, no continuation 1, pending 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 3, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +26.26R; adaptive +22.83R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-02-09 to 2026-02-15 UTC

- Source events: 7. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 2, no continuation 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 2, non-positive-history block: 3.
- Weekly result: V1 +3.46R on 2 attempts; adaptive +4.33R on 1. Cumulative: V1 +29.72R; adaptive +27.15R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.87R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +3.54R / median MAE -0.57R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2026-02-16 to 2026-02-22 UTC

- Source events: 4. Funnel outcomes: no retest 2, no reclaim 1, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1, positive-history allow: 2, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +29.72R; adaptive +27.15R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-02-23 to 2026-03-01 UTC

- Source events: 1. Funnel outcomes: no retest 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +29.72R; adaptive +27.15R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-03-02 to 2026-03-08 UTC

- Source events: 4. Funnel outcomes: no retest 1, structure invalidated 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 1, non-positive-history block: 1.
- Weekly result: V1 +0.26R on 2 attempts; adaptive +0.26R on 2. Cumulative: V1 +29.98R; adaptive +27.42R.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +1.22R / median MAE -0.21R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2026-03-09 to 2026-03-15 UTC

- Source events: 2. Funnel outcomes: no retest 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +29.98R; adaptive +27.42R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-03-16 to 2026-03-22 UTC

- Source events: 8. Funnel outcomes: no retest 2, structure invalidated 2, no reclaim 2; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 5, non-positive-history block: 1.
- Weekly result: V1 +0.90R on 2 attempts; adaptive +1.50R on 1. Cumulative: V1 +30.88R; adaptive +28.92R.
- Filter review: blocked 1 completed counterfactual attempt(s), worth -0.60R in hindsight; this outcome may update later weeks only after settlement.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +1.23R / median MAE -0.65R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2026-03-23 to 2026-03-29 UTC

- Source events: 4. Funnel outcomes: no retest 1, no reclaim 2, no continuation 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 1, non-positive-history block: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +30.88R; adaptive +28.92R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

### Week 2026-03-30 to 2026-04-05 UTC

- Source events: 8. Funnel outcomes: no retest 1, structure invalidated 2, no reclaim 2, pending 1; completed V1 attempts: 2 (1 positive, 1 non-positive).
- Past-only decisions this week: warm-up allow: 5, positive-history allow: 3.
- Weekly result: V1 +0.36R on 2 attempts; adaptive +0.36R on 2. Cumulative: V1 +31.25R; adaptive +29.28R.
- Weekly learning: 1 positive and 1 non-positive attempts; median MFE +0.95R / median MAE -0.66R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2026-04-06 to 2026-04-12 UTC

- Source events: 5. Funnel outcomes: no retest 2; completed V1 attempts: 3 (0 positive, 3 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 3.
- Weekly result: V1 -3.00R on 3 attempts; adaptive -3.00R on 3. Cumulative: V1 +28.25R; adaptive +26.28R.
- Weekly learning: 0 positive and 3 non-positive attempts; median MFE +0.16R / median MAE -1.10R. The sample is small, so no threshold or strategy change is inferred from this week alone.

### Week 2026-04-13 to 2026-04-19 UTC

- Source events: 3. Funnel outcomes: no retest 1, structure invalidated 1, no reclaim 1; completed V1 attempts: 0 (0 positive, 0 non-positive).
- Past-only decisions this week: warm-up allow: 2, positive-history allow: 1.
- Weekly result: V1 +0.00R on 0 attempts; adaptive +0.00R on 0. Cumulative: V1 +28.25R; adaptive +26.28R.
- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.

## End-of-replay conclusion

The 52-week adaptive filter finished below the frozen V1 in total R (+26.28R versus +28.25R), although it had higher mean R per selected attempt. It blocked 31 completed V1 paths worth +1.96R in hindsight, and its chronological halves had opposite implications. Therefore it is not adopted. The week-by-week log is the requested learning journal; it does not convert an in-sample result into verified future profitability.

Machine-readable tables: `weekly_sequential_replay.csv` (all weeks) and `weekly_regime_filter_decisions.csv` (one decision for every source event). Reproduce with `.venv/Scripts/python.exe research/2026-10-21-trend-runner-retest-continuation/build_weekly_sequence_report.py`.
