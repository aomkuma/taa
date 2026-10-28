# Prediction, written before the run (2026-10-27)

The owner, 2026-10-27, before anything was measured outside the fitted year:

> "ข้อสองนี่ฉันเดาไว้เลยว่าคงขาดทุนติดลบเหมือนที่ผ่านๆ มา อันนี้เดานะ"
> ("I'd guess the second one comes out negative like all the others. This is a guess.")

**The claim being tested:** the three bots, with the parameters chosen on 2025-10-20 .. 2026-10-23
(+0.331 R a trade over 102 trades), run unchanged on 2023-09-01 .. 2025-10-19 - data the parameters have
never seen - will be **negative**.

**Why the guess is well founded (the record):**

| setup | on its learning data | on data it had not seen |
|---|---|---|
| V2b / V2s (the picture library) | positive or near flat | -0.169 R / -0.085 R |
| LV3 | +0.013 R | -0.139 R |
| break and retest | positive in learning | -0.221 / -0.390 R |
| PLAN-1 B2 | +0.213 R over 26 weeks | +0.148 R (held, the one that did not break) |

**And one warning already measured on the three bots themselves:** dropping the best 5 trades of 102 leaves
+0.092 R a trade, under the +0.15 goal. A result carried by a handful of trades is the shape that usually
does not repeat.

**My own prediction, written at the same time (so it can be scored too):** the trend bots (DOWN, UP) lose
on the older data - their parameters (box 0.20 / 0.33 of the leg, the 38.2-78.6 % band) were picked from a
grid on one year. The range bot has a better chance of surviving, because its rule is simpler and its box
comes from H4 rather than from a tuned number, but I expect the whole to land between -0.10 and +0.10 R a
trade, not near +0.33.

**What counts as the answer:** R a trade on 2023-09-01 .. 2025-10-19, all three bots, same parameters, same
exits, same gates, spread 0.30 USD a trade. Written here before the run; the result goes under it.

---

## Result

Run 2026-10-27 (`unseen.py`), same parameters, same exits, same gates, spread 0.30 USD a trade:

| period | trades | win % | R / trade | total R | worst drawdown |
|---|---|---|---|---|---|
| unseen 2023-09 .. 2024-09 | 70 | 19 % | +0.139 | +9.7 | -5.8 R |
| unseen 2024-10 .. 2025-10 | 77 | 23 % | **-0.193** | -14.8 | -18.9 R |
| **both unseen periods** | **147** | **21 %** | **-0.035** | **-5.1** | |
| fitted 2025-10 .. 2026-10 | 102 | 33 % | +0.331 | +33.7 | -9.4 R |

Per bot on the unseen data: DOWN -0.142 then -0.384; UP +0.068 then -0.087; RANGE +0.418 then -0.079.

**The owner's guess was right.** The system does not survive outside the year it was fitted on: +0.331 R
becomes -0.035 R, and the worst drawdown is twice as deep (-18.9 R against -9.4 R). The bot that looked best
when fitted (DOWN, +0.280) is the worst on unseen data. Nothing here is a system to run.

**What this rules out:** another pass of the same kind - pick thresholds on one year's grid, then measure on
that same year. Four setups have now died this way (V2b, V2s, LV3, break-and-retest) and these three make
five. The fault is the method, not the parameters.

**Scoring the two predictions:** the owner's ("negative, like the others") - right. Mine ("between -0.10 and
+0.10 overall; the trend bots lose; the range bot has the better chance") - right on the range, right on the
trend bots, right on the magnitude.
