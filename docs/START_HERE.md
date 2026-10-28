# Start here

Everything built before 2026-10-28 is stopped and archived. This file and `docs/HOUSE_RULES.md` are the
whole live document set; the work itself lives in `eye/`.

## What this repository is now

| | |
|---|---|
| **The work** | `eye/` - learning to trade gold by eye, a hundred hand-read trades, recorded one by one |
| **The raw material** | bar and tick history in `data/history` and `data/ticks`, and the indicator primitives in `app/indicators` - nothing above them is in use |
| **The machine** | `app/` still builds and its tests pass, but **no strategy is enabled in `config.yaml`**, in any lane. A started engine sends no order |
| **The record of what was tried** | `docs/archive/README.md` and `research/archive/` - a record, **not a starting point** |

## What we are doing

Watch price, find an entry that has an edge, enter on a timeframe and exit on that timeframe. No
indicators. The owner, 2026-10-28:

> Trading now barely needs any indicators at all. Just price, the trend and the decision. Let price run
> into one of the levels on the left of the chart, from earlier days or earlier hours.

The method, the hundred moments, the rules written before the first chart was drawn, what has been tried
and whether it worked, and every trade: `eye/METHOD.md`, `eye/TRIED.md`, `eye/LESSONS.md`,
`eye/ledger.csv`.

## The number everything is judged against

**+0.15 R a trade after costs.** The archived system reached **-0.115 R a trade**: it was right about
direction 53.8 % of the time, which was enough, and still lost, because its winners paid +0.643 R while
its losers cost a full 1.00 R.

So the question is not which way price goes. It is whether an entry read by eye at a real level pays more
than one R when it is right.

## What is known so far, and how little it is

Eight hand-read trades. Four taken with the structure at the level made +0.14 R each; four taken against
it lost a full stop every time. That is the most promising thing measured and it is still nothing -
measured backwards, on eight trades, with one winner carrying the good half. `eye/LESSONS.md` keeps it
honest.

## Before changing anything

Read `docs/HOUSE_RULES.md`. Every rule in it was paid for with a real mistake.
