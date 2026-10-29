# Expectation, written before the run (Claude, 2026-10-29)

The owner, 2026-10-29: "find the answers by testing and proof" - for (1) which levels are major enough to block
the take-profit, and (2) whether the H1 lean is right (the 27/10 buy it refuses).

## Test 1 - the H1 lean (eye/research/lean_test.py)

Hourly moments inside the owner's windows, 2025-10 to 2026-10-27, the lean as the bot computes it (rule 1). The
outcome: from the moment's close, which comes first on M5 bars within 24 h - price X above or X below, X =
k x the median of the last 20 H1 ZigZag legs (k 0.25, 0.5, 1.0).

Expected: the lean side comes first 52-56 % of the time (a small edge); "no lean" near the unconditional rate;
the unconditional up-first rate above 50 % (gold rose over the year). A lean worth keeping beats the
unconditional rate for its side by clearly more than the noise (n in the hundreds: about +/- 4 points).
27/10: lean SELL most of the day (Hf 4034.23), flipping to BUY only after price traded above the H1 high
before Lf - i.e. late for the owner's buy.

## Test 2 - which levels price respects (eye/research/band_test.py)

Every time M5 price reaches a band (H1 or H4 fixed pivots, age >= 24 h, half-width 0.10 x the median of 20
legs, as rule 8), which comes first: a turn back by W beyond the near edge, or a break by W beyond the far
edge (W = the half-width x 2). Against a control: the same bands shifted to the midpoints between pivots.
Split by timeframe and by how many pivots of that timeframe fall inside the band (1, 2, 3+).

Expected: a single-pivot band turns price about as often as the control (near 50 %); bands with 2+ pivots
turn it more (55-60 %); H4 slightly above H1. If so, "major" = 2+ pivots, and single-pivot bands should not
block the target.
