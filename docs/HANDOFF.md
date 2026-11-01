# Session handoff

Last updated **2026-11-01 Thai** (read with `Get-Date`).

**The rules and the process in force.** The owner's setup is `eye/METHOD.md` 2e. The bot's rules are
**`eye/BOT_RULES.md`** (the only spec in force; `eye/BOT_SPEC.md` is the history). Every change follows CLAUDE.md,
"How the system is developed": discuss and conclude -> record -> Codex reviews the documents -> a Sonnet developer
codes -> Codex reviews the code until no findings -> the full suite and a commit -> **the reading checked against the market on
several months, drawn, judged by Claude then the owner** -> only then, with the owner's word, a trading run, every
trade drawn. Tests green means the code matches the spec, never "passed". Every result is recorded the moment it is
measured.

**Where the work stands (2026-11-01) - read this first; the box after it (2026-10-31) still holds for the code.**

- **Paused by the owner** (*"update the documents and the handoff, then rest and do something else"*). Nothing is
  running; the last commit is 3728254 (rule 16 m15); this update (docs only) is committed after it.
- **Measured on 2026-10-31 / 11-01** (all in `eye/BOT_RESEARCH.md`, from "July - October with rule 16 m15, all day"
  to the end; the scripts in `eye/wip/prototypes_2026-11-01/` - research prototypes, not the bot, not committed):
  - The bot with rule 16 m15, July - October all day: -0.062 R a fill (213, legs on M5), -0.040 (83, legs on M15);
    `h4_old` -1.10 R in all. Losses are not the target's distance - at a 1 R target the entries win 46 %.
  - The break and retest (rule 17) was the one kind positive in all three sets (+0.23 / +0.23 / +1.22 R, few). Alone
    on every M5 leg: +0.222 R July - October (112; +0.219 with the stricter gap rule), **-0.076 on November 2025 -
    June 2026 (193; the same under both rules)**; SELL retests
    positive in both (+0.264 / +0.196; the owner had said *"the edge is when the big trend is down"*), lumpy by month.
  - Not supported by the data in Claude's forms: Fibonacci clusters or left levels marking turns; push counts; M30
    better than M15 (worse); the M / W second touch; the bounce to the 23.6 % line (the owner's 30/10 chart) on every
    leg; wave 4 at a known price (best miss a fifth of the move); legs ending on the previous leg's extension lines
    (no more than on lines between them); each wave on its textbook target. Layering 0.01 lot at every line of the
    previous leg wins 82 - 88 % of cycles but loses in total (the runs through every line; worst cycles -298 to
    -1153 USD); one line with its own stop and a Fibo target: no row over 50 % at 1:2, best +0.10 / +0.01 R.
  - Two measuring faults were caught and fixed before quoting (an order placed after price passed its line, a
    withdrawal by a target price always passes) - every simulation now asserts a stop exit has R < 0.
- **The owner's words of these two days** (METHOD 2e row "Measuring the target (2026-11-01)"): enter at the top and
  the bottom; wins over 50 % *and* 1:2, not relaxed; the turning point of the current leg is the target measured
  from the previous leg; count the points - after 5 look to sell, after 3 buy wave 4 and sell the top above; enter
  0.01 lot at every important Fibo line to learn which line works; TP at the Fibo level price can reasonably reach.
  **The owner does not believe pooled numbers** - *"they are pooled, without knowing whether it works the way I
  think"*: draw single trades first.
- **Next, when the owner resumes**: draw the trades of the best single-line form (entry 161.8 %, stop beyond 200 %,
  target 61.8 %, M15), the losing ones first, one image at a time, and ask what the owner sees that would skip them;
  the owner's choice of leg on 30/10 ("why that leg") is still unanswered. Nothing here is a rule yet; BOT_RULES is
  unchanged since 3728254.
- **The owner's run zones (2026-11-01, most of the day)** - METHOD 2e row "The run zones" (the owner's words: a box of
  gold's run, about 76 - 80 lately, drawn from a price cluster and moved along; the lines are points to watch, targets
  and turning lines; a zone shift after a full step back with the structure; SL past the liquidation zone; two
  positions - before the line and on the fake break; no fade against momentum; trade only in a sideways market -
  sideway / sideway up / sideway down - and only when gold runs about a step a day; the setup reviewed every 3 - 6
  months). Every form and measurement in `eye/BOT_RESEARCH.md` from "The owner's run zones, drawn"; prototypes in
  `eye/wip/zones_2026-11-01/` (not committed; `system_long.py` runs the whole system). **Where it stands**: v8 zones
  (two neighbouring H4 ZigZag turns 1 - 3 steps apart), variant C (P1 10 before the line, P2 15 into it, SL S/2, TP one
  step), momentum skips, the weighted D1 .4 / H4 .3 / H1 .2 / M15 .1 sideways gate: **November 2025 - October 2026,
  41 setups, +0.615 R a setup, +1378 USD at 0.01 lot a position** - built and tuned on that year; on the two years
  before (never used) no step gives an edge (-0.097 R with the range step; -0.012 / +0.055 / -0.091 with 40 / 45 / 50).
  The owner: the market then was not this setup's market, and a setup is reviewed every 3 - 6 months. Not a bot rule
  yet - the next step, at the owner's word, is BOT_RULES through the process, then months after today.
- **A side study, stopped by the owner on 2026-11-01 ~10:55 Thai: Volume Profile on XAUUSD M5** (Codex, 2026-10-31 -
  11-01; `research/xauusd_poc_m5/`, the summary in its `RESEARCH_STATUS.md`). Outside the owner's method (METHOD 2e) and
  outside the development process above; not part of the bot. About 50 trading-rule variants on FBS-Demo data to
  2026-10-28 (264 sessions, 184 development / 80 validation): fades at VAL/VAH to POC, breakouts, retests, other stops,
  targets and filters, over prior-session, 6 h, 12 h and 200-bar M5 profiles. **None met its own predeclared rule**
  (>= 20 development trades, net R positive in 2 of 3 development folds, validation positive). The one positive
  result (+4.77 R) was withdrawn when the profile was rebuilt from M1 tick_volume (-7.98 R); the best development run
  (12 h breakout, +27.51 R / 62) lost -6.02 R / 33 on validation. The last run (a 1.5x tick-volume filter on the 200-bar
  breakout) was stopped before writing a result. Limits: the owner's reference chart is OANDA, the data FBS - the
  levels are not the same; the data to 2026-10-28 has been searched about 50 times and no longer serves as a holdout.
  Not started, the owner's to decide: whether price reacts at POC / VAH / VAL more than at random levels (no trading),
  the levels drawn over months of candles, and whether Volume Profile has a place in the owner's method at all.
  Committed: the reports, scripts and small CSVs; the large CSVs (over 200 KB) are left out and regenerate from the scripts.

**Where the work stood (2026-10-31) - the code's state still holds; the rest is history.**

- **The owner's goal**: *"to know where 100 and 0 are"* - the leg's start and end read right (METHOD 2e "The goal").
- **The method** (METHOD 2e, the owner's words; `eye/BOT_RULES.md` the form, rules 2, 16, 17): **the side is held on
  M15** - an HH or the owner's M -> BUY, an LL or a W -> SELL, until the opposite (rule 16 as rewritten 2026-10-31,
  built; H4's clear trend, else fade the latest run is kept as `side_rule` h4); a **trend
  leg** of the side traded on the pullback (0 % at the leg's start, entry 38.2 %, stop beyond 0 %, target 161.8 %); a
  break past its end -> **its retest** while the M15 side at that decision is still the leg's (rule 17: target 161.8,
  else 200 %). Targets reachable first, 1:2 only a
  filter.
- **Code**: BOT_RULES is built and committed (c09c13e, 3b64f86, e98fe71; the full suite green) - including rule 0's
  `windows` (2026-10-31, the owner: *"run it all the time"*; decide at every 5-minute time, 00:00 - 23:55 Thai) and the
  parameters from the database, and rule 16's `side_rule` m15.
- **Rule 16 rewritten** (2026-10-31, step 7 found H4 "not clear" through the August rise): the side is held on M15
  until the opposite break, with the owner's M and W (an M buys, a W sells), trend legs only; the owner chose to judge
  it by a trading run (*"C"* - July to October, every trade drawn). Built.
- **The parameters from a database** (2026-10-31, the owner: *"every config value read from a db"*, per market - *"some
  markets may need some values switched off"*; a web page later): built (`eye/bot_config.py`; a fresh machine runs `.venv\Scripts\python eye/bot_config.py seed --market XAUUSD --set default --by <who>` first; research runs now write `eye/research/XAUUSD/<set>/`).
- **Step 7 started** (`eye/BOT_RESEARCH.md`, "Step 7: the leg's 0 and 100 drawn"): on 15/07 the M5 leg put 100 % at a
  small swing; **M15 put 0 and 100 where the owner reads them** (*"OK, better"*), but late; the 161.8 % target was
  beyond where price turned. The owner took Claude's proposal: measure the leg on M15, M5 for the entry - being
  drawn on more days, August - October.
- **First run, October 2026** (`eye/BOT_RESEARCH.md`, "October 2026 with rule 3 on and off"): rule 3 on -0.23 R a fill
  (17); **rule 3 off +0.11 R (32)** - trend legs +0.13 (20), retests +2.42 (2), **fades -0.40 (10)**. Under 30 per
  group, one month already seen - a direction only. **Next: draw every trade (`r3_off` first, the losing fades
  first) one image at a time for the owner, MT5-style, before believing any number.**
- **Open**: levels from the left / the owner's 2-3 price clusters as obstacles to a target (to be measured); counting
  three peaks - Elliott waves - in each wave aimed at (an idea of the owner's, not a rule).
- **How the owner wants it**: Claude supervises (Sonnet builds piece by piece, Codex reviews, Claude runs the mutation
  checks - never while an agent edits the file); MT5-style drawings one at a time; the owner reads price, not strips.

**History of 2026-10-30 (superseded by the box above; kept as the record):**

**Where the bot stands (2026-10-30).**
- **The trend timeframe is M30** (the owner: *"we change to M30 and drop 1H - change it all to M30"*): the lean (rule 1)
  and the state - sideways, trend, break (rule 11) - are read on M30, built from the stored M15 (BOT_RULES "Data");
  H1 is kept only as a record (`state_tf` H1). Specified in BOT_RULES and METHOD 2e and reviewed by Codex; **not built**.
- Built and committed: rules 0-10, 12-15 as BOT_RULES writes them - rule 8's take-profit is the Fibo extension (no
  tested level beat a control); rule 1 is the lean, kept as `h1_read` lean (no tested reading of H1 told the side).
- **Rule 11 - the state** (a range ignores its middle swings; a close beyond its edge is a break, then a trend that
  way): built on **H1** in the working tree, **not committed** - the build, its tests (the bot's 125) and a mutation
  check (22 of 24 caught) are there, backed up, with a half-done rule 3 change, in `eye/wip/` (not committed: `bot2e_h1_state_reviewed.py.txt` - the
  reviewed H1-state build; `bot2e_rule3_half_done.py.txt` and `test_eye_bot2e_rule3_half_done.py.txt` - the working tree with
  rule 3 half done; `working_tree_2026-10-30.diff`). **Its reading fails the market check**: on July-October
  the H1 version read August's rise 4020 -> 4697 as SELL from 10/08 (`eye/BOT_RESEARCH.md`, "The H1 state on four
  months"). The cause [Claude]: how a range is started and widened - a touch widens an edge without a cap and the break
  is tested after the widening. The research prototype `eye/research/h1_state.py` has v1 (as built), v2, v3 (closes
  tested before each pivot; v3 no widening); `eye/research/state_tf.py` runs it on M30 - better on August, not on all
  months.
- **Rule 3 - the M5 trend at the decision** (`m5_trend` now): specified and reviewed, **not built** - 20 of 25 October
  fills had been taken with no M5 trend (`eye/BOT_RESEARCH.md`, "Where the bot reads M5 wrongly").
- Trading runs so far are October only, under 30 fills, not judged; the last one predates these changes.
- **The working tree is not clean on purpose** - four tracked code files are modified and must not be committed as
  they are (research outputs - `eye/bot_ledger.csv`, `eye/bot_log.csv`, `eye/research/<variant>/`, `eye/trades/` - are
  untracked by design; stage only by explicit paths):
  `eye/bot2e.py` (the H1-state build **plus a half-done rule 3** - `m5_trend` started, its tests not written; the bot's
  tests may fail), `tests/unit/test_eye_bot2e.py` (the H1-state tests), `eye/draw_trades.py` (parses the new
  "H1 state sideways: lo, hi, legs, leg" structure text), `eye/research/h1_read_month.py` (calls `bot2e.h1_state`, which
  exists only in the working tree). The reviewed H1-state build without the rule 3 start is
  `eye/wip/bot2e_h1_state_reviewed.py.txt`.

**Next, in order (CLAUDE.md's process):**
1. Rework how a range starts and widens **on M30** in the research prototype until its drawing (July-October, the
   side it allows, its edges) matches the market to Claude's eye and then the owner's - August's rise BUY, October's
   4080-4220 range and its break down, July's swings - and record each attempt in BOT_RESEARCH.
   **2026-10-30 morning:** v2, v4 (edges on closes) and v5 (the breaking leg starts the next range) drawn on M30 -
   none better than v1 (`eye/BOT_RESEARCH.md`, "The state on M30 - v2, v4, v5"; `h1_state.py` modes v4, v5).
   **Then, with the owner:** what a range is was researched from outside sources and the owner agreed where a range
   starts (METHOD 2e, the Sideways row; `eye/BOT_RESEARCH.md`, "What a range is - outside sources"). **Next: a new mode
   in `h1_state.py`** building on v2 - (1) a range starts at the trend's last extreme and the first bounce, (2) a pivot
   beyond an edge short of the break level does not move the edge, (3) the walk starts further back - drawn on M30
   July-October, Claude judges first, then the owner. v4 and v5 dropped.
   **Then (the owner: "start"), CLAUDE.md's order instead of a prototype first:** rule 11's state rewritten in
   `eye/BOT_RULES.md` (a range = the trend's extreme `E` and the first bounce `B`; the edges never move; only a close
   beyond 127 % breaks) with a note in `eye/BOT_SPEC.md`; the rule 14 lean text settled
   (`not read (M30 sideways); computed <lean>`). **Codex reviewed it twice** - round 1: 6 ambiguities and the 1,500 /
   3,000 contradiction, all fixed; round 2: its hand walk of a 9-pivot sequence came out decided, 3 small points fixed.
   **Then the owner's looks** (METHOD 2e "Two views"): the trend on M30 over 7 trading days, the range traded on M30
   over 4, the leg on M5 over 2 (`trend_days`, `range_days`, `setup_days`; the 3,000-bar walk withdrawn) - written
   into BOT_RULES ("The looks", rule 11). **Codex reviewed it twice** (round 1: which rules the setup look bounds, a
   leg starting before the look, M15, the lean, H1, weekends, METHOD's example vs the set values, attributions - all
   fixed; round 2: two small points, fixed). The owner then: no trend on the 7 days means a range - traded as one
   (rule 11, "The M30 state at `now`"; Codex: none after one fix). **Five models read it** (`eye/BOT_RESEARCH.md`,
   "Rule 11 and the looks read by five models"); the owner chose **1A** (one walk on the 1,500-bar frame, the looks
   only date the range and the break - *"write the code tightly"*: rule 14's stability check) and **2B** (a pivot past
   the first edge without a 127 % close is a test - *"wait for the retest anyway"*); rule 11 rewritten, the rest fixed
   (`eye/BOT_SPEC.md`, "Five models' review"). Codex reviewed it. **Step 4 under way, piece by piece** (the owner: each
   function delivered with its unit tests and checked before the next; checked by Claude and Fable, then a mutation
   run): new module `eye/state11.py`, tests `tests/unit/test_eye_state11.py` (not committed). Piece 1 - `m30_from_m15`
   (equals the prototype's M30 on all 38,331 bars) and `look` - passed, 14/14 mutants caught. Piece 2 - `walk` (rule
   11's one walk) - passed after one round (h <= 0 after a break now dropped, spec updated; pivots must alternate),
   29/29 mutants caught, 58 tests. Piece 3 - `state_at`, `classify`, `describe` - passed, 19/19 mutants. Piece 4 -
   rule 14's stability check (`eye/research/state11_check.py`) - July-October: 0 / 0 / 0 (BOT_RESEARCH, "Rule 11's
   state - the stability check"), Fable confirmed the zeros are real; 12/12 mutants of the check caught; 110 tests.
   Piece 5 - the state drawn on July-October (`eye/research/state11_draw.py`, `eye/trades/state11_*.png`, 115 tests).
   **Claude's eye: not passed** - wrong in every month (August 19-21 SELL through the rise, October's range read as
   flips; BOT_RESEARCH, "Rule 11's state drawn on July-October"). Waiting on the owner's judgement; then step 1 again.
   Then step 4 - a fresh Sonnet developer builds `state_tf` M30, the
   looks and the state from the reviewed text.
2. Write the passing reading into BOT_RULES rule 11 (and its M30 acceptance values), Codex reviews it.
3. A fresh Sonnet developer builds `state_tf` M30 and the reworked state (starting from the uncommitted H1 build),
   Codex reviews the code, mutation check, the full suite, commit.
4. The bot's own reading drawn again on several months - the owner passes it.
5. Rule 3 (`m5_trend`) built the same way, its M5 reading drawn and passed.
6. Only then, with the owner's word, a trading run - every trade drawn and judged.

**Carry these into the steps above - they are not done:**
- **Step 1, check on purpose:** a wide range breaks late - with the H1 build, the 4066-4229 range (h 162) needed a close
  below 4022 to break, so on 22/10 19:30-22:00 it still allowed a **BUY (leg 5) while price was falling through the
  edge**. The reworked M30 reading must not do this.
- **Step 3, two tests owed:** the H1-state mutation check left 2 of 24 uncaught - "the touch test uses `h` after the pivot
  widens the edge" and "the break window starts at the pivot bar" (the table: `eye/wip/mutation_h1_state_2026-10-30.log`). The reworked build needs tests that catch both, and its own full mutation check.
- **Step 2, one spec question from the developer:** while the state is sideways the build writes the lean as
  `not read (H1 sideways); computed <rule 1 lean>`; BOT_RULES rule 14 says only `not read (... sideways)`. Settle the
  text in the spec.
- **Step 5, the owner's test for rule 3** (2026-10-30: *"test that the bot reads the trend right and does not trade
  against the market"*): unit tests (UP / DOWN / mixed, equal prices, fewer than two pivots, an unfixed pivot ignored,
  BUY and SELL, an M15 leg on M5 pivots, `m5_trend` h100 unchanged); the bot's M5 reading equal to
  `eye/research/m5_structure_check.py`'s `structure()` at every filled decision of the October ledgers; an audit of
  every October window bar (decide() without writing or scoring) - every order the bot would write has the M5 trend
  of its side, **0 mismatches**; a mutation check. The half-done start is in `eye/wip/bot2e_rule3_half_done.py.txt`.
- **After the readings pass, with the owner:** what the drawn October losers showed - legs days old (across weekends)
  and orders at a level price reached slowly (`eye/BOT_RESEARCH.md`, "The current build - October 1-27"); and what
  replaces the lean (rule 1) - judged by the trades (R per trade), never by direction rates.
Walking by hand resumes at real day 5, 2026-04-08.

This file holds **state only** - where the work stands and where it resumes. The thinking lives in the
files it points at, and they are few on purpose: everything built before 2026-10-28 was stopped and
archived that day, and the rebuilding is deliberately small.

| What | Where |
|---|---|
| How to work here, and the owner's own rules | `CLAUDE.md` |
| What the repository is now, and the one number | `docs/START_HERE.md` |
| Rules each paid for with a real mistake | `docs/HOUSE_RULES.md` |
| **The owner's setup** - what the trading holds to | `eye/METHOD.md` **2e**: the answers table, the seven-step principle, divergence, the worked example, what Claude understands, what can be done |
| How a day is walked | `eye/METHOD.md` 2c |
| The nine trading rules | the bottom of `eye/METHOD.md` - 2e replaces rules 4 and 9; the rest stand |
| The weaknesses found, and what was fixed | `eye/RULES_REVIEW.md` (sections 1-3 the rules, 5-6 the 2e review) |
| Every method tried, with a verdict | `eye/TRIED.md` - row 18 the owner's setup, 19 the bot, 20 the removed M1 entry, 21 the owner's Fibonacci |
| **The bot** - its rules, and every research run with its result | **`eye/BOT_RULES.md` (the rules in force)**, `eye/BOT_SPEC.md` (the history, revisions 1-9), `eye/BOT_RESEARCH.md`, `eye/bot_research.py`; each run's ledger and log in `eye/research/<variant>/` (not committed; `summary.csv` is) |
| What the trades support | `eye/LESSONS.md` |
| Every reading, written before the reveal | `eye/SHEETS.md` |
| The trades | `eye/ledger.csv`, `eye/ledger_control.csv` |
| Every window walked, trade or not | `eye/sessions.csv` |
| The archived work - **old data, never decides the present** | `docs/archive/`, `research/archive/` |

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

````text
Continue TAA (C:\Users\korap\taa). Chat with me in Thai; docs, code and comments in English; times to me
in Thai time read with PowerShell Get-Date (Git Bash date is wrong on this machine). Follow CLAUDE.md.

Read first, in order:
1. docs/HANDOFF.md - the top box "Where the work stands" (the rest is history)
2. CLAUDE.md - "How the system is developed" (steps 1-8)
3. docs/START_HERE.md
4. eye/METHOD.md - section 2e is my setup (rows "The goal", "Keep it simple", the 07/10 drawing, "The side")
5. eye/BOT_RULES.md - the bot's rules in force; eye/BOT_RESEARCH.md - the last sections

My setup is answered in 2e - do not ask the questions again. An example I give is a principle to
generalise, never a rule with its numbers; a question I ask is a question, not a rule. The bot's rules in
force are eye/BOT_RULES.md; follow CLAUDE.md's development process exactly - tests green is not passing, a
reading passes only when it is drawn on several months and matches the market to my eye. Judge a rule by the
trades it gives (R per trade), not by how often price goes one way first. Next: HANDOFF, "Where the work stands (2026-11-01)" -
I do not believe pooled numbers: draw single trades MT5-style, one image at a time (the losing ones first), and judge them with me before any total; the target is measured with the Fibo of the previous leg (METHOD 2e "Measuring the target"). Drawing a reading on the stored bars (no trading, research prototypes) is part of the work; a trading run or a
bot research run needs my word. Record every result when it is measured.
````

---

## Where it stood, 2026-10-28 - the walk by hand (history; the bot's state is at the top of this file)

**The work.** Trading gold by eye on real candles, no strategy in `config.yaml`. The owner's bar is
**+0.15 R a trade after costs**.

**The owner's setup** (`eye/METHOD.md` 2e, dictated 2026-10-28), for a sell - a buy is the mirror:

1. the **H1 trend** gives the sell side the edge, and price comes up into a **resistance from the left**;
2. **3-5 ZigZag peaks** into it with **divergence** on MACD or RSI against price (one is enough) - **or two
   that make the owner's W** (an M for a buy - the owner's words, the textbook's reversed), which needs no
   divergence;
3. the **structure breaks** - the last swing low goes;
4. the **low breaks** - the low the bounce after it started from;
5. **entry on the retest** of that broken low, on M5-M15 (the owner: *"break the low, then retest"*);
6. **stop beyond the highest top** of the move;
7. **target just before the next level** from the left; **held until stop or target**, no time limit.

Steps 3-4 are Claude's generalisation of the owner's example (as the owner asked); step 5 and the rest
are the owner's answers. MACD and RSI are the owner's exception to "no indicators". Settings are MT5's defaults:
ZigZag 12/5/3, MACD 12/26/9, RSI 14. The owner's one example, worked on the stored bars after the fact,
pays +1.48 R - an illustration, not evidence.

**How a day is walked** (`eye/METHOD.md` 2c): a date taken whole, the owner's three windows in order -
Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai - advancing a few bars at a time, and
**every window written into `eye/sessions.csv` whether it produced a trade or not.**

**The tools.**

- `eye/walk.py` draws, per look, `_a` = H1 above M15 and `_b` = M5, with MT5's ZigZag on each frame and
  MACD (as MT5 draws it: main as histogram, simple 9-bar signal - **not** `app.indicators.trend.macd`) and
  RSI under M15 and M5; nothing uses a bar not closed at `now`.
- `eye/score.py` fills an order when price trades **through** the entry from the side it was on (limits
  and stops alike - it used to fill every sell as a limit, RULES_REVIEW M1), holds the trade until stop or
  target, and marks one still running at the end of the stored bars `open` - not a result.
- **Data: FBS-Demo only** (owner, 10-28). Refreshed with
  `.venv\Scripts\python scripts/download_history.py --symbols XAUUSD --timeframes M5,M15,H1 --days 5`, which
  runs through the bot's own terminal `C:\MT5\taa-bot` (logged in to FBS-Demo; it never touches the
  owner's real terminal), merging into `data/history/FBS-Demo` (stored to 28 Oct server time: M15 12:30, M5 11:55, H1 11:00; `score.py` scores on M5). MT5
  server time is UTC+2 since 25 Oct (**Thai = server + 5**) and was UTC+3 before it, so for the April days
  being walked **Thai = server + 4**. `walk.py` and the ledgers use Thai time; server time matters only when
  comparing with the owner's MT5 screen.
- **Checked against the owner's MT5:** every M15 ZigZag pivot from 26 Oct 19:00 to 28 Oct 12:30 server
  matched in price and time, and the 12:30 bar's open and low matched the owner's FBS-Real screen to the
  cent. **Not yet checked: MACD and RSI values** (Claude's: M15 27 Oct 19:30 server, MACD 12.20, signal
  13.31, RSI 78.25 - the owner reads MT5's Data Window, Ctrl+D), and ZigZag on M5 and H1.

**The ledger, all of it** (before 2e; re-scored after the clock fix, `RULES_REVIEW.md` C1/C3):

| | |
|---|---|
| Decisions that were trades | **13** (9 filled, 4 never filled), plus 3 moments stood aside |
| As planned | **-4.53 R, -0.348 a trade** |
| The same ideas taken at the price on the screen | **-0.15 R, -0.012 a trade** (held until stop or target) |
| Real days walked | 4 - 2026-04-01, 04-02, 04-06 and 04-07 (03/04 was Good Friday, no bars) |
| Windows walked | 12, of which 11 count: 3 `shut`, 0 `open-missed`, 3 `open-taken`, 5 `no-setup` |

`python eye/score.py summary` reads `ledger.csv` only (D1-1, D2-1 and the reset trade #1, which is a
pre-rules trade sitting in the judged ledger); `python eye/score.py ledger_control.csv summary` gives the
control; the figures above are the two together. `python eye/rules.py` reads both. The decisions keep the
planned scores (none was time-closed); their on-sight column was re-scored under the hold rule. The
fill fixes re-score every planned column of all twelve identically.

### What happened on 2026-10-28, after the handoff of 16:48

- **The nine rules were reviewed with Codex**, each reader apart (`RULES_REVIEW.md` 1-3). A scoring bug
  was fixed: the clock started on a bar already seen and rolled #15 a day forward; the numbers everywhere
  were corrected.
- **Claude proposed METHOD 2d** (a trend pullback); the owner said it was not their way. **On hold**, kept
  as a record; `eye/looks.csv` belonged to it and is unused.
- **The chart images in `eye/walk/` and `eye/sheets/` were deleted** at the owner's word (recoverable from
  937f75a).
- **The owner dictated their setup** - METHOD 2e - and **the archive was declared old data** (CLAUDE.md,
  HOUSE_RULES).
- **2e and its tools were reviewed by Claude and Codex apart** (`RULES_REVIEW.md` 5-6). Codex missed the
  fill bug; Claude missed four consistency faults. All fixed but the two jobs below.

---

## Where it resumes

**2026-10-29, in order:**

1. **Round 2 - an entry on M1 (removed).** Built by Claude on a misreading (BOT_SPEC revision 4).
   October: 3 distinct trades, none won; Codex found no bug. Removed at the owner's word; kept in
   `BOT_RESEARCH.md` and `TRIED.md` row 20 as a record.
2. **The owner's Fibonacci** (volunteered; drawn high -> low to play an up move, low -> high to play a down move - item 3b; "the
   counter-move just ended" is Claude's wording): trend - 0 % at
   the low, 100 % at the high,
   enter on the pullback to 38-23 % (61 % when the bulls are strong; its stop beyond 23 %), stop beyond 0 %,
   target 127-161 % (the owner's proposal); sideways - the edge 88-127 %, target around 100 %; with and without
   the count (*"try both"*). The owner foresees the hard part: *"reading whether it is a trend or
   sideways"*. Every word is in METHOD 2e; the open readings are listed there and run as variants.
3. **Round 3 measured** - BOT_SPEC revision 5 (R13-R17, `mode=fib` in `eye/bot2e.py`): about 33 fills in
   October, 1 won; Codex found no bug. The owner's
   M5 / M15 charts of 27/10 then showed the leg is drawn on the counter-move just ended - *"Yes - to play an up move, draw high -> low; to play a down move, draw low -> high."* (METHOD 2e). Round 4 - revision 6 (R18) - ran
   (history; `BOT_RESEARCH.md`); its `fib_side` options are withdrawn. The rules in force are `eye/BOT_RULES.md`.
4. **The documents were reviewed by Codex, Sonnet and Haiku apart** and corrected: the M / W sides in the
   written-out steps (they had the textbook's), stale status in this file, START_HERE and TRIED,
   attributions of Claude's readings to the owner.


**Done on 10-28:** the `setup` and `trigger` columns, `rules.py` judging the seven steps, and **real day 3,
2026-04-06**, the first day under 2e (03/04 was Good Friday - no bars after 03:50 Thai). Asia: **D3-1**, a
buy stop limit (trigger 4644.0, limit 4643.0, stop 4599.5, target 4668.0) - **no fill**: the break ran
straight through the target before any retest, and rule 8 withdraws it (left resting: +0.57 R, the plan's R as written in `SHEETS.md`). London
`shut`: a 44 USD run from a double bottom with no divergence. New York `no-setup`: divergence twice, but
MT5's ZigZag drew two lows, never 3-5. `eye/SHEETS.md` has every look.

**Read again with the owner after the day was scored** (`eye/SHEETS.md`, the end of day 3; METHOD 2e):

- **Two peaks that make an M (buy, at support) or a W (sell, at resistance) count**, not only 3-5; they
  may be asymmetric.
- **At support, buy. The owner's M is a buy and W a sell, the opposite of the textbook.** Claude read "M"
  the textbook way and took it for a sell; the record is corrected.
- So day 3 **London**, recorded `shut`, holds the buy Claude refused: an asymmetric M (tops 4678.79,
  4667.74) whose lows 4643.61 / 4644.97 sat on the 4642-4651 support, then the run to 4706.58. The rows of
  `sessions.csv` keep what was recorded at the time; the note is the correction.
- **Measured on three years of M15 gold** (METHOD 2e, the table): M and W, of either kind, went up first
  52-57 % of the time - the years' rise is in every row; the shape alone separates little. The level, the
  H1 side and divergence were not in that count.

**The owner, 10-28: a clear M at support (W at resistance) is entered without divergence** (day 3
London's M on 4642-4651 is the case); divergence is required for the 3-5 count (METHOD 2e step 2).

**Real day 4, 2026-04-07, walked:** no decision. Asia, London, New York all `no-setup`; step 7's next level sat a few dollars over every retest entry (`SHEETS.md`, "Day 4 in one place"). The minimum reward was then answered by the owner: **at least 1:2**.

**The bot, first version (history; owner, 10-28: *"write the code and let a bot do the work"*).** `eye/bot2e.py`
applied METHOD 2e bar by bar (then `eye/BOT_SPEC.md`; now `--mode 2e`, a record - the rules in force are
`eye/BOT_RULES.md`, see the top of this file). Divergence for the 3-5 count: **one oscillator is enough** (owner, 10-28). The owner's reward rule: **at least 1:2**,
and when the target just before the next level gives less - **no trade, for now**. Revision 3 (`min_r` 2.0, counting by zone) was built and
October 2026 run in 11 variants: **no trade** (`BOT_RESEARCH.md` round 1); with the floor off, 1-4 setups a
month, the best 1.31 R. `eye/bot_ledger.csv` is empty because research runs write to `eye/research/`.

**Next by hand: real day 5, 2026-04-08, Asia 07:00 Thai** (walking by hand continues beside the bot).

**How a day is walked (written for day 4, still the procedure; for day 5 use `"2026-04-08 07:00"`):** Read M and W **the owner's way** (M at support = buy, W
at resistance = sell) and count two peaks that make one. `.venv\Scripts\python eye/walk.py "2026-04-07 07:00" 0`,
one step per command (a slip on day 3 printed two at once). At each look, the pivots with MACD and RSI:
the helper Claude used lives in the session scratchpad, so rebuild it - `zigzag_pivots` on the closed bars
of M5 and M15, `walk.macd_mt5` and `app.indicators.momentum.rsi` at each pivot. Read divergence against
**fixed** pivots only (day 3: the reading changed when a pivot fixed). Write each look into `SHEETS.md`
before advancing; a decision into `ledger.csv` with `setup` and, for a 2e entry, a `trigger`; the window
into `sessions.csv`. **Do not run `score.py` until the whole day is walked.**

Carried from the earlier days, still true under 2e: **the stop goes beyond the band and the extreme, never
inside the level** (`TRIED.md` 15-16), and **the entry has to be taken when it happens** - both earlier
days produced a setup that was gone by the time it was complete.

**After that, when it is wanted:** let the code list the candidates - steps 2-5 are mechanical, so a scan
can find every place they occurred, by the clock, for the eye to judge only the level and the H1 trend
before the reveal (METHOD 2e, row 3; it answers the "one reader" hole). And a second reader on the charts.

## The owner's answers to the three-agent questions (2026-10-28)

1. Divergence: *"if both happen, it is clear"* - nothing recorded about one alone then. **Superseded:** the owner
   later settled that one oscillator is enough (METHOD 2e; BOT_RULES rule 4).
2. The entry: *"break the low, then retest"* - the sell is on the retest of the broken low, not on the
   break (METHOD 2e step 5; the buy is written out beside it).
3. The archived -0.115 comparison: *"delete it"* - removed from every live document (the history files,
   `eye/RULES_REVIEW.md` and the retired `eye/CODEX_BRIEF.md`, keep it as a record).

**The record in money** (done 10-28): `eye/money.py`, 200 USD at 0.01 lot: 200.00 -> 110.13 (-44.9 %),
deepest fall 97.18, seven losses in a row. The lot is an assumption; risk is the owner's.

## Open, and nobody has closed them

*(2026-10-30: the first three rows - the H1 lean, rule 11 on M30, rule 3 - are closed: the lean and rule 11 withdrawn,
the side is rule 16, rule 3 `m5_trend` now built. The open points now are in "Where the work stands" at the top.)*

| | |
|---|---|
| **What replaces the H1 lean** - no tested reading of H1 told the side; the bot with the lean off did no worse in October (before rule 11 was rewritten 21 fills, after it 12; not judged) | `eye/BOT_RESEARCH.md`, the last sections; BOT_RULES rule 1 |
| **Rule 11, the state on M30** - the H1 build's reading failed the market check (August read as SELL through the rise); the trend timeframe is now M30 (the owner); rework how a range starts and widens until the drawing passes the owner's eye | `eye/BOT_RESEARCH.md`, "The H1 state on four months"; BOT_RULES rule 11 |
| **Rule 3, the M5 trend at the decision** - specified, not built; its reading to be checked on several months before any trading run | BOT_RULES rule 3 |
| **The clean test is forward** - the stored months were used to choose; the months after 2026-10-28 as they arrive | BOT_RULES rule 15 |
| **MACD and RSI not yet checked against MT5**, nor ZigZag on M5 and H1 | `eye/walk.py` |
| **One reader.** Codex runs with the prompt piped on stdin (`codex.exe` ships with the VS Code extension, not on PATH: `~/.vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe`; `exec - --sandbox read-only`). It has reviewed documents twice, never a chart | `TRIED.md` row 14 |
| **Two judgements in 2e** - which level from the left counts, and what the H1 trend is at that moment (the owner's example had just broken an H1 lower high) - are where a reader's bias enters | `RULES_REVIEW.md` M9 |
| **Nothing enforces the sequential reveal.** `walk.py` accepts any step | `TRIED.md`, the review table |
| **The review agenda on the nine rules** (C5, C6, C9, X1) - partly overtaken by 2e, not decided | `RULES_REVIEW.md` 1-3 |

## Standing constraints

Ask before: `git push`, any deploy, starting DEMO or LIVE, anything touching the owner's accounts, and any
change to risk. Committing per step by explicit paths is fine without asking. LIVE stays off and needs
Phase 14 and an explicit word. DEMO and the hourly observer are disabled in Task Scheduler. Archive, never
delete - unless the owner says to delete (as with the chart images, 10-28).

**Everything in an archive folder is old data and never decides the present** (owner, 2026-10-28) -
`docs/archive/`, `research/archive/`, any `archive` folder: not a number, a verdict, a rule or a lesson
(`CLAUDE.md`, `docs/HOUSE_RULES.md`).

**Later on 2026-10-30 (the rebuilt bot):** built from the committed code, a piece at a time (Sonnet), each checked by
Claude (real mutation runs) and Codex: H1 / H4 / the lean / the old range / mode 2e removed; **rule 16** - the side
from M15 structure (strip B, reusing `eye/signal_study.py`; acceptance values exact); the setup look (2 days);
**rule 3 `m5_trend` now** (October: 0 mismatches over 1,817 window bars). Drawing tools `eye/research/bot_read_day.py`,
`bot_view.py` (MT5-style, ZigZag + the bot's Fibo at a moment, one image per new leg). On 07/10 the owner: 100 % belongs
at the top before the pullback -> **rule 2 changed** (`L0` = the latest fixed LOW; an early leg once the pullback
reaches 38.2 % - the owner "about 38, 61 %"); specified and reviewed by Codex, **not built yet**. Nothing committed -
the owner: commit once it works.
