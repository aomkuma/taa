# Past-only weekly side/session filter — historical walk-forward

**Decision: exploratory only; do not add to the strategy.** This is a causal replay on already inspected pre-exam development data, not independent validation.

## Frozen rule for this replay

At each source stop event, inspect only previously ALLOWED and completed candidate attempts from the same side/session cell, within the preceding 52 weeks and with their exit time before the current event. If fewer than five prior attempts exist, allow the original candidate during warm-up. Otherwise allow the cell only when its trailing mean R is positive. Blocked candidate outcomes are not fed back into the model. No same-week/future outcome is used.

## Paired result

| Policy | Completed attempts | Total R | Mean R | Median R | Win rate |
|---|---:|---:|---:|---:|---:|
| Frozen candidate | 108 | +28.25 | +0.262 | -0.377 | 38.9% |
| Past-only filter | 77 | +26.28 | +0.341 | -0.342 | 41.6% |
| Blocked counterfactual | 31 | +1.96 | +0.063 | -0.543 | 32.3% |

The filter allowed 434/632 source events, selected 77/108 completed candidate attempts, and blocked 31 completed counterfactual attempts (+1.96R). Warm-up decisions: 350.

## Chronological halves (all source events ordered by event time)

| Half | Baseline attempts | Baseline R | Filter attempts | Filter R | Blocked completed |
|---|---:|---:|---:|---:|---:|
| first half | 52 | +1.24 | 32 | -4.44 | 20 (+5.68R) |
| second half | 56 | +27.00 | 45 | +30.72 | 11 (-3.72R) |

## Interpretation and next step

A filter can raise mean R while lowering total R simply by taking fewer attempts; both totals and per-attempt returns matter. Because side/session groupings were suggested by this same historical journal, the replay is still vulnerable to research-selection bias even though its trade-by-trade rule is past-only. Do not tune its lookback, minimum history, or threshold on this dataset. Keep the original V1 and this filter outside the strategy; the result only decides whether the prior-only adaptive idea merits a separately frozen study.

Limits: M1 OHLC diagnostic labels, recorded spread included, slippage excluded, event attempts can overlap, and locked exam [2026-04-18, 2026-10-18) excluded. `weekly_regime_filter_decisions.csv` records every source event and its causal decision; `weekly_regime_filter_by_week.csv` contains weekly paired totals.
