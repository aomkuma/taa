# The decision checklist, rewritten so no item reads two ways - DRAFT for the owner (2026-10-25)

Status: a draft. Nothing here is in force; `DECISION_CHECKLIST.md`, `app/strategy/checklist.py` and `kb.yaml` are
unchanged. Every `[OWNER Qn]` is a meaning the sources do not settle; the questions are in section 3.

Sources read: `DECISION_CHECKLIST.md`, `app/strategy/checklist.py`, `app/strategy/kb.yaml` (P01-P25, R01-R09,
W01-W10, S01-S11, L16-L19), `docs/OWNER_GOALS.md`, `docs/OWN_SETUP.md`, `app/strategy/knowledge.py`,
`app/strategy/liquidity.py`, `app/strategy/behaviors.py`, `app/strategy/picture.py`, `app/ai/trader.py`, and the
memories named in the brief.

## 1. The verdict (one definition for every item)

Each item is a yes/no question about **this trade** (this side, this weapon, this entry, stop and target).
**pass** = the answer is the one that supports this trade. **fail** = the answer argues against this trade, and
that includes "the reading is missing" (write "no reading" in the note). **n/a** = only when the item's "n/a when"
column holds. That means the item does not apply to this weapon, or its reading is neutral (`none`) and so speaks
for neither side. Reasons like "not checked" or "unclear" are never n/a: they are fail. The note quotes the reading
or the map line used (e.g. `d1_regime=up`, `buy_stop 4,101.20`), never a paraphrase.
There are two kinds of item. A **HARD** item that fails means no trade, and the AI may not argue it away. A
**WEIGHTED** item that fails is evidence against, weighed with the rest (P03). **Code** items are decided by the
code from its readings and shown to the AI as already answered. The AI copies the code's verdict and never
re-judges it.

## 2. The items

Readings are the names in the READINGS json (`knowledge.features`). The "map" is THE LIQUIDITY MAP block
(`liquidity_lines`). "Entry frame" (E) is the frame named in C1.

| id | The question (yes = pass) | yes = / no = / n/a when | decides | kind | source |
|---|---|---|---|---|---|
| A1 | Does the D1 side, read as `[OWNER Q2a: d1_regime / d1_big / d1_rhythm]`, point the trade's way? | yes: the reading equals the trade's side (up = BUY). no: it is the opposite. n/a: it reads `none`. | AI (reading copy) | WEIGHTED | P06, P07; memory taa-owner-tf-framework ("The daily chart tells which side has the edge") |
| A2 | Is the entry at support / resistance? That means `line_dist_step` <= 0.15 (inside a `[OWNER Q8: main or main+half]` line's band) with the line on the trade's stop side. Or, if not, is the trade a named pullback (A4) or a through-the-line weapon (W04 / W05)? | yes: either one holds. no: price is mid-zone (`line_dist_step` > 0.15) and it is not a pullback. n/a: W01 (timed). | AI | WEIGHTED | P05, P17 ("never mid-price except a pullback"); memory taa-zones-bands-plan-timing |
| A3 | Between the entry and the take-profit point (C5), is there no strong level from the readers' strong levels (hundreds of bars) and no line band? | yes: the path to the target is clear. no: a strong level or band sits before the target. | AI | WEIGHTED | P06 ("they set the targets, the room"); S03 / S04 are shadows: note them, do not apply them |
| A4 | Does the M15-H1 trend agree with the trade? That is `h1_rhythm` = the trade's side, and `m15_rhythm` = the side, or `m15_leg` has turned to the side after a counter-leg (a pullback ending). | yes: as stated. no: `h1_rhythm` is against the trade, or both are against. n/a: a fade / reclaim weapon only if the owner answers `[OWNER Q2b]` "allowed". | AI | WEIGHTED | P07; memory taa-owner-tf-framework ("Find the trend in M15-1H"); W08 |
| A5 | Is the H1 ATR(14) at most 1.1 x its 20-day median (`h1_vol` <= 1.1)? | yes / no from the reading. | **code R01** (W10) | HARD | R01 (in force since 2026-04-17) |
| A6 | Is it inside an owner's window (`session` is asia, london or ny)? And is no US release within 60 min (`release_min` > 60), or, if one is, is the weapon W01? | yes: both hold. no: `session`=none (the code then needs `confidence` >= 70) or release <= 60 with a weapon other than W01. | **code R09, R07** | HARD (R09 passes at confidence >= 70) | R09, R07, P11; window edges `[OWNER Q1]` |
| A7 | Is the trade with yesterday's strong day (`yesterday` strong_up = BUY) and with the D1 `phase`? Or, if it is against a one-way run, is that run spent (`runaway`=none)? | yes: as stated. no: against a strong yesterday or phase while `runaway` points against the trade. n/a: `yesterday`=none and `phase`=none. | AI | WEIGHTED | P19, P04(3), S07 (shadow) |
| A8 | Is the trade the trade of one weapon listed under WEAPON now (its `when` holds), with a status the owner allows (`[OWNER Q7]`)? | yes: a listed weapon of an allowed status. no: no listed weapon, or a different weapon's trade. | AI (the list: code) | HARD | P02, P08 ("Recognise the animal first ... or step back") |
| B1 | On E, do the swings since the level show higher lows AND higher highs (BUY), or lower highs AND lower lows (SELL), read from swings, not one bar's close? | yes: both. no: only one of the two, or the mirror. n/a: W01, W03 (range break, timed). | AI | WEIGHTED | P04(2), owner 10-23 21:45, W09 |
| B2 | Is a completed chart pattern from the owner's set at the level on E and on M1? The set is double / triple bottom or top, H&S / inverse H&S, a base and its break, a sweep + higher low (lower high), a channel break, a break and retest, a triangle. And does every entry frame used agree? | yes: a named pattern, complete (its trigger broke). no: none, a half-formed one, or a steep arrival with no structure. n/a: W01. | AI | HARD | P17; memory taa-entry-needs-chart-pattern ("at least M1 must show a chart pattern") |
| B3 | Turn trades only: on M5, was a liquidate zone on the trade's stop side (equal lows / a swing low for a BUY) swept by >= 0.1 M5 ATR and closed back (`sweep`=low for a BUY, high for a SELL)? Was that at a level of the kinds `[OWNER Q5b]`, with the sweep bar's tick volume >= `[OWNER Q5a]` x the frame mean? | yes: all three. no: `sweep` reads the other side or none, or the volume is short. n/a: continuation weapons (W01, W03, W04, W05, W08). | AI | WEIGHTED | P18 ("a level + price action + volume + high volatility"), W07, W09, L19 ("W07's loose 'sweep'") |
| B4 | If price has consolidated at a line (`bars_at_line` >= 8 and the box <= 0.3 step, `m15_range12_atr` < 3), is the trade in the direction THROUGH the line? | yes: it trades through. no: it bounces off the line out of the consolidation. n/a: `bars_at_line` < 8. | AI | WEIGHTED | P10, F01, W04 ("a bounce at a line alone lost": W06) |
| B5 | If a line was pierced in the last hour (`line_break` up / down), is the trade WITH the break? | yes: the trade's side = `line_break`. no: the trade counts the pierced line as support / resistance against the break. n/a: `line_break`=none, or the move is a sweep closed back (`sweep` on that line: that is B3, not B5). | AI | WEIGHTED | day 1 journal, W05; S01 (shadow) |
| C1 | Is E the smallest of M1 / M5 / M15 whose ATR(14) covers the 5 USD target? And does the planned exit (frame and time stop) match the weapon: a scalp out <= 60 min `[OWNER Q9]`, W01 30 min, W03 60 min, a turn weapon (R03) 120 min? | yes: both. no: a smaller frame whose swing cannot reach 5 USD, a mixed entry / exit frame, or no time stop. | AI | WEIGHTED | memory taa-adaptive-timeframe (10-18 / 10-20); P17 ("enter and exit on the same frame"); R03 |
| C2 | Is the trade NOT a flip to the other side after this weapon's stop-out in the same move? (R04; a same-side re-entry after a sweep is allowed.) | yes: not a flip. no: a flip. n/a: no stop-out today on this weapon. | AI | HARD (R04, in force for B2 / turn weapons) | R04. Shown, not applied: S01, S10, S11 (shadows) |
| C3 | Is the entry within `[OWNER Q6]` of where the turn or run starts (the pattern's extreme / the broken line), i.e. not chasing? | yes: within it. no: farther (B2's late entry was 1.7-1.8 pattern heights past the extreme: F04). | AI | WEIGHTED | P04(1), OWNER_GOALS "late entry" |
| C4 | Is the stop at or beyond the map's stop for this side (`a SELL's stop beyond it` / `a BUY's stop beyond it`)? And is it beyond the structure on E that proves the idea wrong, and not inside any liquidate zone in the map? | yes: all of these. no: nearer than the map's stop, or on / inside a liquidate zone. | AI (the map's stop: code) | HARD | P16, L16, S02; memory taa-terms-liquidate-zone-take-profit |
| C5 | Is the take-profit point at least 5 USD from the entry, at `[OWNER Q3a]`, and short of the next `[OWNER Q8]` line's band (the line -/+ 0.15 step)? A liquidate zone is never the target. | yes: as stated. no: under 5 USD, or beyond the band, or set at a liquidate zone. If the band is nearer than 5 USD: `[OWNER Q3b]`. | AI | HARD (the 5 USD floor) | P09; memory taa-flexible-arsenal ("The >= 5 USD target floor is fixed"), user-gold-pip-usd, L19 |
| C6 | Does the decision state the exits: break-even at +1 R by `[OWNER Q4a]`, half off at +1 R only when the size is above 0.01 lot, the time stop (C1), and the exit when `[OWNER Q4b: 'the market grows unsure']`? | yes: all stated. no: missing. (A pre-trade check of the plan; the management itself is judged at HOLD / EXIT.) | AI | WEIGHTED | owner 10-23; R03; S06 is a shadow |
| C7 | Size: the risk % from the owner's profile, with the AI's `half` = half the risk. Is the 0.01-lot minimum recorded and never a veto? | yes / no from the lane. | **code** (ai_lane risk_scale) | code | P15, memory taa-small-account-streak |
| C8 | Is the entry a trade at the current price (or a pending order not yet passed), triggered by the last `[OWNER Q10]` closed bar(s) of E, and not a trade that was missed earlier? | yes: as stated. no: a look-back entry. Closed bars only: code (CandleService). | AI + code | HARD | P13 |
| C9 | Has the structure this setup is built on NOT yet run its course (its target, or the next line, not reached since it formed)? | yes: not run. no: the target has been reached. A new trade on that structure is then a re-entry of a finished cycle (P24). A same-side re-entry after a stop-out sweep is not a finished cycle (R04). | AI | HARD | P24 (owner 10-23 22:05) |

## 3. Questions for the owner (one line each)

- **Q1 Windows (Thai time).** P11 and the memory say London "13:00-14:00, plus or minus a little" and NY "the open +
  1-2 h" (the cash open is 09:30 NY = 20:30 Thai in summer). R09 and the code use London 13:00-15:00 and NY
  08:00-11:30 NY time. Memory taa-owner-tf-framework (10-20) adds "NY tends to run up to 4 hours". Options:
  (a) London 13-14, NY 09:30-11:30 NY; (b) keep the code: London 13-15, NY 08:00-11:30 NY; (c) London 13-15,
  NY 09:30-13:30 NY (open + 4 h).
- **Q2a The D1 side reading.** The roles are settled (memory taa-owner-tf-framework: D1 = the side, M15-H1 = the
  trend, M1-M5 = entry / exit / stop; "the big TFs" in C1 / C2 = these). Which reading is "the daily side"?
  (a) `d1_regime` (D1 over a rising 50-day mean, P25's split); (b) `d1_big` (500 D1 bars); (c) `d1_rhythm`.
- **Q2b Fades against M15-H1.** May a fade / reclaim (P02 "fade the false break", W07) trade against the M15-H1
  trend? (a) never; (b) only when it is with D1 and the M15 / H1 are not running into the level (L17); (c) yes when
  B2 + B3 pass, at half size.
- **Q3a The target when the next swing is farther than 5 USD.** The 5 USD floor is settled (taa-flexible-arsenal).
  (a) always 5 USD; (b) the next swing (quick, but bigger); (c) the nearer of the next swing and half the zone.
- **Q3b The band nearer than 5 USD.** (a) skip the trade; (b) trade, with the target just before the band.
  "The TP 5-10 % short" is (c) taken off the swing / band, never below 5 USD.
- **Q4a Break-even at +1 R.** The code needs an M1 close at +1 R (L19: the best closes were 0.96 / 0.93 R and never
  armed it). Options: (a) a touch (bid / ask) of +1 R; (b) an M1 close at +1 R; (c) a touch at +0.8 R.
- **Q4b "The market grows unsure, take the profit and leave".** (a) an E-frame close against the trade after
  +0.5 R; (b) the M15 rhythm turns against; (c) no progress for half the time stop.
- **Q5a The sweep's volume.** (a) the sweep bar's tick volume > 1.0 x the frame mean (what `picture.sweeps`
  records); (b) >= 1.5 x; (c) no volume condition.
- **Q5b "A level everyone sees" (W07).** (a) the day's high / low, yesterday's high / low, the Asia range, round 50s
  and main zone lines; (b) (a) + M15 swing highs / lows + equal tops / bottoms; (c) everything the map lists (what
  the code does now).
- **Q6 "Chasing".** (a) entry at most 0.5 pattern heights past the extreme / line; (b) entry-to-the-map's-stop at
  most 1.5 x the distance from the structure to that stop; (c) entry at most 0.25 step from the level's band.
- **Q7 Weapons in shadow status** (W04, W05, W06, W08, W09; W07 partial). (a) the AI may trade them; (b) only real /
  partial ones are traded, shadows are recorded; (c) shadows at `half` size only.
- **Q8 Which lines are support / resistance and targets.** With half lines, every price is at most 0.25 step from a
  line. Bands of +-0.15 then cover 60 % of all prices, which leaves very little "mid-price". (a) main lines only;
  (b) main and half lines; (c) main lines for targets, both for entries.
- **Q9 The scalp's hold.** "Out <= 60 min" (C1) vs "hold for a short trend run when the picture is clear"
  (user-gold-pip-usd) vs R03's 120 min. (a) 60 min always; (b) 60 min, longer while the E structure holds;
  (c) per weapon (R03 for turns).
- **Q10 How late is still "now" (C8).** (a) only the trigger bar just closed on E; (b) up to 2 E bars, if price is
  still within C3's distance; (c) whenever C3 passes.
- **Q11 R02's reach.** As coded, R02 (D1 ATR(20) < 60, "PLAN-1's pieces") vetoes every AI trade too (finding 1).
  (a) intended; (b) PLAN-1 only, so drop it from the AI's brakes; (c) the AI trades at `half` below 60.

## 4. Other ambiguities and contradictions found

1. **R02 vetoes the AI** (`app/ai/trader.py` `rule_vetoes`). `STAND_ASIDE = {"stand_aside", "stand_aside_plan1"}`,
   so R02 (`action: stand_aside_plan1`, says "PLAN-1's pieces trade only while ...") stops every AI BUY / SELL
   while `d1_atr20` < 60. Two readings: a PLAN-1-only switch, or a market-wide one. Fix: owner Q11, then scope it
   with a `side` / lane field.
2. **"A failed item is a reason not to trade unless you say why it does not matter here"** (CHARACTER). This lets
   the AI argue away any failure, including the stop (C4), the pattern (B2), C8 and C9. Fix: the HARD / WEIGHTED
   split in section 1. A failed HARD item = no trade.
3. **"Pool" vs "liquidate zone".** KB P04 ("outside every liquidation pool"), P16 ("outside every pool"), S02,
   S05, W09, L16 and OWNER_GOALS ("the pools everyone sees") still say pool. CHARACTER mixes "liquidation zone"
   and "liquidate zone". These texts go verbatim into the system prompt. Fix: "liquidate zone" everywhere, on the
   stop side only.
4. **The map prints "above:" / "below:" without saying which side each list serves.** A BUY can read "above" as
   its targets, which is exactly the L19 misreading. Fix: label the lists "above (a SELL's stop side)" and
   "below (a BUY's stop side)", plus a line: "not targets".
5. **The C5 floor contradicts "the actual TP 5-10 % short of it".** 5-10 % short of a 5 USD target is 4.50-4.75,
   which breaks the fixed floor (taa-flexible-arsenal). Fix: Q3b(c).
6. **Shadows written as rules in the checklist.** C2 "no buy-bounce on a boar day under a pierced level" is S01,
   and C2 "small-TF trades against the big TFs are not taken" is S10. C3's room is S04, and C6's failed break is
   S06. The KB says shadows are "never applied until it holds >= 4 weeks". Fix: move them to "shown, not applied"
   notes (done in the draft).
7. **"Mid-range" (CHARACTER) vs P17 "never mid-price except a pullback".** CHARACTER drops the pullback exception.
   Fix: copy P17's words.
8. **`confidence` is undefined, yet R09 gates on it (>= 70).** `buy_odds` / `sell_odds` are defined ("reaches its
   target before its stop") but `confidence` is not. Fix: define confidence = the chosen side's odds, or state
   what else it means.
9. **P09 "when the market grows unsure, wait" vs C6 "take the profit and leave".** One is an entry rule (wait),
   the other an exit rule (leave). Fix: keep both, named apart (A8 / step back for entries; C6 Q4b for exits).
10. **P03's "C1 > C2 > ... > C9" is SPEC section 3's nine evidence components** (zone plan, structure, trend ...),
    not the checklist's C1-C9 (weapon, direction ...). Same names, different lists. Fix: rename SPEC's to
    E1-E9 or W-order.
11. **B5 vs W07.** "A pierced line is fuel" vs "a false break closed back is traded back". The reading
    `line_break` = the last M15 close is in a different half-line cell than 4 bars before (any half line, no
    hold). W05 says "an H1 close beyond" a zone line. Fix: B5 applies to a close-and-hold, B3 to a sweep closed
    back. Align `line_break` with W05's H1 close, or write the M15 definition into W05.
12. **The sweep reading is looser than the words.** `recent_sweep` / `level_sweep` take any M5 equal-tops pool,
    day swing, the day's / yesterday's high or low, or a zone line (half lines too), with no volume test.
    `picture.sweeps`' docstring says "with the bar's volume over the frame's mean", but that volume is only
    recorded, never filtered. P18 / W09 / B3 say "with volume" and W07 says "a level everyone sees". Fix: Q5.
13. **The map's structure is 2 h of M5 (`STRUCTURE_M5 = 24`).** For a SWING (the H4 pullback, C1 "the rifle") or
    an E of M15, "the structure that proves it wrong" is larger. Two readings: the map's stop is always enough,
    or it is a minimum. Fix: C4 reads "at or beyond" the map's stop (a minimum).
14. **Three trend readings per frame** (`*_rhythm` ZigZag, `*_big` 500 bars, `*_trend` close vs a rising 50-bar
    mean), but CHARACTER says "read hundreds of bars of trend" and the checklist says "the big TFs". Fix: each item
    names its reading (A1 / A4), plus Q2a.
15. **KB `items` mapping slips.** S10 (against H1 and H4 rhythm) is tagged [A3] and S11 (no SELL in a bull regime)
    is tagged [A2]. Both are direction items (A4 / C2). R09 cites P11 but disagrees with it on London.
16. **CHARACTER's "a trade every day ... waiting a whole window out needs a stated reason"** vs P08 / P23 ("or step
    back", "trades less"). One can push the AI to force a trade. Fix: add "a failed HARD item, or no weapon whose
    animal is present (A8), is the stated reason".
17. **C6's "half" and the AI's size `half`.** One means closing half the position at +1 R, the other half the risk
    at entry (`risk_scale=0.5`). Fix: call the exit "part-close"; a half-risk 0.01-lot trade cannot part-close.
18. **A5 "1.1 x usual" vs memory taa-stand-aside-high-volatility's VOL-16 (H1 ATR 12-16 USD).** R01 settles A5
    (H1 ATR(14) / its 20-day median > 1.1). VOL-16 is an absolute band found after the run and is not in force.
    The checklist text should quote R01, not "usual".
19. **Adaptive E: "ATR covers 5 USD".** The readings expose only `h1_atr` (and the map's M5 ATR); M1 / M15 ATR
    are not shown to the AI. Fix: add `m1_atr`, `m5_atr`, `m15_atr` to the readings, or let the code name E.

## 5. Redundant or overlapping items

| Overlap | Proposal |
|---|---|
| C1 and C5 both state the target ("target >= 5 USD or the next swing, before the line's band"); CHARACTER repeats it a third time | The target lives in C5 only; C1 = the entry frame and the hold; CHARACTER cites "C5" |
| C4 restates P16 (P16 says "pool") | C4 = the question; P16 reworded to "liquidate zone"; CHARACTER cites C4 instead of restating it |
| C2 "with the big picture" = A1 + A4 | C2 becomes the R04 no-flip check; direction lives in A1 (D1) and A4 (M15-H1) |
| B1 / B2 / B3 vs P17 / P18 | B2 carries P17's pattern (HARD); B1 the swings; B3 P18's turn picture; B2's equal lows as a stop zone moves to C4 |
| C3 "not chasing" vs C9 "the finished cycle" vs C8 "no look-back" | C3 = distance from the start (Q6); C9 = the structure's target already reached; C8 = the trigger is now (Q10) |
| A2 (bands) vs C5 (the target before the band) vs A3 (room to strong levels) | A2 = where the entry stands; A3 = what lies on the path; C5 = where the target sits |
| A5 vs W10, A6 vs W01 / R07 | Code items, prefilled; W10 / W01 stay in the weapon catalogue |
| C6 vs R03 (half at +1 R, break-even, 120 min for turn weapons) | C6 points to R03 for turn weapons and states the scalp's own exits |
| C7, C8 (closed bars) | Code; shown as prefilled, not answered by the AI |
