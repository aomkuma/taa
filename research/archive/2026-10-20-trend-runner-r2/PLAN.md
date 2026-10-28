# TREND-RUNNER Round 2 (TR2) - adaptive exit selector plan

Started: 2026-10-20 20:02 Thai time. This plan was written before computing any TR2 selector result.

## Objective

Keep the causal TR1 opening-impulse/first-pullback entry, but choose `FAST`, `RUNNER` or `SKIP` from information
available at entry and a model fitted only on older completed trades. The purpose is to adapt to changing session,
direction, volatility and higher-timeframe flow without changing a rule after each loss.

TR2 is a new research setup. It does not modify TR1 round 1, PLAN-1, Setup OWN, engine configuration, DEMO, LIVE or
database state.

## Evidence boundary

- Immutable design inputs: TR1 frozen P1 and P2 entries/results, 2025-10-18 through 2026-04-17.
- P2 is already seen from TR1 round 1. It is design evidence here, never described as new validation.
- The declared exam, 2026-04-18 through 2026-10-17, remains locked and must not be read.
- A genuinely new validation slice does not yet exist. TR2 may finish as a shadow-ready candidate, not a promoted
  trading strategy.
- Raw M1 needed for causal features may be read only through 2026-04-17. TR1 raw tick outcomes are reused from the
  frozen independently verified artifacts rather than resimulated or altered.

## Fixed entry and actions

The entry population is exactly the 280 frozen TR1 entries: 0.25 H impulse, M1 causal first pullback/continuation,
all Asia/London/New York windows. No TR2 feature changes entry time, side, fill, initial stop or risk.

At a monthly rebalance, TR2 predicts the clipped expected R of two already-frozen actions:

- `FAST`: initial stop, +2R target, 60-minute maximum;
- `RUNNER`: the frozen SPLIT exit, one third at +1R and two thirds on the M5-to-M15 trail.

Choose RUNNER only when its predicted R exceeds FAST by at least 0.05R. Otherwise choose FAST. Choose SKIP only when
the larger prediction is below -0.05R. Predictions and action choices stay fixed until the next calendar month.

## Causal feature set

All price features use only bars whose clock end is no later than entry:

1. trade-direction H1 flow over six completed H1 bars, divided by current H1 ATR;
2. trade-direction H4 flow over three completed H4 bars, divided by H1 ATR;
3. open space in the trade direction to the nearer of the previous UTC-day extreme and recent 20-H1 extreme,
   divided by H1 ATR and capped to [0, 5];
4. current H1 ATR percentile within the previous 120 completed H1 ATR values;
5. initial risk/H;
6. pullback ratio;
7. minutes from anchor to entry, capped at 240;
8. side (+1 buy, -1 sell);
9. Asia and London indicators (New York is the reference category);
10. mean `RUNNER - FAST` R over the previous 20 completed entries of the same session, shifted one trade and clipped
    to [-2, 2]. When fewer than five exist, use zero.

The session-history feature is recalculated causally for every row. It never includes the current or later outcome.

## Adaptive model fixed before measurement

- Refit on the first day of each calendar month.
- Training rows: entries in the 90 calendar days before that month, never current-month rows.
- Require at least 60 completed training rows; months without enough history are warm-up and not scored.
- Two separate ridge regressions predict FAST R and RUNNER R.
- Training targets are clipped to [-1.5R, +5R] so one giant runner cannot set the policy.
- Features are standardized from the training window only, then clipped to z = [-3, 3].
- Intercept is unpenalized; ridge alpha is 10.
- Missing feature values are imputed with the training median only.
- No model coefficient or threshold changes inside a month.

Predeclared sensitivity diagnostics are alpha 5/20 and training windows 60/120 days. They cannot replace the primary
after results are visible.

## Evaluation

Compare PRIMARY, always FAST and always RUNNER on exactly the same scored opportunities. Report action counts,
executed trades/day, mean/total R, USD at 0.01 lot, 95% bootstrap interval, worst trade, drawdown, losing streak,
weekly/monthly/session/direction cuts, best-one/best-three removal and coefficients per refit.

Prototype readiness gates (not promotion gates):

- at least 100 scored opportunities and at least 60 executed trades;
- mean R/trade at least +0.15 on executed trades;
- removing the best trade remains non-negative;
- maximum drawdown no worse than always RUNNER on the same opportunities;
- no one month or session provides the entire total R;
- causal truncation, independent recomputation and material mutant checks pass.

Even if all pass, status is `SHADOW CANDIDATE`, not validated. Forward validation requires at least 60 new trading
days or 100 new opportunities collected after this work, without opening the historical exam.

## Work phases

1. Verify TR1 hashes and copy only immutable artifact hashes into TR2 provenance.
2. Implement an exam-inaccessible bar reader and causal H1/H4 feature builder.
3. Add hand-worked and real-data truncation tests.
4. Freeze the model/action definitions above in `HYPOTHESIS.md`.
5. Build the 280-row feature/outcome panel and independently verify it.
6. Run the one predeclared causal walk-forward plus sensitivities.
7. Plant future-feature, same-row-outcome, scaling and monthly-refit bugs.
8. Write the honest result, readiness decision and forward shadow specification.

