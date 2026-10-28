# TREND-RUNNER three-year monthly walk-forward (M1 approximation)

**Status: completed historical research replay; not independent validation and not a promotion result.** The exam and forward-shadow data were not used; no strategy or order path was changed.

## Scope actually tested

- Requested evaluation start: 2023-10-21 UTC. Warm-up entries begin 2023-09-01 to give the frozen monthly model prior completed outcomes.
- Evaluation ends before 2026-04-18 UTC because the historical exam `[2026-04-18, 2026-10-18)` remains locked. Entries whose full 8-hour outcome would cross that boundary are excluded. The post-exam/forward-shadow period beginning 2026-10-21 is also excluded.
- Consequently this is not three uninterrupted years of test outcomes: the locked six-month block is absent. The scored interval is 2023-11-01 through 2026-04-17.
- Setup: frozen TR1 0.25-H1-ATR impulse + M1 pullback/continuation and frozen SPLIT/RUNNER exit. Selector: frozen TR3 monthly RUNNER/SKIP ensemble, with 60/90/120-day windows, 60-row minimum per component, alpha 20, 0.05R confidence threshold and 0.5 disagreement penalty.
- Execution approximation: M1 bar open plus recorded spread for entry; bid OHLC for BUY and spread-adjusted ask OHLC for SELL; zero slippage. Same-candle stop/favorable ambiguity resolves against the trade. M1 cannot recover tick order or exact fill sequence.

## Walk-forward result

The causal scanner generated 1,310 complete opportunities including warm-up; 1,242 were inside the requested evaluation interval. The model scored 1,231 opportunities over 30 monthly refits (first scored 2023-11, last scored 2026-04); 11 early evaluation opportunities were unscored during model warm-up. It selected RUNNER 313 times (25.4%) and SKIP 918 times. No outcomes were censored.

On the 1,231 identical scored opportunities:

- Always RUNNER: **-19.35R total**, -0.016R/trade, 126.57R maximum drawdown.
- Frozen TR3 selection: **+41.36R total** across 313 selected RUNNER trades; +0.132R per selected trade and +0.034R per scored opportunity; 35.14R maximum drawdown.
- Trade-level IID 95% mean interval: selected RUNNER trades [-0.098R, +0.390R]; selector return per scored opportunity [-0.025R, +0.100R]. Both cross zero; temporal clustering is not captured by this IID bootstrap.
- Removing the best trade leaves +22.56R; removing the best three leaves **-3.00R**.

Selected RUNNER contribution was uneven by calendar year: 2023 -6.25R (14 trades), 2024 +19.47R (66), 2025 +0.17R (168), and 2026 +27.98R (65, partial through Apr 17). In particular, the near-zero 2025 result and reliance on the partial 2026 period warn against reading the pooled total as a stable edge.

## M1-method audit against frozen P1/P2 tick results

All 280 frozen P1/P2 entries matched by session anchor, with direction and impulse/pivot/decision timestamps exact. Entry price median absolute difference was 0.00, but median initial-risk difference was 0.12 in P1 and 0.04 in P2.

For the matched frozen entries, the M1 replay was systematically more profitable than the tick replay:

- P1 SPLIT mean: tick +0.265R/trade vs M1 +0.339R/trade; mean absolute per-trade difference 0.075R; profit-sign agreement 99.3%.
- P2 SPLIT mean: tick +0.088R/trade vs M1 +0.152R/trade; mean absolute per-trade difference 0.064R; profit-sign agreement 100%.

This directional uplift matters: despite the conservative same-bar stop rule, the bar approximation overstates average RUNNER returns by about 0.06–0.07R/trade on the available overlap. The three-year M1 results must therefore be treated as a **low-fidelity robustness diagnostic**, not as tick-equivalent performance; no bias correction was fitted after seeing this audit.

## Integrity checks and decision

- 1,231 scored entries were inside the allowed pre-exam interval; no exam or post-shadow rows were loaded.
- All 30 refit months had exactly the frozen 60/90/120-day components, each with at least 60 eligible rows; every training outcome completed before that month start. Test rows remained in their refit month.
- Four simulator unit tests passed, covering same-bar stop-first ambiguity, gap-through-stop, fixed 2R target, and partial-plus-stop accounting.
- The model's form was chosen after later development data had already been seen. This chronological replay is useful for robustness research but does not become a pristine independent validation merely by running backward through older prices.
- No integration, threshold change, or live/demo action is justified by these results. Keep TR1/TR3/TR4 frozen; the only confirmatory evidence would be a new, predeclared forward sample or a separate rule frozen before genuinely untouched data.

Reproduction: `.venv/Scripts/python.exe research/2026-10-21-trend-runner-3y-walkforward/walkforward.py`, then `audit_m1_vs_ticks.py` and `verify_walkforward.py`. Primary predictions and yearly/quarterly breakdowns are included in this folder.

## Trade-journal follow-up

A separate, descriptive M1 path journal now covers all 1,231 scored opportunities: see `JOURNAL.md`, `trade_journal.csv`, and `trade_journal_summary.json`. It records exit reason and time, holding time, MFE/MAE before exit, first-touch ordering for +/-1R, time to 1R/2R/3R, pullback from peak, entry context, and favorable excursion after exit through the original 8-hour horizon. The journal preserves the same exam/post-shadow boundary and does not change the frozen strategy.

Main observation: 70.6% of non-profitable counterfactual RUNNER trades were stopped before +1R (632/895), with median pre-exit MFE +0.17R and median holding time 11 minutes. However, 98.0% later showed at least +1R favorable movement from the modeled exit price within that remaining 8-hour horizon. This is a lead for a separately frozen delayed-confirmation/continuation study, not proof that stops should be widened. Profitable vs non-profitable entry medians for H1 ATR, pullback ratio, and open space were similar, so this pass did not identify a clean standalone entry filter.

Reproduce the journal with `.venv/Scripts/python.exe research/2026-10-21-trend-runner-3y-walkforward/build_trade_journal.py`.

A full historical weekly review now groups all 1,231 journal rows into 129 UTC Monday-Sunday weeks and adds per-trade review flags without changing the source journal or strategy: see `weekly_journal/WEEKLY_REVIEW.md`, `weekly_journal/weekly_summaries.csv`, and `weekly_journal/weekly_trade_journal.csv`. Reproduce with `.venv/Scripts/python.exe research/2026-10-21-trend-runner-3y-walkforward/build_weekly_journal.py`.

The follow-up fixed M5 reclaim/re-entry hypothesis was tested separately and rejected; see `research/2026-10-21-trend-runner-post-stop-recovery/RESULTS.md`. The next research direction is initial-entry confirmation, not wider stops or further tuning of the failed re-entry candidate.
