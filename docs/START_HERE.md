# Start here

Everything built before 2026-10-28 is stopped and archived. This file, `docs/HOUSE_RULES.md` and
`docs/HANDOFF.md` are the whole live document set; the work itself lives in `eye/`. **`docs/HANDOFF.md`
is where a new session starts**: it carries the current numbers, where the walking resumes, and what is
still open.

## What this repository is now

| | |
|---|---|
| **The work** | `eye/` - learning to trade gold by eye, a hundred hand-read trades, recorded one by one |
| **The raw material** | bar and tick history in `data/history` and `data/ticks`, and the indicator primitives in `app/indicators` - nothing above them is in use |
| **The machine** | `app/` still builds and its tests pass, but **no strategy is enabled in `config.yaml`**, in any lane. A started engine sends no order |
| **The record of what was tried** | `docs/archive/README.md` and `research/archive/` - **old data: it never decides the present** (owner, 2026-10-28), a record so the same ground is not covered twice |

## What we are doing

Watch price, find an entry that has an edge, enter on a timeframe and exit on that timeframe. No
indicators. The owner, 2026-10-28:

> Trading now barely needs any indicators at all. Just price, the trend and the decision. Let price run
> into one of the levels on the left of the chart, from earlier days or earlier hours.

Later the same day the owner named what they actually trade, and the work holds to it: **price structure +
divergence + counting the peaks** (`eye/METHOD.md` 2e). The owner then dictated the setup, and it is written in
full in 2e: the H1 trend gives the side; at a level from the left on that side, 3-5 ZigZag peaks (or two that make
an M or a W) with divergence on MACD and RSI against price (the owner's one exception to "no indicators"); the structure
breaks, the low (high) goes, entry on the retest of it; stop beyond the extreme of the move; target just before the
next level; held until stop or target. **In the owner's words an M is a buy and a W a sell** - the
opposite of the textbook; read them the owner's way (`eye/METHOD.md` 2e, "The owner's words for
patterns").

The method, the hundred moments, the rules written before the first chart was drawn, what has been tried
and whether it worked, and every trade: `eye/METHOD.md`, `eye/TRIED.md`, `eye/LESSONS.md`,
`eye/ledger.csv`.

## The number everything is judged against

**+0.15 R a trade after costs.** The question is whether an entry read by eye at a real level pays more
than one R when it is right.

**The record is kept in R, and read in money with `eye/money.py`** (the owner, 2026-10-28: *"make it simple
- think from a 200 USD account and work it out in money"*): a **200 USD** balance, **0.01 lot** (on gold,
1.00 of price = 1 USD), the 0.30 spread included, every trade of both ledgers in date order. Read on
2026-10-28: **200.00 -> 110.13 USD (-44.9 %)**, deepest fall from a high 97.18 USD, seven losses in a row.
The lot is the reading's assumption, not a decision - risk is the owner's to set.

## What is known so far, and how little it is

**Twelve decisions that were trades, nine of them filled, one winner**, plus three moments stood aside.
Taken together: **-0.378 R a trade.** Three things have been measured on them, all backwards, none
decided:

- **The structure at the level.** Four trades taken with it made +0.14 R each, four taken against it lost a
  full stop every time - but take the single +3.67 R winner out of the good half and both halves lose
  about -1.02 R. It is a hypothesis, not a result.
- **Waiting for a better price cost more than every losing trade.** The same twelve ideas taken at the
  price that was on the screen make **-0.144 R a trade** instead of -0.378 (corrected twice on 2026-10-28:
  a scoring bug, then the owner's rule to hold until stop or target - `eye/RULES_REVIEW.md` C1 and section
  7), and all three plans that never filled would have won,
  missed by 3.37, 3.85 and 3.82 USD - partly by construction, since an unfilled limit is one price left in
  the planned direction. On the nine filled trades, on sight was worse. An order now goes no further than **4 USD**
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

Real day 3 is walked under 2e. Claude's own proposal for the entries, METHOD 2d (enter only a pullback
in a trend), is **on hold**: the owner said it is not their way, and it never ran. The weaknesses found on
10-28 - in the nine rules, then in 2e and its tools, each reviewed by Claude and Codex apart - and what
was fixed are in `eye/RULES_REVIEW.md`.

## Before changing anything

Read `docs/HOUSE_RULES.md`. Every rule in it was paid for with a real mistake.
