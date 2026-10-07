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

## 6. Still to do

- Heavy family (pattern breakout, neckline, harmonic): the replay ran out of commit memory with four processes
  (the page file is a fixed 2 GB); to run two at a time or after the page file is enlarged.
- The same review for setup_fib_pullback and setup_elliott_wave.
- Tests of the two hypotheses in §5.2 (replay with an H1/H4 configuration; a failed-break setup in shadow).
