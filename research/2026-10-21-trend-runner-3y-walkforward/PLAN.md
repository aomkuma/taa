# TREND-RUNNER three-year M1 walk-forward research plan

## Objective

Run a chronological, monthly walk-forward study of the frozen TR1 entry + SPLIT/RUNNER setup and frozen TR3 RUNNER/SKIP selector over the locally available M1 history. This is research only; it does not alter TR1/TR3/TR4 or any order/execution path.

## Requested span and hard boundaries

- Available M1 begins 2023-09-01 UTC. The requested approximate three-year lookback starts 2023-10-21 UTC.
- The historical exam remains excluded: do not read price rows or ticks with timestamps in `[2026-04-18 00:00 UTC, 2026-10-18 00:00 UTC)`.
- To avoid using locked data to settle a trade entered before the boundary, do not score entries whose full eight-hour outcome horizon would overlap the locked exam.
- Do not consume the post-exam/forward-shadow period on or after 2026-10-21 UTC in this historical replay.
- Therefore the usable test path is discontinuous and shorter than three full observation years: 2023-10-21 through the pre-exam cutoff, with the locked interval visibly excluded. Report this exactly.

## Frozen strategy definitions

- TR1 entry: XAUUSD; Asia/London/NY anchors; 0.25 completed-H1 ATR impulse; causal M1 radius-1 first pullback/continuation; 0.20–0.65 pullback ratio; stop buffer and accepted risk ratio from `FROZEN_ROUND_1.md`.
- Candidate outcomes: frozen FAST and SPLIT/RUNNER definitions, with the SPLIT structure trail and eight-hour maximum.
- TR3 action: frozen RUNNER/SKIP monthly ensemble from `research/2026-10-20-trend-runner-r3/PLAN.md`; no threshold/model tuning or diagnostic substitutions.
- TR3 training at each UTC month start uses only entries in the prior 60/90/120 calendar-day windows with complete outcomes available before month start, at least 60 rows in each window, and the frozen features/preprocessing/ensemble parameters.

## M1-only execution model and limitations

The available M1 starts in 2023, but tick history starts only 2025-10-01. The historical replay must therefore be labelled **M1 OHLC approximation**, not tick-accurate backtest. Entry uses the first M1 quote proxy after the causal signal, spread points from the bar, and zero slippage. Exits are simulated from complete M1 OHLC with a predeclared conservative intrabar rule: if a stop and a favorable milestone/target are both touched in the same bar, resolve the stop first; M5/M15 trail updates become active only at their confirmed clock-close time. Gaps through a stop fill at the worse observed bar open. No synthetic tick path is permitted.

Before the multi-year measurement, replay the available P1/P2 overlap using the same M1-only rules and compare entry fields/outcomes to frozen tick results solely as a method audit. Do not tune the bar model to improve the P1/P2 result. Report the discrepancy; if the M1 approximation materially changes trade labels/expectancy, present the three-year study as a low-fidelity robustness diagnostic and do not treat it as equivalent to the frozen tick result.

## Walk-forward outputs

- Entry/outcome coverage by month and year; incomplete/censored rows and reasons.
- Always-RUNNER baseline versus frozen TR3 RUNNER/SKIP on identical scored opportunities.
- Number of eligible/scored opportunities, selected trades, total and mean R, win rate, max drawdown, losing streak, best-one/best-three removal, and deterministic block-bootstrap interval.
- Per-calendar-year and chronological segment contribution, trade count, action rate, session, direction, and training-row counts.
- Full chronological predictions/actions with refit month and model/component scores; no post-hoc filter.
- Compare fixed R1 SPLIT baseline with selected TR3 only on the same scored rows.

## Decision discipline

- This replay is historical and exploratory even when each monthly prediction is causal. The model form was designed after inspecting later development data; do not call the result independent validation.
- Do not inspect or use the locked exam. Keep the existing live forward-shadow journal and its post-2026-10-21 boundary untouched.
- No integration, order changes, or promotion follows automatically from a positive aggregate result.
