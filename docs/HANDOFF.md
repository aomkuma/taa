# Session handoff

Last updated **2026-11-09 20:45 Thai** (read with `Get-Date`). This file holds **the current state and what to do next only**
(the owner, 2026-11-04: *"documents should hold only what is used, not every history"*); the history is in `git log`.

**The process in force**: CLAUDE.md, "How the system is developed" - discuss and conclude -> record -> Codex reviews
the documents (Sol: `codex.exe exec -m gpt-6.1-sol --sandbox read-only`, prompt on stdin; `codex.exe` is in
`~/.vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/`) -> a developer codes (Opus for the zone runner, the owner
2026-11-03) -> Codex reviews the code until it finds no P1 (P2 / P3 recorded as known defects, fixed after the release; the
owner, 2026-11-09) -> the full suite and a commit ->
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
- **Where it stands (2026-11-09 20:45)**: the code to release is `app/zone/trader.py` sha c81d231f and
  `tests/zone_replay_broker_gate.py` sha cfcc3f69 (uncommitted, with the rest of `app/zone/`, `app/cli/zone.py`,
  `app/storage/models/zone.py`, the migration 0044, the `app/broker` changes, `tests/unit/test_zone_*.py`,
  `tests/unit/zone_live_support.py`, `tests/zone_replay*.py`). Sol's code review 12 found no P1 - **the first release
  (the owner, 2026-11-09: *"get the first release out; leave the non-severe defects for now"*)**.
- **Known defects, fixed after the release** (Sol's code review 12, all P2; scratchpad `code_rev12_log.txt`):
  - the grid cache can keep an old H4 grid when H1 recovers after H4 advanced within the same Thai month
    (`trader.py:856`) - key it on the effective event cutoff;
  - an L8 deadline's expiry is checked behind the positions / deals / history reads (`trader.py:1072`): while those
    reads keep failing, a gone order, an owed close, an unknown place or a market entry give no hands-off - one
    expiry check of every running condition in phase 2;
  - a missing quote returns before the exhausted SL-modify cap is checked (`trader.py:3605`);
  - a holiday closure (no quote, but H1 bars at that New York weekday / hour in the previous four weeks) is judged
    stale, not closed: resting orders removed and setups interrupted, hands-off if the broker refuses the removals for
    a bar (Sol, spec review of "Market closed", P2) - a holiday or session rule in Words;
  - when an owed interruption has nothing left to interrupt, `_decide` runs before `_manage` clears the latch, so the
    decision waits one cycle (2 s live).
  - the replay double (Sol's code review 13, P2): a cycle just past the stale deadline can still be skipped
    (`tests/zone_replay.py:825`), and an hour left undecided during a multi-hour catch-up escapes `undecided_hours`
    (`:771`) - the runner logs both at WARNING, so every WARNING line of a replay is read by hand until they are fixed.
- **2026-03 M15 tick replay on the release code (2026-11-09 21:25; scratchpad `replay_rel1_m15_tick.txt`): the
  gate says PASS - 46 / 46 visits, 7 / 7 setups matched in every field, 2774 s - but 14 WARNING lines, where the last
  PASS (before review 5's fixes) had none**: 10 hours undecided at the daily reopening (22:00 UTC on 03-16 .. 03-31,
  "placing was not allowed through the 60 s from its first quote"), the data called stale at the daily break on 03-11
  and 03-24 (21:00:24 UTC; the removals performed; setup 207 ended `interrupted`), and one blocked P1 met by the
  quotes (setup 208). L2 says the daily break is the market closed (nothing stale-removed) and L11 says an
  uninterrupted replay with an undecided hour fails - the harness does not check it. **A normal-case defect: not
  released.** The cause (the developer, from a short in-process replay of 03-16): Words "Market closed" judged the
  four-week history in server time; the break follows New York (17:00) and the server clock EU daylight saving, so
  after each DST change the break was taken for an open market, the stale data latched, and the latch blocked the
  reopening's decision; the replay double then skipped the cycles of the 60 s window. Setup 208's line is a normal
  rule-3 cancellation. **Fixed in the spec** (the history in New York time; the stored H1 misses 17:00 New York on 645
  Monday - Thursday days, the rest holidays; Sol: no other finding); built (trader.py cb70dbf2, the harness's L11 check of
  undecided hours, stale removals and interruptions); Sol's code review 13: no P1.
- **2026-03 M15 tick replay on trader cb70dbf2 (2026-11-10 10:46; scratchpad `replay_rel2_m15_tick.txt`): PASS** -
  46 / 46 visits, 7 / 7 setups matched in every field, no undecided hour, no stale removal, no interruption, 2239 s;
  one WARNING line, read by hand: a blocked P1 (4464.098) met by the quotes and cancelled - a rule-3 cancellation (L5)
  that the simulation also makes (the setup matched).
- **2026-03 M15 poll replay on trader cb70dbf2 (2026-11-10 11:17; scratchpad `replay_rel2_m15_poll.txt`): PASS** -
  46 / 46 visits, 7 / 7 setups matched in every field, 1834 s; the same one WARNING line (the rule-3 cancellation).
- **Next**: the full suite once -> commit -> the owner judges the charts (below) -> LIVE only on the owner's word.
- **The work after this release (the owner, 2026-11-10)**: a trade journal page in the system's web app (`app/web`),
  read from the zone runner's store (`zone_live_setup`, `zone_live_request`, `zone_live_visit`): the list of trades,
  the result in R and in money, and a chart of each trade's entries and exits. Through the full process (spec, review,
  build, review, tests).
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
