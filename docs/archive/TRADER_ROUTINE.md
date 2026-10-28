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

### The day report of a replay or live day (owner, 2026-10-28)

One day at a time, and each day reported in full before the next is read. The owner asked for exactly four
things, so the report has four parts and no padding:

1. **Every decision where the measurer disagrees with the AI.** The measurer reads each wake themselves -
   the readings, the picture, the checklist - and states their own call before looking at what followed.
   Only the disagreements are listed: a WAIT the measurer would also have waited through is left out
   (owner 2026-10-26). Each disagreement names the time, what the AI decided, what the measurer would have
   done, and which checklist item or knowledge-base entry divides them. `code sees / same?` in the
   generated report is the code's weapon reading against the AI's: a machine against a machine, not this.
2. **Every trade in detail.** The table has these columns and is not complete without them (owner,
   2026-10-28 - the first version left out the four that decide whether a weapon is worth keeping):

   | column | why it is there |
   |---|---|
   | the owner's window | Asia 07-09, London 13-15, New York 19:30-23 Thai - which session the entry sits in |
   | in / out, Thai time | when, to the second |
   | **the strategy that entered** | the weapon (W01..W09) or "the morning plan, scenario X"; a result per weapon is the only way to judge one |
   | side | BUY / SELL |
   | entry | the fill |
   | **SL** | the stop as placed |
   | **TP** | the take-profit as placed - not just "it left on TP"; a target never reached is itself the finding |
   | exit, and why | the price and the reason (TP, SL, SIGNAL, time) |
   | **the holding time** | how long the trade was open; a quick winner and a long scratch are different trades |
   | R | after costs |
   | USD and lots | on the reference account |

3. **Profit and loss** on the **150 USD account** - the owner's real account size (150 USD at 1:2000). R a
   trade, R summed, net USD, the balance at the day's end and the day's worst drawdown. One account, not a
   pair: a second account computed from the first account's trades rather than run through the engine shows
   growth that could never have happened. On 2026-07-06 the arithmetic 100 USD account read +14.23 USD while
   the same account run through the engine took one trade of the three and ended **-0.35** - the engine
   refused the other two (RISK_BELOW_MIN_LOT, MAX_TOTAL_OPEN_RISK, DAILY_LOSS_LIMIT). Any further account
   size is its own engine run, never arithmetic on another's trades; the AI's prompt carries no account or
   position size, so the stored answers are reused and it costs nothing.
4. **The day's close:** what the market did, what the system did, what a good hunter would have picked, and
   the one lesson - which goes to the knowledge base as a shadow, never straight to a rule.

`research/archive/2026-10-24-replay/day.py <date>` produces parts 2-4 and the table of every wake. Part 1 is the
measurer's own work and is written on top of it.

**During a measurement run the code does not change** (`docs/CODING_STANDARDS.md` section 11): a run whose
days sit on different code versions is not a record of one system, which is the fault that cost the AI
trader's first record. Lessons from day 1 are applied after the last day, as the next run.

## Bias guards

- The read is written and committed before the session; the review never edits it.
- Every trade and signal is listed - no picking the ones that fit a view.
- Rules are judged only on the weeks after they took effect; mined rules start as shadows.
- The owner's views and mine are prompts to measure; the market's record decides.
