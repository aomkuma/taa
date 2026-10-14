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

## 11. Setup workbench: `setup_harmonic_prz` on eight symbols (2026-10-09)

Owner, 2026-10-09: one setup at a time; **target ≥ +0.15 R/trade net of costs** (90 % CI lower bound > 0 in both
halves), ≥ 300 trades a year on the eight symbols (EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD,
XAUUSD), max drawdown ≤ 15 R. Harmonic-only replay with the H4/D1 market map on every signal
(`research replay-family harmonic`), analysed with `research hypotheses --holdout-symbols AUDUSD,XAUUSD`
(`data/research/l810_harmonic_M15.txt`).

| | Mean R [90 % CI] | Oct-Mar / Apr-Oct |
|---|---|---|
| as traded (821 signals, ~820 a year) | **+0.021 [−0.07, +0.11]** | +0.013 / +0.030 |
| the other direction | −0.135 | −0.08 / −0.20 |
| random direction (expectation) | −0.057 | −0.04 / −0.09 |

- **Gap to the target: about +0.13 R per trade.** The direction carries information on all eight symbols (+0.16 R
  over the other direction, +0.08 R over random, both halves), but the result is about zero after costs.
- Exits: nearer targets are worse (1 R −0.017, 0.5 R −0.10); wider stops ~0 (+0.01 to +0.03); a retest entry does
  not help (−0.015 at 0.5 R / 2 R). 73 % of the stopped trades reached their target later, yet no exit or stop
  variant turns that into a gain: the losers' paths do not separate from the winners' at entry.
- Walk-forward: the best rule of one half (a ×2 stop) gives +0.01 to +0.02 R on the other half and −0.04 to −0.09 R
  on the hold-out symbols. Context rules (115 candidates incl. the H4/D1 map features): the best of each half fall
  to about zero on the hold-out symbols; a low cost share (spread ≤ ~0.13 of the stop) holds on the other half
  (+0.12 to +0.16 R) but not on the hold-out symbols (−0.01 to −0.02 R).
- **Decision:** no harmonic rule reaches the target yet; the bot keeps trading it on DEMO only as the measured
  setup. Next (owner, 2026-10-09): the **pre-run price behaviour** study, independent of the setup (§12).

## 12. Pre-run price behaviour (owner's question, 2026-10-09)

The owner's observation: before price really runs it often swings or makes a false break (60-70 %), more so
before the New York open, before news and in the illiquid morning. **Not** a request to trade against the break:
the setup keeps its direction; the question is the entry timing after that behaviour. Measured so far (S/R zones
from swings, 8 symbols, one year): a close back inside the zone within 3 bars after a break 45 % (M15) / 44 %
(H1), within 12 bars **69 % / 66 %**, the same on every symbol. Planned study: (1) what happens before real runs
(sweep of the other side, break-and-shake, compression), how long and how deep, by session and news time;
(2) entry-timing rules in the setup's direction (wait for the sweep / false break to finish, stop beyond its
extreme; avoid or delay the high-false-break hours), walk-forward with hold-out symbols on every setup.

## 13. Inverted setups on DEMO (owner, 2026-10-09)

All setups were far from the target, so the owner chose to trade each setup's signals **the other way** at the
same exit prices (SL = the original TP, TP = the original SL). History, re-simulated with both spreads: breakout
+0.036 R, pattern breakout +0.059, fib +0.055, harmonic −0.196 (R of the original risk); none reaches +0.15. The
nine `*_inverted` strategies trade on DEMO since 2026-10-09 13:45 UTC (first trade: EURUSD BUY, the inverted
`setup_breakout` SELL on the New York opening-range break). Concept, mechanics and the work that remains:
docs/INVERTED_SETUPS.md.

## 14. Pre-run behaviour and the inverted trades, measured (2026-10-11)

Goal before: the best history estimate of an inverted setup was +0.059 / +0.036 R (pattern breakout / breakout,
R of the original risk; §13), a gap of about +0.10 R to the target (≥ +0.15 R/trade net).

**Part 1, what happens before real runs** (`research/2026-10-11-pre-run/pre_run.py`, output
`data/research/pre_run_part1.txt`; 8 symbols, M15 and H1, 2025-10-15 .. 2026-10-05; definitions fixed before
the run). A run = +3 ATR within 16 bars before −1 ATR. Precursors over the 8 bars before: a sweep of the other
side's 20-bar extreme closing back inside, a false break on the run's side, compression (lowest fifth of the
window range). Every number is compared with a **random-walk baseline**: the same bars shuffled per symbol.

| | M15 market | M15 random walk | H1 market | H1 random walk |
|---|---|---|---|---|
| lift of P(run) after a sweep of the other side | 1.01 (halves 1.05 / 0.97) | 0.98 | 0.88 | 0.93 |
| lift after a false break on the run's side | 0.96 | 0.98 | 0.98 | 0.98 |
| lift after compression | 0.90 | 1.00 | 1.06 | 1.00 |
| a break closes back inside within 12 bars | 64.9-74.5 % by hour | 66-70 % | 62-78 % | 63-71 % |

- **Sweeps, false breaks and compression do not announce runs:** they precede runs exactly as often as they
  precede any bar (lift ≈ 1, like the random walk). The behaviour the owner sees before runs is real, but it is
  just as common before moves that never come.
- **The 66-69 % false-break rate of §12 is mostly what a random walk does** (66-70 %). What exceeds it, in both
  halves on M15: breaks in the Asian session (72.5 %), London (74 %), the rollover hours 17-20 New York (74.5 %)
  and the hour before the US release slots (73.8 %; a proxy, no historical calendar here). At the New York
  open (09:30-11:30 NY) breaks fail **less** (64.9 %, 65.2 / 64.7 by half), about like a random walk.
- Sweeps before runs reach a median 0.5 ATR (p75 0.9) beyond the swing and end a median 4 bars before the run.

**Part 2, the setups and their inverted trades** (`research hypotheses`, new: `--inverted` simulates the inverted
setup's trade itself, in R of its own wider risk; new features `ny:<bucket>`, `ny_minute`, `pre_news`,
`pre:sweep_against`, `pre:false_break_with`, `pre:compression_pct`; outputs `data/research/l811_*.txt`;
hold-out XAUUSD for the light family, GBPUSD for the heavy pair, AUDUSD+XAUUSD for harmonic):

| Setup | n | Original, R | Inverted, R of its own risk [90 % CI] | Halves (inverted) |
|---|---|---|---|---|
| setup_breakout | 3,750 | −0.149 | −0.002 [−0.02, +0.02] | +0.012 / −0.017 |
| setup_pattern_breakout (EURUSD, GBPUSD) | 901 | −0.222 | −0.005 [−0.04, +0.03] | −0.022 / +0.014 |
| setup_fib_pullback | 378 | −0.159 | −0.025 [−0.08, +0.03] | −0.097 / +0.045 |
| setup_elliott_wave | 552 | −0.072 | −0.025 [−0.08, +0.02] | −0.051 / +0.004 |
| example_trend_pullback | 55 | +0.028 | −0.062 [−0.20, +0.10] | — |
| setup_candle_reversal (EURUSD, GBPUSD) | 331 | −0.098 | **−0.095 [−0.16, −0.03]** | −0.063 / −0.157 |
| setup_neckline_break (EURUSD, GBPUSD) | 89 | +0.003 | −0.103 [−0.24, +0.02] | −0.159 / −0.048 |
| setup_harmonic_prz (8 symbols) | 821 | +0.021 | **−0.118 [−0.16, −0.07]** | −0.111 / −0.126 |

- **The §13 estimate was too high.** It took −(the original's result) − two spreads; the full re-simulation also
  pays what the bar-based fills charge both sides (a gap through a target fills at the target, a bar touching
  both levels counts the stop, the exit-side spread at the exit bar): for setup_breakout original + inverted =
  −0.150 R against −0.118 R for two spreads and costs. In R of the original risk the inverted breakout is
  −0.001 (the identity alone gives +0.03); the account risks the inverted trade's own stop (≈ 2× wider), so per
  trade it sees about half of that. The truth for fills at the target price or better lies between.
- **No context rule survives** (walk-forward on the other half and the hold-out symbols, 144-160 candidates per
  setup, with the new New York-time and pre-run features): the New York buckets chosen on one half fall on the
  other (breakout inverted: London open +0.062 → −0.089). A low cost share (spread ≤ ~0.03 of the stop) is the
  recurring best rule for the inverted breakout family (+0.04 to +0.10 R on the other half) but about +0.01 to
  +0.015 R on the hold-out symbols.
- **Gap after: about +0.15 R per trade** for every inverted setup (the best is ≈ 0). Inverting removes the
  original's loss on the breakout family and leaves the costs; it does not create an edge. Harmonic and candle
  reversal inverted lose with the CI below zero (their original direction carries information, §9, §11).

**Owner's decision (2026-10-11):** nothing is switched off on these harness numbers. Every setup is
measured with the backtester instead, in two worlds: two separate backtests over the same four months
(2026-06-05 .. 2026-10-05, eight symbols), started together, the original and the inverted each with its own
account (INVERTED_SETUPS §5; results in §15 when they finish). The next lever has to change the trades themselves (where the original direction is
informative: harmonic; the cost share: higher timeframes, wider structures), not their side.

## 15. Harmonic in two worlds, backtested over a year (2026-10-11)

Owner, 2026-10-11: judge setups with the backtester, one setup at a time, harmonic first; the original and
the inverted as two separate worlds (INVERTED_SETUPS §5). `setup_harmonic_prz` and
`setup_harmonic_prz_inverted`, 8 symbols, 2025-10-15 .. 2026-10-05 as three 4-month runs (`4mA`, `4mB`, `4m`)
joined per world, research config `data/research/config_paired_bt.yaml` (breakers at their widest, 0.5 %
risk). Outputs `data/backtests/inv/harmonic_1y_*.txt`; scripts in `research/2026-10-11-pre-run/`.
Goal before: harmonic +0.02 R in the replay harness (§11), gap +0.13 R.

| World | Trades | Win % | R/trade [90 % CI] | Max DD | Avg win / loss |
|---|---|---|---|---|---|
| normal | 779 (~780 a year) | 39 % | **−0.027** [−0.10, +0.05] | 44.6 R | +1.42 / −0.97 R |
| inverted | 746 | 61 % | **−0.133** [−0.18, −0.09] | 101.2 R | +0.41 / −1.00 R |

- **The normal side is the better world** in every period and every symbol group; the inverted world loses
  with its CI below zero, in every market phase and both halves. The harmonic direction carries information
  (as §9 and §11 found), so inverting it pays the spread twice *and* takes the wrong side.
- **How price moved:** 58 % of the normal world's losers turned at once (under 25 % of the way to the target),
  22 % went 25-50 %, 20 % more than half way; 73 % of the stopped trades reached the target later. A wider stop
  at the same target does not convert that (×1.5: ±0.00 R paired).
- **Break-even costs about 0.05 R a trade:** the engine moves the stop to entry at +1 R (79 trades closed at
  break-even). On the same trades without it: +0.042 R [−0.04, +0.13] (halves +0.043 / +0.040); with
  break-even at +1 R −0.008 (paired −0.050; first half −0.017, second half also negative). The rest of the gap
  between the re-simulation and the backtest is fills and spreads at the exit.
- **Market phase on three screens (§3.1 of CONFLUENCE_DIRECTION):** normal world `against_h4` (H4 trending
  against the trade, i.e. a reversal at the end of a move) +0.151 R (n = 74; halves +0.08 / +0.25; hold-out
  symbols +0.02); `pullback` (H4 with, M15 against: the classic triple-screen entry) −0.38 R (n = 26, both
  halves negative): a reversal pattern does not fit a continuation phase. 68 % of the trades fall in
  `other` (an H4 or H1 transition), −0.06 R. Groups are small; no phase reaches the goal alone.
- **No context rule survives** (90 candidates incl. the New York-time and pre-run features): the best of each
  half falls to about 0 on the hold-out symbols (AUDUSD, XAUUSD).
- **Gap after: about +0.18 R per trade** for the backtest as it trades now (−0.027); about +0.11 R with
  break-even off (≈ +0.04). Trades per year (780) meet the target; drawdown (44.6 R) does not.

**Proposals to the owner (decides):** (1) trade harmonic on the normal side, not inverted; (2) no break-even
for harmonic (a per-strategy exit setting), to be confirmed by a two-world backtest with it off; (3) prefer the
`against_h4` phase and avoid `pullback` as a gate candidate, measured again once implemented. None of these
reaches the goal yet; the next lever is the entry itself (58 % of the losers turn at once).

### 15.1 Without break-even, confirmed by the backtester (2026-10-11, late)

Same year and research config, `break_even_trigger_r` and `trailing_start_r` switched off
(`data/research/config_paired_bt_nobe.yaml`); normal world only; output `data/backtests/inv/harmonic_nobe_*.txt`.

| Variant | Trades | Win % | R/trade [90 % CI] | Halves | Max DD | Avg win / loss |
|---|---|---|---|---|---|---|
| as configured (break-even +1 R) | 779 | 39 % | −0.027 [−0.10, +0.05] | −0.011 / −0.047 | 44.6 R | +1.42 / −0.97 |
| **no break-even / trailing** | 773 | 34 % | **+0.024** [−0.06, +0.11] | +0.021 / +0.028 | 30.2 R | +1.97 / −0.97 |

- **+0.051 R a trade, in both halves**, and a third less drawdown: the re-simulation's estimate holds in the
  backtester. Losers turning at once: 53 % (58 % before).
- **Three screens without break-even:** `against_h4` +0.211 R (n = 73; halves +0.20 / +0.23; **hold-out
  symbols +0.13**); `range_h1_other` +0.067 (hold-out +0.22); `pullback` −0.444 (n = 26; every half and the
  hold-out negative). `other` (H4/H1 in transition, 69 % of the trades) ≈ 0.
- **Gap after: about +0.13 R per trade** (+0.024 against +0.15); drawdown 30 R (target ≤ 15 R); 773 trades a
  year. Code: `position_management.by_strategy` (PLAN §A11) can switch break-even/trailing off for harmonic
  alone; **not set in config.yaml until the owner decides**.

### 15.2 How to improve harmonic, from its backtest trades (2026-10-11, owner's question)

On the 773 no-break-even trades (`data/backtests/inv/harmonic_nobe_filters.txt`), each filter judged on both
halves and the hold-out symbols (AUDUSD, XAUUSD). The filters were picked after looking at this data (about ten
tried), so each must be confirmed as a coded gate in a new two-world backtest and on symbols not seen yet.

| Filter | Trades/yr | R/trade | Halves | Hold-out | Max DD |
|---|---|---|---|---|---|
| none (no break-even) | 773 | +0.024 | +0.02 / +0.03 | +0.00 | 30.2 R |
| skip `pullback` | 747 | +0.041 | +0.04 / +0.04 | +0.03 | 25.3 R |
| **H4 against the trade or ranging** | 203 | **+0.142** | +0.14 / +0.14 | **+0.25** | **11.7 R** |
| **New York 12:00-20:00** | 167 | **+0.183** | +0.17 / +0.19 | +0.14 | **7.1 R** |
| London / New York morning | 266 / 340 | ~0 | mixed | negative | — |

- Harmonic works as a **reversal at the end of a move or inside a range**; it loses while the H4 trend still
  runs with the trade. With that gate the drawdown target holds and R/trade is near the goal (gap ≈ +0.01 R),
  but trades fall below 300 a year: more symbols are the lever for the count.
- Next: the phase gate (H4 against/range, no `pullback`) coded for harmonic and backtested in two worlds; then
  the New York afternoon on top; then more symbols (out-of-sample and the trade count).

### 15.3 The refined harmonic, coded and backtested (2026-10-12)

Owner, 2026-10-11/12: turn the inverted copies off, code the improvements, including a confirmation at the PRZ.
New code: the backtester gives strategies the H4/D1 market map (`MarketContext.htf`, as live and replay;
TAA-L809), `HarmonicParams.phase_gate` / `confirm`, `SetupParams.max_rr`. Year, 8 symbols, no break-even,
research config; outputs `data/backtests/inv/harmonic_v12_compare.txt`.

| Variant | Trades/yr | Win % | R/trade [90 % CI] | Halves | Hold-out | Max DD | Net |
|---|---|---|---|---|---|---|---|
| no break-even (§15.1) | 773 | 34 % | +0.024 [−0.06, +0.11] | +0.02 / +0.03 | +0.00 | 30.2 R | +705 |
| **V1: + H4 against/range, R:R ≤ 3** | **181** | **41 %** | **+0.211 [+0.04, +0.39]** | **+0.23 / +0.18** | **+0.37** | **8.5 R** | +1,821 |
| V2: V1 + PRZ confirmation (`prior_bar_break`, ≤ 6 bars) | 89 | 31 % | −0.096 [−0.32, +0.14] | +0.08 / −0.31 | +0.12 | 16.3 R | −465 |

- **V1 meets three of the four goals:** +0.211 R/trade (≥ +0.15; +0.16 with 0.05 R extra cost), the CI's lower
  bound above zero over the year, max drawdown 8.5 R (≤ 15 R); positive on 7 of 8 symbols (USDJPY −0.11).
  **Gap: trades, 181 a year against ≥ 300.**
- **The PRZ confirmation fails:** waiting for a close beyond the previous bar removes the good entries and
  enters late (win rate 31 %); rejected.
- **Caveat:** the H4 gate was found on this year (§15.2); V1 confirms the code reproduces it, not that it holds
  out of sample. Next: the same V1 on symbols not used yet (also the lever for the trade count), and forward.
- **Owner's decision, 2026-10-12:** the bot trades `setup_harmonic_prz` with V1 (config.yaml), no break-even
  or trailing for it, the inverted copies off.

## 16. Breakout F1 and the aggressive preset (2026-10-14)

Breakout F1 (`setup_breakout` with `{screen_h4: with, screen_h1: with, fade_counter_trend: true,
trend_entries: false, friday_cutoff_utc: "16:00"}`, market map H1/H4/D1): wait for a break against the H4 and
H1 trend, then trade it with the trend; every trade is a `FADE` (the plan's inverse: stop at the plan's target,
target at the plan's stop; `risk.fade` sets its RR floor and SL cap). Monthly runs Oct 2025 - Sep 2026 on the
eight symbols (`data/backtests/inv/setup_breakout_f1_YYYY-MM`):

| Setup | Trades/yr | Win % | Avg win / loss | R/trade | Halves |
|---|---|---|---|---|---|
| breakout F1 | 99 | 80 % | +0.44 / -0.97 R | **+0.159** | +0.159 / +0.158 |
| harmonic V1 (§15.3) | 181 | 41 % | +1.92 / -0.97 R | +0.211 | +0.238 / +0.184 |
| both | 280 | | | +0.192 | |

- F1 meets the +0.15 R/trade goal on its own, with both halves alike; the trade count (99/yr) is the gap.
- **Owner's decision, 2026-10-14:** F1 trades in both modes (config.yaml) and both setups form the aggressive
  preset (PLAN §A36), fades at half risk. The compounding Monte Carlo of that preset (PLAN §A36 table) is the
  risk the owner accepts by choosing it: at 7.5 % about half the simulated years reach the 60 % stop.
- Caveat as in §15.3: F1 was shaped on this year; forward results (DEMO) are the test.

## 10. Still to do

- Heavy family on USDJPY and XAUUSD (`fam_heavy_USDJPY/XAUUSD.db`, replaying since 2026-10-07 19:48 UTC): rerun
  §9 on all four symbols.
- Harmonic variants (swing size, ratio tolerance, M5): counts with `harmonic_funnel.py`, replays per variant.
- A failed-break setup in shadow (TAA-L803).
