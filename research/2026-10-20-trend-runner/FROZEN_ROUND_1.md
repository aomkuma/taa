# TR1 frozen round 1

Frozen: 2026-10-20 15:00:30 Thai time (08:00:30 UTC), before any TR1 P2 read. The exam remains locked and is not
supported by the frozen runner.

## Frozen entry

- XAUUSD FBS-Demo; Asia 07:00 Thai, London 13:00 Thai and New York 08:30 local/DST-aware.
- Last completed H1 ATR(14) is H. The first M1 close within 60 minutes at least 0.25 H from the anchor reference sets
  direction.
- First causal M1 radius-1 opposite fractal, pullback ratio 0.20-0.65, without crossing the anchor reference.
- First later M1 close beyond the three-bar continuation extreme; deadlines are 120 minutes for Asia/London and 240
  minutes for New York.
- Market fill on the first raw quote within five minutes: ask for buy, bid for sell, zero primary slippage.
- Stop beyond the pullback pivot by max(fill spread, 0.10 M1 ATR). Accept initial risk from 0.05 H through 0.50 H.
- All three sessions and both directions remain included. There is no result-derived state or session filter.

## Frozen selected exit: SPLIT

- One third closes at exactly +1R. Before that partial, a stop closes the full position.
- Two thirds follow the causal structure trail with no profit target.
- Start at the initial stop. Ratchet on post-entry M5 radius-1 pivots with max(entry spread, 0.10 M5 ATR) buffer;
  never widen.
- When executable price first reaches +3R, retain the current stop, ignore later M5 pivots and use only M15 pivots
  confirmed at/after graduation.
- Maximum intended duration is eight hours; exit on the first executable quote at/after the deadline.
- Bid marks/stops longs, ask marks/stops shorts; ordered equal-time quotes are retained; stop gaps fill at the worse
  quote and declared targets at the declared price.

FAST, SWING and STATE are frozen controls on the same entries. They cannot replace SPLIT after P2 is read.

## P1 result known at freeze

SPLIT: 138 complete trades, +0.265 mean R, +36.52 total R, +192.92 USD at 0.01 lot, 31.9% positive, 13.16R maximum
drawdown and 9/13 positive weeks. Removing the best trade leaves +0.147R/trade; removing the best three leaves
-0.017R/trade. The individual-trade bootstrap interval crosses zero. London supplied most of the result, and the
+16.424R winner is visibly exceptional. These weaknesses are frozen and must be judged honestly in P2.

The common P1/P2 runner reproduced all 138 entries and 552 exit rows exactly. Independent raw-quote replays passed
for all 364 opportunity-study rows and all 552 exit rows. Real-data truncation, 56 unit tests, 14 foundation mutants,
8 opportunity mutants and 9 exit mutants passed. Twelve P1 charts (six winners, six losers) matched the rule.

## Integrity and validation command

`freeze_manifest.json` stores SHA-256 for the executable source, exact rule documents and P1 artifacts. The runner
checks every hash before any P2 data loader is enabled. The one permitted P2 command is:

`python research/2026-10-20-trend-runner/frozen_round.py --period P2 --allow-validation`

Any hash mismatch aborts before the P2 bar reader or tick store is called. P2 selects nothing and changes nothing;
it reports SPLIT plus the three frozen controls. A failed SPLIT result marks this round failed. It does not authorize
switching to the best P2 control.
