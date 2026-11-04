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
- **Where the spec stands**: Sol's reviews are down to one or two edge-timing points a round; the last fixes (Sol: the
  setup's bar loop waits behind a pending entry) are in. **Not yet fixed - from the last Haiku sweep**: an uncaught
  error inside a cycle (-> hands-off) and a failed write-ahead row; exits at one `time_msc` (stops before TP, then the
  ticket); what counts as one of the "3 tries"; `zone_live_visit` needs the setup id and outcome columns, a runner
  `close` has no logic exit price; the BE stop rounded for the broker, unrounded in the logic; L2's undecided sentence
  "unless reserved"; the 3-tries cap is for SL modifies only (an expiry extension keeps retrying); a P2 past its
  refusal cap is not placed again after L7 clears. Then Sol once more. **Asked the owner** whether, after these and a
  clean Sol round, the spec closes and the build starts, with later Haiku points raised by the developer while
  building (else: review until both find nothing).
- **The code** (`app/zone/`, `app/cli/zone.py`, `app/storage/models/zone.py`, migration `0044_zone_live.py`, the broker
  additions, `tests/unit/test_zone_*.py`, `tests/zone_replay*.py`) is **uncommitted and built for the previous spec**
  (the ownership classifier `app/zone/ownership.py`, the restart recovery). To bring it to the new spec most of the
  ownership and restart code is deleted. A copy of `app/zone` and the zone tests from 2026-11-03 18:39 is in the
  session scratchpad (`backup/`), not in the repo.
- **Before a LIVE start**: the runner reads the stored bars **of the pinned server** (`data/history/<server>/XAUUSD`);
  only `FBS-Demo` exists - the LIVE server's history must be fetched first, and must start no later than FBS-Demo's
  (D1 2021-09-01, H4 2023-04-02, H1 / M15 2023-08-01, M5 2025-10-05). The zone set was built on FBS-Demo bars.
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
