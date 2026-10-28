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

**Everything in `eye/` is in R, with no position size in it.** The account it is for is the owner's real
one: **150 USD at 1:2000**, with 7.5 % of equity risked a trade in the archived settings - the owner's own
choice, never a concern to raise. Nothing in the eye record converts R into USD yet, so no drawdown,
streak or margin figure can be read out of it. That is a gap, not a decision.

## What is known so far, and how little it is

**Twelve decisions that were trades, nine of them filled, one winner**, plus three moments stood aside.
Taken together: **-0.378 R a trade.** Three things have been measured on them, all backwards, none
decided:

- **The structure at the level.** Four trades taken with it made +0.14 R each, four taken against it lost a
  full stop every time - but take the single +3.67 R winner out of the good half and both halves lose
  about -1.02 R. It is a hypothesis, not a result.
- **Waiting for a better price cost more than every losing trade.** The same twelve ideas taken at the
  price that was on the screen make **-0.124 R a trade** instead of -0.378, and all three plans that never
  filled would have won, missed by 2.57, 3.85 and 3.82 USD. An order now goes no further than **4 USD**
  from price.
- **A stop inside the band loses a trade the read got right.** Day 2's one decision was filled, swept five
  dollars past a stop placed inside the level's band, and the target it was aiming at came ninety minutes
  later. The same idea with the stop beyond the band pays +1.63 R instead of -1.02.

`eye/LESSONS.md` keeps all three honest; `eye/TRIED.md` carries the verdict on every method tried, including
the ones that failed.

The method being run now is **real trading days, one at a time** (`eye/METHOD.md` section 2c): a date
taken whole, all three of the owner's windows walked in order, every window written into
`eye/sessions.csv` whether it produced a trade or not. **Two days are done, 2026-04-01 and 2026-04-02:
six windows walked, four of them with no trade, two decisions.** Day 1's New York window could not be
judged - scoring its London trade had already shown me what price did inside it - so it was walked as an
observation and is marked that way.

## Before changing anything

Read `docs/HOUSE_RULES.md`. Every rule in it was paid for with a real mistake.
