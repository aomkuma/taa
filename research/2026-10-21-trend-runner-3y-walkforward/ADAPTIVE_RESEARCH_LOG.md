# Adaptive strategy research log

Status: research only; baseline strategy and isolated RETEST-CONTINUATION observer are unchanged.

Source: `trade_journal.csv`, 1,231 historical M1 OHLC opportunities from 2023-11-01 through 2026-04-17. The selector's RUNNER decisions are frozen walk-forward outputs. R excludes slippage/costs per the current research scope. Weekly boundaries are UTC Monday-Sunday.

## Experiment 1 — Gate sessions using their trailing performance

Hypothesis: stop trading a session when its recent RUNNER results show that the current market is unfavorable, and re-enable it once recent results recover.

Tested rule: at each UTC week, inspect only the preceding 12 calendar weeks. Enable a session if it had at least 5 selected RUNNER trades and their summed RUNNER R was positive; otherwise skip that session for the current week. Existing RUNNER picks and exits are otherwise unchanged. The first 12 weeks are warm-up and excluded from both sides of the fair comparison.

| Measure | Frozen baseline, common period | Adaptive session gate |
|---|---:|---:|
| Selected trades | 297 | 183 |
| Total | +49.61R | +44.17R |
| Mean per trade | +0.167R | +0.241R |
| Win rate | 31.0% | 36.6% |

The adaptive gate improves mean R and win rate but gives up 5.44R total while taking 114 fewer trades. Do not call it a total-return improvement. Comparing +44.17R against the full-period baseline +41.36R would be unfair because it counts 16 early baseline trades (-8.25R) during the adaptive gate's warm-up.

| Calendar year | Baseline trades | Baseline R | Adaptive trades | Adaptive R |
|---|---:|---:|---:|---:|
| 2024 | 64 | +21.47 | 30 | +21.73 |
| 2025 | 168 | +0.17 | 96 | +11.47 |
| 2026 | 65 | +27.98 | 57 | +10.97 |

Interpretation: the gate helped in 2025, was roughly flat in 2024, and removed too much profitable exposure in 2026. It is not ready to promote. The previous 12-week/5-trade idea is now logged as a weak risk-control hypothesis, not an accepted selector.

## Regime clue — H1 ATR percentile at entry

The selected trades split into three equal-sized, sample-quantile ATR-percentile buckets descriptively as follows (bucket cut points are sample-derived, so this is not a deployable rule):

| H1 ATR-percentile cohort | Trades | RUNNER R | Mean R |
|---|---:|---:|---:|
| Low third | 107 | +25.76 | +0.241 |
| Middle third | 104 | +39.03 | +0.375 |
| High third | 102 | -23.44 | -0.230 |

A simple retrospective filter retaining entries with `h1_atr_percentile_120 < 0.80` yielded 259 trades and +62.56R vs 313 and +41.36R baseline. By year it was -8.41R vs -6.25R (2023), +15.65R vs +19.47R (2024), +20.76R vs +0.17R (2025), and +34.57R vs +27.98R (2026). This was discovered after reviewing the full sample. Although the feature is causal, the filter's design was influenced by this same sample; treat it strictly as a lead, not evidence that a live veto will work.

## Experiment 2 — Let trailing high-ATR results control the high-ATR gate

Feature audit: `r2/features.py` selects the latest completed H1 bar available by entry, compares that ATR with up to the prior 120 completed H1 ATR values, and does not use outcomes. The percentile is therefore causal at entry (subject to the existing M1 bar/entry approximation).

Tested rule: at each UTC week, among the preceding 52 weeks' selected RUNNER trades with `h1_atr_percentile_120 >= 0.80`, skip high-ATR RUNNER selections this week only if at least 10 such prior trades exist and their cumulative R is negative. Before enough history is available, leave the baseline unchanged. This is a chronological replay; the current week's trades never affect that week's decision.

| Measure | Frozen baseline | Adaptive high-ATR gate |
|---|---:|---:|
| Selected trades | 313 | 277 |
| Total | +41.36R | +64.22R |
| Mean per trade | +0.132R | +0.232R |
| Win rate | 30.4% | 32.9% |
| Total excluding each variant's top 5 | -21.48R | +1.38R |

| Calendar year | Baseline trades | Baseline R | Adaptive trades | Adaptive R |
|---|---:|---:|---:|---:|
| 2023 | 14 | -6.25 | 14 | -6.25 |
| 2024 | 66 | +19.47 | 66 | +19.47 |
| 2025 | 168 | +0.17 | 144 | +16.44 |
| 2026 through 2026-04-17 | 65 | +27.98 | 53 | +34.57 |

This is a materially better research lead than the trailing-session gate: it kept all baseline exposure until the trailing high-volatility cohort itself showed losses, improved returns in both 2025 and 2026, and the filtered result remains slightly positive after removing the top five wins. However, the threshold/lookback/minimum were explored on this full historical sample, so these are not independent confirmation and the gate is not accepted for production. Do not unlock or use the separately reserved 2026-04-18 to 2026-10-18 exam to retroactively tune it.

The gate removed 36 high-ATR trades worth -22.86R in aggregate; 4 of those were winners, so the rule did miss some legitimate continuations. The top five baseline winners were all retained. The result is sensitive to the ATR threshold: the total stayed positive across the 0.70-0.90 grid, but after removing each variant's top five, only 0.80 remained positive (+1.38R); 0.85 was -2.56R, 0.75 -13.18R, 0.70 -10.43R, and 0.90 -9.13R. Lookbacks of 26/52/104 weeks gave +61.59/+64.22/+62.54R, but excluding top five gave -1.25/+1.38/-0.30R. This near-zero concentration-adjusted margin means the apparent improvement is fragile despite the better gross total.

Gate-state audit: with the 52-week rule, the high-ATR gate switched on once (week of 2025-02-24) and stayed on through the last scored week (2026-04-13)—60 consecutive weeks. It was active for 60 of 129 weeks but actually skipped trades in only 21 weeks. This is not a full setup shutdown: during those active weeks it allowed 150 normal-ATR entries worth +47.38R and blocked 36 high-ATR entries worth -22.86R. A 26-week lookback was similarly sticky (60 active weeks); 13 weeks / 5 minimum trades stayed on 56 weeks. The 8-week / 5-trade version switched more often (9 transitions, 35 active weeks) but returned +52.65R and remained -10.19R after top-five removal. The 13-week / 5-trade version returned +57.26R and -5.58R ex-top-five; with 10 minimum trades it dropped to +41.51R. The high-return 52-week variant is therefore more like a high-volatility veto while normal-volatility trades continue, not rapid adaptation within the high-volatility cohort.

### Trade-journal review of the four missed winners

| Trade | Context | Result | ATR percentile | Open space (ATR) | Pullback ratio | MFE before modeled exit |
|---|---|---:|---:|---:|---:|---:|
| M1WF-00851 | London SELL, 2025-06-24 | +0.45R | 0.942 | 0.06 | 0.638 | 3.04R |
| M1WF-01141 | London SELL, 2025-12-29 | +1.89R | 0.958 | 1.02 | 0.592 | 10.47R |
| M1WF-01144 | London SELL, 2025-12-30 | +0.40R | 0.800 | 3.05 | 0.451 | 1.53R |
| M1WF-01267 | Asia SELL, 2026-03-24 | +2.11R | 0.892 | 3.75 | 0.273 | 5.36R |

These are real continuations worth understanding, not evidence the gate is wrong by itself. An exception allowing all high-ATR entries with open space >=1 ATR recovered three winners but also restored many losses: total fell from +64.22R to +48.39R. An >=2 ATR exception yielded +52.11R. Open space alone does not separate these winners well enough; do not add that exception.

### M15 chart review and pre-entry context

The four winners were paired with a blocked loss of the same side and session, choosing the closest H1 ATR percentile. These are illustrative pairs only; they do not match the market date or establish significance. All four charts are generated from complete M15 candles resampled from the frozen M1 source, normalized to initial risk, and clipped at -3R/+8R:

- [M1WF-00851 vs M1WF-00673](adaptive_research/missed_winner_charts/missed_winner_01_m1wf-00851.svg)
- [M1WF-01141 vs M1WF-01070](adaptive_research/missed_winner_charts/missed_winner_02_m1wf-01141.svg)
- [M1WF-01144 vs M1WF-01072](adaptive_research/missed_winner_charts/missed_winner_03_m1wf-01144.svg)
- [M1WF-01267 vs M1WF-01029](adaptive_research/missed_winner_charts/missed_winner_04_m1wf-01267.svg)

The chart paths are not one pattern: M1WF-01141 shows fast continuation; M1WF-00851 and M1WF-01144 need later follow-through after choppy/weak early movement; M1WF-01267 runs early then gives back a large part of its peak while still closing the modeled trade positive. The same-side/session blocked losses mostly fail quickly, but M1WF-00673 reaches +0.83R favorable movement before its ambiguous stop. A single short post-entry confirmation would likely miss at least some delayed winners.

Pre-entry medians for the 4 blocked winners vs 32 blocked losses also do not give a clean separator: 15m directional return / H1 ATR is +0.322 vs +0.342; 60m return is +0.863 vs +0.663; entry location in prior 60m range is +0.956 vs +0.968; directional body fraction is 0.542 vs 0.550; prior range / H1 ATR is 1.072 vs 0.965. With only four winners, these are descriptive only. Data is in `adaptive_research/blocked_winner_context.csv`; chart pair selection is in `adaptive_research/blocked_winner_chart_index.csv`.

I also tested a possible early-confirmation exception. All four blocked winners touched +1R within 13 minutes, but so did many blocked losers: among blocked trades that touched +1R by 15 minutes, 4 were winners and 25 were losses, totaling -17.37R. Thus “let high-ATR trades through if they hit +1R quickly” would not rescue the gate; it admits more losing paths than winners. This is not a viable exception from these data.

Decision: do not add an open-space exception or an early price-confirmation requirement from these cases. Next, test a causal ATR-gate recovery condition so the high-volatility block can reopen after a recent high-ATR cohort improves, then review sensitivity and missed winners again.

Recovery probe: allowing high-ATR trades again whenever the trailing 8 weeks turned positive (at least 1 or 3 observations) increased activation/deactivation, but returned +60.40R / 281 trades or +61.40R / 280 trades, respectively; after top-five removal these were -2.44R and -1.44R. A 13-week window with at least 5 trades never activated recovery and matched the original +64.22R / 277 trades. So far, no tested recovery rule improves on the original gate's fragile concentration-adjusted result. Keep the original candidate frozen for research only; do not add a recovery override yet.

Reproduction: `adaptive_gate_audit.py`; it exports the chronological weekly decisions, per-trade gate result, and summary under `adaptive_research/`.

## Next experiment

1. Sensitivity audit and missed-winner chart review are now complete; recovery probes (8- and 13-week positive-R windows) did not improve concentration-adjusted results.
2. Keep the ATR gate as a research-only candidate. Do not change the live selector, execution code, or separate RETEST-CONTINUATION observer.
3. The source M1 history begins 2023-09-01. The remaining 2026-04-18 to 2026-10-18 exam is explicitly locked, and the current source only reaches 2026-10-21; therefore no untouched historical period remains for an honest independent test of this new rule. The next valid evidence is a separately collected future/demo shadow journal or another isolated dataset, not more tuning on the same three years.

This log records analysis, not a standing promise to deliver future messages while the session is inactive. When research is resumed, continue from “Next experiment” rather than reopening the same exploratory grid.
