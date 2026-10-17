# Reversion agent - limit entries and fading stretched moves (gold M1)

Folder: `research/2026-10-18-moments/agents/reversion/`. Run everything from the repo root with
`PYTHONPATH=research/2026-10-18-moments/agents/reversion` and `REV_CACHE=<scratch dir>`.

## Files

- `common.py` - bars (M1, bid + spread), sessions, H1 trend (EMA20 slope + close vs EMA50, closed H1 bars only),
  the half-years (DEV H1..H5, before 2026-03-01) and the test window.
- `feats.py` - features at a bar's close: ATR(60) of the M1 range, z-scores of the last k = 1..30 minutes against
  the 60-minute std of 1-minute changes, distance from 15/30/60-bar mean typical price and EMA20/50 in ATR,
  Bollinger(20) position, H1 trend, session.
- `sim.py` - vectorised trade simulator (market and limit entries, stop/target/time, break-even, losers' kinds).
- `allsim.py` - every development minute simulated on both sides for a geometry (cache), so a rule is scored at once;
  the coin = the mean of both sides at the rule's own minutes.
- `scan.py` - the rule scan (feature x threshold x session x H1 trend x fade/follow x geometry).
- `tickcheck.py` - replays trades on ticks (2025-10+) to check the M1 approximation.
- `f1_stretch.py` - first measurement: gross fade returns after |z| >= 2 / 3.

Sessions: 0 Asia 00:00-07:00 UTC; 1 London 07:00 London .. 08:00 ET; 2 New York 08:00-12:00 ET; 3 the rest.
Geometry in ATR(60) units of the M1 range (relative, follows the current pace).

## Simulation of limit orders (written before any result)

A BUY limit at ask level L = (bid close + spread) - off x ATR, valid V minutes from the next bar, fills on the first
bar whose ask low (low + spread) <= L - 0.01, at min(L, the bar's ask open). A SELL limit at bid level
L = close + off x ATR fills when high >= L + 0.01, at max(L, open). No fill = no trade (the pending order blocks other
signals until it expires). After the fill: stop on the adverse side's extreme (-0.07 slippage), target as a limit (no
slippage), both in a bar = the stop; in the fill bar only the stop counts (the target is not credited). Time exit at
the close + slippage. A break (> 5 minutes without a bar: the daily break, weekends) closes the trade at the last
bar's close before it (from scan v1 on; v0 dropped such trades); a break right after the decision bar = no order.
Hand-checked (2025-12-03 15:01 / 15:38 / 16:31 UTC): market fill 4210.73 + 0.23 + 0.07 = 4211.03, target 4222.30
first reached at 15:18 (high 4224.40), stop 4213.70 hit at 16:53 (low 4209.97) for -6.71; limit 4207.17 filled at
15:02 (ask low 4206.31), target at 15:07; the sell limit 4232.06 never reached = no trade.

## Log

### F1 - gross fade returns after a stretch (`f1_stretch.py`, development only)

|z| >= 2 or 3 over k = 1..15 minutes, the next 5..60 minutes, price-scaled to 4100 gold, gross of costs: means of
-0.3 .. +0.4 USD with no sign kept in all five half-years for any (k, h) overall. Asia: the stretch tends to
*continue* (fade negative in most cells); London: the fade is slightly positive at h = 5 in all five half-years
(+0.1 .. +0.4 USD gross at |z| >= 3, k = 1..5) - about the size of the costs; New York: mixed, H5 continues. The H1
trend filter does not help the fade at this scale. Conclusion: a gross reversion of a few tenths of a USD exists at
the 5-minute scale in London; nothing near the 0.3-0.4 cost plus a profit.

### Round 0 - baselines (`r0.py`; z5 >= 3 fade, 3 x ATR stop and target, 60 min)

| Variant | H1 R | H2 R | H3 R | H4 R | H5 R | coin R (H1..H5) |
|---|---|---|---|---|---|---|
| market | -0.250 | -0.206 | -0.116 | -0.111 | -0.112 | -0.30 -0.21 -0.16 -0.14 -0.06 |
| limit 0.5 ATR, 10 min | -0.252 | -0.203 | -0.115 | -0.084 | -0.047 | -0.33 -0.21 -0.13 -0.14 -0.03 |
| limit 1 ATR, 10 min | -0.309 | -0.168 | -0.104 | -0.132 | -0.037 | -0.30 -0.18 -0.13 -0.14 -0.02 |
| limit 2 ATR, 15 min | -0.316 | -0.149 | -0.180 | -0.126 | -0.009 | -0.22 -0.18 -0.19 -0.17 -0.03 |

The fade of a 5-minute stretch is a coin, at market or with a limit. Costs in R are set by the ATR: 2023-24 had an M1
range of 0.3-0.9 USD against a 0.24 spread (costs ~0.2-0.3 R at 3 ATR); 2025-26 has 2-5 USD (costs ~0.03-0.05 R).
A limit entry cuts the cost a little (no entry slippage) and fills 55-85 %.

### Scan v0 (`scan.py`, 10 geometries x 13 features x thresholds x 5 sessions x H1 filter x fade/follow)

Superseded by v1 (the simulator then dropped every trade that crossed the daily break; now it closes before it).
10,366 rules with >= 60 trades in every half-year; 4.6 % had an edge over the coin (R ours - R coin, the coin = the
mean of both sides at the same minutes) in all five half-years against 3.1 % by chance alone (1/32) - a weak excess.
Where the excess sat: session 3 (US afternoon/evening, 12:00 ET .. 24:00 UTC) 9.6 %, fading a stretch *with* the H1
trend (buy dips in an uptrend) 8.5 % against 1.7 % for fades against it, the wide 6/6 ATR geometry 9.2 %.
Three families stood out:
- A: US afternoon, fade a distance >= 3 ATR from the 60-bar mean, with the H1 trend (buy the dip in an uptrend);
- C: New York morning, *follow* a 15-bar push (dv15 >= 3 ATR) with the H1 trend, entering on a 1-ATR limit pullback;
- B: Asia, follow a 10-15 minute push with the H1 trend.

### Scan v1 (break-aware simulator; `scan_dev.csv`, `rank.py`)

10,446 rules; 4.1 % with an edge over the coin in all five half-years (chance 3.1 %). The excess again sits in rules
*with* the H1 trend (8.3 % vs 1.4 % against it) and session 3. Against a second baseline - the H1 trend alone
(every minute of the session with a trend, side = the trend; `fam.py`) - the trend alone is a coin (trend R = its
coin R within +-0.04 in every half-year), so the families' edges do not come from the trend alone.

### Costs from here on (BRIEF.md "Real costs")

`sim.COST = REAL`: the ask = bid + spread column + 0.08 (entries, limit fill checks, a sell's stops/targets and time
exits), stop fills slip 0.15 (New York 08:00-12:00 ET 0.20), entry slippage 0.07 at market, none on a limit fill.
R = USD / (stop + 0.07).

### Round 2 - the three families refined (`r2.py`, `r2_out.txt`; development, real costs)

Mean R over H1..H5, the coin's, edge = the difference (R points):
- NYC (New York, follow a 15-bar push >= 3 ATR with the H1 trend, limit 1 ATR back, 3/3 ATR, 60 min): -0.001 vs coin
  -0.130 (edge +0.13), but fragile: threshold 2.5 -> edge +0.02, 4.0 -> -0.03; market entry +0.11; off 1.5-2 ATR
  +0.06. A peak, not a plateau - most of it is the scan's selection.
- NYB (New York, fade Bollinger(20) >= 2.5 sd with the H1 trend, limit 1 ATR, 6/6 ATR, 120 min): +0.029 vs -0.044
  (+0.07); neighbours +0.04 .. +0.10 (6/8 ATR, 180 min: +0.035 R, +0.10 edge); threshold 3.0 breaks (-0.10, few
  trades). Losers 68/19/14 % vs the coin's 67/22/11 % - no kind stands out.
- PMA (US afternoon 16-20 UTC, fade a 4-ATR distance from the 60-bar mean with the H1 trend, 6/6, 120 min): -0.017 vs
  -0.063 (+0.05); the limit entry helps (+0.08 / +0.09 edge at 0.5-1 ATR, mean R +0.005; at 2 ATR +0.029 R). Kind 3
  ("entered too early") 35 % vs the coin's 17 % at market - the deeper limit takes it (31 %, 38 % vs coin 50 % at 2 ATR).
In every family H1..H4 are negative (costs 0.1-0.3 R when the M1 range was < 1 USD) and H5 positive (+0.1 .. +0.24).

### Round 3 - one rule for the day (`r3.py`, `r3_out.txt`)

Written before it was computed: buy the dip in an H1 uptrend / sell the rally in a downtrend when the close is
>= 3 ATR from the 60-bar mean, limit 1 ATR further, 6/6 ATR, 120 min, London + New York + the afternoon to 15:30 ET.
Result: mean R -0.049 vs coin -0.064, **edge +0.015** (3.65 trades a day); every neighbour (feature, threshold,
offset, geometry) within -0.01 .. +0.04 except z15 >= 2.5 (+0.12, 0.8 a day, one half-year carries it). Against
the trend -0.008, no trend +0.007. **Generalised, the stretch-fade with the H1 trend is a coin**; the families'
+0.05 .. +0.13 were mostly the scan picking the luckiest cells. What does cut the loss: wider geometry (10/10 ATR,
240 min: -0.010 R vs -0.108 at 4/4/90) - fewer, bigger trades make the costs smaller in R, not the side better.

| Step (development mean R, H1..H5) | R | coin | edge |
|---|---|---|---|
| baseline z5 fade at market, 3/3 ATR (round 0, old costs) | -0.159 | -0.17 | +0.01 |
| fade with the H1 trend, 60-bar distance, limit 1 ATR, 6/6 (round 3 base) | -0.049 | -0.064 | +0.015 |
| same, 10/10 ATR, 240 min | -0.010 | -0.052 | +0.042 |

### Round 4 - round numbers with resting limits (written 2026-10-17 before it is computed)

Cause (Osler 2000/2003 on FX order books): take-profit and resting limit orders cluster at round numbers, so price
tends to stall / bounce at the first touch of a round level, while stop orders sit just beyond it. A limit entry is
the natural tool: it waits at the level. Rule: at a bar's close in London / New York / the afternoon (07:00 London ..
15:30 ET), if the nearest round level below the bid (multiple of S USD) is 0.5 .. D ATR away and has not been
traded in the last 30 bars, place a BUY limit there (fills when the bid trades 0.01 through it), valid 15 minutes;
the mirror SELL for the nearest level above; when both qualify, the nearer. Stop k ATR, target m ATR from the fill,
hold 120. **The judge is the placebo**: identical rule with the levels shifted by 0.37 S (and 0.63 S); the round
number matters only if it beats both placebos in most half-years. S in {5, 10, 50}; D in {2, 4}; (k, m) in
{(3, 3), (4, 6), (6, 6)}.

**Result (`r4.py`, `r4_out.txt`):** the bounce at round numbers is *worse* than at placebo levels: at S = 10 the round
level beat the placebos in only 1-3 of 10 half-year comparisons (mean R -0.09 .. -0.16 vs placebo -0.04 .. -0.12,
i.e. 0.03-0.07 R worse), at S = 5 even, at S = 50 mixed (fewer trades). No bounce; if anything price goes *through*
round numbers more often (Osler's other half: stops cluster beyond round levels and accelerate the move).

### Round 4b - through the round number with a stop order (written before it is computed)

Mirror of round 4, same windows and freshness: the nearest round level 0.5 .. D ATR away, a SELL stop at the level
below (fills when the bid trades 0.01 through it, at the level or worse - 0.15 slippage, New York 0.20) / a BUY stop
at the level above; valid 15 minutes; stop k ATR, target m ATR, 120 minutes. Judge: the same against the placebo
levels (0.37 S and 0.63 S). S in {5, 10}, D in {2, 4}, (k, m) in {(3, 3), (4, 6), (6, 6)}.
