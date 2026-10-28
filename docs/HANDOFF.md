# Session handoff

Last updated **2026-10-28 17:30 Thai** (read with `Get-Date`). The owner has said what they trade - price
structure + divergence + counting the peaks - and the work now waits on them to say how, in their terms.

This file holds **state only** - where the work stands and where it resumes. The thinking lives in the
files it points at, and they are few on purpose: everything built before 2026-10-28 was stopped and
archived that day, and the rebuilding is deliberately small.

| What | Where |
|---|---|
| How to work here, and the owner's own rules | `CLAUDE.md` |
| What the repository is now, and the one number | `docs/START_HERE.md` |
| Rules each paid for with a real mistake | `docs/HOUSE_RULES.md` |
| **The owner's principle** - what the work holds to | `eye/METHOD.md` **2e** - its details still open |
| How a day is walked | `eye/METHOD.md` 2c |
| The nine trading rules | the bottom of `eye/METHOD.md` - they stand where 2e does not contradict them |
| The weaknesses found in the rules, and what was fixed | `eye/RULES_REVIEW.md` |
| Every method tried, with a verdict | `eye/TRIED.md` |
| What the trades support | `eye/LESSONS.md` |
| Every reading, written before the reveal | `eye/SHEETS.md` |
| The trades | `eye/ledger.csv`, `eye/ledger_control.csv` |
| Every window walked, trade or not | `eye/sessions.csv` |
| The archived work - a record, **not a starting point** | `docs/archive/README.md`, `research/archive/` |

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

````text
Continue TAA (C:\Users\korap\taa). Chat with me in Thai; docs, code and comments in English; times to me
in Thai time read with PowerShell Get-Date (Git Bash date is wrong on this machine). Follow CLAUDE.md.

Read first, in order:
1. docs/START_HERE.md
2. docs/HANDOFF.md - this file, the "Where it resumes" section
3. eye/METHOD.md - section 2e is my principle, 2c is how a day is walked; then eye/TRIED.md,
   eye/LESSONS.md and eye/RULES_REVIEW.md

Before anything else, ask me the three open questions of METHOD 2e - how I read divergence, how I count
the peaks, and how they combine into an entry, a stop and a target - and write my answers in my terms. Do
not fill them in yourself. Then continue the real trading days: 2026-04-03, Asia 07:00 first, one window
at a time, reporting each trade to me as it happens.
````

---

## Where it stands, 2026-10-28

**The work.** Trading gold by eye on real candles, no strategy in `config.yaml`. The owner's bar is
**+0.15 R a trade after costs**; the archived system reached -0.115.

**The principle** (`eye/METHOD.md` 2e, owner, 2026-10-28): *"what I trade is price structure + divergence
and counting the peaks of the chart."* Of the three, only price structure is in the nine rules; none of the
thirteen mentions divergence, and counting is only rule 4's undefined "three or four legs, trade the
fifth". **Divergence may need an oscillator, which would be an exception to the 10-28 stance "no
indicators" - the owner's call, not yet made.**

**How a day is walked** (`eye/METHOD.md` 2c): a date taken whole, the owner's three windows in order -
Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai - advancing a few bars at a time, and
**every window written into `eye/sessions.csv` whether it produced a trade or not.**

**The ledger, all of it** (re-scored after the clock fix, `RULES_REVIEW.md` C1/C3):

| | |
|---|---|
| Decisions that were trades | **12** (9 filled, 3 never filled), plus 3 moments stood aside |
| As planned | **-4.53 R, -0.378 a trade** |
| The same ideas taken at the price on the screen | **-2.60 R, -0.217 a trade** (was -0.124 before the fix) |
| Real days walked | 2 - 2026-04-01 and 2026-04-02 |
| Windows walked | 6, of which 5 count (01/04 New York is an excluded observation): 2 `shut`, 0 `open-missed`, 2 `open-taken`, 1 `no-setup` |

`python eye/score.py summary` and `python eye/rules.py` give the live versions; the numbers above were
checked against them at 17:28 Thai.

**The three things measured, none decided, all backwards:**

1. **The structure at the level** - with it 4 trades at +0.14 R, against it 4 trades all a full stop. Take
   the one +3.67 R winner out and both halves lose alike, and the with/against labels are not in the
   ledgers - only in prose (`LESSONS.md` 1, `RULES_REVIEW.md` X2). A hypothesis.
2. **Waiting for a better price** - on sight beats planned by **+0.161 R a trade** over 12, all of it from
   the three plans that never filled (missed by 3.37, 3.85 and 3.82 USD), which win on sight largely by
   construction; on the nine filled trades on sight was **worse** by 1.15 R. Rule 7's 4 USD cap rests on
   this (`LESSONS.md` 4).
3. **A stop inside the band loses a trade the read got right** - day 2's only decision; the same idea with
   the stop beyond the band pays +1.63 R (`LESSONS.md` 5).

**And one about the method** (`LESSONS.md` 6): of the five counted windows, **two were `shut`** - the
market moved more than a hundred dollars and the rules could not take it - and the one catchable setup was
takeable for about **twenty minutes**, at the level.

### What happened on the evening of 2026-10-28

- **The rules were reviewed with Codex**, each reader apart; Claude's half was committed before Codex's
  was opened (`eye/RULES_REVIEW.md`, 0ecf0fe).
- **A scoring bug was found and fixed**: `score.py` started the clock on a bar already on the screen and
  rolled #15 a day forward. Every trade was re-scored and every file carrying the old numbers corrected
  (1050ddc).
- **Claude proposed METHOD 2d** (label every picture, enter only a pullback in a trend). The owner said "try
  it", then on the plain summary: *"not really my way"*. It is **on hold** and kept as a record; it never
  ran. `eye/looks.csv` (header only) was made for it and is unused.
- **The chart images in `eye/walk/` and `eye/sheets/` were deleted** at the owner's word (51 files,
  recoverable from 937f75a; `walk.py` draws a chart again on demand).

---

## Where it resumes

**1. METHOD 2e, in the owner's terms.** Ask the owner the three open questions and write the answers as
they give them - Claude does not fill them in (that is how 2d happened):

1. Divergence read on what - MACD, RSI, or price alone? If an oscillator, `walk.py` has to draw it under
   the M5 frame, from `app/indicators` (the MT5-exact primitives).
2. How the peaks are counted - three pushes, a triple top, waves 1-5 / ABC, or something else.
3. How the three combine into an entry, a stop and a target.

**2. Then real day 3, 2026-04-03, Asia 07:00 Thai.** `python eye/walk.py "2026-04-03 07:00" 0`, advancing a
few bars at a time. Write the reading into `SHEETS.md` before the reveal, and the window into
`sessions.csv` with its `reach` before moving to London.

Carry into day 3, from day 2's single trade:

- **The invalidation goes beyond the band, not at a minor low inside it** (`TRIED.md` rows 15 and 16).
- **The entry has to be at the level** - both days produced a setup that was gone by the time it was
  complete.

**Agenda from the review, not decided** (`RULES_REVIEW.md` sections 1-3) - they change the rules, so they
are the owner's: rules 5 and 7 together leave only one shape (C5); the 4 USD cap is in dollars while the
risk ranges 7x (C6); rule 9 puts the target on the line, against the owner's band rule (C7); a 12-bar step
is coarser than the ~20-minute catch window (C9); `shut` has no priced trade behind it (X1).

## Open, and nobody has closed them

| | |
|---|---|
| **Divergence and "no indicators"** - the owner trades divergence; the 10-28 stance says no indicators, and `walk.py` draws none | `METHOD.md` 2e |
| **One reader.** Codex now runs: pipe the prompt on stdin to `codex exec` (`codex.exe` ships with the VS Code extension, not on PATH: `~/.vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe`; `--sandbox read-only`). It reviewed the rules on 10-28 but has not read a chart, so one person still chooses the trade and labels which rules held | `TRIED.md` row 14, `RULES_REVIEW.md` |
| **Seven of the nine rules have no operational definition.** Day 2 showed it live: "the higher low" could be read at two scales | `TRIED.md`, the review table |
| **Nothing enforces the sequential reveal.** `walk.py` accepts any step, so the tooling cannot prove a decision came before the bars that judge it | `TRIED.md`, the review table |
| **The 4-hour resolve window was never checked** against the owner's rule that a 4-8 hour hold is fine if it pays. Day 1's target arrived about eight hours out | `METHOD.md` 4 |
| **Nothing in `eye/` converts R into USD** on the owner's 150 USD account | `START_HERE.md` |

## Standing constraints

Ask before: `git push`, any deploy, starting DEMO or LIVE, anything touching the owner's accounts, and any
change to risk. Committing per step by explicit paths is fine without asking. LIVE stays off and needs
Phase 14 and an explicit word. DEMO and the hourly observer are disabled in Task Scheduler. Archive, never
delete - unless the owner says to delete (as with the chart images, 10-28).

**Everything in an archive folder is old data and never decides the present** (owner, 2026-10-28) -
`docs/archive/`, `research/archive/`, any `archive` folder: not a number, a verdict, a rule or a lesson
(`CLAUDE.md`, `docs/HOUSE_RULES.md`).
