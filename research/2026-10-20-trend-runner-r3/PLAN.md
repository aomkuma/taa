# TREND-RUNNER Round 3 - robust runner ensemble plan

Started after reviewing the completed TR2 result on 2026-10-20. No R3 result had been computed when this plan was
written.

## Purpose

TR2 showed that selected RUNNER exits were profitable while selected FAST exits lost, but its single 90-day model
was unstable and its result depended on one large winner. TR3 will therefore solve a narrower problem: identify
high-confidence opportunities to hold the already-frozen TR1 RUNNER exit, otherwise skip.

TR3 is a new isolated research setup. It does not edit TR1, TR2, PLAN-1, Setup OWN, engine/configuration, DEMO, LIVE
or database state.

## Evidence boundary

- Input is the independently verified 280-row TR2 feature panel covering 2025-10-20 through 2026-04-17.
- All P1/P2 data and the TR2 findings are seen development evidence. R3 has no unseen validation slice.
- The 2026-04-18 through 2026-10-17 historical exam remains locked and is not used.
- R3 cannot be promoted from this run regardless of performance.

## Primary model fixed before measurement

- Fit RUNNER R only; there is no FAST action.
- Refit at each UTC calendar month start.
- Fit three ridge models using 60, 90 and 120 calendar-day training windows.
- A training row must enter within its window and its RUNNER outcome must complete before month start.
- Require 60 eligible rows in every component; otherwise the month is warm-up.
- Use the same 11 causal entry features already independently verified in TR2.
- Training target is RUNNER R clipped to [-1.5, 5].
- Median imputation, mean/population-standard-deviation scaling and z clipping [-3, 3] use training rows only.
- Intercept is unpenalized; ridge alpha is 20 for all components.
- Ensemble prediction is the median of the three component predictions.
- Disagreement is their population standard deviation.
- Confidence score is `median - 0.5 * disagreement`.
- Choose RUNNER only when confidence score is greater than +0.05R and at least two components predict above zero.
- Otherwise choose SKIP. Decisions and model state remain frozen within the month.

No threshold or component will be changed after the primary result is seen. Predeclared diagnostics only:

1. score threshold 0.00 with disagreement penalty 0.5;
2. score threshold 0.10 with disagreement penalty 0.5;
3. score threshold 0.05 with no disagreement penalty;
4. score threshold 0.05 with disagreement penalty 1.0.

## Evaluation and sizing

Compare against always RUNNER on identical scored rows. Report total/mean R, bootstrap interval, drawdown, losing
streak, best-one/best-three removal, months/sessions/directions, action rate and coefficient stability. Fixed 0.01
lot USD is retained only as an audit metric. The operational comparison uses constant $10 initial risk per executed
trade, so normalized cash is `10 * R`.

Development-readiness gates:

- at least 100 scored opportunities and 60 executed RUNNER trades;
- at least +0.15R per executed trade and higher mean R than always RUNNER;
- total R at least half of always RUNNER while executing fewer trades;
- non-negative total after removing the best trade;
- drawdown at least 10% lower than always RUNNER;
- positive contribution outside the best month and outside the best session;
- all boundary, training-causality, ensemble, invariance and mutation checks pass.

Even a full pass means only `FORWARD SHADOW CANDIDATE`. Future evidence must start after the rules are frozen and
continue for both 60 new trading days and 100 new opportunities.

## Work order

1. Freeze hashes and hypothesis.
2. Build an independent R3 package that reads only verified artifacts.
3. Add unit, invariance and mutation tests before measurement.
4. Run the primary once, then only the four declared diagnostics.
5. Audit concentration, instability and sizing.
6. Write the decision and forward handoff without enabling orders.
