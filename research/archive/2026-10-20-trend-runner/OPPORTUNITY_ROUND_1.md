# TR1 opportunity study - round 1 definitions

Written before computing: 2026-10-20 13:58 Thai time (06:58 UTC). No TR1 P1 outcome had been computed when these
definitions were written. P2 and the exam remain locked.

This is a descriptive P1 study, not a frozen trading rule. Its purpose is to determine whether a causal first-pullback
entry leaves enough continuation to justify building a runner.

## 1. Population

XAUUSD, FBS-Demo, weekdays in P1: 2025-10-18 through 2026-01-15. One opportunity is sought independently at each of
three anchors:

- Asia: 07:00 Thai;
- London: 13:00 Thai;
- New York: 08:30 New York, DST-aware.

A day is usable when its first M1 bar is available within five minutes of the anchor and the last completed H1
ATR(14) is available. An anchor is not filled at its opening price.

## 2. Impulse - three settings, all reported

The reference is the open of the first M1 bar at or after the anchor. H is the MT5 ATR(14) of the last H1 bar whose
clock end is at or before the anchor.

The three predeclared thresholds are `0.25 H`, `0.50 H` and `0.75 H`.

For each threshold, the impulse is the side of the first M1 close within 60 minutes of the anchor that is at least the
threshold away from the reference. A close above chooses buy; a close below chooses sell. When the same close could
qualify both because of malformed data, the event is refused. If neither side qualifies, there is no opportunity for
that threshold and anchor.

The impulse is known at that M1 bar's close. Its side is never taken from a later maximum excursion.

## 3. Entry timeframes

The same first-pullback definition is measured independently on M1, M5 and M15. Round 1 does not choose the best
timeframe or combine their entries. Every timeframe/threshold result and candidate count is printed.

Bars are built from M1. Each bar becomes available at its clock end even when its final minute has no tick.

## 4. First valid pullback

For the impulse side, scan entry-timeframe bars whose availability is after the impulse confirmation. A pullback pivot
is a radius-1 confirmed fractal:

- buy: a low no higher than the lows of the bar immediately before and after it;
- sell: a high no lower than the highs of the bar immediately before and after it.

The pivot is usable only after the right-hand bar closes. Equal lows/highs are allowed; the earlier confirmed pivot is
examined first.

For a buy:

- the impulse extreme is the highest high from the anchor through the pivot;
- pullback depth is `impulse extreme - pivot low`;
- impulse span is `impulse extreme - anchor reference`;
- the pivot low must remain above the anchor reference;
- depth/span must be from 0.20 through 0.65 inclusive.

The sell case is mirrored. A zero or negative impulse span is invalid. Fractal pivots that do not qualify are reported
as rejected and scanning continues to the next pivot; the first qualifying pivot is the first valid pullback.

## 5. Continuation entry

The continuation level is the formation's extreme in the impulse direction:

- buy: the maximum high of the pivot bar and its immediate left/right bars;
- sell: the minimum low of those three bars.

After the pivot is confirmed, the decision is the first entry-timeframe bar that closes beyond that level. Entry
deadlines measured from the anchor are:

- Asia and London: 120 minutes;
- New York: 240 minutes.

The market entry is the first raw tick at or after the decision bar's clock end, no later than five minutes after it.
A buy fills at ask; a sell fills at bid. Entry slippage is 0 in the primary study.

The initial stop is past the pullback pivot by a buffer equal to the larger of:

- the bid/ask spread at the fill;
- 0.10 times entry-timeframe ATR(14), using the latest bar available at the decision.

Reject a candidate whose price risk is below `0.05 H` or above `0.50 H`. These limits keep a tiny/noisy stop and a
whole-session stop out of the same population. Every rejection reason is counted.

There is at most one candidate per anchor, threshold and entry timeframe. Round 1 does not impose one-position-at-a-
time across these parallel descriptive cells.

## 6. Opportunity labels - not available to the entry

From the same fill and initial stop, follow raw bid/ask ticks for at most eight hours. A buy is marked on bid and a
sell on ask.

Record:

- whether the stop occurs before +1R;
- first passage to +1R, +2R, +3R and +5R before the stop or eight-hour end;
- time to each milestone;
- maximum favourable and adverse excursion in R;
- adverse excursion from entry through each milestone's first passage (or through the observed path when that
  milestone is not reached);
- the maximum giveback after first reaching +1R and +2R;
- whether the position remains open at the next session anchor;
- the outcome at 60, 120, 240 and 480 minutes using the first quote at or after the horizon.

A gap through the stop is filled at the first worse quote. A milestone is credited at its declared R price, not at an
improved gap price. Same-millisecond quotes keep file order. If an eight-hour path would cross the P1 end, it is
truncated at P1 end and labelled incomplete rather than reading P2.

## 7. Report - no selection in this step

For every window x impulse threshold x entry timeframe cell, report:

- usable anchors, impulses, valid pullbacks, fills and each rejection reason;
- median impulse, pullback depth, risk/H and time from anchor to entry;
- shares reaching 1R/2R/3R/5R before the stop;
- MFE, MAE, giveback and holding-time distributions;
- collisions with the next anchor;
- the full candidate rows in `opportunities_p1.parquet`.

The report may describe stable patterns but must not declare a winning rule. Any rule selected from this study is
written into `FROZEN_ROUND_1.md` before P2 is enabled.

For the saved rows, pullback depth is divided by H. Pullback duration is the elapsed time from impulse confirmation
to pivot confirmation; this is descriptive metadata and is not an entry filter.
