# Trade journal: TREND-RUNNER M1 path analysis

**Scope:** 1,231 scored entries, 2023-11-01T00:39:00+00:00 through 2026-04-17T12:46:00+00:00. The locked exam and post-shadow data were excluded. This is a descriptive M1 OHLC reconstruction, not tick-level evidence.

## What distinguished profitable from non-profitable opportunities?

| Counterfactual RUNNER group | Trades | Win rate | Mean result | Median MFE before exit | Median MAE before exit | Median 8h MFE | Median favorable movement after exit |
|---|---:|---:|---:|---:|---:|---:|---:|
| Profitable | 336 | 100.0% | +2.097R | 3.66R | -0.51R | 6.83R | 3.31R |
| Non-profitable | 895 | 0.0% | -0.809R | 0.36R | -1.11R | 4.07R | 4.75R |

Here “before exit” includes the M1 exit candle, so its high/low ordering is not known. MFE/MAE are price excursions relative to the initial risk, not realized R. “Favorable movement after exit” is the best later executable-side mark minus the modeled exit price, normalized by initial risk and floored at zero; it is not a tradable counterfactual return.

## Concrete path findings

- Of the 895 non-profitable counterfactual RUNNER outcomes, 632 (70.6%) were stopped before a confirmed +1R touch. Their median favorable excursion before exit was only 0.17R; median adverse excursion for all losses was -1.11R. Median holding time was 11 minutes.
- Profitable opportunities reached +1R before -1R on 99.7% of cases, versus 21.5% for non-profitable ones. Their median hold was 94.5 minutes and median pre-exit MFE was 3.66R.
- After a non-profitable modeled exit, 98.0% later moved at least 1R favorably from that exit price within the original 8-hour horizon; median favorable movement was 4.75R, with median time to that later best mark 219 minutes. This suggests a testable timing/stop/continuation hypothesis, **not** proof that widening stops would help.
- Entry-context medians for profitable vs non-profitable cases were similar: H1 ATR 8.26 vs 7.51; pullback ratio 0.444 vs 0.449; open space 1.77 vs 1.64 ATR. These simple medians do not show a clean standalone entry filter.

## Did the selector help on these same opportunities?

- TR3 selected 313 trades, total +41.36R, mean +0.132R, median pre-exit MFE 0.87R, median pre-exit MAE -1.04R.
- TR3 skipped 918 opportunities; if they had instead used the same RUNNER exit, their counterfactual result was -60.71R total and -0.066R per opportunity. This comparison is descriptive and does not change the frozen selector.

## Exit and path breakdowns

The same summary JSON also breaks trades down by exit reason, path class and year/action. The per-trade file records exact entry/exit timestamps, reason, holding time, time-to-1R/2R/3R, MFE/MAE, pullback from peak, entry ATR/pullback/open-space context, and movement remaining after exit. This makes individual cases traceable without claiming a causal label from OHLC alone.

## Interpretation boundary

Follow-up status: the fixed M5 reclaim/re-entry test was run and rejected; see `../2026-10-21-trend-runner-post-stop-recovery/RESULTS.md`. The next research lead is initial-entry timing/confirmation, isolated and frozen before fresh forward-shadow evaluation.

The journal can answer “what price path preceded or followed this simulated result?” It cannot by itself prove “why the market moved,” and M1 candles cannot resolve within-minute order. The strong after-stop movement is the next research lead: test delayed confirmation/re-entry or structural stop alternatives only in a separately frozen study, never by silently changing the current result. The setup/selector were chosen after later development data had been seen; use these findings to nominate hypotheses only, then freeze any candidate rule before a separate untouched forward test. No entry/exit rule, risk parameter or live path was changed.
