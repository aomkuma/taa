# Agent "cross" - notes (2026-10-17)

Angle: other markets as the source of direction (indices, the dollar composite, risk-on/off crosses), minutes to
a few hours, H1 at most. Owner update (2026-10-17): trade gold **and the seven majors**; indices/crosses are inputs
only. Design only on 2023-11-01 .. 2026-03-01 (five halves: 23-11, 24-05, 24-11, 25-05, 25-11 [4 months]);
the one test per frozen rule on 2026-03-01 .. 2026-10-14 (index data ends 2026-10-05 23:59 UTC).

Files: `panel.py` (aligned M1 closes of gold + 12 markets, ffill <= 3 min; AUDJPY = AUDUSD x USDJPY; USD
composite of the six majors), `align_check.py` (timestamps: the cross-correlation of 1-min returns peaks at lag 0
for every input, winter and summer, all hours and London/late hours: no clock shift that could fake a lead),
`measure.py` / `measure2.py` (correlations by half), `buckets.py`, `screen.py` / `screen2.py` (episodes,
drift-adjusted), `fxlab.py` (instruments, real costs, the simulator; `check_sim.py`: 0 mismatches vs
`ny_lab.M1.trade` on 400 random gold trades with ny_lab's costs), `design.py` (the trade grid), outputs `out_*.txt`.

Costs (the auditor's): gold entry = spread column + 0.08 + 0.07 slip, stop slip 0.15 (0.20 in 12-17 UTC);
FX: spread column + 0.25 pip, entry slip 0.2 pip, stop slip 0.3 pip. R = P&L / (stop + stop slip).

## Step 1 - what relations exist (design data, corr x100, vol-scaled returns, every 5th minute)

Input's last L minutes -> the target's next H minutes (not the same minutes). Flag = same sign in 5/5 halves.

Gold (`out_measure.txt`, `out_measure2.txt`):
- Equities (US500/JP225/US100, mean of US500+JP225 = "eq") and AUDJPY lead gold **in the same direction**
  (risk-on -> gold up later), all hours: eq L60 -> H60 +4.3 +1.0 +1.3 +2.4 +4.4 (partial after gold's own
  move +4.5 .. +6.1). Strongest in New York 12-17 UTC (AUDJPY L60 H60 +1.6 +1.1 +6.0 +5.1 +10.8) and 17-21 UTC
  (eq L60 H60 +17.4 +1.6 +6.8 +2.6 +0.6 - one half dominates). Tiny: 1-5 % correlation.
- The dollar composite's last 30-60 min -> gold: no stable sign in most cells (consistent with h6: gold and the
  dollar move together in the same minutes, -31 .. -56 corr, and the lead is not there).
- Gold's own: late 17-21 UTC a small reversal at 15 min -> 60 (-3.5, 5/5).
- As episodes (|z| >= 2, drift-adjusted), gold's excess move over 60 min is 0.4-1.5 USD with hit rates 52-56 %:
  below what a 5 USD target / real costs need (7-15 win points over a coin).

Majors (`out_measure2.txt`) - the cleanest structure found, consistent across pairs:
- **London 07-12 UTC: equities up over the last 30-60 min -> the dollar up over the next 30-120 min.**
  EURUSD eq L30 H60 -1.8 -3.3 -3.0 -5.4 -6.3 (partial -3.0 .. -8.7), GBPUSD -1.8 -2.1 -1.0 -4.4 -3.0,
  USDCHF +3.1 +6.8 +6.0 +3.8 +2.6, USDCAD +3.4 +2.9 +0.5 +6.0 +12.4, USDJPY +0.4 +2.9 +3.9 +7.9 +3.6. Same sign
  5/5 halves in five pairs (AUD/NZD not). Note the same-minute sign is the opposite (EURUSD +9 with US500 in the
  same minute), so this is the dollar's later move, not co-movement.
- **17-21 UTC: the sign flips** - equities up -> the dollar down later: USDCHF eq L60 H60 -2.1 -3.7 -7.2 -4.6
  -9.0, US100 similar; GBPUSD/AUDUSD/NZDUSD up, USDCAD down (episodes).
- New York 12-17: AUDUSD/NZDUSD follow equities (+2 .. +5), USDJPY fades big equity moves (episodes).
- Episodes (`out_screen2.txt`, drift-adjusted, before costs): London |eq30| >= 2.5 -> 60 min: USDCHF +4.0 pips,
  EURUSD +3.6, GBPUSD +3.7, USDCAD +2.0 (5/5 halves each; n ~105 = one every ~5.5 trading days); US100_60 >= 2.5:
  EURUSD +4.8, USDCHF +4.7. Costs ~1.3-1.6 pips. Edge ~0.3-0.5 of the pair's 60-minute sd.
- Multiple testing: screen2 ran ~2,300 cells; the London cluster is believable because five pairs agree with one
  economic sign (the dollar), not because one cell is high.
