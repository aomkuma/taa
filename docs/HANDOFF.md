# Session handoff

Last updated **2026-10-29 Thai** (read with `Get-Date`). The owner's setup is written down in full
(`eye/METHOD.md` 2e) and a bot applies it (`eye/bot2e.py`). Its first version (2e's break-and-retest entry) made **no trade in
October 2026** - history; the Fibonacci build's runs are below. **Now (2026-10-29 evening):** the bot's rules in force are **`eye/BOT_RULES.md`**, and **`eye/bot2e.py` builds
them, rule 11 as rewritten this evening included** - written by a Sonnet developer, reviewed by Codex until no
findings, gates and full suite green. Tested
today at the owner's word *"find the answers by testing and proof"* (`eye/BOT_RESEARCH.md`, the last three
sections): **no tested band of H1 / H4 pivots is respected more than a control**, so rule 8's take-profit is the
Fibo extension (1.618, variant 1.272), no band cap; **no tested reading of H1 (rule 1 and three others) tells the
side of the next 24-47 USD move** (best 0.52 against a bar of 0.55). **The bot run with and without the lean** (before rule 11 was rewritten - the withdrawn M5 range still in; the owner's word;
`fib_lean` on/off, October 1-27, every decision drawn): on - 7 fills, 1 won, -3.74 R; off - 21 fills, 7 won,
+1.40 R (+0.07 a fill). Under 30 fills - not judged. Seen on the drawn trades: the old rule 11's "range" was one fresh
M5 swing - **Claude's misreading**; the owner: sideways is read on **H1**, the trend for the entry on M5, the trade from
the H1 range's third leg to its fifth. **Rule 11 is rewritten** (BOT_RULES) and built through the process; not yet run. **Open, with the owner:** what replaces
the lean, and rule 11 (built) once it is run and measured - in the discussion
of how the basic rules put the trades on the winning side of 50 % (judge by the trades, not by direction rates). The development process is in CLAUDE.md ("How the system is
developed"). Walking by hand
resumes at real day 5, 2026-04-08.

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
1. docs/START_HERE.md
2. docs/HANDOFF.md - this file, the "Where it resumes" section
3. eye/METHOD.md - section 2e is my setup, 2c is how a day is walked; then eye/TRIED.md and
   eye/RULES_REVIEW.md sections 5-6

My setup is answered in 2e - do not ask the questions again. An example I give is a principle to
generalise, never a rule with its numbers; a question I ask is a question, not a rule. The bot's rules in
force are eye/BOT_RULES.md, built in eye/bot2e.py. Judge a rule by the trades it gives (R per trade), not by
how often price goes one way first. Next: the discussion with me of how the basic rules put the trades on the
winning side - what replaces the H1 lean, and rule 11's H1 range (HANDOFF, "Open"). No bot or research run
without my word.
````

---

## Where it stands, 2026-10-28 (the bot and Fibonacci of 10-29: "Where it resumes")

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

| | |
|---|---|
| **What replaces the H1 lean** - no tested reading of H1 told the side; the bot with the lean off did no worse in October (21 fills, not judged) | `eye/BOT_RESEARCH.md`, the last sections; BOT_RULES rule 1 |
| **Rule 11, the H1 range** - rewritten from the owner's answer (sideways on H1, trend on M5, legs 3-5); its target's principle is the owner's (the M5 target, the H1 edges as support / resistance / take-profit), the min / max formula Claude's; leg 6 on: no side and no edge target (Claude's reading of the owner's "be ready for it to run through the edge", confirmed); built, not yet run | BOT_RULES rule 11; METHOD 2e "Sideways" |
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
