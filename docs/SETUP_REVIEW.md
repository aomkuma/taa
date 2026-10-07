# Setup Quality Review — why the setups lose (2026-10-07)

Record of the owner's question and the analysis. The conversation was in Thai; this is the English summary
(project docs rule). Every number is a **hypothetical, bar-based replay** of past data, net of the replay's
costs. Nothing here predicts results or claims profitability.

## 1. The question

After the first DEMO trades lost, the owner's view (Thai): "ขาดทุนเพราะ setup ไม่ดี … แทนที่จะปิด ควรหาว่าทำไม
มันถึงติดลบ … setup ไม่ผิด แต่มันคือ timing และการตีความหรือไม่ … ให้ AI มาช่วยวิเคราะห์อีกขั้นได้ไหมว่า setup นี้
เหมาะสมที่จะเข้าหรือยัง … ถ้าไปสรุปว่า setup นี้ใช้ไม่ได้ มันจะไม่เกิดการพัฒนา"

*Translation:* the losses mean the setups are weak. Instead of switching them off, find out why they lose. Maybe
the setup is not wrong, and the problem is timing and interpretation. Can the AI judge whether a setup is ready
to enter? Concluding "this setup does not work" leads nowhere.

## 2. Data and method

- `python -m app.cli advisory replay` over 2025-10-15 .. 2026-10-05 on EURUSD, GBPUSD, USDJPY and XAUUSD (M15
  entries, H1 bias), one family of setups per run, with only the detectors the family needs. M5 history
  (downloaded for this review) resolves each signal's stop or target.
- Every signal is a shadow trade, measured in R net of costs: PLAN (fixed stop and target) and MANAGED
  (break-even and trailing as the bot does).
- 90 % confidence intervals by bootstrap. Conditions are chosen on Oct-Mar and measured on Apr-Oct
  (walk-forward) before anything is called a finding.
- Scripts used (scratch, not part of the product): re-simulation of each signal on M5 bars with other entries
  (sanity check: correlation 0.99 with the replay), context features at the signal bar, fade and random
  baselines.

## 3. Results, light family

| Setup | Signals / year | PLAN mean R [90 % CI] | MANAGED mean R [90 % CI] |
|---|---|---|---|
| setup_breakout | 3,750 | −0.154 [−0.19, −0.12] | −0.165 [−0.20, −0.13] |
| setup_fib_pullback | 378 | −0.163 [−0.27, −0.05] | −0.089 [−0.19, +0.02] |
| setup_elliott_wave | 552 | −0.075 [−0.17, +0.02] | −0.082 [−0.17, +0.00] |
| example_trend_pullback | 55 | +0.03 [−0.30, +0.35] | +0.10 [−0.19, +0.39] |
| setup_smc_reversal | 1 | — | — |

Nearer targets (1 R, 1.5 R) do not change the picture. setup_breakout is 74 % of all signals, so it decides the
bot's results.

## 4. Why setup_breakout loses

**Timing (rejected as the main cause).** The same signals entered with a limit that waits for a pullback of
0.25-1.0 ATR (4-16 bars), same stop and target:

| Entry | Filled | Win rate | Mean R |
|---|---|---|---|
| market (as now) | 100 % | 30 % | −0.132 |
| retest 0.5 ATR, 8 bars | 80 % | 20 % | −0.151 |
| retest 1.0 ATR, 8 bars | 60 % | 9 % | −0.252 |

The deeper the pullback, the lower the win rate. A breakout that comes back to the entry has usually failed;
one that works does not come back. Waiting selects the failures.

**Direction (the signal points the wrong way).** Same entry time, same distances and costs:

| Direction | Mean R [90 % CI] |
|---|---|
| breakout as traded | −0.132 [−0.17, −0.10] |
| random direction | −0.078 [−0.12, −0.04] |
| fade (the other way) | −0.011 [−0.05, +0.03] |

- The random baseline shows the **cost drag: about 0.07-0.08 R per trade**. M15 stops are small, so the spread
  is a large share of the risk.
- The breakout direction is **worse than random**: on these symbols and this timeframe, these breaks tend to
  fail and price returns into the range. Fading is close to zero after costs, not an edge either.

**Context (no robust filter).** Split by hour, stop size, bar size, close location, stretch from EMA20, ATR
percentile, prior compression, prior range and higher-timeframe alignment: no bucket is positive for the
breakout. The best single conditions chosen on Oct-Mar (+0.10 to +0.22 R) all fall to about zero on Apr-Oct
(−0.10 to +0.02 R). Simple context rules fitted on history do not survive new data.

## 5. What this means

1. "The setup is not wrong, the timing is" does not hold for the retest kind of timing; it holds in a wider
   sense: the M15 break is mostly noise plus a slight tendency to fail, and the costs on M15 stops are large.
2. The interpretation question is the productive one: **where is a break meaningful?** Two hypotheses the data
   supports testing next:
   - **a higher timeframe** (H1 entries, H4 bias): larger stops cut the cost share and the noise;
   - **a failed-break setup** defined on purpose (a close back inside the range after a break, PLAN_LEARNING
     §L20.2), instead of fading every break.
3. An AI judge ("is this setup ready to enter?") can only help if it sees information these features do not
   carry (multi-timeframe structure, the significance of the level, news). It must be measured forward in
   shadow like everything else (docs/AI_ANALYST_DISCUSSION.md stages A-B); on history it cannot be judged
   fairly.
4. Switching setups off is a separate risk decision for the bot; the shadow measurement continues either way.

## 6. More hypotheses (owner, 2026-10-07): "it breaks out, comes back to the entry, then really runs"

Same 3,750 breakout signals, re-simulated on M5 (all / Oct-Mar / Apr-Oct agree unless noted):

| Hypothesis | Mean R |
|---|---|
| as traded | −0.13 |
| target 0.5 R / 1 R (target too far?) | −0.10 / −0.12 |
| break-even after +0.5 R | −0.12 |
| trail 0.5 R once +0.5 R | −0.08 |
| time stop after 4 bars without +0.5 R | −0.10 |
| stop ×2, same R multiple (stop inside the noise?) | −0.05 |
| cheapest quarter of spread/stop vs dearest | −0.08 vs −0.17 |
| first signal of the day vs later ones | −0.08 vs −0.15 (Oct-Mar: both −0.15) |
| re-enter at the entry after a stop | −0.14 |
| **retest 0.5-1 R with a stop 2.5-3 R from the signal entry** | **0.00 to +0.02** (both halves) |

- 61 % of the losers were +0.25 R, 43 % +0.5 R and 21 % +1 R before their stop; **55 % of the stopped trades
  reached the original target later** (within 72 h). The owner's reading is right: the direction is often right
  and the stop sits inside the noise; a retest entry only works together with a stop beyond the noise.
- The live DEMO plans of 2026-10-07 show the same: a 0.5 ATR scale-in spacing on a 1.5 ATR stop puts every
  limit part into the noise band under the stop (GBPUSD parts with 7.2, 4.1 and 1.1 pip stops; USDJPY: three
  parts filled within 51 minutes, then all stopped).

## 7. Development approach and the roles of AI (owner's question, 2026-10-07)

**Approach:** one hypothesis at a time per layer of the algorithm, each measured in R net of costs, as a shadow
variant on the same signals (A/B), on a year of history with walk-forward (choose on one half, judge on the
other), then forward in shadow, then DEMO, then LIVE (PLAN_LEARNING §L13).

| Layer | Question | Next candidates |
|---|---|---|
| Signal | where to look | the setups and their detectors; a failed-break setup (§L20.2) |
| Interpretation | is this break meaningful here | timeframe (H1/H4 replay running), playbook by regime (§L20.1), level significance |
| Entry timing | when | retest entry modes with waiting entries (§L19.3, hook H2) |
| Stop | where the idea is wrong | beyond the noise (winners' MAE quantile, structure), lots cut to keep the risk % (§L19) |
| Exit | how to keep winners | trailing, partials, time stop as exit policies (hook H3) |
| Portfolio and costs | how much at once, at what cost | heat and plan counting (TAA-1207), spread-to-stop limits |

**AI roles, each measured before it is trusted:**

1. **Research agent** (this review): turns the owner's hypotheses into tests on the data, runs them and writes the
   synthesis; can run as a regular research report. It proposes; the owner decides.
2. **Signal-quality model** (statistical, §L6 meta-labeling): learns from thousands of shadow outcomes whether a
   setup is ready to enter; judged walk-forward. The simple context rules here did not survive walk-forward,
   so it needs the richer evidence features.
3. **LLM analyst** (docs/AI_ANALYST_DISCUSSION.md): a multi-timeframe thesis per symbol, measured forward in
   shadow against the bot; its verdict can later become one input of the signal-quality model.
4. **Explanation and review** (TAA-1303/1305, built): narratives in Thai and English, and the veto review once
   its calibration is shown.

The AI never sizes a trade, widens a stop or bypasses a risk check.

## 8. The H1 leads and the stop-plus-retest lever (2026-10-07, second session)

Same method, `hypotheses.py STRATEGY DB_GLOB` (now aware of the entry timeframe: "N bars" are entry bars,
so a 16-bar wait is 4 h on M15 and 16 h on H1). H1 = `fam_lightH1_*` (H1 entries, H4 bias). Train = Oct-Mar,
test = Apr-Oct. Outputs in `data/research/hyp_*.txt`.

**Absolute results, setup_breakout** (mean R [90 % CI]):

| Variant | M15 all | H1 all | H1 train | H1 test |
|---|---|---|---|---|
| as traded | −0.13 | −0.061 [−0.13, +0.01] | +0.053 | −0.161 [−0.25, −0.07] |
| stop ×2, same R multiple | −0.05 | +0.032 [−0.03, +0.09] | +0.122 | −0.047 [−0.12, +0.03] |
| retest 0.5 R, stop 2 R, 4 bars | −0.04 | +0.074 [−0.00, +0.15] | +0.144 | +0.014 [−0.08, +0.11] |
| retest 1 R, stop 2 R, 16 bars | +0.01 | +0.134 [+0.03, +0.24] | +0.212 | +0.069 [−0.06, +0.21] |
| retest 1 R, stop 3 R, 16 bars | +0.02 | +0.075 [+0.00, +0.14] | +0.156 | +0.007 [−0.08, +0.09] |

- On H1 almost **every** rule is positive on Oct-Mar and negative on Apr-Oct (as traded +0.05 → −0.16; BUY
  +0.15 → −0.28). The half-year (the market's regime) moves the result more than any rule does.
- Honest walk-forward: the rule with the best train result (retest 1 R, stop 2 R, 16 bars, out of ~45 tried)
  gives **+0.069 R [−0.06, +0.21]** on the test half. Not an edge: the interval contains zero and the choice
  was made among many rules.

**Paired effect** (variant minus as traded on the same signal; an unfilled retest counts 0 R):

| Strategy, TF | retest 1 R, stop 3 R, 16 bars: all / train / test | stop ×2, same R multiple: all / train / test |
|---|---|---|
| setup_breakout M15 (3,750) | **+0.139** [+0.09, +0.18] / +0.15 / +0.13 | +0.082 / +0.14 / +0.03 |
| setup_breakout H1 (1,141) | **+0.103** [+0.02, +0.18] / +0.03 / +0.17 | +0.093 / +0.07 / +0.11 |
| setup_fib_pullback M15 (378) | +0.141 [+0.01, +0.28] / −0.02 / +0.27 | +0.035 / −0.05 / +0.11 |
| setup_fib_pullback H1 (114) | −0.154 [−0.37, +0.06] / +0.10 / −0.38 | −0.035 / −0.00 / −0.07 |
| setup_elliott_wave M15 (552) | +0.061 [−0.06, +0.17] / −0.02 / +0.14 | +0.051 / −0.01 / +0.11 |
| setup_elliott_wave H1 (171) | −0.027 [−0.19, +0.14] / −0.06 / +0.02 | −0.096 / −0.15 / −0.02 |

1. **For the breakout the lever is robust:** waiting for a retest and putting the stop beyond the noise
   improves the same signals by about +0.10 to +0.14 R, in both halves, on M15 and H1, and on every symbol on
   M15 (EURUSD +0.10, GBPUSD +0.11, USDJPY +0.21, XAUUSD +0.14). Part of it is simply not trading a third of
   the signals (unfilled); with a losing baseline that also counts.
2. **The lever does not create an edge by itself:** the absolute result is about zero on M15 (+0.02 R) and
   depends on the half-year on H1. It removes most of the loss; it does not add a gain.
3. **It is not a general rule:** for setups that already enter on a pullback (fib, elliott) a second wait on
   H1 picks the failures (fib H1 test −0.38 R) and the M15 gains appear only in one half. An entry mode must be
   chosen per setup and measured per setup (TAA-L702 reports per strategy; L706 selects per strategy).
4. setup_fib_pullback H1 as traded: +0.118 [−0.08, +0.33] (train −0.13, test +0.34) on 114 signals: unstable,
   too few.

**Decision for the bot (recommendation):** no product change from history alone. Next: TAA-L702 adds
`PULLBACK_WIDE` / `WIDE_STOP` as shadow variants so the lever is measured forward on live signals, per
strategy and timeframe; the H1-vs-M15 question for the bot (TAA-1602) waits for that forward evidence and the
heavy family.

**Scale-in parts (TAA-1209), M15 breakout, `app.cli research hypotheses` (all / Oct-Mar / Apr-Oct):** a limit
0.5 R deep with the plan's stop, i.e. the shape of today's scale-in parts, gives −0.234 R (−0.226 / −0.243) on
the filled trades, against −0.149 R at market; with the stop 2 R from the signal's entry −0.095 R (4 bars) /
−0.065 R (16 bars). The deeper part is the worse part unless its stop moves beyond the noise, so spacing rules
alone do not fix scale-in; a single entry stays the recommendation until a wide-stop variant wins forward.

**Forward measurement (2026-10-07 14:00 UTC):** `PULLBACK`, `WIDE_STOP` and `PULLBACK_WIDE` run as shadow
variants on the DEMO engine (TAA-L702); the production code reproduces the harness on H1 breakout (paired
+0.060 / +0.077 / +0.115 R against +0.057 / +0.075 / +0.116 R).

## 9. Heavy family, first pair (EURUSD, GBPUSD; 2026-10-08)

`app.cli research hypotheses --strategy NAME --from "data/research/fam_heavy_*.db"` (M15 entries, H1 bias,
2025-10-15 .. 2026-10-05; outputs `data/research/l707_heavy_*_M15_pair1.txt`). USDJPY and XAUUSD were still
replaying; these numbers cover half the symbols. "Random" is now the exact expectation of a coin per signal (the
mean of both directions), not one draw: a single draw added about ±0.1 R of noise on a few hundred signals.

| Setup | n | As traded, all [90 % CI] | Oct-Mar / Apr-Oct | Other direction | Random | Stopped trades that reached the target later |
|---|---|---|---|---|---|---|
| setup_pattern_breakout | 901 | −0.222 [−0.30, −0.14] | −0.16 / −0.29 | −0.172 | −0.197 | 44 % |
| setup_harmonic_prz | 272 | +0.050 [−0.09, +0.19] | +0.15 / −0.06 | −0.171 | −0.060 | 76 % |
| setup_candle_reversal | 331 | −0.098 [−0.21, +0.01] | −0.10 / −0.10 | −0.196 | −0.147 | 68 % |
| setup_neckline_break | 89 | +0.003 [−0.25, +0.27] | +0.05 / −0.04 | −0.034 | −0.015 | 50 % |

- **setup_pattern_breakout repeats setup_breakout:** negative in both halves and on both symbols (EURUSD −0.23,
  GBPUSD −0.21), and the traded direction is worse than both the other direction and random. Retest 0.5 R with
  a stop 2 R from the entry (16 bars) improves the same signals by +0.126 R (+0.05 / +0.21) and stop ×2 by +0.086
  (+0.02 / +0.16), but the absolute stays negative (−0.125 / −0.136 R).
- **setup_harmonic_prz is the only setup whose direction carries information:** as traded beats the other
  direction by +0.22 R (both halves) and random by +0.11 R (−0.19 / −0.02 paired against random, i.e. the traded
  side wins in both halves). Its result still depends on the half (+0.15 / −0.06) and the symbol (EURUSD +0.20,
  GBPUSD −0.02); no edge is shown. 76 % of its stopped trades reached the target later, yet a wider stop or a
  retest does **not** help it (paired −0.03 / −0.05 R): its stops are not the problem, its targets are far.
- **setup_candle_reversal:** about −0.10 R in both halves; the traded direction beats random by +0.05 R in both
  halves (weak information). A retest 0.5 R with a 2 R stop gives −0.039 R (paired +0.065: +0.04 / +0.12).
- **setup_neckline_break:** 89 signals, no conclusion.
- The walk-forward selections (best rule on one half, judged on the other) pick different rules for each half
  and none holds up (pattern breakout: −0.39 R on the other half for the first half's choice). No setup in this
  family has a rule that survives walk-forward.

**Reading:** across both families, breakout-type setups lose with the direction worse than random; the stop
lever reduces their loss but does not turn it. Harmonics are the one place where the direction is informative,
which makes them the better candidate for further work (more symbols, M5, swing size and tolerance variants,
targets nearer than the far D-leg projection), measured the same way.

## 10. Still to do

- Heavy family on USDJPY and XAUUSD (`fam_heavy_USDJPY/XAUUSD.db`, replaying since 2026-10-07 19:48 UTC): rerun
  §9 on all four symbols.
- Harmonic variants (swing size, ratio tolerance, M5): counts with `harmonic_funnel.py`, replays per variant.
- A failed-break setup in shadow (TAA-L803).
