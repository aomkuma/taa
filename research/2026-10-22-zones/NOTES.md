# The owner's zones - notes (kept current)

## The owner's principles (2026-10-22; he has repeated them many times - read before any zone work)

- **No sharp lines.** A zone line is a price LEVEL with a +- range: price may stop short of it or overshoot it. Allow
  for it: targets before the next line, stops beyond the band, never an entry "on the line" as such.
- **The zone is the plan; the edge is the entry point and timing.** "In life there are no sharp lines - it is planning,
  and finding the entry point and timing that has the edge." The grid tells where price is in its range, the next
  zone (the target) and the usual run (about half a zone); the entry comes from timing - a pattern, a sweep and
  reclaim, confirmation on the entry timeframe.

- **Reaching a zone is not a reason to trade.** Read the whole chart: how many times price has hit the level, and the
  trend and momentum at each touch up to now. With LL / LH and repeated hits on a support, it is not a buy (the level is
  being worn down and is more likely to break); the mirror at a resistance. The journal records, at every entry, the
  touch count of its band, the structure (HH/HL or LH/LL) and the momentum of each touch, before any of it becomes a rule.

## The zone grid (owner 2026-10-22, H4 XAUUSD Aug-Oct 2026)

- Gold ran in zones of about 70-90 USD (one D1 ATR(20)); inside them about half a zone.
- After a strong move the zone size is carried along in equal steps from the base the move left; the zone SHIFTS
  (re-anchors) on a new strong move; inside the grid an H4 close beyond a line moves the active zone and flips the
  line's role.
- v1 (`zone_grid_v1.py`): impulse = a D1 body >= 1.5 x ATR20; anchor = the body edge of the 2 D1 bars before it;
  step = ATR20 (daily). Fits the owner's lines 4293.24 / 4217.25 / 4141.83 / 4066.41 (and 4369 / 4445 / 4522)
  within 1-4 USD on 2026-10-21 (anchor 4293.03 = the 2026-09-23 open). Charts: `charts/zone_*.png`.

## Measured

- **How H4 turns sit around the lines** (learning period 2025-10-20 .. 2026-04-17, 364 fractal turns; `zone_band.py`,
  `zone_band_v2.py`): anywhere in the zone - about 20 % within +-0.10 step of a line, 40 % within +-0.20, median a
  quarter step (27 USD); the same by market size, by line, by month, and with straight (fixed-step) lines. So the line
  alone is not an entry; a band of about a third of a step catches ~70 % of turns.
- **Journal (Asia B2 in the NY window, `../2026-10-18-moments/agents/journal/ny_b2/`):** entries right on a line lost
  (2025-11-21: 2.4 and 0.3 USD from a line, both stopped); targets at the next zone line with half off at +1 R led the
  base by +5.4 R over weeks 2-5.

## The owner's example chart (2026-10-23, H4 2026-09-16 .. 10-23) and an open point

- Every leg ran line to line: 4,369 / 4,293 / 4,217 / 4,141 / 4,066 / 3,990 (76 USD steps; the grid re-anchored at
  the 2026-10-22 close: 4,142.26, step 74.08 -> lines 4,142 / 4,068 / 3,994, within 0-4 USD of the owner's).
- A 3-week range spanned two zones (4,066-4,217) with lower highs 4,220 -> 4,215 -> 4,198.7; Monday 19 Oct 20:00 Thai
  broke 4,141 on volume; three weaker re-tests from below (Tue 20:00 to 4,155.5, Wed to 4,141.9 / 4,141.2, Thu 00:00
  to 4,142.2) all closed back under it. The precise sell: the re-test, the stop above the already-swept 4,155.5
  (~25 USD), the target the next line 4,066 (~70 USD, ~3 R). Thursday 12:00 touched 4,066.7, 16:00 swept 4,057 and
  closed 4,088; the 20:00 NY bar broke 4,066 on the chart's highest volume (81k) and ran one zone to 3,990.
- Open point: the code's step = D1 ATR(20); after the February 2026 crash it rose to 220-240 USD, far above the
  owner's 70-90 (journal week 17: targets out of reach). To measure on the old years: do H4 turns keep ~70-90 USD
  spacing when the ATR is high, or widen with it?
