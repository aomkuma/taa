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

### Other readings of the H1 lean - the result (lean_cands.py, 2026-10-29)

The plan above, run as written (`eye/research/lean_cands.py`; `eye/research/lean_levels/lean_cands_summary.txt`). Candidate A
reproduces `lean_test.py` exactly (0.487 / 0.506 at k 0.25), so the four are measured alike.

| candidate | with a lean | k 0.25: pooled (BUY / SELL) | k 0.5: pooled (BUY / SELL) | months above 0.5 (k 0.25 / 0.5) | passes |
|---|---|---|---|---|---|
| A - rule 1 | 0.83 | 0.497 (0.487 / 0.506) | 0.506 (0.505 / 0.508) | 4 / 6 of 13 | no |
| B - ZigZag depth 5 | 0.85 | 0.520 (0.502 / 0.537) | 0.510 (0.497 / 0.522) | 7 / 8 | no |
| C - EMA(50) | 0.91 | 0.517 (0.501 / 0.534) | 0.520 (0.517 / 0.523) | 6 / 7 | no |
| D - the last 24 h | 0.74 | 0.517 (0.506 / 0.530) | 0.507 (0.506 / 0.509) | 8 / 6 | no |

n per side 772-1,251. In every candidate the BUY lean came first 0.53-0.58 in the first half of the year and
0.42-0.48 in the second: the reading follows whichever way the half-year drifted, not the next move.

- **Measured:** none passes - no reading of the closed H1 bars tested here tells the side of the next 24-47 USD
  move better than 0.52 pooled, against a bar of 0.55.
- Expectation against the result: expected none to pass, B at 0.51-0.53 (0.520 / 0.510) and C, D at 0.49-0.53
  (0.517-0.520 / 0.507-0.520) - as expected.
- Brought to the owner: what replaces the lean is the owner's to say. Rule 1 stays as written until then.

### Strong moves - do they carry on? (lean_strength.py, 2026-10-29, the owner: *"on a very clear trend day, would trading against it lose?"*)

Expectation written before the run (`eye/research/lean_levels/EXPECTATION.md`, test 3). The same 2,720 moments; the strength = the
move of the last 24 closed H1 bars in ATR(14) units of H1; the outcome as before (k 0.25 / 0.5): the move's side
first.

**The buckets set before the run were wrong for the measure:** a 24-bar move in 1-bar ATR units is large by nature
(median 2.3), so ">= 3 ATR" held 39 % of the moments - not "strong". By the planned buckets continuation was
0.489-0.522 (k 0.25) and 0.495-0.534 (k 0.5). Re-cut **after the run** by the strongest share of moments:

| strongest | |move| at least | k 0.25: continuation first (n, months above 0.5) | k 0.5 |
|---|---|---|---|
| all | 0 | 0.510 (2,686, 8/13) | 0.510 (2,159, 7/13) |
| top 25 % | 3.9 ATR | 0.529 (677, 7/13) | 0.519 (568, 7/13) |
| top 10 % | 5.7 ATR | 0.567 (270, 72 days, 8/13) | 0.529 (238, 5/13) |
| top 5 % | 6.6 ATR | 0.504 (135, 48 days, 4/13) | 0.496 (123, 3/13) |

- **Measured:** even the strongest 24 h moves carry on into the next 24-47 USD about as often as they turn; the top
  10 % at 0.567 (k 0.25) falls back to 0.504 in the top 5 %, so no steady pattern. The re-cut thresholds were chosen
  after seeing the data.
- Expectation against the result: expected 0.55-0.60 for the strongest moves; measured about 0.50-0.57, not
  steady.
- **Not answered here:** this counts which barrier price touches first, not the bot's trades (a pullback entry,
  a stop beyond it, a 1.618 target). September's loss was trades. The bot itself, run with and without the lean,
  measures it (below - October only, under 30 fills, not judged) (the owner's word, 2026-10-29: *"if you want to try option three first, go ahead"*).

## The bot with and without the H1 lean - October (the plan and the expectation, written before the run)

The owner, 2026-10-29: *"if you want to try option three first, go ahead"*; and on how to judge it: every
direction statistic comes out near 50 % - what matters is how the rules put the trades on the winning side. So
the measure is the trades: R per filled trade after costs, the win rate against the break-even rate 1 / (1 + R),
the size of the losers. `eye/bot_research.py --from 2026-10-01 --to 2026-10-27 --variants
eye/research/lean_onoff.json`: `r8_lean_on` (the defaults, commit with `fib_lean`) and `r8_lean_off`. Every trade
drawn (`eye/draw_trades.py`) and judged by eye before any number is believed.

**Expectation:** few fills either way (under 30 - not judged on its own, rule 15); off has more orders (the lean
refused about half the candidates), and its extra trades are counter-lean BUYs and SELLs whose R per trade is no
worse than the on trades' - the lean showed no edge on direction. If the off trades lose clearly more, the lean
does something the direction test missed.

### The result - October 1-27 (2026-10-29)

`eye/research/r8_lean_on/`, `r8_lean_off/` (ledgers and logs not committed; `summary.csv` is); every decision drawn
(`eye/trades/r8_lean_off/`, the on run's eight decisions are among them - same ids and prices). Winning trades are
at +2.05 to +2.49 R, so the break-even win rate is about 0.31.

| | decisions | filled | won | R total | R per fill |
|---|---|---|---|---|---|
| lean on - legs | 7 | 6 | 1 | -2.71 | -0.45 |
| lean on - ranges | 1 | 1 | 0 | -1.03 | -1.03 |
| **lean on - all** | 8 | 7 | 1 | **-3.74** | **-0.53** |
| lean off - legs | 11 | 9 | 3 | +1.19 | +0.13 |
| lean off - ranges | 19 | 12 | 4 | +0.21 | +0.02 |
| **lean off - all** | 30 | 21 | 7 | **+1.40** | **+0.07** |

- **Measured:** with the lean on, 7 fills, 1 won. With it off, 21 fills, 7 won (0.33, about break-even), +0.07 R a
  fill. Two of the off run's three extra leg fills are winners the lean had refused (07/10 SELL +2.49, 08/10 BUY
  +2.42). **21 fills - under the 30 rule 15 asks; not judged.**
- Expectation against the result: expected fewer than 30 fills (21), more orders off (30 against 8), the off trades
  no worse (better on these few).
- **Seen on the drawn trades [Claude's reading, to discuss with the owner]:**
  - **The range trades are mostly not ranges.** Rule 11 takes the latest two fixed M5 pivots as the range whenever
    M5 has no trend; 19 of the off run's 30 decisions are such "ranges", their two pivots 25 minutes to 5 hours apart
    (01/10: 21:10 -> 21:35, 23.55 USD). Selling at 88 % of one fresh up-swing (16/10, 12/10) is fading an impulse,
    not trading the edge of a sideways market.
  - **A stale leg:** 26/10 13:00 BUY drew its Fibo on 23/10's leg (4034.23 -> 3975.58, three days old) after price had
    made newer swings; stopped.
  - 01/10 BUY: the order sat at 61.8 % after price had already bounced to 4185.86 - near the 100 % - and come back;
    stopped.
- **The owner's answer (2026-10-29):** sideways is read on **H1** and the trend for the entry on M5; the range counts
  after price has gone back and forth inside it, and the trade is from its third leg to its fifth. The range rows
  above (lean on 1, lean off 19) were **Claude's misreading** - a range read on M5 and faded at its edges - and that
  rule is withdrawn (BOT_RULES rule 11 rewritten). The leg rows stand as measured.

## The current build - October 1-27 (the plan and the expectation, written before the run)

The owner, 2026-10-29: *"run it"*. The build at commit 613f00f (BOT_RULES with rule 11 rewritten: sideways read on
H1, the H1 range's side in legs 3-5, its edge as the target), `eye/bot_research.py --from 2026-10-01 --to 2026-10-27
--variants eye/research/r11_onoff.json`: `r11_lean_on` (the defaults) and `r11_lean_off`. Judged by the trades: R per
fill after costs, the win rate against the break-even 1 / (1 + R), the losers; every decision drawn and checked by eye
against the rules before any number is believed.

**Expectation:** fewer decisions than the pre-rewrite lean-off run (30) - the M5 range orders are gone; H1 reads as
sideways on part of October (the 23-27/10 range at least), where the range's side replaces the lean; the edge target
lowers R, so some sideways legs fall under 1:2. Fills under 30 in each variant - not judged on October alone. The leg
trades of the pre-rewrite runs that fall outside an H1 range should repeat unchanged.

### The result (2026-10-29 evening)

`eye/research/r11_lean_on/`, `r11_lean_off/`; every decision of the off run drawn (`eye/trades/r11_lean_off/` - the on
run's eight decisions are among them, same ids and prices).

| | decisions | filled | won | R total | R per fill |
|---|---|---|---|---|---|
| lean on | 8 | 7 | 1 | -3.73 | -0.53 |
| lean off | 15 | 12 | 3 | -1.89 | -0.16 |

- **H1 sideways** was read on 10 October days, about 8 % of the evaluated bars (218 of 2,511 log rows, lean on), all in
  legs 3-4. **No order was written while H1 was sideways**: the reasons there - the leg had run (142), against the
  range side (45), no bounce / price not above the order price (25), trend run at the limit (6). The H1 ZigZag fixes
  late: on 26/10 the 23/10 range had only 2 fixed pivots until the evening; it read sideways from 26/10 19:30.
- **Measured:** both runs lose; the wins pay +2.40 to +2.49 R, the break-even win rate about 0.30; off won 3 of 12
  (0.25). Under 30 fills - not judged.
- Expectation against the result: fewer decisions than 30 (15) as expected; sideways on part of October, as expected,
  but **no range trade at all** - not expected.
- **Seen on the drawn trades [Claude's reading, to discuss with the owner]:**
  - **Old legs:** the leg can be days old - 19/10 BUY on the 16-17/10 leg, 26/10 SELL and BUY on 23/10's legs (across
    the weekend); all stopped. Rule 2 gives a leg no age limit [Claude].
  - **Orders placed after price has already come back to the level from far beyond it:** 01/10 BUY (price had
    returned from 4185.86, near the 100 %), 05/10 BUY, 19/10 BUY (price at the 61.8 % line after hours of drift) - a
    level reached slowly, not a pullback turning; stopped. The owner: price that reaches a level tends to carry on.
  - The three winners (07/10 SELL, 14/10 SELL, 16/10 SELL at 19:25) were fresh legs, decided within a few hours of
    the leg's end.

### The bot's H1 reading against the owner's October H1 chart (2026-10-29)

The owner showed the October H1 chart and asked only to compare it with what the bot reads. `eye/research/
h1_read_month.py 2026-09-24 2026-10-28` draws the bot's own reading for every H1 close (rule 11, rule 1) over the
candles: `eye/trades/h1_read_2026-09-24_2026-10-28.png`.

- **The owner's chart:** price in a range of about 4080-4220 from the end of September to about 21/10, then a break
  down, then a range of about 3980-4080 from 22/10.
- **The bot's reading:** H1 sideways **14 %** of the hours, in short patches with edges of their own (around
  05/10, 08/10, 14/10, 21/10 and 26-27/10 - the last 3987-4034); lean SELL **51 %**, lean BUY **27 %**, none 9 % - the
  lean flips inside the owner's range (BUY 09-13/10, SELL 14/10, BUY 15-19/10, SELL from 20/10). The 4080-4220 range is
  never read as one range.
- **Why [Claude's reading of the code]:** rule 11 needs every fixed H1 pivot after the first two to sit in an edge zone
  (88-127 % / -27-12 %); the range's middle swings (4130-4190) are pivots too, so each one ends the range.

### Where the bot reads M5 wrongly (2026-10-30, the owner: *"find the trend on M5 - a win rate this low means trading against the market on M5"*)

`eye/research/m5_structure_check.py` reads the M5 structure at each filled decision (the latest two fixed M5 highs
and lows at the decision: higher high and higher low = UP, lower high and lower low = DOWN, otherwise MIXED) for the
October runs `r11_lean_off` and `r8_lean_off` (25 distinct fills).

| M5 structure at the decision, against the trade | fills | won | R | R per fill |
|---|---|---|---|---|
| with the trade (UP for a BUY, DOWN for a SELL) | 5 | 3 | +5.20 | +1.04 |
| MIXED - no M5 trend | 20 | 5 | -4.45 | -0.22 |
| against the trade | 0 | - | - | - |

- **Measured:** no trade was against a clear M5 trend; **20 of 25 were taken when M5 had no trend at all**, and those
  lost; the 5 taken with the M5 trend won 3. 5 and 20 fills - far too few to conclude.
- **Where it comes from in the rules [Claude's reading]:** rule 3 as it was then (now `m5_trend` h100, a record -
  rule 3 reads the trend at the decision since 2026-10-30) tested the M5 trend **once, at `H100`** - `H100` above
  the one M5 high before it - and never at the decision. By the decision the pullback has made its own lower lows, and
  M5 is often no longer rising; that rule still passed. The owner's 27/10 example (three legs down, then the high broken,
  then the run) has the M5 trend turning back up before the entry.
- `eye/research/m5_break_check.py` (whether the pullback's last swing was broken before the decision) is kept; its
  reference is `H100` itself on a one-leg pullback, so it does not separate the cases.

### The H1 state on four months - the reading is not yet the market's (2026-10-30)

The owner: *"I don't call that passing - passing is the bot reading the chart as close to the market as possible."*
The H1 state as built (rule 11, the prototype `read()` - call it **v1**) was run on its own, without trading, on every
H1 close of July-October 2026 and drawn, coloured by the side it allows (`eye/research/h1_read_month.py`,
`eye/research/h1_state.py`, images `eye/trades/h1_read_*.png`, `h1_state_v*_*.png`).

- **v1 fails in a trend.** August 2026 rose 4020 -> 4697; v1 read it sideways all month and, from 10/08, allowed **SELL
  only** through the rise 4311 -> 4697. Cause [Claude]: a touch widens the edge with no cap, and the break is tested
  after the widening, so a trend keeps stretching the range and never breaks it. July too read 100 % sideways (a
  4023-4369 range held from May).
- **v3** (research only: the closes leading into each pivot tested against the range as it stood before it; no
  widening): August close to the market - BUY on the rise, SELL in the mid-month chop, BUY on the break up, SELL on
  the fall from 28/08; but October's range broken mid-month and read as alternating trends, and July held the old
  4023-4369 range with BUY all month.
- **M30** (the owner's suggestion; M30 built from the stored M15, v1, `eye/research/state_tf.py`, images
  `eye/trades/state_M30_v1_*.png`): August mostly BUY on the rise and SELL on the fall from 28/08, but SELL on its
  start (01-05/08); October's range 4066-4229 seen, the break down on 22/10 seen, but legs past 6 from 15/10 (no side);
  July 70 % SELL.
- **Measured, not judged by a number:** no version yet reads all four months the way the candles move. The common
  cause [Claude]: how a range is started (from which pair of pivots) and widened; the timeframe changes the scale of
  the problem, not its cause.

### The state on M30 - v2, v4, v5 (2026-10-30, step 1 of HANDOFF "Next"; research prototype, no trading)

`eye/research/state_tf.py <first> <last> M30 <mode>` on July, August, September and 24/09-28/10, images
`eye/trades/state_M30_<mode>_*.png`. Every version below is [Claude]'s, written before its run.

| Version | What it changes | Expected | What the drawing shows |
|---|---|---|---|
| v2 on M30 | v1's wick edges; closes tested before each pivot is taken in; a touch widens an edge only up to the break level | close to v1 | **almost identical to v1** on all four months (October: range 4071-4229, legs 6+ from 15/10, break down 22/10; August SELL 01-05/08 and 14-18/08 through rises; July SELL 70 %). The cap rarely binds on M30. |
| v4 | as v2, but the edges are the pivots' extreme **closes**, not wicks (a wick past the bodies does not move an edge) | October's range about 4080-4215, the break down earlier than 4022 | **worse**: close-based two-pivot ranges are narrow and break all the time - sideways 8-37 %, October's range never seen (BUY 09-14/10, then SELL 14/10-27/10 through the range), August 18-20/08 SELL through the 4330 -> 4520 rise |
| v5 | as v2, and after a break the **breaking leg itself** (its two pivots) starts the next range - to close a gap found in v2-v4: after a break nothing is tested until two new pivots fix, so a V-shaped turn keeps the old trend | turns read sooner | **fails**: a breaking leg is a long move, so its range is huge and never breaks again - October SELL for a month (90 %), August BUY 100 % including the fall on 28/08, September BUY 88 % through the fall |

- **Measured:** none of v2, v4, v5 reads the four months better than v1 on M30. v1 / v2 remain the closest:
  October's range and its break are seen (late), the rest of the failures stand.
- **Found in the code [Claude]:** in v2-v4, after a break the trend holds until two new pivots fix; on a V-shaped
  turn that is long. v5's way of closing it fails; the gap is still open.
- **[Claude's reading]:** each change trades one month for another because the target is known only for October
  (the owner's 4080-4220 range, the break down, 3980-4080 from 22/10) and for August's rise. Tuning further against
  Claude's own reading of July and September would be METHOD 2d again; the owner's reading of those months is the
  acceptance target that is missing.

### What a range is - outside sources, and why the bot draws it wrongly (2026-10-30)

The owner: research the basics (what a price range is, what ZigZag is and how it is used) from outside sources
before asking. What the sources say (mostly broker / education sites and secondary summaries of Wyckoff and Al
Brooks, not their own texts):

- **A range** is price moving back and forth between a floor and a ceiling, **testing the same edges more than once**
  (some say two to three bounces before it counts). Wyckoff: a range follows the end of a trend - the climax's extreme
  and the first rally (reaction) after it set the edges, and a later test of the climax's area confirms them. Brooks:
  a trend flattens into a range; in a range most breakout attempts fail. A break is a close beyond an edge; a broken
  edge often changes role.
- **ZigZag** joins alternating swing highs and lows and drops moves under its threshold (MT5: Depth 12 sets the swing
  size most; Deviation 5, Backstep 3). The last leg repaints - only fixed pivots are used (the bot does). Higher highs
  and higher lows = up, lower highs and lower lows = down; a range's edges are drawn through recent swing highs / lows.
- Sources: therighttrader.com (trading range), journalplus.co (range trading), vtmarkets (sideways markets), fxtm
  (range in forex), OANDA Japan (MT5 ZigZag settings), LuxAlgo (ZigZag structure; Swing High/Low), Wiley (Al Brooks,
  *Trading Price Action: Trading Ranges*), the Brooks course forum, TradingView (Wyckoff anatomy of a trading range).

**Why the bot draws the range wrongly** - against the sources:

| | cause | measured / reading |
|---|---|---|
| 1 | an edge widens on every touch beyond it, without a cap - a trend stretches the range instead of breaking it | measured: August read as a range, SELL through the rise (H1) |
| 2 | a wick moves an edge | measured: M30 v1 low edge 4066 from the 07/10 wick; the owner's 4080 |
| 3 | a wide range breaks late (27 % of a stretched height) | measured: H1, 22/10 BUY leg 5 while price fell through the edge |
| 4 | after a break, nothing is tested until two new pivots fix | found in the code (v2-v4) |
| 5 | **any two consecutive pivots start a range at once** - the sources start it at the end of a trend and want the edge tested again | Claude's reading, not yet traced on the drawing |
| 6 | the walk starts at the first pivots of the 1,500-bar window, which slides - an old range can carry on | measured on H1 (July held May's 4023-4369); not checked on M30 |

**Agreed with the owner (2026-10-30), for the next prototype mode** - build on what exists, change only what is wrong:
keep the fixed ZigZag pivots, M30 from M15, the touch zones 88 / 12 %, the break at 27 % (the owner's 127 %), the leg
count and "sideways from two legs" (it already means the first edge was tested again), v2's order (closes tested
before a pivot is taken in), `state_tf.py`, and the uncommitted H1 build with its tests. Change: (1) a range starts
at the trend's last extreme and the first bounce from it, not any two pivots; (2) a pivot beyond an edge but short of
the break level is a touch and does not move the edge - a close beyond the break level is a break; (3) the walk starts
further back so an old range does not carry from the window's start. v4 and v5 are dropped.

### Closes between two ZigZag pivots (2026-10-30, measured for rule 11's text)

Claude wrote into rule 11 that the closes between two consecutive pivots lie between their prices "by the ZigZag's
construction"; checked on the stored M30 bars (built from M15, 38,331 bars, ZigZag 12/5/3 on 3,000-bar frames every
1,000 bars): **125 of 6,282 pivot pairs had a close outside the two pivot prices, by up to 16.04 USD**. The claim was
wrong and was taken out; rule 11 now ignores the closes between `E` and `B` as a rule, not as a property of ZigZag.

### Rule 11 and the looks read by five models (2026-10-30, the owner: "send it to every model on this machine")

The same read-only brief (ambiguities, contradictions, attributions, trading sense, a hand trace) to Codex, Sonnet,
Opus, Fable and Haiku, on `eye/BOT_RULES.md` after the looks were written. Claude grouped the findings and checked the
ones a file can settle.

| # | Finding | Models | Claude's check | Kind |
|---|---|---|---|---|
| 1 | **A look's walk starts by taking its first two pivots as a range**, and the look slides every bar - the state can change with no new price (a pivot leaves the look), and a trend cut at the look's start is read as a range | all five | true, from the text (the short looks make it much more frequent than the 1,500-bar frame did) | design - the owner's |
| 2 | **A pivot beyond the first edge, short of the 127 % close, counts as a test** - a staircase trend (a higher high after a shallow pullback) is read as a range and sold | Sonnet, Opus, Fable, Haiku | true; it is Claude's [Claude] reading of "without a new extreme beyond it", against its plain sense | design - the owner's |
| 3 | The two walks' combination leaves a case open: range look trending, trend look "neither"; and a fresh break on the range look is ignored when the trend look is sideways | Opus, Fable, Haiku | true (rule 11, "Only when neither walk...") | text |
| 4 | "No trend on the 7 days is a range" vs the 7-day walk "neither" (legs 1) giving no side | Sonnet, Opus, Fable | true | text, follows the owner's sentence |
| 5 | The `state_tf` H1 acceptance values come from prototype v1 (edges that widen) and cannot be produced by the new text | Sonnet, Opus, Fable | true (`lo` 4110.78 -> 4104.21 -> 4066.42 inside one range) | text |
| 6 | "the owner's 127 % line" - the break at 127 % is Claude's (the owner gave 88-127 % as the entry zone) | Sonnet, Fable, Haiku | true (rule 11) | attribution |
| 7 | Rule 2 "with no age limit" vs the 2-day setup look | Fable | true | text |
| 8 | A second break the same way - say plainly that it starts a new `E` / `B` | Sonnet, Haiku | the text implies it | text |
| 9 | The structure written (rule 14) does not say which look gave the state | Fable | true | text |
| 10 | Rule 13 still says "the lean nor the M30 range"; the break written once as "beyond its edge", once as 127 % | Opus, Sonnet, Haiku | true | text |
| 11 | Opinions, not checked: a tiny `h` after a break flickers; a deep first bounce makes `h` wide and freezes a trend against the move | Sonnet, Opus, Fable, Haiku | to be seen on the drawing | trading sense |
| - | Haiku's "quote not found" for *"confirm the two you said"* and "sideways is read on the higher timeframe" | Haiku | the first is in BOT_RULES only (from the 10-29 chat); the second is a paraphrase in rule 11, not a quote | minor |

**Measured: nothing** - this is a reading of the text. Findings 1 and 2 change what the bot reads and are the owner's
to decide; 3-10 are text fixes; 11 waits for the drawing.

After the owner's choices (1A, 2B) rule 11 was rewritten and Codex reviewed it: no contradiction, no wrong attribution;
three small points (the 2,500-bar check's settings fixed; a pivot touching both edges cannot happen - a HIGH is tested
only against the high edge; a close on a pivot bar belongs to one segment by the text). Its hand walk of an
11-pivot sequence came out decided: at the end, trending up by case 2 (the range's `E` older than 4 days, the break
inside 7).

### Rule 11's state - the stability check on July-October (2026-10-30, rule 14; a reading, no trading)

`eye/research/state11_check.py 2026-07-01 2026-10-28` on the built `eye/state11.py` (step 4, pieces 1-4; not
committed). Expected before the run [Claude]: 0 / 0 / 0, since the walk no longer starts at a look.

| | result |
|---|---|
| M30 closes checked | 3,930 |
| (a) the state from a 1,500-bar frame vs a 2,500-bar frame | **0 differences** |
| (b) changes of state | 112 - a pivot fixed 69, a close broke 38, the range look passed `E` 4, the trend look passed the break 1; **0 without a cause** |
| (c) `lo` / `hi` changed under the same `E` / `B` | **0** |

- **Fable checked the zeros are not trivial:** the 2,500-bar ZigZag differs from the 1,500-bar one over the shared span
  at 249 closes, and a 1,000-bar frame gives a different state at 304 - so (a) can fail; a cause is present at only
  286 of 3,930 closes (7.3 %), so (b) is not passed by default; all 112 changes were recomputed one by one and each
  cause confirmed. (c) is nearly true by construction (edges are the `E` / `B` pivot prices). The check functions' unit
  tests were too weak (sent back to the developer).
- **The share of each state (measured; not judged):** down 48.7 %, up 35.6 %, **sideways 15.7 %**; case 1 581 closes,
  case 2 3,312, case 3 37, **case 4 (no side) 0**. [Claude, a reading to check on the drawing, not a conclusion:] the
  state is mostly "trending" because almost every 7 days hold a break - small ranges after a break break easily (the
  five models' finding 11). Whether that matches the market is step 7's question, on the drawing.
- In 7 changes the break was dated hours before the close where it was recognised (e.g. recognised 08/07 19:00, the
  breaking close 15:30) - closes after a break are tested only once the new `B` is fixed (rule 11 as written).

### Rule 11's state drawn on July-October - Claude's eye: not yet the market (2026-10-30, step 7)

`eye/research/state11_draw.py` (step 4 piece 5), images `eye/trades/state11_2026-07-01_2026-07-31.png`, `..._08-01_08-31`,
`..._09-01_09-30`, `..._10-01_10-28`. Measured shares (closes): July BUY 38 % / SELL 62 %, case 2 91 %; August 45 / 55,
case 2 93 %; September 41 / 59, case 2 81 %, case 3 4 %; October 52 / 48, case 2 71 %, case 1 29 %; "either" and "none"
0 % in every month.

Claude's reading of the drawings (to be judged by the owner):
- **Right:** October's break down on 22/10 and the SELL after it, the 3987-4034 range of 23-27/10 and the BUY on its
  break up on 28/10; August's BUY 05-13/08 and 21-25/08 on the rise, SELL on the fall from 28/08; September's fall
  from 26/09 SELL.
- **Wrong:** August 19-21/08 - **SELL through the rise 4324 -> 4524** (after the 18/08 break down the new range is
  `E` 4324.54 / `B` 4523.91, legs 1, so the down trend holds until a close above 4577); August 01-05/08 SELL on the start
  of the rise 4030 -> 4170; July 20-23/07 SELL through the rise 3960 -> 4140; September 23-26/09 BUY through the fall
  4370 -> 4245; October's 4080-4220 range (the owner's, 01-21/10) never read as one range - the side flips about eight
  times inside it as small ranges break.
- **The common cause [Claude]:** both failure modes come from a range's height being set by one bounce. After a
  break the trend holds until the range of `E` and its first bounce `B` breaks the other way at 27 % beyond it: when
  the bounce is big (a V turn), the turn is read late, against the move; when it is small, the range breaks at once
  and the side flips on noise.
- **Verdict (Claude): not passed** - wrong in every month; back to CLAUDE.md step 1 with the owner.

### The side from price structure against rule 11 - six weeks drawn (2026-10-30; research, no trading)

The owner, on the weekly drawing of 06-10/10: *"the 7th, falling that hard in the morning - how can it buy?"*, and
when the sell came, price went sideways up - *"traded like this it always loses"*; then: *"go by the colour strip,
compared with the price structure"*. Measured on 07/10: rule 11 stayed BUY until 17:00 (the 30/09 break up, 6 days
old, still inside the 7-day look; a close below the 127 % line 4117 needed) and M30's ZigZag fixes late (the 4184.25
top of 02:00 fixed at 14:30; the 4066.42 low of 19:30 fixed at 01:30 next day).

`eye/research/structure_side.py` draws three strips under one week of M30: rule 11's side; **A** - a side from M30
structure [Claude, from the owner's 2e step 3]: a close above the latest fixed swing HIGH -> BUY, below the latest
fixed swing LOW -> SELL, otherwise unchanged; **B** - the same on M15 pivots and closes. Images
`eye/trades/structure_side_<week>.png`; side changes per week (rule 11 / A / B): 20-24/07 4 / 2 / 6; 03-07/08
3 / 3 / 7; 17-21/08 3 / 3 / 8; 21-25/09 1 / 2 / 10; 06-10/10 2 / 4 / 4; 19-23/10 5 / 3 / 5.

Claude's reading of the strips (the owner judges):
- **A and B follow the structure far better than rule 11**: 07/10 SELL from about 09:00 (rule 11 17:00); 19-21/08
  BUY on the rise (rule 11 SELL); 21-25/09 SELL through the fall (rule 11 BUY); 20-22/07 BUY on the rise (rule 11
  SELL); 22/10 SELL on the fall (all three).
- **B turns sooner** (19/08 07:00 BUY before the rise; 08/10 07:00 BUY after the 4066 low) **but flips in chop**
  (10 changes on 21-25/09, mostly 21-22/09).
- **Neither reads a range**: in sideways stretches (08/10, 20-21/10, 24/09) A holds an old side and B flips.

### The three side strips measured against the structure (2026-10-30; `eye/research/side_score.py`, research)

The owner: the strips are wrong and visible from the picture; then *"you can see M15-M30 is the closest"*. The
structure in hindsight = the final M30 ZigZag legs; a side decided at a close is held over the next M30 bar.
July 1 - October 28: 3,930 M30 closes, 22,476 USD of bar-to-bar movement, 122 legs of at least 50 USD.

| strip | right USD | wrong USD | right | strip P&L (no costs) | big legs: median lag | median share of the leg gone first | never on its side |
|---|---|---|---|---|---|---|---|
| rule 11 | 10,743 | 11,703 | 48 % | -1,004 | 1.0 h | 68 % | 47 / 122 |
| A: M30 structure | 11,203 | 11,243 | 50 % | -267 | 1.0 h | 59 % | 36 / 122 |
| **B: M15 structure** | 11,552 | 10,894 | **51 %** | **+99** | 3.0 h | **57 %** | **15 / 122** |

- **Measured:** B is the closest to the structure on every count, then A, then rule 11 - as the owner read the
  pictures. **But all three are near a coin's 50 %**: on a big M30 leg, each strip comes on its side after more than
  half of the leg is gone (the median share counts a leg never reached as 100 %; the median lag counts only legs
  reached - read the two together).
- [Claude] The M30 ZigZag's legs (122 of >= 50 USD in four months, about one a day) are short next to the time a
  structure break needs to show; a side read from breaks of the last swing comes late on most of them.

### Which side of the 50 each signal falls on - the plan and the expectation, written before any result (2026-10-30)

The owner: trading is 50/50; the work is to see, for each signal, which side of the 50 it falls on; done with Codex.
Codex reviewed the plan (no look-ahead; the owner's entry is the **retest**, not the break; the stop beyond the
extreme of the counted move; spread from the bars' stored `spread`; freeze the definitions before results; October
2026 is not clean). Discovery: M15, 2023-08 .. 2025-09; check: 2025-10 .. 2026-10 (M5 there too).

**What the study delivers:** one row per signal B (a close beyond the latest fixed M15 swing) - the owner's
conditions at that moment (divergence MACD or RSI; 3-5 peaks or the owner's M / W; a level from the left; M30
agreeing; the window) and the outcome in R net of spread, for an entry at the break and at the retest (with
no-fills).

**Expected [Claude, before any number]:**
1. About 5-8 signals a week: ~600-800 in discovery, ~300-400 in the check.
2. All signals together, net of spread: **about 0 R a signal** (slightly negative at the break; the strip P&L of
   July-October was +99 USD over four months, flat).
3. Signals meeting the owner's full set (count or M / W, with divergence where the count needs it, at a level from
   the left, M30 agreeing): **a small share, about 5-10 %**, and **better than the rest by 0.1-0.3 R a signal** in
   discovery - the level and the count doing most of it, divergence alone little.
4. The retest entry fills about half the time; **the unfilled ones are the strongest moves**, so the filled retests
   look worse than the break entry would suggest (as in the hand-walked days).
5. **Risk named now:** the edge seen in discovery shrinks in the check; it counts only if the full set stays at or
   above **+0.15 R a trade after costs with at least 30 trades** in the check period. Otherwise: nothing found, and
   back to the owner.

### The signal study's definitions audited before the study (2026-10-30)

The owner: before starting, how do we know the reference documents are right and not confusing? `eye/SIGNAL_STUDY.md`
(one table of definitions, each with its METHOD / LESSONS source and owner vs [Claude]) was audited apart by Codex and
a fresh Sonnet. Both found the first draft had **reduced the owner's entry sequence (break, higher low, the high
breaks, retest) to a single break**, and had left out the 1:2 floor, the targets, no-chasing, the M5 trend and
LESSONS' structure at the level (HH + HL / LH + LL); Sonnet listed further disagreements inside METHOD 2e. Rewritten;
Codex re-audited twice (a hand-walked BUY through S3-S5 came out decided after the last fixes). METHOD 2e corrected
in three places that contradicted the owner's later words (the summary's "MACD and RSI"; "H1" in step 1 of both
sides; "nothing open"). BOT_RULES rule 11 carries a status note: failed, not to be built on. HANDOFF has a short
current-state box at the top. Waiting on the owner to confirm the table and set the open values.

### The bot's reading of 07/10/2026, drawn - the owner's view (2026-10-30)

The rebuilt bot (H1 removed; side from M15 structure, rule 16; setup look 2 days; rule 3 `m5_trend` now) drawn for
07/10/2026 by `eye/research/bot_read_day.py` (`eye/trades/bot_read_2026-10-07.png`): **no order** on a day that fell
4168 -> 4066; the side turned SELL at 09:15; the London fall was stopped by "leg has run" (rule 10) on every bar, Asia
by "no M5 trend of its side". The owner could not read the colour strips (*"I can't read it, but I can read price -
why not draw it as in MT5, add the Fibo lines"*) and read the price: **the sell was there from about 07:00, when a
red candle engulfed the long green candle before it - a sell should have been looked for there.** (An example from
the owner's eye - information, not a rule.) Next: the chart drawn as MT5 shows it, with ZigZag and the bot's Fibo at
a moment (`eye/research/bot_view.py`).

### October 2026 with rule 3 on and off - the rebuilt bot (2026-10-31; the owner: "do it")

The bot as built on 2026-10-30/31 (`eye/BOT_RULES.md`: H1 removed; rule 16 - H4's clear trend -> a trend leg, else a
fade of the latest run; rule 2's trend leg and fade leg; rule 17 the break and its retest; setup look 2 days; defaults
otherwise, `max_orders` 1). `eye/bot_research.py`, variants `r3_now` (defaults) and `r3_off` (`m5_trend` off), 2026-10-01
.. 10-28, scored by `eye/score.py`, net of spread. Outputs `eye/research/r3_now/`, `eye/research/r3_off/`.
Expected before the run [Claude]: more trades with rule 3 off; R per trade not predictable; under 30 trades each - a
direction only.

| variant | orders | filled (resolved + open) | won | lost | R total | R per resolved fill |
|---|---|---|---|---|---|---|
| `r3_now` | 24 | 18 (17 + 1) | 4 | 13 | -3.94 | **-0.23** |
| `r3_off` | 43 | 33 (32 + 1) | 10 | 22 | +3.45 | **+0.11** |

By kind (resolved fills; `kind_of` from the structure text):

| kind | `r3_now`: n, R, R/fill, won | `r3_off`: n, R, R/fill, won |
|---|---|---|
| trend leg (H4 clear) | 6, -2.33, -0.39, 1 | 20, +2.60, +0.13, 6 |
| break and retest (rule 17) | 1, +2.38, +2.38, 1 | 2, +4.84, +2.42, 2 |
| fade (H4 not clear) | 10, -3.99, -0.40, 2 | 10, -3.99, -0.40, 2 |

- **Measured:** rule 3 off took 14 more trend legs and one more retest (07/10 07:40, +2.46) and turned the month from
  -3.94 to +3.45 R; the fades are the same in both (rule 3 never applied to them) and lost: 2 of 10 won, -0.40 R each.
  No variant reaches the owner's +0.15 R a trade; 32 and 17 resolved fills - **far too few to conclude** (one month,
  already seen; the clean test is forward).
- The summary's "fills" column counts resolved fills only (the open one is apart) - checked against the ledgers.
- Not yet done: every trade drawn and checked against the rules (CLAUDE.md step 8) before any number is believed.
