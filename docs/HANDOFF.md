# Session handoff

Last updated **2026-11-09 01:40 Thai** (read with `Get-Date`). This file holds **the current state and what to do next only**
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
- **Points found while building** are raised by the developer, written into the spec and reviewed by Sol with the
  code (the owner's rule *"ข"*, 2026-11-04).
- **The build (the owner, 2026-11-04: *"get the system working for the best case first, to run it for real; do the
  finishing work alongside"*)**: uncommitted - `app/zone/` (the runner `trader.py`, `core.py`, `store.py`, `live.py`,
  `history_check.py`), `app/cli/zone.py`, `app/storage/models/zone.py`, the migration 0044, the `app/broker` changes,
  `tests/unit/test_zone_*.py`, `tests/zone_replay*.py`. The normal case exact, hands-off the safety net. Sol reviews the
  code until a review finds nothing; every fix carries a test (`tests/unit/test_zone_review_fixes*.py`) that fails with
  the fix reverted. The developer is Opus (CLAUDE.md step 4).
- **Where it stands (2026-11-09 01:40)**: Sol's code reviews 7 and 8 fixed by Opus (`test_zone_review_fixes12.py` -
  `fixes14.py`; every zone test file passes one at a time; ruff, mypy, bandit, architecture clean); the spec decisions
  they raised reviewed clean and committed (2e2eb0a - 9ab9cca). **Sol's code review 9: 8 findings** - 3 of the normal
  case (a quote judged against the wrong exec bar while an expected bar is late; a candidate dropped for the other's
  visit losing its life events and its end at `--now`), 5 of the safety net (owed removals and timers lost when later
  reads fail; an ordinary stop exiting with a market entry or a gone order unexplained; `--now` confirming from an old
  orders snapshot; the account-switch ERROR each cycle). Opus fixes them in two batches, the normal case first. No
  replay has been run on the code since review 5's fixes (the last PASS: 46 / 46 visits, 7 / 7 setups, 1460 s).
- **Two tracks (the owner, 2026-11-09)**: once Sol's review finds nothing in the normal case -> the 2026-03 M15 tick
  replay, then poll -> the full suite once -> commit by explicit paths -> the owner judges the charts (below); the
  safety net (hands-off, `zone stop`, failed reads) is reviewed alongside until clean. LIVE only on the owner's word.
- **The replay scope (the owner, 2026-11-07)**: one month, 2026-03, with the set's `exec_tf` M15 - *"if one month
  matches, assume it matches"*; M5 is replayed only before a switch to it.
- **The machine**: long runs need it awake and on power. After a sleep the CPU can stay throttled (2026-11-08: 19 %
  `% Processor Performance`, a plain 10M-step Python loop 10.3 s, tests about 10x slow; back to normal by 2026-11-09) -
  check that counter when timings look odd.
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
