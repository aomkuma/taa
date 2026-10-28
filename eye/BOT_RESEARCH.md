# Bot research - finding where the profit is

The owner, 2026-10-28: *"run one month - keep going until it makes a profit"*; and *"the three of you find
the secret of making a profit together - and don't forget to record every action and its result."*

**The three:** a Sonnet agent builds and runs; Codex reviews and proposes from its own reading; Claude
coordinates, checks every result before it is believed, and decides what is kept.

**The ground rules, written before the first run:**

- **The month:** October 2026, 1-27 (the latest full stretch of stored bars). Money: 200 USD, 0.01 lot,
  0.30 spread (`eye/money.py --ledger bot_ledger.csv`).
- **What may change:** the `[Claude]` definitions in `eye/BOT_SPEC.md` (band width, H1 mode, the count
  window, buffers, timeframes, the zone rule). **What may not change without the owner:** the owner's rules
  in METHOD 2e - the H1 side, at a level of the right kind, 3-5 peaks with divergence or an M / W, the break
  and the retest, the stop beyond the extreme, the target just before the next level, at least 1:2, held to
  stop or target. If one of the owner's rules is what stands between the bot and a profit, it is brought to
  the owner as a question, with the numbers - not changed.
- **The trap, named now:** tuning on one month until it is positive finds what fits that month. So the
  variant that wins October is then run **once, unchanged, on September 2026**, and both months are
  reported as they come out.
- **Every run is a row below**, kept even when it loses.

## Runs

| # | date | who proposed | what changed | why | Oct trades (filled) | won / lost | USD from 200 | kept? |
|---|---|---|---|---|---:|---:|---:|---|
| 0a | 10-28 | - | baseline: revision 3, h1 `strict`, min_r 2 (owner), band_frac 0.10, count window 20 | the starting point | **0** | - | 200.00 | the base |
| 0b | 10-28 | - | baseline, h1 `lows` | the other H1 reading | **0** | - | 200.00 | the base |

**What the baseline shows** (October, 1,767 bars evaluated with the market open; `strict` / `lows`): H1 gave
no side on 849 / 620; step 2 found no 3-5 count and no M/W on 430 / 551, no counter-move on 194 / 190, no
divergence on both on 140 / 136; step 3 had no higher low yet on 111 / 179; the reward was under 2R on 12 /
58. **Zero trades in a month: the bot as specified is too narrow to measure.** The gates are, in order: the
H1 side, then the count.

**Claude's hypotheses, written before reading Codex's or Sonnet's:**
- C-H1: the H1 side from only the last two fixed H1 pivots of each kind is too slow - one stale pivot holds
  "no side" for days. A side from H4 or from the last three swings may be closer to what the owner reads.
- C-H2: the count of 3-5 on an M5 zone is cut by ZigZag depth 12: pushes inside a zone are often smaller
  than a depth-12 swing, so the count is 1-2 where a reader sees 4. The M15 count is the closer one.
- C-H3: `band_frac` 0.10 of the median H1 leg is narrow for gold at 4,000; a band of 0.15-0.20 would hold
  more of a zone's touches.
- C-H4: "divergence on both" for the count may be stricter than the owner meant ("if both happen it is
  clear" says both is the strong case, not that one is not enough) - **this one touches the owner's rule:
  if it is the key, it goes to the owner.**

**Codex's reading of the October log** (read-only, its own hypotheses before seeing Claude's):
- 1,147 of 1,767 bars reach step 2. Counts: 1 on **551**, 2 on 214, 3 on 145, 4 on 22, 5 on 25. Of the 3-5
  counts, **56** diverge on both, **113 on MACD only**, 1 on neither.
- Ranked `[Claude]` changes: (1) a longer count window than 20 pivots; (2) wider bands; (3) M15 before M5 or
  alone - on 22/10 London **M15 counted three highs with divergence on both and broke 4104.92, then stopped
  at "no fixed lower high"**; (4) the step 3-5 swing sequence (179 bars break but no fixed swing yet);
  (5) a smaller stop buffer for the 58 rows under 2R.
- **For the owner, from Codex too:** does the 3-5 count need divergence on both? 113 bars have MACD only.
- On the fall from 4141: not shown reachable by `[Claude]` changes alone from this log.

**Agree / differ (Claude):** agree on M15 (C-H2) and bands (C-H3); Codex adds the count window and the swing
sequence, which Claude had not; the divergence question is the same as C-H4 - the owner's, not ours.

**The owner answered the divergence question (2026-10-28): *"one"*** - the 3-5 count needs divergence on
one oscillator, not both. `div_mode` = one becomes the owner's default (BOT_SPEC R11), not a research variant.
