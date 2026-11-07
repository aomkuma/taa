# Session handoff

Last updated **2026-11-04 Thai** (read with `Get-Date`). This file holds **the current state and what to do next only**
(the owner, 2026-11-04: *"documents should hold only what is used, not every history"*); the history is in `git log`.

**The process in force**: CLAUDE.md, "How the system is developed" - discuss and conclude -> record -> Codex reviews
the documents (Sol: `codex.exe exec -m gpt-6.1-sol --sandbox read-only`, prompt on stdin; `codex.exe` is in
`~/.vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/`) -> a developer codes (Opus for the zone runner, the owner
2026-11-03) -> Codex reviews the code until nothing is found (P3 included, the owner) -> the full suite and a commit ->
the reading checked against the market, drawn, judged by Claude then the owner -> only then, with the owner's word, a
trading run. Tests green means the code matches the spec, never "passed".

## 1. The run-zone runner for LIVE - the work now

- **Goal (the owner, 2026-11-02)**: LIVE when it is done; 0.01 lot a position, fixed; no DEMO; *"I watch the trades and
  take the risk myself"*. LIVE needs `ENABLE_LIVE_TRADING=true` and `LIVE_TRADING_CONFIRMATION=I-ACCEPT-LIVE-RISK-<login>`
  in `.env`, set by the owner, and the owner's word to start.
- **The spec: `eye/ZONE_LIVE.md`** - the normal case exact (parity with the simulation on uninterrupted runs); an
  abnormal case (every start that finds the magic not flat, anything the runner cannot know or do, the owner acting by
  hand) is **hands-off**: placing stops, every order of the magic removed, no position touched (its broker SL / TP),
  until the magic is flat, then a fresh start at the next H1 open (the owner, 2026-11-04: *"let it go - get the normal
  case right first"*; the owner's hand confirmed *"ตกลง"*).
- **The spec is closed** (2026-11-04: Sol's closing review "no findings"; the owner's rule *"ข"* - later points are
  raised by the developer while building).
- **The build (the owner, 2026-11-04: *"get the system working for the best case first, to run it for real; do the
  finishing work alongside"*)**: track A (Opus) brings `app/zone/trader.py` to the spec's normal case - "ours" = this
  process's placements, L5's fills, the basic hands-off as the safety net, the ownership classifier and the restart
  recovery deleted - then the replay spans for parity; track B (Sonnet, in parallel, new files only) the start's
  history checks (the pinned server's store and its depth, L2) and the tests of hands-off's eight causes; A wires B in.
  **Track B done**: `app/zone/history_check.py` and `tests/unit/test_zone_handsoff_causes.py`. **Track A done**
  (uncommitted): `app/zone/ownership.py` and the restart recovery deleted; the normal case kept; hands-off's eight
  causes detected; ruff, mypy, bandit, architecture clean; every zone test file passes one at a time (handsoff 33).
  **Replay after the decision-window fix (the hour's first quote)**: 2026-03 M5 tick and poll, 2026-03 M15 tick - all
  PASS (46 / 46 visits, 7 / 7 setups matched in every field, no WARNING line); 2024-03 M15 and 2026-03 M15 poll passed
  before the fix and are not re-run. Claude re-ran: ruff, mypy, bandit clean; architecture 17, trader 59, handsoff 33,
  restart 16, history_check 37 passed. Track A's developer stopped on Opus's weekly limit (resets 2026-11-08 13:00).
  **Sol's code review (2026-11-04 23:10): 13 findings (5 P1), each reproduced on FakeMT5** - the normal case: a
  market P2 before P1's fill, deal times without milliseconds, P2 given its own block, an original-SL exit recorded
  as BE, M15 requiring an M5 file, the live path writing the stored bars; the safety net, three roots: placing checked
  once per cycle not per send; the runner's view built from what it saw, not what it sent (manual exits with magic 0,
  the owner's-hand fields, accepted tickets); timers cleared before their action (stale removal, the 3-tries cap,
  `stop --now`). **All 13 fixed** (Sonnet, 2026-11-05; uncommitted; each with a test in
  `tests/unit/test_zone_review_fixes8.py` that fails with its fix reverted): a marketable P2 only after P1's deal is
  read; deal times to the millisecond; P2 tested against P1's block only; an exit at the original SL is `SL` unless the
  BE stop was confirmed; only the required frames loaded (M15 needs no M5 file); the live path writes no bars; placing
  re-checked before every send; deals of our positions kept whatever their magic; the latest accepted SL / expiry
  expected; the 3-tries cap checked before the BE close; accepted tickets known at once; the stale removal owed until
  done; `stop --now` exits after 60 s. Claude re-ran: ruff, mypy, bandit clean. **Replay 2026-03 M15 tick and M5 tick:
  PASS** (46 / 46 visits, 7 / 7 setups, 0 differences, no WARNING line). Four old assertions held the behaviour L5
  rule 3 and L7 forbid (P2's own block; P2 placed beside an unconfirmed market P1) - changed to the spec (Claude
  re-ran: trader 58, fixes7 6, fixes8 21 passed).
  **Sol's code review 4 (2026-11-05 01:20): 7 findings (2 P1)**. Three were spec gaps, **fixed in `eye/ZONE_LIVE.md`,
  Sol clean, committed (41b7aad)**: the hour's first quote = the later of the H1 open and the last pre-hour quote read
  (a late recovery opened a new 60 s); a failed forming-H1 read not fresh; an unknown place found cancelled is cause
  7, not `moot`; the in-bar touch order recognised in the visit records (WARNING, the traded row carries the setup id);
  tick replay cycles through gaps over `stale_quote_seconds`. The code findings, by root, all with the Sonnet
  developer: one exit classifier from the first exit deal (`how` came back a second time); the M5 start's arming from
  H1 only, complete only after its whole bootstrap; `stop --now` behind an unacknowledged stop; one broker-read path
  and the last pre-hour read; one "ticket known" function; the in-bar touch order. Then the replays and Sol again.
  **Replay after these fixes (2026-11-05)**: 2026-03 M15 tick PASS (46 / 46 visits, 7 / 7 setups, no WARNING); M5 tick
  FAILED on one row - the span's first hour, 2026-03-01 23:00 (the weekly reopening), `undecided` for the runner
  against the simulation's `abnormal`: the replay starts with no pre-hour quote read, so L2's window counts from the H1
  open (the spec's rule; the live runner cycles through the weekend). The fix is in the replay harness (the last tick
  before the span served, the runner cycling from before the first hour) - with the developer, then both replays again.
- **`.env` (changed by Claude on the owner's word, 2026-11-04 18:22)**: `ENABLE_HIGH_RISK_PROFILE=false`,
  `ENABLE_LIVE_TRADING=true`, `LIVE_TRADING_CONFIRMATION=I-ACCEPT-LIVE-RISK-28941169` (`TRADING_MODE=LIVE`, `FBS-Real`) -
  **the LIVE gate is open**: anything of the system started now can trade LIVE. No strategy is enabled in
  `config.yaml`; DEMO and the observer are off in Task Scheduler; the zone runner is not started (the owner's word).
- **FBS-Real history fetched** (read-only, D1 / H4 / H1 / M15 from 2021-08-22; `data/history/FBS-Real/XAUUSD`, passes
  `history_check`). Its bars differ from FBS-Demo's by under 0.40 USD on 99 % (up to 9 USD on news bars; measured,
  `eye/BOT_RESEARCH.md`). **The zone set on FBS-Real bars** (cut to FBS-Demo's first bars): 107 setups, +0.399 R a
  setup, +1868.86 USD, drawdown -280.02 - against FBS-Demo's 109, +0.392 R; the differences are in 2024.
- **Before a LIVE start**: the runner reads the stored bars of the pinned server (`data/history/FBS-Real/XAUUSD`),
  brought up to date from the broker at start (L2).
- **The simulation** (built 2026-11-02, `eye/zone_bot.py`, set `XAUUSD/default@v26` in `data/bot_config.db`): October
  2023 - October 2026, 109 setups, +0.392 R a setup, 41 % TP, +1868.9 USD at 0.01 lot a position, drawdown -280.0;
  charts in `eye/research/zone/XAUUSD/default/`. **Still open (CLAUDE.md step 7)**: the owner judges the charts - does
  the bot read the zones and entries as the owner does.

## 2. The Fibonacci bot - paused since 2026-11-01

- Rules in force: `eye/BOT_RULES.md` (unchanged since commit 3728254, rule 16 m15); the owner's setup `eye/METHOD.md`
  2e; measurements `eye/BOT_RESEARCH.md` (the last sections).
- Next, when the owner returns to it: draw the trades of the best single-line form (entry 161.8 %, stop beyond 200 %,
  target 61.8 %, M15), the losing ones first, one image at a time, and ask what the owner sees that would skip them -
  **the owner does not believe pooled numbers**. The owner's choice of leg on 30/10 ("why that leg") is unanswered.
- Still open: the clean test is forward (the months after 2026-10-28); MACD and RSI not checked against MT5.

## 3. Stopped side studies

- Volume Profile on XAUUSD M5 - stopped by the owner 2026-11-01; `research/xauusd_poc_m5/RESEARCH_STATUS.md`. Not part
  of the bot; whether it has a place in the owner's method is the owner's to decide.

## Standing constraints

- Ask before: `git push`, any deploy, starting DEMO or LIVE, anything touching the owner's accounts, any change to
  risk. Committing per step by explicit paths is fine. DEMO and the hourly observer are disabled in Task Scheduler.
- Everything in an archive folder is old data and never decides the present (the owner, 2026-10-28).
- Run long test files one at a time (parallel replay tests exhausted Windows memory, 2026-11-03).

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

````text
Continue TAA (C:\Users\korap\taa). Chat with me in Thai; docs, code and comments in English; times to me in Thai time
read with PowerShell Get-Date. Follow CLAUDE.md.

Read first: docs/HANDOFF.md (the whole file - it is the current state only), then CLAUDE.md, eye/ZONE_RULES.md and
eye/ZONE_LIVE.md. The work now is section 1 of HANDOFF: the run-zone runner for LIVE - finish the spec's open points,
then bring the uncommitted code to the spec (a developer builds, Sol reviews until clean), then the replay, the full
suite, the commits. Documents hold only what is used - no history. Record every result when it is measured.
````
