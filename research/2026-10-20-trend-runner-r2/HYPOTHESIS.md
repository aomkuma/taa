# TR2 frozen hypothesis

Frozen before the first selector measurement on 2026-10-20 (Asia/Bangkok).

## Question

Can information available at a frozen TR1 entry choose between its already-frozen `FAST` and `SPLIT`/`RUNNER`
outcomes, or skip a low-expectancy entry, without using the current trade's outcome or later prices?

## Population and boundary

- Use exactly the 280 frozen P1+P2 TR1 entries dated 2025-10-18 through 2026-04-17.
- The historical exam begins at 2026-04-18 00:00 UTC and is inaccessible to TR2.
- P1 and P2 are both seen design data. This round creates no new validation evidence.
- Entry, side, fill, stop and risk remain unchanged.

## Features known at entry

Only M1 rows ending before the exam boundary may be loaded. H1 and H4 bars become available at their UTC clock
end and must have `available_at <= entry_time`.

1. Direction-aligned H1 close movement over six completed H1 bars, divided by H1 ATR(14).
2. Direction-aligned H4 close movement over three completed H4 bars, divided by that H1 ATR.
3. Directional open space to the nearest applicable resistance/support among:
   - the high/low of the most recent completed UTC trading day, not merely the previous calendar date; and
   - the high/low of the most recent 20 completed H1 bars.
   The positive distance is divided by H1 ATR and capped to `[0, 5]`; if no level lies ahead, it is 5.
4. H1 ATR percentile against the preceding 120 completed H1 ATR values, excluding the current ATR.
5. Frozen initial `risk_h1`.
6. Frozen `pullback_ratio`.
7. Minutes from anchor to entry, capped to `[0, 240]`.
8. Side, +1 for buy and -1 for sell.
9. Asia and London one-hot indicators; New York is the reference.
10. Mean `RUNNER_R - FAST_R` of the last 20 same-session trades whose FAST and RUNNER outcomes both completed
    before the current entry. Require five such observations, otherwise use zero; clip to `[-2, 2]`.

## Primary policy

At each calendar month start, fit two ridge models from eligible trades entered in the preceding 90 calendar days
and whose two outcomes completed strictly before month start. Require 60 rows. Months below the minimum are warm-up
and are not scored.

- Targets: FAST R and RUNNER R, separately clipped to `[-1.5, 5]`.
- Missing values: training-window median.
- Standardization: training-window mean and population standard deviation only; clip z-scores to `[-3, 3]`.
- Regression: unpenalized intercept, ridge alpha 10.
- Monthly coefficients and preprocessing remain fixed for all entries in that month.
- Choose `SKIP` when `max(pred_fast, pred_runner) < -0.05`.
- Otherwise choose `RUNNER` only when `pred_runner > pred_fast + 0.05`; choose `FAST` otherwise.

Predeclared diagnostics are alpha 5 and 20 with the 90-day window, plus 60-day and 120-day windows with alpha 10.
They are sensitivity checks and cannot replace the primary after its result is known.

## Readiness, not promotion

The primary needs at least 100 scored opportunities, 60 executed trades, at least +0.15 R per executed trade,
non-negative total after removing its best trade, drawdown no worse than always RUNNER on identical scored rows,
and edge not wholly supplied by one month or session. All causal, independent and mutation checks must pass.

Passing means only `SHADOW CANDIDATE`. Promotion still requires at least 60 genuinely future trading days or 100
future opportunities gathered after this work. TR2 will not open, use, or report the locked historical exam.
