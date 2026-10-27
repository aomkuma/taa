# The fix, as a hypothesis that can fail (written 2026-10-27, before the run finished)

The owner, 2026-10-27: *"the problem is the code, measuring things as fixed numbers ... the market is
flexible with its conditions, so fixed numbers make it hard to place the entry, the exit and the stop."*

## The claim

Three thresholds in `bots.py` were absolute price amounts, so the same rule meant a different thing in each
period as gold went 2,170 -> 4,383 and its H1 ATR 5.3 -> 21.6:

| threshold | 2023-09 .. 2024-09 | 2024-10 .. 2025-10 | 2025-10 .. 2026-10 |
|---|---|---|---|
| take-profit at least 5.00 USD | 0.95 x H1 ATR | 0.54 x | 0.23 x |
| ZigZag deviation 0.05 USD, spread 0.30 USD | the same drift |  |  |

**Claim:** that scale drift is one cause of the out-of-sample collapse (+0.331 R fitted -> -0.035 R unseen,
PREDICTION.md). Expressing the three as multiples of the H1 ATR should remove it.

## What the claim predicts, and what would falsify it

1. **Consistency, not level.** The old version's R a trade ranged +0.139 / -0.193 / +0.331 across the three
   periods - a spread of **0.524 R**. If the scale drift was a real cause, the relative version's spread
   across the same three periods must be clearly smaller. **Falsified if the spread stays above about 0.4 R.**
2. **The gate's bite must differ by period in the old version.** If 5.00 USD was binding, the share of
   signals it rejected has to be much larger in 2023 (where it is 0.95 ATR) than in 2026 (0.23 ATR).
   **Falsified if the rejection share is similar in all three periods** - then the threshold was never the
   thing that changed, and the cause is elsewhere.
3. **Trade counts should even out.** The old version took 70 / 77 / 102 trades. If the gate was the cause,
   the relative version's counts should be closer to each other.

## What the claim does NOT predict

It does **not** predict a profitable system. Two separate faults were found:

- **the scale fault** (this fix): absolute numbers against a market that doubled;
- **the selection fault** (not fixed here): the parameters were chosen as the best of ~50 variants measured
  on one year of ~100 trades, which is worth roughly +0.25 R of pure selection by itself.

So my prediction, written before the result: **the spread across periods narrows, and the level stays near
zero or negative** - somewhere between -0.10 and +0.10 R a trade overall. A relative threshold cannot undo a
parameter that was picked by looking at the answer.

## Result
