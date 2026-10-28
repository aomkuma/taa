# The archive, closed 2026-10-28

The owner, 2026-10-28: write it down, stop everything, move the setups and the research into the archive,
and start with a clear head.

Nothing here is deleted and nothing is lost - git keeps every version, and the conclusions that cost the
most to learn are summarised below so a fresh start does not have to re-learn them. **No strategy is
enabled in `config.yaml` any more**, in any lane: the engine as it stands sends no order even if it is
started with a day plan in place.

## Where the work went

| What | Now at |
|---|---|
| Setup OWN, its 17 rounds, PLAN-1's lane | `docs/archive/OWN_SETUP.md`, `OWN_SETUP_ROUNDS.md`, `PLAN1_LANE.md` |
| The setups at a glance, the learning plan and its tickets | `docs/archive/STRATEGIES.md`, `PLAN_LEARNING.md`, `TICKETS_LEARNING.md` |
| The AI chart reader, the learning discussion, parked ideas | `docs/archive/AI_CHART_READER.md`, `LEARNING_DISCUSSION.md`, `IDEAS.md` |
| Every dated research folder, 2026-10-07 to 2026-10-26 | `research/archive/` |
| The AI trader's whole record and its journals | `research/archive/2026-10-24-replay/` (`RECORD.md`, `rerun_2026-10-28/JOURNAL.md`, `ISSUES.md`) |
| The three bots, the locked rules, the weights study | `research/archive/2026-10-26-three-bots/` |

**Still live, deliberately.** `research/2026-10-23-entry/` was NOT archived: the hourly observer task
(`TAA Observer`, still registered and Ready) runs `observe.py` from it and appends to its `diary/`, and
`DECISION_CHECKLIST.md` lives there and is read by a test. The owner's standing habit is that the observer
keeps watching even when nobody trades, so stopping it is a separate decision. Say the word and it goes
too, with the scheduled task disabled in the same change.

Also live: `docs/OWNER_GOALS.md` and `docs/OWNER_TRADING.md` (the owner's own goals and trades, not
research), `docs/TRADING_FLOW.md` (how the machine works), `docs/TRADER_ROUTINE.md`, `docs/PLAN.md`,
`docs/TICKETS.md`, `docs/CODING_STANDARDS.md`, the runbooks, and `docs/PATTERNS.md` / `docs/CHART_READ.md` /
`docs/INDICATORS.md` / `docs/ADVISORY.md`, which document shipped code rather than a setup.

## What this body of work established, in the order it matters

**1. The losses were geometry, not direction** (the last measurement made, 2026-10-28). Over the 17 entry
candidates of 2026-07-06 and 07: 7 winners averaging **+0.643 R**, 6 losers at **-1.00 R**, a win rate of
**53.8 %**, giving **-0.115 R a trade** - the measured result to the third decimal. At that win rate the
winners must average **+1.14 R** to reach the owner's +0.15 bar. A 53.8 % win rate says the direction
reading was already good enough; the money was lost by taking targets nearer than the stops.

**2. No edge-side filter earned its place, including the one that shipped.** On the same candidates:
`lean_h4` (the locked R10) **-0.165 R**, `trend_h4` (the slope-inclusive reading I proposed) **-0.625 R**,
`lean_h1_first` (the owner's own ordering) **-0.205 R**, and **no gate at all -0.115 R**. Every filter did
worse than not filtering. 13 fills settle nothing, and the candidates were produced while the prompt
already told the AI that R10 existed, so the set is biased toward what R10 allows
(`research/archive/2026-10-24-replay/gate_compare.py`).

**3. A rule is only in force where its reading reaches the decider, and only on the paths that check it.**
R10 was locked on 2026-10-27 and its number was never put in the readings, so the answerer guessed from
three other H4 readings and guessed the wrong way all through the morning of 2026-07-06, when the real lean
stood at +3.515. Once the reading existed, the morning plan still armed a trade against it, because the
plan-order path consulted nothing. Both are recorded as DECISION_CHECKLIST D6 and ISSUES 37-41.

**4. The owner's frame ordering was written down backwards and reasoned from.** The owner said
**H1 → H4 → D1, in order of importance**; two documents recorded "D1 first" / "D1 strongest". The
measurement agrees D1 matters least and disagrees about H1, which it ranks second from last - but the H1
rule was withdrawn for measurement faults, not after a clean test, so that disagreement was never settled.

**5. What the AI trader actually did, in full.** 2026-07-06: 27 wakes and no trade at all in a 74.47 USD
range; after the readings were supplied, 3 trades and +0.71 R; after R10 became a real check, 2 trades and
+0.30 R. 2026-07-07: 1 trade, **-1.08 R**. Two days on the owner's own 150 USD account: 150.00 -> 139.05.
The first build traded those same two days for +0.21 and -2.43 R, so the work halved the bad day - and
never reached the bar.

**6. Leaks between deciding and trading, each measured.** An armed order died after 30 minutes while its
qualifying signal came 14 minutes later (ISSUES 42); a WAIT's order was refused on six unanswered HARD
checklist items because the prompt never told the AI to answer them for one, which threw away 4 of 6 such
orders (ISSUES 44); and "the cycle is spent" retired a setup that had never been entered (ISSUES 40).
Three of them in sequence killed the cleanest entry of 2026-07-06 (ISSUES 45).

**7. Habits that cost real evidence, now rules in `docs/CODING_STANDARDS.md` section 11.** A run's report
belongs in the research folder in the same change, under the name a reader looks for - four reports once
went to `data/` (gitignored) while four 0-byte files held their names, and a third of the record was lost
until it was recovered. Say which commit produced a number. Do not edit `app/` while a multi-process run is
in flight. Label a planted bug by what it actually catches.

## The state the machine is in

- No strategy enabled in any lane; the day-plan gate stays on; the loss breakers remain deactivated by the
  owner's decision of 2026-10-27; LIVE off and needing Phase 14.
- The engine, the web service and the DEMO tasks are all stopped or disabled.
- The replay store, the answers cache and the ledger are backed up under `data/replay/ai/backup_*`
  (gitignored, this machine only).
