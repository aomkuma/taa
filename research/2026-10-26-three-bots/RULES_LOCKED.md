> **WITHDRAWN THE SAME EVENING — 2026-10-27, 19:xx Thai. Read the second section first.**
> Everything in the first section was measured with the wrong parameter set (`bots.P()` defaults instead
> of the shipped `bots.SHIPPED`) and with a one-hour lookahead in the frame readings. It is kept, not
> deleted, so the record shows what I got wrong and how it was caught.

# Rule set 1 (WITHDRAWN) — locked 2026-10-27, 17:5x Thai

Written **before** any day after 2026-10-27 has been traded or replayed. Everything below was chosen on
2023-09 .. 2026-10-24 and is now frozen. The point of writing it down is that from tomorrow the data has
not happened yet, so no choice made later can quietly improve these numbers.

Anything changed after today is a **new** rule set with its own section and its own start date. The rows
above it are never rewritten.

## The two rules

**A — do not enter against the hour's own momentum.**
Momentum of H1 = (H1 close − its 50-bar mean) ÷ its 14-bar Wilder ATR, read from the last H1 bar closed
before the decision, signed so that positive means the frame leans the way this trade is going.
**Refuse the entry when that number is below −1.0.**

**B — the range bot does not break downward.** `range_break` takes the upward break only.

## Why each, in one line of evidence

| rule | evidence | holds its sign in both halves? |
|---|---|---|
| A | six bands of H1 momentum run −0.612 → +0.328 R a trade, monotonic | yes at both extremes (−0.63/−0.60 and +0.70/+0.26) |
| B | a downward range break gives −0.810 R in bull and −0.817 R in bear — independent of the regime | yes |

## What the rules did on the history they were chosen on

| | trades | win | R a trade | total R | fitted / never seen |
|---|---|---|---|---|---|
| the bots as they are | 248 | 33 % | −0.106 | −26.2 | −0.005 / −0.158 |
| A | 189 | 38 % | +0.026 | +5.0 | +0.216 / −0.058 |
| **A + B** | **171** | **39 %** | **+0.101** | **+17.2** | **+0.260 / +0.023** |

## What was considered and left out, and why

- **C — refuse when D1 momentum is stretched past +2 ATR our way** (+0.131 R, +0.191/+0.102). Left out as
  a veto because it drops 39 % of the trades for a gain that the thinner sample cannot carry. Kept as a
  candidate for *reducing size* rather than refusing, to be measured separately.
- **The owner's hard D1 side rule as a binary gate.** Measured and rejected on the evidence: aligning the
  side with the D1 regime is worth 0.06 R (−0.112 aligned against −0.173 counter over 220 trades), while
  the regime itself is worth 0.38 R regardless of side. The owner's own correction the same day — *"D1
  should not be that rigid; it is a quantity, not a gate"* — is what rule A implements, with the ordering
  the measurement found (H1 strongest at +0.148 correlation with R, then H4 +0.111, then D1 +0.047)
  rather than the ordering first proposed.
- **Session cells** (UP in Asia 07-09, DOWN in London 13-15 both held their sign). Left out of this lock:
  they are cells of 30 and 17 trades, and session is already half-encoded in the entry windows.

## The honest weakness of this lock

These two rules were chosen after seeing both halves of the history. The split into fitted and unseen
years limits the damage but does not remove it: the choice itself saw everything. The number of candidate
rules considered was small (five, listed above), so the selection premium should be far below the +0.45 R
measured for picking the best of 88 variants — but it is not zero.

**That is exactly why this file exists and is dated.** The clean test is the forward one: from
2026-10-28, every day is data that had not happened when these rules were written.

## How it will be judged

Day by day, week by week, in `JOURNAL.md`, three bots in one account, at most two open at once, each in
its own market condition — the owner's measure, not a per-rule trade count. Reported: the week's trades,
R, USD, the account, and every entry the rules refused with what it would have done.


---

# Rule set 2 — locked 2026-10-27, 19:xx Thai

## Why set 1 was withdrawn, within two hours of writing it

Two independent faults, both found by the developer session reviewing my code:

1. **The wrong parameters.** Every measurement ran `bots.P()` — the dataclass defaults — instead of the
   configuration the app ships. They differ in every bot, and for the range bot they differ in *kind*:
   `P()` defaults to `range_mode="fade"` (sell a sweep that closed back inside the box) while the shipped
   strategy is `"break"` (an M5 close out of the box). So rule B, "the range bot does not break
   downward", was derived from a setup we do not run. On the shipped bot, range sells are not the
   disaster that rule was built on.
2. **A one-hour lookahead.** `to_frame` indexes a bar by its OPEN; I shifted the index back an hour as
   if it were a close, so every H1/H4/D1 reading became available an hour before its bar closed, and the
   H4 and D1 buckets sat an hour out. Rule A's apparent strength was partly that lookahead.

Both are now impossible to repeat: `bots.run` refuses the bare defaults (`test_bots.py`), and a
hand-worked point-in-time test pins the open/close convention.

## The single rule

**The larger timeframe must lean the way the trade is going.**

H4 momentum = (H4 close − its 50-bar mean) ÷ its 14-bar ATR, from the app's own ATR, read from the last
H4 bar **closed** before the decision, signed so positive means it leans the trade's way.
**Take the trade only when that number is at least 0.**

This is the owner's own rule of 2026-10-27 — *"every trade takes only the side with the edge on a
timeframe larger than the entry timeframe"* — with the frame the measurement chose. The entry is M5; H4
is larger. The threshold is zero, not a fitted number.

## What it does, on the shipped bots over 2023-09 .. 2026-10-24

| | trades | win | R a trade | total R | fitted / never seen |
|---|---|---|---|---|---|
| the bots as shipped | 239 | 37 % | +0.102 | +24.3 | +0.226 (95) / +0.020 (144) |
| **H4 momentum behind ≥ 0** | **199** | **40 %** | **+0.210** | **+41.8** | **+0.214 (81) / +0.207 (118)** |
| and range buys only | 162 | 43 % | +0.223 | +36.1 | +0.307 (60) / +0.173 (102) |
| rule set 1's rule A alone (H1 ≥ −1) | 192 | 35 % | +0.123 | +23.6 | +0.216 (72) / +0.067 (120) |

The two halves give +0.214 and +0.207 — the closest agreement anything has shown in this work, and the
reason this rule is taken and the H1 one is not.

## The frame ordering, corrected

Correlation of "momentum behind the trade" with the trade's R, after the lookahead was removed:

| frame | correlation with R |
|---|---|
| **H4** | **+0.156** |
| H1 | +0.048 |
| D1 | +0.030 |

Before the fix I reported H1 strongest at +0.148. That was the lookahead. The owner proposed the order
H1 → H4 → D1 with D1 strongest; the measurement puts **H4 strongest and D1 weakest**, so the middle
frame carries it — nearer than D1, slower than the hour.

## What is left out, and why

- **Range buys only.** It adds +0.013 R overall and is better inside the fitted window (+0.307) than
  outside it (+0.173) — the opposite of what a durable rule looks like. The sell cells are now 15 and 14
  trades. Not taken; measured again when there are more.
- **The D1 side gate.** Aligning the side with the D1 regime is worth +0.122 against +0.041, about
  0.08 R — real but small, and the H4 rule already carries most of it.
- **Anything about stop width.** Widening the down bot's stop on the real path: x1.0 −0.031, x1.5 −0.092,
  x2.0 −0.080. The stop is not the problem; a winner's median adverse excursion is 0.29–0.41 R while a
  loser's is 1.04–1.09 R.

## The honest weakness, again

This rule was chosen after seeing both halves, like the last one. What is different: it is **one** rule
with a threshold of zero rather than a fitted number, it comes from the frame the owner named, and its
two halves agree to within 0.007 R. The clean test is still the forward one, and the forward test has not
started yet — the previous attempt to start it was withdrawn before a single day was run.
