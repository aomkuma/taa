# The foundation: what is left to rebuild from

The owner, 2026-10-28: clear everything, keep the raw data and the basic indicators, waiting to be put
together again.

So this file is the inventory of what survived, and nothing in it is a strategy, a setup, a rule, a weapon
or a conclusion. Those are in `docs/archive/README.md` and `research/archive/`, kept as a record of what was
tried and what it cost - **not as a starting point.** Read that file before rebuilding anything, for one
reason only: so the same ground is not covered twice.

## 1 The raw data

| Store | What is in it |
|---|---|
| `data/history/FBS-Demo/<symbol>/{M1,M5,M15,M30,H1,H4,D1}.parquet` | closed bars only. M5/M15/H1 for 29 symbols (28 FX pairs and gold) from 2025-10; H4/D1 from 2024-04; gold M1 the whole year, FX M1 from 2026-07-08 |
| `data/ticks/XAUUSD/<date>.parquet` | gold ticks from 2025-10-01 to 2026-10-16, bid and ask - the only source that prices a spread honestly |
| `data/plans/<date>.md` | the day plans the gate reads (P26) |
| `data/replay/ai/backup_*` | the replays' stores, answer caches and ledgers, gitignored, this machine only |

Bars are stamped at each bar's **open** in the Parquet store and at its **close** in the app's own frames.
Getting that one hour backwards is an hour of lookahead, and it voided a day of conclusions on 2026-10-27.

## 2 The indicators and primitives

Pure functions, no I/O, no opinion about how to trade:

- `app/indicators/` - the indicator set, with `docs/INDICATORS.md` for each formula and its conventions.
- `app/strategy/zigzag.py` - MetaTrader 5's own ZigZag, ported and tested against it.
- `app/evidence/` - the pattern detectors, catalogued in `docs/PATTERNS.md`.
- `app/core/clock.py` - the only place a wall clock or a broker server time may be read.
- `app/market_data/` - the candle service that hands out **closed bars only**, and the watermarks that
  guarantee a bar is evaluated once even across a restart.
- `app/broker/` - the read-only gateway, `FakeMT5`, and the one module allowed to send an order.
- `app/risk/` - the position sizer, the limits, the mode gates, the kill switch, the day-plan gate.
- `app/backtest/` - the engine that runs a strategy over bars or ticks and writes a report.

**Research indicators are MetaTrader 5's own formulas**, not textbook ones. The derivations that proved
that are in `research/archive/2026-10-18-moments/agents/precursors/foundation.py`.

## 3 What is switched off

- **Every strategy in `config.yaml` is `enabled: false`**, in the main lane and in all five extra lanes -
  twenty of them. A started engine sends no order.
- The day-plan gate stays on, the loss breakers stay deactivated (the owner's decision of 2026-10-27), and
  LIVE needs Phase 14 and an explicit word.
- `TAA Observer` is **Disabled** in Task Scheduler; the DEMO engine, web, worker and check tasks were
  already disabled. Nothing of ours runs.
- The code of the old setups, readers, knowledge base and AI trader is **still on disk and still tested**
  (`app/strategy/`, `app/ai/`) but nothing enables it. It was left in place rather than ripped out because
  removing it would break the registry, the config schema, the web API samples and some hundreds of tests,
  which would leave a repository that cannot be built on. Stripping it is its own job, to be done
  deliberately if the owner wants a bare skeleton.

## 4 The rules of the house that survive the clearing

These are about how to work, not what to trade, and they were each paid for:

- A rule is in force only where its reading reaches the decider, and only on the paths that check it.
- A run's report belongs in its folder in the same change, under the name a reader looks for; never an
  empty file in its place; say which commit produced the number (`docs/CODING_STANDARDS.md` section 11).
- Do not edit `app/` while a multi-process run is in flight.
- Label a planted bug by what it actually catches.
- An abnormal count stops the report until it is explained.
- Reproduce any decision-bearing number through the engine before reporting it.
- The owner's frame ordering is **H1 → H4 → D1, in order of importance**. It was written down backwards in
  two places and reasoned from for a day.

## 5 The one measured fact worth carrying forward

Over the 17 entry candidates of 2026-07-06 and 07: **7 winners averaging +0.643 R, 6 losers at -1.00 R, a
win rate of 53.8 %, giving -0.115 R a trade.** At that win rate the winners must average **+1.14 R** to
reach the owner's +0.15 bar. Every direction filter tried did worse than no filter at all.

**The direction reading was already good enough. The money was lost on the geometry of the trades.**
Whatever is built next should be judged on that number first.
