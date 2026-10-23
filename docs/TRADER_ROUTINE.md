# The trader's routine (owner 2026-10-23)

"Imagine you sit at the computer this morning, open the chart, see the price structure, open the checklist and
have enough information to say which setups it fits. Every trade takes the most suitable setup; after it closes,
record it in the journal, find the mistakes, learn why it won or lost. This is the routine for a trader - all of it
without bias." (owner, 2026-10-23). The picture behind it: the market is a forest, the setups are weapons, the
situations are animals, and the clock tells when each animal comes out (docs/OWNER_GOALS.md).

Status marks: done = the bot's code passed its checks; partial; missing.

## 1. Before the session - read the forest (written and saved BEFORE the session, never edited after)

| Step | What | Status |
|---|---|---|
| Health | data complete (no gaps), server clock, MT5 link, spread, disk; the machine awake | done (breakers) / missing (sleep) |
| The plan | the zone grid (anchor, step, the last shift), the main and half lines around price with their strength, the strong levels hundreds of bars back | done (`zone_grid`, `strong_levels`) |
| The trend | yesterday's D1 bar (strong?), the 3-day phase, structure on D1 / H4 / H1 / M15 and whether the picture is clear | done (`context_read`, `structure_read`); the clarity rule is too strict |
| The pressure | volatility vs usual, today's run and range so far, momentum at the nearest lines (visits, bounces, worn, time at the line) | done (`context_read`, `level_momentum`) |
| The clock | today's sessions (Asia 07-09, London 13-15, NY 19:30-23 Thai) and the US releases | partial (the calendar lacks FOMC / PCE / GDP / PPI after 2026-10-15) |
| The animal | which situation is in front (elephant / tiger / boar / deer / rabbit / none) | missing (draft rules in `research/2026-10-23-entry/routine_read.py`) |
| The weapons | which weapons are armed today for that animal and session, which stay in the bag | missing (the situation -> weapon table) |

Tool today: `research/2026-10-23-entry/routine_read.py [AS_OF]` writes `live/<time>_read.md`; commit it at once.

## 2. Before every trade - the checklist (one "no" = no trade, and the reason is recorded)

1. The animal is known, and this weapon is measured for it.
2. The clock: inside the window where this animal appears; a release nearby makes it a tiger (news weapon only).
3. Volatility: not above the stand-aside line (H1 ATR <= 1.1 x usual) unless the weapon is built for it.
4. The zone plan: where price sits; the target before the next line; room to the next strong level.
5. A clear structure on the entry timeframe, agreeing with the one above (as the weapon requires).
6. Trend and momentum: the larger frames, a one-way run or not, the push into the level spent or not, the level worn.
7. A precise entry: not chasing - price has not already run from the start of the move; at least 1 R left to the
   target after the spread.
8. The stop beyond the structure that proves the trade wrong, and outside every liquidation pool (recent swings,
   round numbers, yesterday's high / low, swept wicks).
9. The exit plan of the weapon (the half at +1 R, the rest to the entry, the target before the line, the time exit).
10. Size: the account's risk percent; when the 0.01-lot minimum risks more, it is recorded, never a veto.
11. Cost: the spread under its ceiling.
12. Count: no stacking; about one trade a session (about three a day).
13. All the evidence weighted: the score passes (once weights have passed their gates).
14. Record before the order: every reading, the animal, the weapon, the reason.

## 3. During and after the trade

- Manage only by the weapon's plan; never move the stop farther away.
- After the exit: the best and worst excursions, the exit reason, R and USD.

## 4. The journal - every day, every week (without bias)

- Every trade AND every signal the checklist turned down, with what it would have made.
- What the market did / what we did / what a good hunter would have picked.
- Mistakes: which checklist item was wrong, missing or ignored; a lesson becomes a shadow rule, applied only after
  its forward record holds (at least 4 weeks), and deleted when it costs.
- Weekly to the owner, then wait for "continue".

## Bias guards

- The read is written and committed before the session; the review never edits it.
- Every trade and signal is listed - no picking the ones that fit a view.
- Rules are judged only on the weeks after they took effect; mined rules start as shadows.
- The owner's views and mine are prompts to measure; the market's record decides.
