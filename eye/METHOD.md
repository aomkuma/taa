# Trading by eye: the method

The owner, 2026-10-28, after everything else was archived: *"start from looking at price structure and
finding an entry with an edge. That is all. Any timeframe; the principle is enter on a timeframe, exit on
that timeframe. Try trading with your bare eyes."* Then: *"you need to trade a hundred times before the
picture appears."*

So this folder is a hundred hand-read trades on real candles, and nothing else. No indicator, no rule set,
no filter, no knowledge base. **These rules are written before the first chart is drawn**, so that what
follows can judge them.

## 1 What is read

Gold, **M5**, drawn as candles and looked at as a picture - never read as a table of numbers. M5 because
of what the first hand-read showed on 2026-08-14: the newest structure on M5 sat 6-8 USD from price while
on M15 it sat 17-20 USD away, so the M15 plan bought a shelf the market had already left. M5 keeps the
entry current and halves the stop, and its stops stay many times the spread, which M1 would not.

Each sheet shows **six panels, each a different moment**, about 90 bars (7.5 hours) up to its cut-off.

## 2 How the moments are chosen

**By the clock, never by what they look like.** Picking moments that look interesting is how a library of
"patterns" becomes a record of hindsight (the lesson that voided an earlier body of work).

- Start 2026-02-02, then **every second trading day**.
- The hour rotates through the owner's windows: **08:00, 14:00, 20:30 Thai**, one per sampled day, in turn.
- A moment is skipped only when the data has no bars for it (a weekend or a gap), and the next day is taken
  in its place, keeping the rotation.
- July 6-9 and October 19-27 of 2026 are **excluded**: those days were examined in earlier work and are no
  longer unseen.

## 3 What a decision is

For each panel, before anything after the cut-off is drawn, I write:

- **the structure I see** in a sentence - what the swings are doing, where the shelves and the origins of
  moves are;
- **BUY, SELL or no trade**;
- when it is a trade: **entry, stop and target, as prices**, and the structure each one comes from.

The entry must be a price the market can reach from where it is now - not a price I would like. If the
level I want is already far behind price, that is **no trade**, and it says so.

## 4 How a trade is scored

- Entry fills when price trades through it within **24 bars** (2 hours) of the cut-off. If it never does:
  **no fill**, which is recorded and counted - a plan that does not fill is a plan that earned nothing.
- After the fill, the first of stop or target decides the result. **A bar touching both counts as the
  stop.**
- If neither is touched within **48 bars** (4 hours) of the fill, the trade is closed at that bar's close.
  Enter on M5, exit on M5.
- R = (the move in my favour) / (entry - stop). Costs: the spread, **0.30 USD**, taken off every entry -
  the owner's real account pays about 30 points on gold.

## 5 What is written down

`ledger.csv` - one row a trade: sheet, panel, cut-off, side, entry, stop, target, fill, exit, exit reason,
R net of the spread, and the structure named at entry.

`SHEETS.md` - every panel's reading in my own words, written before the reveal, and the score after it.

`LESSONS.md` - only what the ledger supports, with the trade numbers that support it. Nothing that comes
from one trade.

## 6 What would make this worth keeping

The owner's bar is **+0.15 R a trade after costs**. The number this body of work has to beat is the one
measured the night everything was archived: **-0.115 R a trade**, where the direction was right 53.8 % of
the time and the winners paid only +0.643 R against losers at -1.00 R. So the question is not "is the
direction right" - it was already. It is **whether a hand-read entry at a live structure pays more than
one R when it is right**.

A hundred trades at a win rate near 50 % still carries a standard error of about 0.1 R, so a hundred will
show a shape, not a verdict. That is what the owner asked for: *see the picture*, not prove a system.
