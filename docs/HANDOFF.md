# Session handoff

Last updated **2026-10-28 17:10 Thai**, after the rules review with Codex (`eye/RULES_REVIEW.md`) and the
owner's decision to let the picture decide first (`eye/METHOD.md` 2d).

This file holds **state only** - where the work stands and where it resumes. The thinking lives in the
files it points at, and they are few on purpose: everything built before 2026-10-28 was stopped and
archived that day, and the rebuilding is deliberately small.

| What | Where |
|---|---|
| How to work here, and the owner's own rules | `CLAUDE.md` |
| What the repository is now, and the one number | `docs/START_HERE.md` |
| Rules each paid for with a real mistake | `docs/HOUSE_RULES.md` |
| The method being run | `eye/METHOD.md` - section 2c is the live one |
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
3. eye/METHOD.md (section 2c is the method in use), eye/TRIED.md, eye/LESSONS.md

Then continue the real trading days under METHOD 2d: 2026-04-03, Asia 07:00 first, one window at a time,
every look labelled in eye/looks.csv before advancing, reporting each trade to me as it happens.
````

---

## Where it stands, 2026-10-28

**The work.** Trading gold by eye on real candles: no indicators, no knowledge base, no strategy in
`config.yaml`. Price structure, levels from the left of the chart, enter on a timeframe and exit on that
timeframe. The owner's bar is **+0.15 R a trade after costs**; the archived system reached -0.115.

**The method in use** (`eye/METHOD.md` 2c) is **real trading days, one at a time**: a date taken whole,
the owner's three windows walked in order - Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00
Thai - advancing a few bars at a time, and **every window written into `eye/sessions.csv` whether it
produced a trade or not.** The clock-sampled moments of `eye/sheets.py` and `moments.csv` are retired and
kept only because the control trades came from them.

**The ledger, all of it:**

| | |
|---|---|
| Decisions that were trades | **12** (9 filled, 3 never filled), plus 3 moments stood aside |
| As planned | **-4.53 R, -0.378 a trade** |
| The same ideas taken at the price on the screen | **-2.60 R, -0.217 a trade** (was -0.124 before the C1/C3 scoring fix) |
| Real days walked | 2 - 2026-04-01 and 2026-04-02 |
| Windows walked | 6, of which 5 count (01/04 New York is an excluded observation): `reach` = 2 `shut`, 0 `open-missed`, 2 `open-taken`, 1 `no-setup` |

Run `python eye/score.py summary` and `python eye/rules.py` for the live versions of both; the numbers
above are from 2026-10-28 16:40 Thai.

**The three things measured, none decided, all backwards:**

1. **The structure at the level** - with it 4 trades at +0.14 R, against it 4 trades all a full stop. Take
   the one +3.67 R winner out and both halves lose alike. A hypothesis (`LESSONS.md` 1).
2. **Waiting for a better price costs more than the losers do** - +0.161 R a trade over 12 (corrected from
   +0.253, `eye/RULES_REVIEW.md` C1), and all of it from three plans that never filled, missed by 3.37,
   3.85 and 3.82 USD; on the nine filled trades on sight was worse. Rule 7 now caps an order at
   **4 USD** from the price on the screen (`LESSONS.md` 4).
3. **A stop inside the band loses a trade the read got right** - day 2's only decision, swept five dollars
   past a stop placed inside the level's band, target reached ninety minutes later. Same idea, stop beyond
   the band: +1.63 R. On the reclaim: +4.80 R (`LESSONS.md` 5).

**And one that is about the method rather than the market** (`LESSONS.md` 6): of six windows, **two were
`shut`** - the market moved more than a hundred dollars and the rules could not reach it - and the one
catchable setup was takeable for about **twenty minutes**, at the level. None of that leaves a row in the
ledger, which is why `sessions.csv` carries `reach`.

---

## Where it resumes

**ON HOLD (10-28 17:40 Thai): 2d is Claude's proposal and the owner said it is not their way - they trade price structure + divergence + counting the peaks. Day 3 waits for that method in the owner's terms; the paragraph below is kept as the plan that was set aside.**

**Next: real day 3, 2026-04-03, Asia 07:00 Thai - the first day under `METHOD.md` 2d.** Walk it with
`python eye/walk.py "2026-04-03 07:00" 0`. At **every look**, before advancing, write a row in
`looks.csv`: the picture's label (TREND / VERTICAL / CHOP / FRESH BREAK / NEWS), the nearest band and its
distance, the step, the decision, and for a refused picture the trade it would have been, priced. Step 12
bars when price is more than one band width from a level, **3 bars inside it**. The only entry is a
pullback in a TREND into a band with the higher low printed (2d step 2). Write the window into
`sessions.csv` with its `reach` before moving to London, and the reading into `SHEETS.md` before the
reveal. 2d is not edited once day 3 starts.

What 2d expects, written before day 3: TREND pictures will be a minority of looks, and some whole days will
produce no trade (day 2 would have produced none). If after about ten windows TREND has not appeared at a
level once, that is predicted conflict B arriving, and it is reported, not worked around.

Two things to carry into day 3, both from day 2's single trade:

- **The invalidation goes beyond the band, not at a minor low inside it.** Writing "if price breaks X the
  level has failed" before the level is reached is what refused a sweep-and-reclaim, which rule 5 names as
  a valid pattern (`TRIED.md` rows 15 and 16, both **FAILS**).
- **The entry has to be at the level.** Both days produced a setup that was gone by the time it was
  complete - predicted conflict C and D, arriving as written.

## Open, and nobody has closed them

| | |
|---|---|
| **No second reader - the tool now works.** `codex exec` runs when the prompt is piped on stdin (`codex.exe` ships with the VS Code extension, not on PATH: `~/.vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe`); it reviewed the rules read-only on 10-28 (`eye/RULES_REVIEW.md`). It has still not read a single chart. Before that: the 50/50 split with Codex never answered one sheet: the prompt went to `codex exec` as an argument, so it waited on stdin 5.5 hours and exited 15, twice. Stopped 16:26 Thai. One person still chooses the trade and labels which rules held - the reviewer's largest finding | `TRIED.md` row 14 |
| **Seven of the nine rules have no operational definition** - partly answered by METHOD 2d (the swing, the five pictures, the turn), untested. Day 2 showed it live: "the higher low" could be read at two scales, and I could pick the one that let me trade | `TRIED.md`, the review table |
| **Nothing enforces the sequential reveal** - `looks.csv` records each look before advancing, but the tooling still does not check it. `walk.py` accepts any step, so the tooling cannot prove a decision came before the bars that judge it | `TRIED.md`, the review table |
| **The 4-hour resolve window was never checked** against the owner's rule that a 4-8 hour hold is fine if it pays. Day 1's target arrived about eight hours out | `METHOD.md` 4, the open question |
| **Nothing in `eye/` converts R into USD** on the owner's 150 USD account, so no drawdown, streak or margin figure can be read out of the record | `START_HERE.md` |

## Standing constraints

Ask before: `git push`, any deploy, starting DEMO or LIVE, anything touching the owner's accounts, and any
change to risk. Committing per step by explicit paths is fine without asking. LIVE stays off and needs
Phase 14 and an explicit word. DEMO and the hourly observer are disabled in Task Scheduler. Archive, never
delete.
