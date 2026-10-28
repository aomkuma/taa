# RETEST-CONTINUATION V1 — frozen forward-shadow research plan

## Objective and status

Study whether an original trend setup that stops before reaching +1R can be re-entered after the market first reclaims the original entry, then retests and resumes in the original direction. The candidate is isolated from TR1/TR3/TR4 and has no order capability.

**Status: rule frozen for prospective observation; historical diagnostic completed; not approved.** At plan creation, the existing forward-shadow status reported 0 opportunities and 0 outcomes. A later, explicitly requested, pre-exam OHLC diagnostic was run on the previously inspected recovery cohort. It is exploratory/in-sample only and does not fill the prospective evidence gap.

## Locked data boundary

- Only new causal opportunities with UTC entry time at or after `2026-10-21 00:00 UTC` may enter this study.
- Do not read or reuse the locked historical exam `[2026-04-18, 2026-10-18)` for any candidate measurement.
- The pre-cutoff recovery study may be replayed only as a clearly labeled, isolated, in-sample diagnostic; it is not prospective validation and must never be merged into the forward journal.
- Wait for the original opportunity's full 8-hour RUNNER outcome to settle before classifying it. Eligible source events are those whose frozen baseline RUNNER stops before first touching +1R.
- One candidate attempt maximum per eligible original opportunity. Record all rejected/expired trigger reasons too, so coverage cannot be hidden.
- Slippage is excluded per instruction. Use recorded spread and executable bid/ask sides. Do not create synthetic rows or write into the Champion shadow database.

## Frozen RETEST-CONTINUATION V1 entry rule

All bars are UTC and use only completed bars. BUY/SELL rules below are mirror images. `E0` is the original opportunity entry, `S0` its original stop, and `R0 = abs(E0-S0)`.

1. **Eligible source event:** the frozen baseline RUNNER stopped before its first +1R touch. Start observing strictly after that modeled stop timestamp.
2. **Reclaim:** wait for the first completed M5 close beyond E0 in the original direction (`close > E0` BUY; `close < E0` SELL). That candle is the reclaim candle. If no reclaim within 8 hours after the original stop, expire the event.
3. **Retest:** among the next six completed M5 bars after reclaim, take the first bar whose range touches E0 and whose close holds on the reclaimed side (`low <= E0` and `close >= E0` BUY; `high >= E0` and `close <= E0` SELL). If none, expire.
4. **Structural invalidation:** at the retest close, define the provisional stop from the retest bar's extreme: BUY `retest_low - B`; SELL `retest_high + B`, where `B = max(original entry spread, 0.10 × ATR(14) of completed M5 bars available at the retest close)`. If ATR is unavailable, cancel as `NO_ATR`. If any completed M5 bar after the retest and before confirmation breaches this already-known stop, cancel the event. If the confirmation candle itself spans the stop, cancel conservatively.
5. **Continuation:** within the next two completed M5 bars after retest, require a close strictly beyond the retest bar's far extreme (`close > retest_high` BUY; `close < retest_low` SELL). Use the first qualifying close. If absent, expire. Enter at the next M1 open, including recorded spread on the executable side. Cancel if that executable entry is already at or beyond the provisional stop.
6. **Initial risk:** set the candidate's initial stop to the provisional structural stop from step 4. Define candidate `1R = abs(entry - initial_stop)` using executable entry. Size is not modeled; report returns in this initial-risk unit. Do not impose an additional R-based target or a hindsight risk cap.
7. **Run management:** no fixed profit target. Trail only on a newly confirmed radius-1 M5 swing pivot formed after candidate entry. A BUY stop may rise to `pivot_low - max(candidate entry spread, 0.10 × ATR(14) at pivot confirmation)`; a SELL stop may fall to `pivot_high +` the same buffer. Stops can tighten only, never loosen. Apply a pivot only after its confirmation timestamp and beginning with the next M1 bar. Exit on the active stop or at the first executable quote at/after 8 hours from entry.
8. **Fill convention:** use executable side (bid for BUY liquidation, ask for SELL liquidation); stop-before-other-actions on a bar, gaps fill at the worse observed open, and no favorable intrabar ordering is inferred. Entry spread and exit side are included. Slippage remains excluded.

## Frozen interpretation and evaluation

- This is one frozen hypothesis. No threshold, ATR buffer, retest window, confirmation window, or exit tuning on this prospective cohort.
- The study is event-level; overlapping candidates are not an account-equity curve. Report overlapping exposure and distinct trading days separately. A portfolio/concurrency replay is required before any deployment discussion.
- At 50 completed attempts spanning at least 30 UTC trading days: publish a descriptive interim report only; do not promote or modify the rule.
- Formal exploratory review requires at least 100 completed attempts over 60 distinct trading days. Report net mean/total R, win rate, payoff, time in trade, MFE/MAE, stop/timeout counts, coverage/rejection reasons, year/month/session/side cuts, chronological halves, max drawdown with overlaps clearly labeled, and deterministic day-block bootstrap interval.
- A positive result is still not proof of future profitability. Before any promotion could be considered, require positive mean in both chronological halves and a 95% day-block-bootstrap interval above zero, then run a separately reviewed portfolio/concurrency and operational-parity check. No automatic integration follows.

## Work checklist

- [x] Keep this candidate in a new isolated research directory; do not edit any strategy or order path.
- [x] Audit prior failure before proposing a follow-up: baseline rule had no same-M1 stop/target collisions; 1.5R stop sensitivity improved but remained negative and is explicitly post-hoc.
- [x] Freeze the new entry, invalidation, stop, trailing, timeout, fill, cost, and data-boundary semantics before prospective measurement.
- [x] Check current shadow readiness; at plan creation it contained 0 opportunities and 0 outcomes.
- [x] Build an independent event simulator, append-only candidate journal, and settled-event wrapper in this directory, with no writes to the existing Champion journal.
- [x] Add tests for completed-bar entry timing, reclaim/retest/confirmation limits, structural invalidation, stop tightening, adverse gap fills, spread, timeout, duplicate idempotence, and cutoff rejection.
- [x] Connect a read-only source-outcome adapter that identifies settled RUNNER stop-before-+1R events from ordered ticks and feeds this journal; it never infers eligibility from final R alone.
- [x] Run the observer against the current forward source journal (read-only): 0 source opportunities; candidate journal remains at 0 events / 0 results.
- [x] On explicit user request, replay the frozen rule against the 632-event pre-exam cohort using M1 OHLC and recorded spread, in a separate output directory; exclude the locked exam and preserve the prospective journal unchanged.
- [x] Build a full weekly journal for all 632 source events (including no-entry weeks), completed attempts, funnel reasons, and chronological concentration.
- [x] Test one causal, past-only 52-week side/session filter with a five-attempt minimum; record every allow/block decision and keep blocked counterfactual outcomes out of later training. Result: 77 attempts / +26.28R versus baseline 108 / +28.25R; not adopted.
- [x] Produce a sequential report for every historical UTC week with weekly and cumulative results, funnel coverage, and the prior-only action state.
- [x] Replay a causal M15/M30/H1 ATR-state policy trade by trade on the isolated pre-exam historical cohort; enforce completed-bar availability and only learn from earlier settled, allowed trades; preserve all blocked outcomes as counterfactual journal rows.
- [x] Publish the ATR experiment week-by-week across 129 active UTC weeks, with all 632 source events, ATR state, prior training count/mean, allow/block decision, each eventual outcome, and weekly/cumulative R.
- [x] Unit-test ATR-state isolation, unsettled outcomes, and exclusion of blocked counterfactuals; verify full cohort baseline matches frozen diagnostic.
- [x] Compare the learned trailing-mean filter with the simpler fixed high-ATR lock (>80th composite percentile); log its allowed and blocked R independently without changing strategy code.
- [x] Produce the historical weekly report in the user's preferred format across all weeks; state USD/account equity as unavailable rather than infer it from overlapping event-level R.
- [x] Freeze the fixed ATR rule at the actual re-entry decision time (ATR(14) M15/M30/H1 percentile composite; block strictly above 0.80, allow at/below) and run it on earlier XAUUSD history from 2021-09 through 2023-10 without opening the reserved 2026 exam.
- [x] Report the holdout week by week, including censored candidates, blocked counterfactuals, chronological halves, and deterministic day-block confidence intervals; do not tune after seeing the holdout.
- [ ] Begin prospective observation only from new data at/after the UTC boundary; keep the first 50 attempts untouched for interim reporting.
- [ ] Do not tune V1 or the failed weekly filter on this same sample. A distinct historical hypothesis may be explored only as a new isolated round and must remain labeled in-sample.
- [ ] If reviewed as promising, perform a distinct portfolio/concurrency audit before discussing promotion.

## Current decision

Do not add RETEST-CONTINUATION V1, the weekly side/session filter, or either ATR filter to any strategy. The +30.96R fixed screen in the 632-event development replay measured ATR at source-stop time, not the candidate's later entry, so it is not evidence for an entry lock. The correct frozen entry-time gate was evaluated on earlier XAUUSD history: 91/94 attempts, +2.325R vs baseline +2.193R; three blocked trades totaled -0.132R. It fails the formal gate: fewer than 100 attempts, negative second-half mean, fixed-gate mean CI crosses zero, and paired improvement CI crosses zero. The earlier market period was also used by other XAUUSD research, limiting independence. Keep this holdout consumed and do not retune against it; the 2026 exam remains locked. Any new candidate requires a new untouched holdout (or explicitly released reserved period) before a pass can be claimed. The prospective observer remains separate and currently has no eligible settled events.
