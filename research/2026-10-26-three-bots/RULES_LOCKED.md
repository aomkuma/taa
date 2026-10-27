# Rules locked before the forward test — 2026-10-27, 17:5x Thai

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
