# The decision checklist - everything the owner and I have agreed, in one place

Owner 2026-10-23: "has everything we discussed been recorded as data and used in the decisions?" It had been written
into several documents but not run at the moment of a decision - so known things were missed (a zone drawn as a sharp
box, a trailing stop in a pool, three bottoms + a sweep + higher lows and highs not seen). From now on every replay /
live step runs the tools below and answers EVERY item in writing before deciding; every new lesson is added here at
once (with its date and source).

The AI trader answers every item of A, B and C (pass / fail / n/a, one line each) before a new trade; the code stops
a trade whose HARD item failed or went unanswered. The items are mirrored in `app/strategy/checklist.py` (a parity
test keeps the two equal) and the answers go into the journal. Rewritten 2026-10-25 so no item reads two ways
(CHECKLIST_DRAFT.md, the owner's answers).

Tools at every step: `rhythm_scan.py` (every TF), `picture_read.py` (M5 / M15 patterns), `routine_read.py` (the zone
plan, strong levels, D1 context, volatility, the clock).
`knowledge/kb.py now` - what the knowledge base (`knowledge/kb.yaml`, the one source of truth: principles, rules,
weapons, shadows, findings, failed methods, lessons, open points) says applies at this moment; every new lesson is
added there as well, with its `when`.

## The verdict (one meaning for every item; owner 2026-10-25)

Each item is a yes / no question about **this trade** (this side, weapon, entry, stop and take-profit point).
**pass** = the answer supports this trade. **fail** = it argues against it - and a missing reading, "not checked" or
"unclear" are fail too. **n/a** = only in the item's own "n/a" case. The note quotes the reading or the map line used
(e.g. `d1_big=up`, `a BUY's stop beyond it 4101.20`). A **HARD** item that fails means no trade - the code stops it,
and an unanswered HARD item counts as failed. A **WEIGHTED** item that fails is evidence against, weighed with the
rest (P03). **Code** items are decided by the code; the AI copies the verdict.

## A. The forest (read first)

| # | The question (yes = pass) | yes / no / n/a | decides | kind | source |
|---|---|---|---|---|---|
| A1 | Does the D1 side (`d1_big`, hundreds of D1 bars) point the trade's way? | yes: it equals the side (up = BUY); no: the opposite; n/a: `none` | AI | WEIGHTED | P06, P07; memory taa-owner-tf-framework |
| A2 | Is the entry at support / resistance - inside the band (+-0.15 step) of a main or half line on the trade's stop side - or a pullback (A4) or a through-the-line weapon (W04 / W05)? | yes: one of them; no: mid-zone and not a pullback; n/a: W01 | AI | WEIGHTED | P05, P17 ("never mid-price except a pullback") |
| A3 | Is the path from the entry to the take-profit point clear of a strong level (the readers' strong levels) and of a main line's band? | yes: clear; no: a strong level or a main band before the take-profit point | AI | WEIGHTED | P06 |
| A4 | Does the M15-H1 trend agree: `h1_rhythm` = the side, and `m15_rhythm` = the side or `m15_leg` turned to the side after a counter-leg (a pullback ending)? | yes: as stated; no: `h1_rhythm` against; n/a: a fade / reclaim weapon that is with `d1_big` while the M15 / H1 rhythm is not running into the level (L17) | AI | WEIGHTED | P07; memory taa-owner-tf-framework; L17 |
| A5 | Is the H1 ATR(14) at most 1.1 x its 20-day median (`h1_vol` <= 1.1)? | yes / no from the reading | code R01 | HARD | R01 |
| A6 | Is it inside the owner's windows (`session` asia 07-09 / london 13-15 Thai / ny 08:00-11:30 New York) with no US release within 60 min, or is the weapon W01 when one is? | yes: both; no: `session`=none (passes only at confidence >= 70) or a release within 60 min and not W01 | code R09, R07 | HARD | R09, R07, P11 |
| A7 | Is the trade with yesterday's strong day (`yesterday`) and the D1 `phase`, or - if against a one-way run - is that run spent (`runaway`=none)? | yes: as stated; no: against them while `runaway` points against the trade; n/a: `yesterday`=none and `phase`=none | AI | WEIGHTED | P19, P04 |
| A8 | Is the trade the trade of one weapon listed under WEAPON now (its conditions hold)? A weapon of shadow status trades at half size (the code halves it). | yes: a listed weapon; no: none listed, or another weapon's trade | AI (the list: code) | HARD | P02, P08 |

## B. The picture at the level (the entry frames M1 / M5 / M15)

| # | The question (yes = pass) | yes / no / n/a | decides | kind | source |
|---|---|---|---|---|---|
| B1 | On the entry frame, do the swings since the level show higher lows AND higher highs (BUY) or lower highs AND lower lows (SELL), read from swings, not one bar's close? | yes: both; no: one of them only, or the mirror; n/a: W01, W03 | AI | WEIGHTED | P04, W09 |
| B2 | Is a completed chart pattern at the level on the entry frame and on M1 (double / triple bottom or top, H&S / inverse H&S, a base and its break, a sweep + higher low / lower high, a channel break, a break and retest, a triangle), with every entry frame agreeing? | yes: a named pattern whose trigger broke, or a pending order at a plan scenario's level (the rejection there is the pattern); no: none, half-formed, or a steep arrival; n/a: W01 | AI | WEIGHTED | P17; memory taa-entry-needs-chart-pattern; WEIGHTED since 2026-10-25 (as HARD it made the AI wait past every planned entry, L20) |
| B3 | Turn trades: was a level everyone sees (the day's, yesterday's or Asia's high / low, a round 50, a main line) on the stop side swept by >= 0.1 M5 ATR and closed back, the sweep bar's volume over 1.0 x the mean (`sweep`=low for a BUY, high for a SELL)? | yes: `sweep` reads the trade's side; no: the other side or none; n/a: continuation weapons (W01, W03, W04, W05, W08) | AI (the reading: code) | WEIGHTED | P18, W07, L19 |
| B4 | If price consolidated at a line (`bars_at_line` >= 8, `m15_range12_atr` < 3), is the trade in the direction THROUGH the line? | yes: through; no: a bounce off the line out of the consolidation; n/a: `bars_at_line` < 8 | AI | WEIGHTED | P10, F01, W04, W06 |
| B5 | If a line was pierced in the last hour (`line_break` up / down) and held, is the trade WITH the break? | yes: the side = `line_break`; no: the pierced line used as support / resistance against the break; n/a: `line_break`=none, or a sweep closed back (that is B3) | AI | WEIGHTED | W05; day 1 journal |

## C. The trade

| # | The question (yes = pass) | yes / no / n/a | decides | kind | source |
|---|---|---|---|---|---|
| C1 | Is the entry frame the smallest of M1 / M5 / M15 whose swing covers the 5 USD target, and is the exit planned on that frame with a time stop (a scalp out at 60 min, longer only while the entry frame's structure holds; W01 30 min; a turn weapon 120 min, R03)? | yes: both; no: a frame whose swing cannot reach 5 USD, mixed frames, or no time stop | AI | WEIGHTED | memory taa-adaptive-timeframe; P17; R03 |
| C2 | Is the trade NOT a flip to the other side after this weapon's stop-out in the same move (a same-side re-entry after a sweep is allowed)? | yes: not a flip; no: a flip; n/a: no stop-out today on this weapon | AI | HARD | R04 |
| C3 | Is the entry within half the pattern's height of where the turn or run starts (the pattern's extreme / the broken line) - not chasing? | yes: within it; no: farther (B2 once entered 1.7 heights late, F04) | AI | WEIGHTED | P04, F04 |
| C4 | Is the stop at or beyond the map's stop for this side (`a SELL's stop beyond it` / `a BUY's stop beyond it`), beyond the structure that proves the idea wrong, and not inside any liquidate zone? | yes: all; no: nearer than the map's stop, or inside a liquidate zone | AI (the map's stop: code) | HARD | P16, L16 |
| C5 | Is the take-profit point the next swing, at least 5 USD from the entry and short of the next main line's band? A liquidate zone is never the take-profit point. | yes: as stated; no: under 5 USD, beyond the band, or at a liquidate zone (a main band nearer than 5 USD = no trade); the actual TP 10 % short, never under 5 USD (code) | AI (the 5 USD floor: code) | HARD | P09, C5 owner 10-22, L19 |
| C6 | Does the decision state the exits: break-even when price touches +1 R (the code moves it), half off at +1 R only above 0.01 lot, the time stop (C1), and out when, after +0.5 R, an entry-frame bar closes against the trade? | yes: all stated; no: missing | AI | WEIGHTED | owner 10-23, 10-25; R03 |
| C7 | Is the size the owner's risk percent (the AI's half = half), with the 0.01-lot minimum recorded, never a veto? | yes / no from the lane | code | code | P15 |
| C8 | Is the entry now - triggered by the last closed entry-frame bar, or by one of the two before it while price is still within C3's distance - and not a missed trade taken late? | yes: as stated; no: a look-back entry | AI + code (closed bars only) | HARD | P13 |
| C9 | Has the structure this setup is built on NOT yet run its course (its take-profit point or the next line not reached since it formed)? | yes: not run; no: reached - a new trade on it is a finished cycle (P24); a same-side re-entry after a stop-out sweep is not | AI | HARD | P24 |

## D. After

| # | Item |
|---|---|
| D1 | Journal every trade AND every skipped signal (what it would have made), what the market did / what we did / what a hunter would have done |
| D2 | A lesson becomes a shadow rule; it applies only after its forward record holds (>= 4 weeks); costly rules are deleted |
| D3 | Add the lesson to this checklist at once |
| D4 | A method is judged only in the daily journal of the system as built, summed week by week - never by whole-period tables of a bare trigger (those check code parity or read a frozen exam) (L18) |
| D5 | An owner word that is new or ambiguous is restated and confirmed before it becomes a rule ("แอ่ง" was the stop's liquidate zone, read as a take-profit: L19) |

## E. The observer's habits (owner 2026-10-23: "always remember, always observe price")

| # | Habit | How it is done |
|---|---|---|
| E1 | Observe even when not trading | `observe.py` every hour of the trading day (Task Scheduler, `scripts/observe-task.ps1`, read-only): the readers' picture into `diary/<date>.md` |
| E2 | Remember | the diary + `diary/observations.jsonl` (every reading, written BEFORE the hour it is scored on) + this checklist + the journals |
| E3 | Know how good the eye is | each reading is scored on the next hour (with / against the M15 rhythm in USD, the half line reached first); the scorecard in every entry |
| E4 | Curious | a move no reading prepared for (>= 1 H1 ATR against the rhythm read; >= 1.5 ATR with no rhythm read; an hour's range >= 2 ATR) goes to `diary/TO_STUDY.md` - studied, never ignored |
| E5 | Before deciding, the scenarios in writing | A / B / C with trigger, stop, target - then scored against what price did |
| E6 | A miss the owner sees | in the same change: an item here, a permanent acceptance case (the owner's chart), a memory |
| E8 | Start of every trading day (replay or live) | the morning plan (P26): the market's condition, yesterday's support / resistance and key levels, the likely trend, the opportunities, the side with the edge, the turn-or-go-on points as scenarios (trigger / stop / take-profit point), releases and windows - from `research/2026-10-24-replay/premarket.py`, written to `plan_<date>.md`, summarised to the owner BEFORE the day is traded, its summary added to the AI's journal |
| E7 | Start of every session | read this checklist, the diary (latest day, TO_STUDY, scorecard) and the latest journal before any trading talk |
