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

**Falsified** (`gate_bite.py`, 2026-10-27). The 5.00 USD take-profit floor rejected **1 of 496** complete
signals across the three periods (1 % in 2023-09 .. 2024-09, 0 % in both later ones), because every bot's
target is set by a swing or by half an H4 box and is far larger than 5 USD anyway. Prediction 2 said the
hypothesis fails if the rejection share is similar in all three periods. It is. The scale drift of that
threshold was never what changed, so making it relative fixes nothing.

The floor was removed anyway (owner: "you can take the 5 USD out") - a number that never binds only makes the
rule read as if it did.

---

# The second hypothesis: selection (`selection_bias.py`, 2026-10-27)

88 variants, each run on the fitted year and on the two earlier years:

- picking the best of 88 is worth **+0.454 R** over the average of the 88, by selection alone;
- the top 5 by fitted score averaged **+0.291 fitted -> +0.064 unseen**;
- across all 88 the fitted mean is -0.058 and the unseen mean -0.037: there is no broad edge to find;
- but the correlation between the fitted and unseen scores is **+0.35**, not 0 - the measurement carries
  something, it is just far too weak to pick a winner from.

**And the collapse is not uniform - this is the part I had wrong:**

| variant | fitted | unseen |
|---|---|---|
| RANGE break H4 tp 0.8 buf 0.2 | +0.396 | **+0.407** |
| RANGE break H4 tp 0.5 buf 0.2 | +0.287 | **+0.467** |
| RANGE break H4 tp 0.8 buf 0.6 | +0.231 | **+0.243** |
| DOWN box 0.2 retr 0.382-0.786 buf 0.2 minR 1.2 | +0.280 | **-0.289** |
| DOWN box 0.2 retr 0.382-0.786 buf 0.5 minR 1.2 | +0.208 | **-0.222** |
| DOWN box 0.2 retr **0.5-0.886** buf 0.2 minR 0.8 | +0.245 | **+0.023** |

The range bot holds its sign in both halves at several settings. The trend bot reverses sign - except at the
**deeper retrace band the owner asked for** (2026-10-27: "gold's Fibonacci has to be deeper - the 23 and 88
levels"). I measured 0.382-0.786 against 0.5-0.886 on the fitted year, saw +0.280 against +0.245, and kept
mine. On unseen data that choice is -0.289 against +0.023: I spent 0.31 R a trade to follow a number fitted
on one year instead of the owner's reading of how gold actually pulls back.

**The lesson, in one line:** a one-period measurement is not strong enough to overrule a trader's structural
reasoning; it is only strong enough to reject something that reasoning never claimed.
