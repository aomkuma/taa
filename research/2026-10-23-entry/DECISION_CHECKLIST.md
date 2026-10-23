# The decision checklist - everything the owner and I have agreed, in one place

Owner 2026-10-23: "has everything we discussed been recorded as data and used in the decisions?" It had been written
into several documents but not run at the moment of a decision - so known things were missed (a zone drawn as a sharp
box, a trailing stop in a pool, three bottoms + a sweep + higher lows and highs not seen). From now on every replay /
live step runs the tools below and answers EVERY item in writing before deciding; every new lesson is added here at
once (with its date and source).

Tools at every step: `rhythm_scan.py` (every TF), `picture_read.py` (M5 / M15 patterns), `routine_read.py` (the zone
plan, strong levels, D1 context, volatility, the clock).

## A. The forest (read first)

| # | Item | Source | Tool |
|---|---|---|---|
| A1 | The big picture from hundreds of bars on H1 / H4 / D1: the trend (swings, LH / LL counts) - not the last few bars | owner 10-23 ("load hundreds of candles") | rhythm_scan big trend |
| A2 | The zone grid: main lines one step apart, half lines, as BANDS (+-0.15 step) - never sharp boxes; the plan, not the entry | owner 10-22 / 10-23 | routine_read |
| A3 | Strong levels hundreds of bars back; the room to them | owner 10-23 | routine_read |
| A4 | Every TF: which one has a rhythm now, and is the small TF's move a pullback of the big one | owner 10-23 ("look at every TF") | rhythm_scan |
| A5 | Volatility: above 1.1 x usual -> stand aside (the one rule that held twice) | journal + exam | routine_read |
| A6 | The clock: Asia 07-09, London 13-15, NY open (+1-2 h); scheduled releases (a release = the tiger) | owner 10-19 | routine_read |
| A7 | Yesterday's D1 bar (a strong day?) and the phase (a one-way run?) | journal | routine_read |
| A8 | The animal in front, and the weapon measured for it - or step back | owner 10-23 (the hunting picture) | (draft) |

## B. The picture at the level (the entry frames M1 / M5 / M15)

| # | Item | Source | Tool |
|---|---|---|---|
| B1 | Structure: higher lows AND higher highs (or the mirror) - read the swings, not one bar's close | owner 10-23 (21:45) | picture_read |
| B2 | Equal lows / highs: double / triple bottoms or tops at a level | owner 10-23 | picture_read |
| B3 | A sweep of a pool (under equal lows / a swing low) closed back, with volume -> the turn picture (level + price action + volume + volatility) | owner 10-22, 10-23 | picture_read |
| B4 | A consolidation at a line tends to break THROUGH it (measured +0.087, all four years); a bounce at a line alone lost | zone_wait.py | picture_read squeeze + routine_read |
| B5 | A line that has just been pierced is fuel, not support | day 1 journal | routine_read |

## C. The trade

| # | Item | Source |
|---|---|---|
| C1 | The weapon: SCALP (the knife: with the M15 rhythm and the big TFs; M1 / M5 entry; target >= 5 USD or the next swing, before the line's band; out <= 60 min) or SWING (the rifle: the H4 pullback ending at a big level) | owner 10-17 / 10-23 |
| C2 | Direction: with the big picture; no buy-bounce on a boar day under a pierced level; small-TF trades against the big TFs are not taken | owner 10-23 |
| C3 | A precise entry: not chasing; for a with-trend consolidation under a line, the room counts to the NEXT line beyond (shadow) | 10-23 review |
| C4 | The stop beyond the structure that proves it wrong AND outside every pool (swings, equal lows, round numbers, yesterday's H / L, swept wicks) - the first stop and every trailed stop | owner 10-19 / 10-23 |
| C5 | The target before the next line's band (allow it to stop short) | owner 10-22 |
| C6 | Exits: half at +1 R, the rest to the entry; a failed break (3 M5 closes back inside the range) -> out; "when the market grows unsure, take the profit and leave" | owner 10-23 |
| C7 | Size by the account's percent; the 0.01-lot minimum recorded, never a veto | owner 10-18 |
| C8 | No look-back trades: a missed trade is a lesson, never a trade | 10-23 |

## D. After

| # | Item |
|---|---|
| D1 | Journal every trade AND every skipped signal (what it would have made), what the market did / what we did / what a hunter would have done |
| D2 | A lesson becomes a shadow rule; it applies only after its forward record holds (>= 4 weeks); costly rules are deleted |
| D3 | Add the lesson to this checklist at once |
