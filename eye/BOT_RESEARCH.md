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

## Round 2 (2026-10-29) - an entry on M1: Claude's misreading, removed

**Correction (the owner, 2026-10-29):** *"1H 6 USD was only a question - not meant to be researched or taken further; it was a comparison."* Claude had taken the owner's question as the
answer on 1:2 and built revision 4 on it. **Removed from the code at the owner's word (*"take it out"*).**
Kept below as the record of a method tried - not the owner's, and not to be run again.

### As it was recorded at the time

Claude took the owner's comparison *"if 1H runs 6 USD, and M1 gets in near the top or the bottom of price,
and it turns, that is 2R already"* for a rule (**a misreading - the owner later: only a comparison**) and
wrote BOT_SPEC revision 4 (R12): the picture on M5 / M15 as before; the break, the retest and the stop on
M1; the stop beyond the extreme only.

**Claude's expectation, written before the run (2026-10-29):** the stop falls from round 1's 10-40 USD to
roughly 2-8 USD, so far more setups pass 2R: **5-15 filled trades in October** (from 0). The tight stop will
be hit by M1 noise more often: **a win rate of 30-40 %**. Whether that pays at 2R+ is open - my guess is near
break-even, between -0.2 and +0.3 R a trade. If it comes out at 0 trades or over 40, that is an abnormal
count and the report stops until it is explained.

### Round 2 results - R12 (entry on M1), October 1-27

| # | date | who proposed | what changed | why | Oct trades (filled) | won / lost | USD from 200 | kept? |
|---|---|---|---|---|---:|---:|---:|---|
| 12 | 10-29 | Claude (misread) | `m1_strict` - R12, h1 strict | Claude's misreading of a question | 2 (2) | 0 / 2 | 183.66 (-2.08 R) | removed |
| 13 | 10-29 | Claude (misread) | `m1_lows` - R12, h1 lows | the same, other H1 reading | 3 (3) | 0 / 3 | 171.51 (-3.11 R) | removed |

The three trades (`m1_lows`; `m1_strict` wrote the first and the third), traced by Claude on M1 for 48 h:

| trade | risk USD | stop hit (Thai) | best move before the stop | target reached later if held? |
|---|---:|---|---:|---|
| 06/10 SELL W at 4144-4145, entry 4137.89 | 7.93 | 07:49, 34 min after the fill | 0.31 R | **yes, 09:35** - after going 1.79 R against |
| 09/10 BUY M at 4175, entry 4186.46 | 11.80 | 19:51, 16 min | -0.09 R | no |
| 13/10 BUY count 4 at 4180, entry 4186.95 | 7.78 | 19:54, 19 min | 0.30 R | no |

**Against the expectation written before the run:** 5-15 trades expected, **2-3** came; 30-40 % won expected,
**none** did. Three trades say nothing about the method (CLAUDE.md: no conclusion from a handful). What is
measured: the M1 entry made 2R reachable (206 / 275 bars now stop at "reward under 2R" instead of every one),
but each entry was the retest of the broken M1 high, already 8-12 USD from the extreme, and all three were
stopped within 34 minutes. **3 distinct trades** (2 under `strict`, 3 under `lows`, the strict two among
them). Codex's review below found no bug.

**Codex's review of the R12 build (2026-10-29, read-only):** no look-ahead (every frame's close time is
checked, M1 included; ZigZag emits only fixed pivots); the R12 formulas faithful, the SELL mirrored;
`entry_mode=setup` reproduces the pinned round-1 decision. **Codex replayed all three October decisions
from the stored M1 / M5 bars and got the same side, entry, stop and target.** One medium risk, not observed
in October: an `L*` older than the 7,200-bar M1 frame (five trading days) is refused - zero such rows.
So the three losses are what the rules as written do, not a bug.

## Round 3 - the owner's Fibonacci (BOT_SPEC revision 5), with and without the count

**Claude's expectation, written before the run (2026-10-29):**
- Arithmetic, not a guess: with the stop at 0 % and the target at the leg's 100 %, R = (1 - e) / e before
  spread for an entry level e: 0.236 -> 3.2, 0.382 -> 1.6, 0.618 -> 0.6 (a stop-at-0 reference; the owner's
  0.618 stop is at 23.6 %, below). **So with `fib_target = high`
  only the 0.236 entry can pass the owner's 2R**; 0.382 and 0.618 need the target to be a level further away.
- Without the count: many more orders than 2e - I expect **15-40 in October** at 0.236 / level targets, a
  win rate near 30-40 % (a 0.236 pullback is deep: many legs break their low).
- With the count: rare, as 2e was - **0-5**.
- Over 60 trades in a month, or 0 in every no-count variant, is an abnormal count and stops the report.

**The owner on what will matter next (2026-10-29):** *"the problem I can see coming is reading whether it is
a trend or sideways - but never mind, try it first."* In revision 5 that reading is Claude's: trend = step 1's
H1 side (`h1_mode`), sideways = no H1 side. Every Fibo decision writes which it was, so the trend / sideways
call can be judged trade by trade after the run.

**The round 3 expectation, updated for the owner's targets (written before any round 3 result):** stop at 0 %
(0.618 entry: at 23.6 %), before spread - entry 0.382: 2.3 R at 127 %, 3.2 R at 161 %; 0.236: 4.4 / 5.9 R;
0.618: 1.7 / 2.6 R. So `ext127` passes 2R for 0.382 and 0.236 only; `ext161` for all three. The trade-count
and win-rate expectation above is unchanged.

### Round 3 results (revision 5 - the wrong leg), October 1-27

15 variants (Sonnet's report, `eye/research/fib*/`): **about 33 fills, 1 won** (M5, 23.6 %, target before the
H1 level: 6 fills, 1 won, -0.55 R, 191.74 USD); every other variant lost every fill, 76.45-195.30 USD. Claude
checked two stop-outs on the bars (15/10 SELL stopped 09:55; 16/10 BUY held to 19/10, stopped): real, not a
scoring bug. **Then the owner's charts of 27/10 showed revision 5 drew the wrong leg** (the finished leg
instead of the counter-move just ended) - so round 3 measured Claude's leg, not the owner's.

**Against the expectation:** 15-40 orders expected without the count - 2-14 came (8-14 at the extension
targets); a 30-40 % win rate expected - 1 in about 33 fills; 0-5 with the count - 1-3 came.

**Codex's review of the revision-5 build (2026-10-29, read-only):** no look-ahead; R13-R17 and the later
notes implemented as written; the SELL mirrored; `mode=2e` unchanged; no M1 logic left. Codex replayed the
15/10 SELL and 13/10 BUY legs from the stored M15 / H1 bars - the fixed pivots match. `ext161` is applied
(targets differ; the same 13 orders of `fib382_ext127` / `fib382_ext161` pass 2R under both). **So round 3's
losses are revision 5's leg, not a bug.**

## Round 4 - revision 6, the owner's leg

**Claude's expectation, written before the run (2026-10-29):** with the owner's leg the entries sit near a
fresh bottom / top, so stops are shorter and the trades are reversals. I expect **more fills than round 3
(10-30 a variant in October)**, a win rate of **25-40 %** at 127-161 % targets, and with the count on, far
fewer trades (0-5). `any` side will trade about twice as often as `h1`, `entry` between them. Whether it pays: unknown; I would
not be surprised by either sign. Over 80 trades in a variant, or 0 in every count-off variant, stops the
report.


## Which high is 100 % - research asked by the owner (2026-10-29)

**NUMBERS IN THIS SECTION ARE SUPERSEDED** - measured with a fill bug in `eye/research/fib_high.py`; the corrected numbers are in "Correction - the fill bug" below.

The owner, asked whether 100 % is the latest high before the low or the high the fall started from: *"research
it and find me the answer."* Two definitions, both sides (a sell is the mirror: which low is 100 % under a
rise of 3-5 higher highs):
- **latest** - the fixed high immediately before `L0`;
- **start** - the highest fixed high of the descending run into `L0` (where the fall began).
On runs of one leg they are the same; only the runs where they differ can tell them apart.

**Claude's expectation, written before the run:** `start` draws a bigger leg - its 38 % level sits further
from the low, its stop is longer, its 161 % target much further. I expect `start` to fill less often and win
less often, with bigger wins; `latest` the opposite. Per trade, I expect the two within 0.1 R of each other -
I have no strong reason to favour either.

**Result (2026-10-29; `eye/research/fib_high.py`, M15 FBS-Demo, 2023-09-01 .. 2026-10-28, both sides, 3-5
legs, no divergence filter, all hours - not only the owner's windows, no H1 side filter; the 2R floor,
spread 0.30; each row a separate entry / target).** R a trade, n trades in brackets; `latest` / `start`:

| entry | target | whole 3 years | 2023-09 .. 2025-03 | 2025-04 .. 2026-10 | with divergence (3 y) |
|---|---|---|---|---|---|
| 23.6 % | 127 % | -0.085 (418) / -0.108 (465) | -0.225 / -0.088 | **+0.030** / -0.122 | -0.084 / -0.258 |
| 23.6 % | 161 % | -0.067 (455) / -0.126 (479) | -0.261 / -0.078 | **+0.103** / -0.163 | -0.081 / -0.271 |
| 38.2 % | 127 % | -0.073 (342) / **+0.024** (375) | -0.186 / **+0.100** | -0.020 / -0.029 | -0.114 / -0.023 |
| 38.2 % | 161 % | -0.118 (446) / **+0.026** (410) | -0.269 / **+0.120** | -0.006 / -0.049 | -0.182 / **+0.029** |
| 61.8 % | 161 % | +0.094 (280) / **+0.235** (160) | +0.099 / **+0.191** | +0.076 / **+0.278** | +0.010 / **+0.332** (90) |

(61.8 % at 127 % never reaches 2R: 1.7 R planned.) The two definitions differ on 85-90 % of the bottoms.
61.8 % / 161 % per half, trades and won: `latest` 120 (34.2 %) and 159 (31.4 %); `start` 78 (35.9 %) and 82
(36.6 %); over three years `start` 160 (36.2 %), `latest` 280 (32.9 %).

**What it says (Claude's reading, measured above; corrected 10-29 after the fourth review - the first
version said "4 of 5", which the table does not show):** over three years **`start` is ahead in 3 of the 5
rows** (38.2 % at both targets, 61.8 % / 161 %) and **`latest` in 2** (23.6 % at both targets - both
negative either way). In the recent half `latest` is ahead at 23.6 % and, by 0.01-0.04 R, at 38.2 %. The
clearest difference is the owner's strong-bull entry (61.8 %, stop beyond 23.6 %, target 161 %): **positive
for both definitions in both halves, and `start` ahead in both** (+0.19 / +0.28 R a trade against +0.10 /
+0.08). So `start` is Claude's choice for the bot's default - **not confirmed by the owner**. Check of the
arithmetic a second way: 61.8 % / 161 % plans 2.62 R; `start` won 36.2 % -> 0.362 x 2.62 - 0.638 = +0.31,
against +0.235 measured (stops cost a little more than 1 R with the spread).
**Against the expectation:** I expected no difference (within 0.1 R): over three years `start` was ahead by
0.10-0.14 R in 3 rows and behind by 0.02-0.06 in 2 - partly right; in the halves the gaps reach 0.2-0.3. I
expected `start` to fill less often: it filled less only at 61.8 % (160 against 280); at 23.6 % and
38.2 % / 127 % it filled more.
**Limits:** one timeframe (M15), Claude's own script, all hours (not the owner's windows), no H1 side, no
session filter; the best row is picked after looking at 5 pairs on the same data. A guide for the bot's
default, not proof the setup pays.

### On the timeframes we trade (2026-10-29) - the owner: *"go by the facts that match how gold actually runs on the timeframe we trade"*

**NUMBERS IN THIS SECTION ARE SUPERSEDED** - measured with a fill bug in `eye/research/fib_high.py`; the corrected numbers are in "Correction - the fill bug" below.

*No expectation was written before these two runs - a slip against the house rule; the numbers below are
read as they came.* Same script, the last year (2025-10-06 .. 2026-10-28; M5 is stored only from 2025-10),
both sides, 3-5 legs, all hours, no H1 filter. R a trade (trades), `latest` / `start`:

| entry | target | M5, 1 year | M15, the same year | M15, 3 years (above) |
|---|---|---|---|---|
| 23.6 % | 127 % | **+0.104** (460) / +0.016 (483) | **+0.095** (154) / -0.166 (168) | **-0.085** / -0.108 |
| 23.6 % | 161 % | **+0.078** (477) / +0.017 (493) | **+0.228** (164) / -0.226 (170) | **-0.067** / -0.126 |
| 38.2 % | 127 % | -0.068 (406) / **-0.038** (398) | **-0.017** (144) / -0.070 (140) | -0.073 / **+0.024** |
| 38.2 % | 161 % | -0.037 (466) / **+0.020** (413) | **-0.085** (156) / -0.162 (143) | -0.118 / **+0.026** |
| 61.8 % | 161 % | +0.070 (265) / **+0.322** (148) | -0.224 (107) / **+0.033** (51) | +0.094 / **+0.235** |

**What the facts say (Claude's reading):** neither high is better everywhere - **it depends on how deep
the entry is, and the same way on both timeframes and in every period run:**
- **the deep entry (23.6 %) goes with the latest high** - ahead on M5, on M15 this year and over three years;
- **the shallow, strong-bull entry (61.8 %, stop beyond 23.6 %) goes with the high the fall began from** -
  ahead on M5, on M15 this year and over three years;
- 38.2 % has no consistent winner (`start` on M5 and over three years, `latest` on M15 this year).
A reading of why, not measured: a deep pullback of the small last leg and a shallow pullback of the whole
fall are close to the same price - both say "the fall's last push is being retested".
The best rows on the timeframes we trade, this year: **M5 61.8 % / 161 % `start` +0.32 R (148 trades)** and
**M15 23.6 % / 161 % `latest` +0.23 R (164)**. Limits as above: all hours, no H1 or window filter, one year
on M5, rows picked after looking.

**One order at a time, or several (2026-10-29).** The bot holds one order at a time (`[Claude]`, from the
first spec). October's log: on M5 it blocked setups on 838 bars - the largest gate - against 25 fills, where
the research script (all hours, no limit) finds about 38 trades a month on M5. Asked whether to run a variant
holding several orders at once, the owner: *"yes - to find the best entry, right?"* `max_orders` (default 1)
is added for research; how many to hold live is a risk decision left to the owner.

### Filled against not filled (2026-10-29) - the owner's reading

The owner, on the M5 38.2 % run (46 orders, 25 filled): *"so if you get in before the price reaches the
level, price has a chance to go on; if you get in when it reaches the line you set, price has a chance to
keep running that way until the stop."* Measured on the October ledgers (M5, `any` side):

| variant | filled: won, R | not filled, taken at the market price at the decision: won, R |
|---|---|---|
| 38.2 % | 4 of 25, -9.83 | 17 of 21, +9.79 |
| 23.6 %, latest high | 4 of 17, +7.61 | 21 of 29, +13.89 |
| 61.8 %, start high | 8 of 24, +2.64 | 9 of 11, +4.84 |
| 61.8 %, start high, `entry` side | 6 of 15, +4.86 | 11 of 14, +5.72 |

**Claude's reading:** the pattern holds in all four, but **part of it is by construction** - a limit that
does not fill is one price ran away from, in the planned direction, and that is known only afterwards.
Taking every order at the market instead does not pay on its own (38.2 % on M5: 46 orders, -0.08 R a
trade). What the numbers do support: a pullback that reaches a deep line is often the leg going on, and the
variants that paid are the ones whose entry sits nearest the bounce (61.8 % of the whole fall, 23.6 % of the
last leg). Still missing: a sign, readable **before** the entry, of which pullbacks will turn - asked of the
owner (a limit resting at the level, or waiting in the zone for a turn on a smaller timeframe).

## Entering before the line, with a tight stop - the owner's idea (2026-10-29)

**NUMBERS IN THIS SECTION ARE SUPERSEDED** - measured with a fill bug in `eye/research/fib_high.py`; the corrected numbers are in "Correction - the fill bug" below.

The owner: *"I actually see this picture often - I forgot to say. Can you find a moment to get in before the
price I meant, with a narrower stop - say just beyond the line I meant?"*

**Claude's definitions `[Claude]`, for the owner to correct:** the intended line `x` (23.6 / 38.2 / 61.8 %
of the leg, the 100 % chosen by depth as measured: 61.8 % with the high the fall began from, 23.6 % with
the latest high, 38.2 % both); **enter early** at `x + d` of the leg, `d` = 5 %, 10 % or 15 % (a limit, after
price has closed above it); **stop just beyond the line**: `x - 0.5 USD`, or `x - 3 %` of the leg; target
161 % as before; at least 2R.

**Claude's expectation, written before the run:** the stop shrinks to a few dollars, so R per win jumps
(often 6-15 R) and the win rate falls hard - I expect **10-20 %** won at `d` = 10 %. Because the pullbacks
that reach the line are the ones that run on through it (above), a stop just beyond the line will be hit
often; I expect the 0.5 USD stop to lose to the 3 % stop. Overall I expect at least one early entry to beat
the same line entered at the line, on M5, by 0.1 R a trade or more - but not on every line.

**Result (2026-10-29; `eye/research/fib_early.py`, the last year, both sides, 3-5 legs, all hours, no H1 or
window filter, target 161 %, at least 2R; R a trade, trades in brackets).** The intended line entered at the
line with the owner's stop, against entered early with the stop 0.5 USD beyond the line:

| line, 100 % | M5 at the line | M5 +5 % early | M5 +10 % early | M15 at the line | M15 +5 % early | M15 +10 % early |
|---|---|---|---|---|---|---|
| 23.6 %, latest | +0.078 (477) | +0.389 (224) | +0.353 (279) | +0.228 (164) | -0.148 (72) | -0.388 (96) |
| 38.2 %, latest | -0.037 (466) | +0.899 (140) | +0.203 (173) | -0.085 (156) | +1.201 (46) | -0.003 (64) |
| 38.2 %, start | +0.020 (413) | +1.075 (76) | +0.723 (94) | -0.162 (143) | +1.015 (31) | -0.077 (36) |
| 61.8 %, start | +0.322 (148) | +0.338 (31) | -0.064 (34) | +0.033 (51) | +1.329 (7) | -0.127 (10) |

(The stop 3 % of the leg beyond the line gives the same picture, a little weaker on M5.)

**What it says (Claude's reading):** entering early with the stop just beyond the line **raises R a trade a
lot on M5 at the 38.2 % line** (from about 0 to +0.2 .. +1.1) and at 23.6 % (to +0.35 .. +0.39); on M15 it
is mixed and the samples are small. **The price of it, measured:** the stops are tiny - median 2.0-2.5 USD at
+5 %, 4.3 USD at +10 % (38.2 %, start) - so 8-17 % of trades win, each win averaging 9-18 R, and the losing
runs are long: **13 in a row** at 38.2 % / start / +10 %, **18-54 in a row** at +5 %. With stops of 2 USD,
the 0.30 spread is 15 % of the risk and any slippage moves the result; M5 bars cannot show what happened
inside a bar (a bar touching stop and target counts as the stop). The rows were picked after looking.
**Against the expectation:** win rates 8-17 % (expected 10-20 %) - right; the 0.5 USD stop beat the 3 %
stop on M5 - wrong (expected the opposite); early beat the line on M5 by more than 0.1 R on 3 of 4 lines -
right.

**The owner's example (2026-10-29, M1, 29/10 05:45 Thai):** *"say I sell at 4043 and the SL is 4046"* - on
a Fibo of the fall 4050.2 -> 4037.0 with price back at the 50 % line: Claude's reading, to confirm - the
intended line is 38.2 % (4045.3), the sell is taken about 12 % of the leg early (4043), the stop about 0.7
USD beyond the line (4046): risk 3 USD. That is the `+10 % early, stop just beyond the line` row.

## Correction - the fill bug in the research script (2026-10-29)

**Found by Sonnet's review (confirmed by Haiku and Codex, and by Claude in the code):** `fib_high.py`
withdrew an order when the bar that reached the entry also reached the stop. For a buy limit below price
every bar that reaches the stop passes the entry first - so those were fills that lost, and the script
dropped them. It hid losers, most of all with the tight stops of the early entry. (The bot is not affected:
its `score.py` counts the same bar as a fill.) Fixed; every table rerun. All hours, no H1 or window filter,
both sides, 3-5 lows into the extreme, target 161 % unless said; R a trade (trades).

**Which high is 100 %, corrected** (`latest` / `start`):

| entry | target | M5, last year | M15, last year | M15, 3 years | M15 2023-09 .. 2025-03 | M15 2025-04 .. 2026-10 |
|---|---|---|---|---|---|---|
| 23.6 % | 127 % | +0.051 (482) / +0.001 (490) | **+0.053** (160) / -0.181 (171) | -0.147 / -0.136 | -0.293 / **-0.123** | **-0.023** / -0.144 |
| 23.6 % | 161 % | -0.002 (513) / -0.004 (503) | **+0.149** (175) / -0.245 (174) | -0.140 / -0.153 | -0.327 / **-0.112** | **+0.024** / -0.186 |
| 38.2 % | 127 % | -0.067 / -0.043 | -0.031 / -0.083 | -0.087 / **+0.010** | -0.193 / **+0.086** | -0.038 / -0.043 |
| 38.2 % | 161 % | -0.052 / +0.012 | -0.109 / -0.174 | -0.144 / **+0.011** | -0.296 / **+0.102** | -0.030 / -0.062 |
| 61.8 % | 161 % | +0.058 (268) / **+0.313** (149) | -0.207 (109) / **+0.013** (52) | +0.067 (290) / **+0.204** (164) | +0.053 / **+0.145** (81) | +0.063 / **+0.262** (83) |

**What survives (Claude's reading):** the one result that holds everywhere is the owner's strong-bull
entry - **61.8 %, stop beyond 23.6 %, target 161 %, with 100 % at the high the fall began from: ahead of the
latest high on M5, on M15 this year, over three years and in both halves** (+0.15 / +0.26 R a trade on M15
by half, +0.31 on M5; 52-164 trades). At 23.6 % and 38.2 % neither high is reliably better - the M15 halves
point opposite ways - and most of those rows lose. **The "it depends on the depth" reading of 10-29 does
not survive** (it rested on one year); the simpler rule - 100 % at the high the fall began from - is never
clearly worse where anything pays.

**Entering before the line, corrected** (stop 0.5 USD beyond the line; "at the line" with the owner's stop):

| line, 100 % | M5 at the line | M5 +5 % | M5 +10 % | M5 +15 % | M15 at the line | M15 +5 % | M15 +10 % |
|---|---|---|---|---|---|---|---|
| 23.6 %, latest | -0.002 (513) | -0.228 (372) | +0.026 (360) | -0.030 (343) | +0.149 (175) | -0.556 (126) | -0.535 (123) |
| 38.2 %, latest | -0.052 (473) | +0.062 (235) | -0.113 (228) | -0.027 (221) | -0.109 (160) | +0.127 (86) | -0.275 (86) |
| 38.2 %, start | +0.012 (416) | +0.278 (119) | **+0.406** (114) | +0.313 (103) | -0.174 (145) | +0.303 (47) | -0.196 (41) |
| 61.8 %, start | **+0.313** (149) | -0.081 (43) | -0.221 (40) | -0.222 (36) | +0.013 (52) | +0.041 (15) | -0.281 (12) |

**What survives:** most of the early-entry gain was the bug. **One family holds on M5: the 38.2 % line of
the whole fall, entered 5-15 % early with the stop just beyond it - +0.28 / +0.41 / +0.31 R a trade on
103-119 trades** (7.6-18.4 % won); on M15 the same rows swing (+0.30 at +5 %, -0.20 at +10 %, 41-47
trades). Early entry at 23.6 % and 61.8 % does not pay. **The best at-the-line result is still 61.8 % /
start (+0.31 R on M5).** The 0.5 USD stop does not beat the 3 % stop on every line (at 61.8 % the 3 % stop is
better). These rows were chosen after looking, on the same year.

**Other corrections from the same reviews:**
- "38.2 % on M5: 46 orders, -0.08 R a trade" (filled vs not filled) - that figure is every order taken at
  the market price (`at_decision_r` of all 46), not the sum of the two rows of that table.
- The owner's M1 example: 0 % at the high 4050.2, 100 % at the low 4037.0 - the 38.2 % line is **4045.16**
  and the sell at 4043 is about **16 %** of the leg early, not 12 %. **Its leg is also not R18's**: it is
  drawn on the fall in the trade's direction (sell after the fall, target 161.8 % below its low, 4029) - a
  continuation, while R18 (the 27/10 buy) draws the counter-move that just ended. *(Asked; the owner: an example is information, not a rule - the drawing is R18's.)*
- The count: the scripts count 3-5 lows (each lower) into the extreme - three lows are three legs down, as
  on 27/10 (4000.00, 3997.23, 3989.14). Codex read it as 2-4 transitions; Claude keeps lows = legs.
- The 2R floor uses the net reward over the gross stop distance (as the bot does); a stop costs a little
  more than 1 R. Order lifetime: 96 bars (8 h on M5, 24 h on M15). Stops that gap are scored at the stop.
- The bot's October runs are unaffected by the bug; they used `fib_high` = latest for 23.6 % on the
  strength of the uncorrected table - that mapping is withdrawn.

**Multi-order runs (bot, October, `max_orders` 10, Sonnet's):** more live orders did not help - R fell in 5
of 8 pairs; at most 2-5 orders live at once. M5 38.2 %: 37 fills, -18.07 R, **200 -> -3.93 USD** (the runner
ignores margin); M5 23.6 % latest: 27 fills, +3.06 R, 252.09 USD (against +7.61 R, 293.10 with one order);
M5 61.8 % start: 29 fills, +0.84 R, 161.60 USD. Not reviewed yet.

## Two plays on one principle (2026-10-29)

**WITHDRAWN as a rule - the owner, the same evening:** *"Do not take what I ask, or what I show as an example, and decide it must be a rule - treat it as supporting information, understand? Because how to draw the Fibo we have already discussed."* What follows was Claude turning the 29/10 M1 example into a second play; it is kept only as the record of what was measured. The rule stays the owner's drawing (R18).

Claude's reading (withdrawn as a rule): besides R18's reversal, a continuation - on the smaller timeframe, the leg in the trade's direction, sold / bought on its pullback, target 161.8 %. Measured below as a record only.

### Continuation against reversal - the plan and the expectation (written before the run)

**Continuation `[Claude]`** (`eye/research/fib_cont.py`): on the small timeframe (M5, context M15; or M1,
context M5) the latest fixed leg in the trade's direction - for a buy, a fixed LOW then the fixed HIGH after
it - drawn 0 % at the low (the stop side), 100 % at the high, as in the owner's 29/10 sell. A limit at the
line (38.2 % or 61.8 %) - or early, 10 % of the leg before it with the stop 0.5 USD beyond the line -
placed once the high is fixed and while price is above the line; withdrawn when price makes a new high
first or after 96 bars. Stop beyond 0 % (beyond 23.6 % for 61.8 %), target 161.8 %, at least 2R. Context
filter on the larger timeframe: `none`; `trend` (its last two fixed highs and lows rising for a buy); and
`trend<3` (rising, and the current run has made fewer than 3 higher highs - the fall / rise not yet complete).

**Expectation:** continuation without a filter loses, as revision 5 did in October (1 won of about 33). With
the larger-timeframe trend it improves; with `trend<3` it improves again but trades rarely. I expect the
best continuation row to be within 0.1 R of the best reversal row (61.8 % / start, +0.31 R on M5), not
clearly above it. On M1 the spread eats more of the small stops: I expect M1 below M5.

**Continuation results (Claude's idea, not a rule - recorded as measured, `eye/research/fib_cont.py`; all
hours, both sides, target 161.8 %; R a trade (trades)):**

| line | entry | M5, context M15, 1 year: none / trend / trend<3 | M15, context H1, 3 years: none / trend / trend<3 | M1, context M5, 1 year: none / trend<3 |
|---|---|---|---|---|
| 38.2 % | at the line | +0.062 (1304) / +0.078 (390) / +0.140 (318) | +0.046 (1251) / -0.022 / -0.018 | -0.095 (6459) / -0.155 |
| 38.2 % | 10 % early | -0.109 / -0.043 / +0.114 (290) | -0.022 / -0.075 / -0.041 | -0.181 / -0.301 |
| 61.8 % | at the line | -0.057 / -0.049 / +0.011 | +0.062 (821) / +0.040 / +0.099 (196) | -0.086 / -0.188 |
| 61.8 % | 10 % early | -0.062 / -0.316 / -0.311 | -0.208 / -0.047 / -0.069 | -0.195 / -0.205 |

Against the expectation: continuation stayed below the reversal (R18's 61.8 % / start, +0.31 R on M5) -
best +0.14 R (M5, 38.2 %, trend<3, 318 trades), not within 0.1 R; on M1 every row lost, as expected. **Nothing
here goes into the bot.**

## September 2026 - the October winner, once, unchanged (2026-10-29, the owner: *"run it"*)

The ground rule written before round 1: the variant that wins October is run **once, unchanged** on
September. The winner on the owner's rules as they stand: **M5, R18 leg, entry 61.8 %, stop beyond 23.6 %,
target 161.8 %, 100 % at the high the fall began from, side from the entry timeframe** (`fib_side = entry`) -
October: 29 orders, 15 filled, 6 won, +4.86 R, 200 -> 234.15 USD. (The 23.6 % row with +7.61 R used the
withdrawn `latest` mapping and is not the winner.)

**Claude's expectation, written before the run:** October's +0.32 R a fill came from 6 wins in 15. The
research script (all hours, one year of M5) put this entry at about +0.31 R a trade over 149 trades, so I
expect September to be positive but smaller - **8-20 fills, +0 to +0.3 R a fill** - and I would not be
surprised by a small loss: one month of 10-20 trades swings by more than 1 R a trade.

**Result (2026-10-29, after the bot code was committed at 87015cc - full suite 4094 passed):**
September 2026, the October winner unchanged: **28 orders, 8 filled, 1 won, 7 lost, -4.61 R, 200 -> 147.85
USD**, deepest fall 110.72 USD. The fills: six BUYs (04/09, 10/09, 21/09, 22/09, 24/09, 25/09) all stopped
while gold fell from about 4,480 to 4,280; one SELL stopped (15/09); one SELL won +2.53 R (25/09 21:00).
Stops 11.6-23.2 USD.

**Against the expectation:** 8-20 fills, 0 to +0.3 R a fill expected - 8 fills, **-0.58 R a fill**: outside
it, on the losing side. **The October result did not hold in September.** By the ground rule written before
round 1, that means **no variant has passed; the setup is not an edge as built.** Claude's reading of the
fills, not measured: September was a falling month and six of the seven losers were buys at bottoms of the
M5 legs - the side from the entry timeframe (`entry`) took reversals against the larger fall.

### The owner on September: the side was wrong (2026-10-29)

The owner: *"the big trend was down and the trade bought - that alone is already wrong."* **The owner's rule
from the start (METHOD 2e): the H1 trend gives the side.** The October winner used `fib_side = entry` - a
Claude variant that drops the owner's H1 rule - and so did `any`. **Neither should have been a candidate:
only variants that keep every owner rule may be chosen.** From here the Fibo runs keep `fib_side = h1`.

**Next run, chosen before it (written 2026-10-29):** October, M5 (and one M15), `fib_side = h1` under both
H1 readings (`lows`, `strict` - both Claude's readings of "the H1 trend"), entries 61.8 / 38.2 / 23.6 %,
100 % at the start high, target 161.8 %, count off (one 61.8 % with the count on). The best on October is
run on September once. **Caveat stated now:** September has already been seen once, so this second check is
weaker than the first - its result is reported as such.

**Claude's expectation:** keeping the H1 side cuts the trades to about half and removes most September-type
losers; I expect the 61.8 % rows to stay positive on October with 5-12 fills, and do not know the sign on
September.

**Where the September buys came from - Claude's trace, confirmed by Codex (2026-10-29):** the code did what
the variant said. With `fib_side = entry` the fib path evaluates both the BUY and the SELL view and never
filters them by the H1 side it has just read (`eye/bot2e.py` ~869-930). At the six buys the H1 reading was:
04/09 lows none / strict SELL; 10/09, 22/09, 24/09, 25/09 SELL / SELL; 21/09 BUY / BUY. So five of the six
buys were against the H1 side the bot itself read. `h1_side()` matches its spec; the closed-bar cut is not
involved. With `fib_side = h1` a BUY cannot be written while H1 says SELL. **Not a code bug - Claude's
choice of a variant that drops the owner's rule.** `fib_side = entry` / `any` are comparison only from here,
never candidates.

**October with the owner's H1 side (the run chosen above):**

| variant (M5 unless said) | orders | fills | won / lost | R | USD from 200 | deepest fall |
|---|---:|---:|---:|---:|---:|---:|
| 61.8 %, H1 lows | 14 | 10 | 4 / 6 | +3.50 | 254.42 | 43.52 |
| 61.8 %, H1 strict | 9 | 7 | 3 / 4 | +3.27 | 265.09 | 26.29 |
| 38.2 %, lows / strict | 18 / 12 | 10 / 8 | 1 / 9, 1 / 7 | -6.19 / -4.11 | 150.18 / 168.86 | |
| 23.6 %, lows / strict | 19 / 13 | 10 / 8 | 1 / 9, 1 / 7 | -4.00 / -1.97 | 163.81 / 187.78 | |
| 61.8 %, lows, count on | 1 | 0 | - | 0 | 200.00 | |
| 61.8 %, strict, M15 | 6 | 1 | 0 / 1 | -1.01 | 150.46 | |

Against the expectation: 61.8 % stayed positive with 7-10 fills - as expected.

## Revision 7, October - the four paired runs (2026-10-29, the owner: "run it")

Code fff8c1a (spec reviewed, code reviewed twice, full suite green). M5, H1 side (lows), entry 61.8 %, 100 %
at the start high, target 161.8 %, R19, R20; `fib_stop` line / swing x `fib_level` off / on. The trades are
drawn (`eye/trades/<variant>/`) and judged against the rules before any number is believed.

**Claude's expectation, written before the run:** R19 and R20 remove most of the 14 orders of the old run -
I expect **3-7 orders a variant**, `fib_level = on` fewer still (0-3); with so few, the R and USD figures say
nothing yet; the point of this run is whether every drawn trade keeps the rules.

**Result and the drawn trades judged (Claude, 2026-10-29; `eye/trades/r7_*/`):**

| variant | orders = fills | won / lost | R | USD from 200 | trades |
|---|---:|---:|---:|---:|---|
| line, level off | 4 | 1 / 3 | -0.59 | 201.93 | 07/10 SELL target; 14/10 SELL stop; 19/10 BUY stop; 26/10 SELL stop |
| swing, level off | 2 | 1 / 1 | +1.47 | 220.07 | 07/10 SELL target; 19/10 BUY stop |
| line, level on | 2 | 0 / 2 | -2.06 | 174.45 | 14/10; 19/10 |
| swing, level on | 1 | 0 / 1 | -1.02 | 180.06 | 19/10 |

R19 refused 788-813 bars ("leg has run") - the largest gate; R20 removed 09/10. Against the expectation: 1-4
orders (expected 3-7; level on 0-3) - lower than expected, and far too few for any number to mean anything.

Judged against the rules: **07/10** keeps every rule. **14/10** and **26/10** (line stop) put the stop under
the latest lower high (4162.82 / 4163.42; 4004.20) - inside the structure; the swing stop removes both (their
R falls under 2). **19/10** - with the swing stop beyond the higher low 4163.28 it keeps the stop rule, but its
leg is from Friday 16-17/10 used on Monday 06:55; **26/10** likewise (Thursday 23/10 -> Monday). **Every
remaining doubtful trade is a leg carried over a weekend** - the open "leg life" point. No other rule broken
in the drawn trades.

## The H1 lean and the major levels - tested (2026-10-29, the owner: *"find the answers by testing and proof"*)

Two questions the built bot raised: its H1 lean refused the owner's 27/10 buy, and its rule-8 bands capped
most targets below R 2 (almost no orders in October). The expectation was written before the runs:
`eye/research/lean_levels/EXPECTATION.md`. Scripts: `eye/research/lean_test.py`, `band_test.py`, `lean_day.py`;
output in `eye/research/lean_levels/`. No bot run.

### The H1 lean (lean_test.py) - 2,720 hourly window moments, 2025-10-08 .. 2026-10-27

The lean computed as the bot does; the outcome: which barrier an M5 bar's high or low touches first within 24 h,
the moment's close +X or -X (a bar touching both, or neither touched: not counted), X = k x the median of the last 20 H1 ZigZag legs. **The median H1 ZigZag leg is 94 USD** (quartiles 78-112):
an H1 pivot is a swing of days, so the lean reads a structure of days.

| X | lean BUY: up first | lean SELL: down first | all moments: up first |
|---|---|---|---|
| 0.25 (~24 USD) | 0.487 (n 1,068) | 0.506 (n 1,169) | 0.478 |
| 0.5 (~47 USD) | 0.505 (n 842) | 0.508 (n 959) | 0.489 |
| 1.0 (~94 USD) | 0.557 (n 377) | 0.565 (n 418) | 0.471 |

The binomial +/- 0.03 (0.05 at 1.0) understates the noise: the moments are several a day with overlapping 24 h
outcomes (Codex, review). The month is the sturdier unit: by month (X 0.5) the lean side came first 0.37 to 0.67,
**above 0.5 in 6 of 13 months**; October 2026 0.398 (n 128).

- **Measured:** for moves of the size traded (24-47 USD) the lean side comes first about as often as not, and
  in half the months less. For moves of a whole H1 leg (~94 USD) 0.56 - a possible edge, on overlapping samples.
- **27/10** (`lean_day.py 2026-10-27`): lean SELL 00:00-18:00 Thai from `Hf` 4034.23 of **23/10 20:00** - a
  pair of pivots four days old; price had ranged 3975-4034 since. The H1 high of 27/10 00:00 (4029.83) was fixed
  only at 19:00, the low of 15:00 (3989.14) only at 04:00 the next day. The lean went BUY at 22:00, after price
  had risen from 3989 to 4052.
- Expectation against the result: expected a 52-56 % edge at the traded sizes; measured none.

### The levels (band_test.py) - 43,914 band reaches on M5, 2025-10 .. 2026-10

Rule-8 bands (H1 or H4 fixed pivots, last 500 bars, >= 24 h old, +- 0.10 x the median of 20 legs - H1 half-width
~9.5 USD, H4 ~17.6 USD). At every M5 reach of a band from outside: a turn (W = 2 x the half-width back beyond the
near edge) or a break (W beyond the far edge), first within 24 h. The control: the same bands centred at the
midpoints of the same legs. Turn rate = turn / (turn + break); the test favours turns (the break has the band's
width more to go), so only real against control means anything.

| | real, all | 1 pivot | 2 pivots | 3+ pivots | control, all |
|---|---|---|---|---|---|
| H1 | 0.658 (n 14,025) | 0.663 | 0.683 | 0.617 | 0.679 (n 14,889) |
| H4 | 0.701 (n 5,118) | 0.693 | 0.688 | 0.732 | 0.733 (n 4,706) |

The control's own split by "pivots" counts pivots near a leg's midpoint - not comparable; each real group is
compared with the control as a whole. **Correction (Codex, review):** an earlier version of this section said no
group beat its control; on the raw counts the H1 2-pivot bands (0.683) are above the control (0.679 all; 0.644 for
the control's 2-pivot split). The raw counts also repeat one band many times with overlapping outcomes, so the test
below de-clusters and compares month by month.

**De-clustered** (the first reach per group, day and direction) and **by month** (the group's turn rate minus the
control's, each month):

| | 1 pivot | 2 pivots | 3+ pivots | control |
|---|---|---|---|---|
| H1, turn rate (n) | 0.691 (408) | 0.703 (337) | 0.649 (208) | 0.685 (496) |
| H1, minus control by month: mean, months above | +0.007, 6/13 | +0.017, 6/13 | -0.026, 4/13 | |
| H4, turn rate (n) | 0.664 (214) | 0.669 (181) | 0.758 (99) | 0.734 (368) |
| H4, minus control by month: mean, months above | -0.031, 4/13 | -0.078, 2/12 | +0.033, 4/8 | |

- **Measured:** no tested band group turns price more than the control with any consistency - the best are above it
  in half the months or fewer, by a mean of 0.03 or less against a month-to-month spread of 0.07-0.16.
- Expectation against the result: expected 2+ pivot bands at 55-60 % against a control near 50 %; measured no
  group consistently above the control.
- **What it means for rule 8 [Claude's reading]:** none of the tested band definitions (H1 / H4 pivots, rule 8's
  width, by pivot count) is shown to be respected more than any other price; the "band" step cut targets on no
  evidence. Other level definitions are not tested here.

### Next - other readings of the H1 lean (the plan and the expectation, written before the run)

The owner keeps H1 as the lean (METHOD 2e: the larger timeframe is never ignored); the reading of rule 1 showed no
edge. Each candidate below is a reading of the **closed H1 bars** at the moment [Claude], measured exactly as above
(`lean_test.py`: the same 2,720 moments, the same outcome, k 0.25 and 0.5; a moment with neither barrier
touched, or both on one bar, is not counted). Every candidate reads the same closed H1 frame the bot cuts:

| candidate | BUY lean when (SELL the mirror; otherwise no lean) |
|---|---|
| A - rule 1 as written | the baseline above |
| B - rule 1 on a faster ZigZag | rule 1 on H1 pivots of ZigZag depth 5 (deviation 5, backstep 3) |
| C - EMA | the last H1 close above EMA(50) of H1 closes, and that EMA higher than 5 bars before (`app.indicators.trend.ema`) |
| D - the last day | the last H1 close above the close 24 H1 bars before by more than ATR(14) of H1 (`app.indicators.volatility.atr`) |

**Passes** if, at k 0.25 and at k 0.5: the lean side comes first at least 0.55 of the counted moments on each
side (BUY and SELL), with at least 300 counted moments on each side; at least 0.53 on each side in each half of the
year (2025-10..2026-03 and 2026-04..2026-10), with at least 100 on each side in each half; and above 0.5 in at least
9 of the 13 months (both sides together). The best of those passing (the highest lean-side-first rate at k 0.25, BUY and
SELL counted moments pooled) is brought to the owner for
rule 1. **If none passes**, that is brought to the owner: what replaces the lean is the owner's to say.

**Expectation (not a result):** none passes. B a little above A (0.51-0.53, faster pivots but the same idea); C and D 0.49-0.53 -
gold's moves of 24-47 USD inside a day turn as often as they run on.
