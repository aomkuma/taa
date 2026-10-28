# Session handoff

Last updated **2026-10-28 18:05 Thai** (read with `Get-Date`). The owner's setup is written down in full
(`eye/METHOD.md` 2e), the chart and the scorer are built for it, and both were reviewed by Claude and Codex
apart. Next: two small tool jobs, then real day 3.

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
| Every method tried, with a verdict | `eye/TRIED.md` - row 18 is the owner's setup |
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
generalise, never a rule with its numbers. Do the tool job in "Where it resumes", then walk real
day 3, 2026-04-03, Asia 07:00 first, one window at a time, reporting each trade to me as it happens.
````

---

## Where it stands, 2026-10-28

**The work.** Trading gold by eye on real candles, no strategy in `config.yaml`. The owner's bar is
**+0.15 R a trade after costs**.

**The owner's setup** (`eye/METHOD.md` 2e, dictated 2026-10-28), for a sell - a buy is the mirror:

1. the **H1 trend** gives the sell side the edge, and price comes up into a **resistance from the left**;
2. **3-5 ZigZag peaks** into it, with **divergence** on MACD and RSI against price;
3. the **structure breaks** - the last swing low goes;
4. the **low breaks** - the low the bounce after it started from;
5. **entry on the retest** of that broken low, on M5-M15 (the owner: *"break the low, then retest"*);
6. **stop beyond the highest top** of the move;
7. **target just before the next level** from the left; **held until stop or target**, no time limit.

Steps 3-5 are Claude's generalisation of the owner's example (as the owner asked); the rest are the
owner's answers. MACD and RSI are the owner's exception to "no indicators". Settings are MT5's defaults:
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
| Decisions that were trades | **12** (9 filled, 3 never filled), plus 3 moments stood aside |
| As planned | **-4.53 R, -0.378 a trade** |
| The same ideas taken at the price on the screen | **-1.73 R, -0.144 a trade** (held until stop or target) |
| Real days walked | 2 - 2026-04-01 and 2026-04-02 |
| Windows walked | 6, of which 5 count: 2 `shut`, 0 `open-missed`, 2 `open-taken`, 1 `no-setup` |

`python eye/score.py summary` reads `ledger.csv` only (D1-1, D2-1 and the reset trade #1, which is a
pre-rules trade sitting in the judged ledger); `python eye/score.py ledger_control.csv summary` gives the
control; the figures above are the two together. `python eye/rules.py` reads both. The twelve keep the
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

**1. Add a `setup` column to the ledgers** - seven characters, `+` held / `-` broken / `?` not judged, one
per step of 2e's principle, like `rules` (not `steps`: `sessions.csv` already has a `steps` column, the bars
walked) - and have `eye/rules.py` count it. A 2e trade is judged by `setup`; its `rules` and `conflict`
columns are still filled (METHOD 2e, row 2).

**2. Real day 3, 2026-04-03, Asia 07:00 Thai, under 2e.** `.venv\Scripts\python eye/walk.py "2026-04-03 07:00" 0`
and advance a few bars at a time; read `_a` first (H1 side, the level), then the entry frames. Write the
reading into `SHEETS.md` before the reveal, every decision into `ledger.csv` with `steps`, and the window
into `sessions.csv` with its `reach` before moving to London.

Carried from the earlier days, still true under 2e: **the stop goes beyond the band and the extreme, never
inside the level** (`TRIED.md` 15-16), and **the entry has to be taken when it happens** - both earlier
days produced a setup that was gone by the time it was complete.

**After that, when it is wanted:** let the code list the candidates - steps 2-5 are mechanical, so a scan
can find every place they occurred, by the clock, for the eye to judge only the level and the H1 trend
before the reveal (METHOD 2e, row 3; it answers the "one reader" hole). And a second reader on the charts.

## The owner's answers to the three-agent questions (2026-10-28)

1. Divergence: *"if both happen, it is clear"* - one alone not ruled out, and not "clear".
2. The entry: *"break the low, then retest"* - the sell is on the retest of the broken low, not on the
   break (METHOD 2e step 5; the buy is written out beside it).
3. The archived -0.115 comparison: *"delete it"* - removed from every live document.

## Open, and nobody has closed them

| | |
|---|---|
| **MACD and RSI not yet checked against MT5**, nor ZigZag on M5 and H1 | `eye/walk.py` |
| **One reader.** Codex runs with the prompt piped on stdin (`codex.exe` ships with the VS Code extension, not on PATH: `~/.vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe`; `exec - --sandbox read-only`). It has reviewed documents twice, never a chart | `TRIED.md` row 14 |
| **Two judgements in 2e** - which level from the left counts, and what the H1 trend is at that moment (the owner's example had just broken an H1 lower high) - are where a reader's bias enters | `RULES_REVIEW.md` M9 |
| **Nothing enforces the sequential reveal.** `walk.py` accepts any step | `TRIED.md`, the review table |
| **Nothing in `eye/` converts R into USD** on the owner's 150 USD account | `START_HERE.md` |
| **The review agenda on the nine rules** (C5, C6, C9, X1) - partly overtaken by 2e, not decided | `RULES_REVIEW.md` 1-3 |

## Standing constraints

Ask before: `git push`, any deploy, starting DEMO or LIVE, anything touching the owner's accounts, and any
change to risk. Committing per step by explicit paths is fine without asking. LIVE stays off and needs
Phase 14 and an explicit word. DEMO and the hourly observer are disabled in Task Scheduler. Archive, never
delete - unless the owner says to delete (as with the chart images, 10-28).

**Everything in an archive folder is old data and never decides the present** (owner, 2026-10-28) -
`docs/archive/`, `research/archive/`, any `archive` folder: not a number, a verdict, a rule or a lesson
(`CLAUDE.md`, `docs/HOUSE_RULES.md`).
