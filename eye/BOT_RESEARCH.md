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

### Round 1 - eleven variants of the `[Claude]` definitions, October 1-27 (Sonnet's runner, `eye/bot_research.py`)

With the owner's rules as they stand (one oscillator enough, at least 1:2):

| # | date | who proposed | what changed | why | Oct trades | won / lost | USD from 200 | kept? |
|---|---|---|---|---|---:|---:|---:|---|
| 1 | 10-28 | - | `base_strict` (div one, 2R) | the owner's rules as answered | 0 | - | 200.00 | - |
| 2 | 10-28 | - | `base_lows` | other H1 reading | 0 | - | 200.00 | - |
| 3 | 10-28 | - | `both_strict` - div both (the old rule) | comparison | 0 | - | 200.00 | - |
| 4 | 10-28 | Claude C-H1 | `h4_side` - side from H4 | H1 side too slow | 0 | - | 200.00 | no |
| 5 | 10-28 | Claude C-H1 | `swings3` - three swings | firmer side | 0 (no side on 1,568 bars) | - | 200.00 | no |
| 6 | 10-28 | Claude C-H2, Codex 3 | `m15_only` | M5 ZigZag too fine | 0 | - | 200.00 | no |
| 7 | 10-28 | Claude C-H3, Codex 2 | `band015` | wider zones | 0 | - | 200.00 | no |
| 8 | 10-28 | Claude C-H3, Codex 2 | `band020` | wider zones | 0 | - | 200.00 | no |
| 9 | 10-28 | Codex 1 | `window30` - count window 30 | zone peaks outside 20 pivots | 0 | - | 200.00 | no |
| 10 | 10-28 | - | `lows_m15` | combination | 0 | - | 200.00 | no |
| 11 | 10-28 | - | `lows_band015` | combination | 0 | - | 200.00 | no |

**Every variant: no trade.** Wider bands moved the block from step 2 to step 3 (129-183 bars "no higher low
yet") but no setup came through.

### The measurement that explains it - the 2R floor switched off, to count only (not a trading variant)

| # | variant | setups through every step but the reward | R of each | if all taken |
|---|---|---:|---|---|
| M1 | strict, min_r 0 | **1** | 1.31 (13/10 BUY) | not filled |
| M2 | lows, min_r 0 | **3** | 1.31, 0.10, 0.23 | none filled |
| M3 | lows, band 0.15, min_r 0 | **4** | 0.80, 0.28, 1.19, 0.38 | 3 filled: 1 won, 2 lost, -1.64 R, **200 -> 158.47 USD** |

**What it says (Claude's reading of these numbers, one month):** under the owner's rules as coded, the
setup is **rare - one to four a month - and its reward is small: no setup in October reached 1:2; the best
was 1.31.** The geometry does it: the stop goes beyond the extreme *and* beyond the zone's band, the target
stops *before* the next level, and on gold in October the next level was usually closer than twice the
stop. So the 2R floor is not the only gate, but it is the last one, and nothing passes it.
**This is a question about the owner's rules, not a `[Claude]` setting**, and it goes to the owner with
these numbers.

## The owner's answer on 1:2 (2026-10-29), and round 2

The owner: *"As we discussed: if 1H runs 6 USD, and M1 gets in near the top or the bottom of price, and it turns, that is 2R already."* - the reward on H1, the risk on M1. Written as BOT_SPEC revision 4 (R12): the
picture (level, count / M / W, divergence) on M5 / M15 as before; the break, the retest and the stop on M1;
the stop beyond the extreme only. **This changes an owner's rule only as the owner stated it**; the M1
definitions are `[Claude]` and marked.

**Claude's expectation, written before the run (2026-10-29):** the stop falls from round 1's 10-40 USD to
roughly 2-8 USD, so far more setups pass 2R: **5-15 filled trades in October** (from 0). The tight stop will
be hit by M1 noise more often: **a win rate of 30-40 %**. Whether that pays at 2R+ is open - my guess is near
break-even, between -0.2 and +0.3 R a trade. If it comes out at 0 trades or over 40, that is an abnormal
count and the report stops until it is explained.

### Round 2 - R12 (entry on M1), October 1-27 (Sonnet's build, before Codex's review)

| # | date | who proposed | what changed | why | Oct trades (filled) | won / lost | USD from 200 | kept? |
|---|---|---|---|---|---:|---:|---:|---|
| 12 | 10-29 | the owner | `m1_strict` - R12, h1 strict | the owner's answer on 1:2 | 2 (2) | 0 / 2 | 183.66 (-2.08 R) | under review |
| 13 | 10-29 | the owner | `m1_lows` - R12, h1 lows | the same, other H1 reading | 3 (3) | 0 / 3 | 171.51 (-3.11 R) | under review |

The three trades (`m1_lows`; `m1_strict` wrote the first and the third), traced by Claude on M1 for 48 h:

| trade | risk USD | stop hit (Thai) | best move before the stop | target later? |
|---|---:|---|---:|---|
| 06/10 SELL W at 4144-4145, entry 4137.89 | 7.93 | 07:49, 34 min after the fill | 0.31 R | **yes, 09:35** - after going 1.79 R against |
| 09/10 BUY M at 4175, entry 4186.46 | 11.80 | 19:51, 16 min | -0.09 R | no |
| 13/10 BUY count 4 at 4180, entry 4186.95 | 7.78 | 19:54, 19 min | 0.30 R | no |

**Against the expectation written before the run:** 5-15 trades expected, **2-3** came; 30-40 % won expected,
**none** did. Three trades say nothing about the method (CLAUDE.md: no conclusion from a handful). What is
measured: the M1 entry made 2R reachable (206 / 275 bars now stop at "reward under 2R" instead of every one),
but each entry was the retest of the broken M1 high, already 8-12 USD from the extreme, and all three were
stopped within 34 minutes. Still under review (Codex), not yet believed.

**Codex's review of the R12 build (2026-10-29, read-only):** no look-ahead (every frame's close time is
checked, M1 included; ZigZag emits only fixed pivots); the R12 formulas faithful, the SELL mirrored;
`entry_mode=setup` reproduces the pinned round-1 decision. **Codex replayed all three October decisions
from the stored M1 / M5 bars and got the same side, entry, stop and target.** One medium risk, not observed
in October: an `L*` older than the 7,200-bar M1 frame (five trading days) is refused - zero such rows.
So the three losses are what the rules as written do, not a bug.
