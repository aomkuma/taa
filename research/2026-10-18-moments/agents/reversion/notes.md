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

**Result (`r4b.py`, `r4b_out.txt`):** the stop order *through* a round level beats the placebo levels in 8-9 of 10
half-year comparisons at S = 10 (mean R -0.065 .. -0.150 against placebo -0.109 .. -0.248, about +0.04 .. +0.06 R)
and 5-8 of 10 at S = 5. So round numbers carry a real, consistent asymmetry (break through > bounce), in line with
the cause. But it is small: every variant still loses (best S 10, D 2, 6/6 ATR: -0.065 R; H5 -0.14), the costs of a
stop entry (0.15-0.20 slippage) eat it. A context factor, not a setup: "do not fade into a fresh round level; a
breakout through one is a little better than through an arbitrary price".

### The account constraint (BRIEF.md, 2026-10-17)

50-100 USD at 0.01 lot: a loss of about 5 (50 USD) to 10 USD (100 USD) a trade at most, gaps included. ATR(60) of the
M1 range was 2-5 USD in 2025-11 .. 2026-02 and 1.5-3.5 in 2026-04 .. 10, so a 10-ATR stop is 15-50 USD: **the 10/10
geometry is not usable on this account.** From here every rule skips a signal whose stop would exceed 10 USD.

### Round 5 - why the losers lose (`diag.py`, `steps.py`, charts `ch_tdl4_*.png`; development only)

The design rule (round 3) with the account in mind: **TDL4** = buy the dip in an H1 uptrend / sell the rally in a
downtrend when the close is >= 3 ATR from the 60-bar mean, BUY limit 1 ATR below the ask (SELL 1 ATR above the bid),
valid 15 min, stop and target 4 ATR, 120 min, 07:00 London .. 15:30 ET, skip when the stop would exceed 10 USD.
(The 10/10 ATR version, TDL10, ran -0.016 R with a worst loss of 170 USD at 0.01 lot - not usable.)

Situations at the entry, TDL4 baseline (3,073 trades, -0.128 R) and after the first filters (526 trades):

| Situation (TDL4) | Losers in | Winners in | R with / without | Worse in |
|---|---|---|---|---|
| London session | 52 % | 49 % | -0.164 / -0.094 | 4 of 5 |
| M15 EMA20 slope against the trade (the dip has turned M15 down) | 45 % | 42 % | -0.161 / -0.103 | 4 of 5 |
| Low half of the 4-hour range the trade's way | 73 % | 70 % | -0.146 / -0.084 | 3 of 5 |
| *after those three:* the first fall off a fresh 4-hour top (buy) / bottom (sell) | 67 % | 60 % | -0.061 / +0.061 | 4 of 5 |
| a fast 15-bar leg against (>= 4 ATR) | 46 % | 39 % | -0.092 / +0.031 | 4 of 5 |
| a flat H1 (close within 0.85 H1 ATR of EMA50) | 32 % | 28 % | -0.098 / +0.016 | 4 of 5 |
| a round 10 level within 2 ATR behind the entry | 16 % | 23 % | +0.154 / -0.061 | better in 4 of 5 |

The charts say the same in a trader's words: the losers are mostly *the first sharp drop off a fresh high* - price
ran up into a 4-hour top, then fell hard for 10-20 minutes and our limit filled inside that fall (kind 1, stopped
within 5-30 minutes); the winners are one- or two-bar spikes that snap back, or dips inside a quiet rising range.

| Step (development, real costs) | Trades (a day) | R | By half-year H1..H5 | Worst | Streak | Max DD (USD) |
|---|---|---|---|---|---|---|
| TDL4 baseline | 3,073 (4.24) | -0.128 | -0.226 -0.147 -0.106 -0.071 -0.007 | -10.2 | 14 | 1,157 |
| no London | 1,617 (2.23) | -0.093 | -0.181 -0.084 -0.069 -0.042 -0.045 | -10.2 | 11 | 525 |
| + M15 not against | 1,004 (1.39) | -0.042 | -0.173 +0.029 -0.101 +0.059 +0.024 | -10.2 | 8 | 212 |
| + upper half of the 4h range (W) | 526 (0.73) | -0.017 | -0.156 +0.099 -0.189 +0.097 +0.111 | -10.1 | 10 | 155 |
| W + H1 not flat (**REV-A**) | 376 (0.52) | +0.013 | -0.240 +0.118 -0.164 +0.200 +0.235 | -10.1 | 6 | 77 |
| W + not off a fresh 4h extreme + 15-bar < 4 ATR | 194 (0.27) | +0.046 | -0.103 +0.244 -0.358 +0.281 +0.053 | -10.1 | 8 | 81 |
| W + all three (**REV-B**) | 142 (0.20) | +0.171 | -0.120 +0.395 -0.211 +0.483 +0.260 | -10.1 | 5 | 40 |

H1 and H3 stay negative in every step: the M1 range was 0.5-0.9 USD then, so the 4-ATR stop was 2-3.5 USD and costs
took 0.15-0.25 R a trade; the coin lost about as much (REV-A H1 -0.240 vs coin -0.158, H3 -0.164 vs -0.181; H2 +0.118
vs -0.089, H4 +0.200 vs -0.050, H5 +0.235 vs +0.039). Cost in R in H5: 0.06. Tick replay of REV-A's 52 trades
2025-10 .. 2026-02 (`tc_rev.py`): every M1 fill filled on ticks, the same exit in 98 %, R +0.279 on M1 vs +0.280 on
ticks.

### FROZEN 2026-10-17, before the test window is computed: REV-A (main) and REV-B (declared variant)

Gold M1, real costs (ask = bid + spread column + 0.08; stop fills 0.15, 08:00-12:00 ET 0.20; limit fills no slippage
and only when the price trades 0.01 through the limit). Decide at a bar's close i (closed bars only):
1. Time: 08:00 .. 15:30 New York time (session New York 08:00-12:00 ET or the afternoon 12:00-15:30 ET; not London
   07:00 London .. 08:00 ET, not Asia); the last 60 bars without a gap.
2. The H1 trend (closed H1 bars): +1 when EMA20 of H1 closes rose on the last bar and the last H1 close > EMA50;
   -1 the mirror; else no trade. Side = the trend.
3. The stretch: dv60 = (close - mean of (H+L+C)/3 over the last 60 M1 bars) / ATR60 (ATR60 = mean high-low of the
   last 60 M1 bars). BUY when dv60 <= -3 in an up-trend; SELL when dv60 >= +3 in a down-trend.
4. M15: the EMA20 of M15 closes (last closed M15 bar minus the one before) not sloping against the side.
5. The 4-hour range: (close - low240) / (high240 - low240) >= 0.5 for a BUY, <= 0.5 for a SELL (240 M1 bars).
6. H1 not flat: |close - H1 EMA50| >= 0.85 x H1 ATR(14).
7. The account: skip when 4 x ATR60 > 10 USD.
8. Order: BUY limit at (close + spread + 0.08) - 1 x ATR60, SELL limit at close + 1 x ATR60, valid 15 minutes; stop
   and target 4 x ATR60 from the fill; time exit after 120 minutes or before the daily break; one position or
   pending order at a time.
REV-B = REV-A plus: 9. not the first fall off a fresh 4-hour extreme (BUY: the 60-bar high is below the 240-bar
high; SELL: the 60-bar low above the 240-bar low); 10. the 15-bar move against the side < 4 ATR60.
Test once: 2026-03-01 .. 2026-10-14, month by month, with the seeded coin (5 seeds) and the losers' kinds.

### THE TEST (run once, 2026-03-01 .. 2026-10-14; `freeze_check.py ... --test`, `test_revA.txt`, `test_revB.txt`)

| Rule | Trades (a day) | Win % | R/trade | Coin R (5 seeds) | Edge (R points) | USD at 0.01 lot | Coin USD | Months + | Worst | Streak | Max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| REV-A (frozen) | 59 (0.30) | 29 | **-0.379** | -0.147 | -0.23 | **-163.3** | -65.8 | 1/8 | -10.08 | 6 | 165 |
| REV-B (declared) | 29 (0.15) | 31 | **-0.332** | -0.139 | -0.19 | **-73.5** | -30.5 | 0/8 (2 flat) | -10.08 | 5 | 78 |

REV-A by month (trades, USD): 03 1 -10.1; 04 6 -27.8; 05 8 -33.6; 06 12 -24.8; 07 11 -41.6; 08 12 +10.5; 09 5 -22.4;
10 4 -13.6. Losers' kinds 51/32/16 % against the coin's 45/29/26 %: more wrong-way (kind 1) and fewer entered-too-early
(kind 3) than the coin. Cost in R 0.06. Average loss 6.9 USD: six in a row = 41.6 USD - fits a 100 USD account, not a
50 USD one; the worst single loss 10.08 USD (the 10 USD cap + slippage). The cap also skipped almost all of March
(the M1 range > 2.5 USD): 1 trade.

**It fails, and worse than the coin.** The step table on the test window (informational, after the test;
`test_steps_tdl4.txt`) shows why: every filter learned on the design data turned the other way.

| Step (TEST) | Trades | R | USD | Max DD |
|---|---|---|---|---|
| TDL4 baseline | 549 (2.82/d) | -0.089 (coin -0.049) | -348 | 423 |
| no London | 272 | -0.185 | -358 | 405 |
| + M15 not against | 148 | -0.241 | -259 | 294 |
| + upper half of the 4h range (W) | 78 | -0.380 | -214 | 214 |
| W + H1 not flat (REV-A) | 59 | -0.379 | -163 | 165 |
| W + all three (REV-B) | 29 | -0.332 | -73 | 78 |

The test's own losers (TDL4 baseline, 549 trades; `diag.py tdl4 --test`): the situations that marked the design
losers marked the test *winners* - low half of the 4-hour range -0.033 vs -0.229 without, M15 against -0.026 vs -0.141,
London -0.016 vs -0.168, flat H1 -0.023 vs -0.136. Only three kept their sign in both: a last bar against >= 1 ATR
(-0.159 vs -0.045), a fast 15-bar leg against >= 4 ATR (-0.127 vs -0.058) and the first fall off a fresh 4-hour
extreme (-0.115 vs -0.078) - the "falling knife off a fresh top" the charts showed - plus the afternoon 12:00-15:30 ET
was the worst slot (-0.262, 30 % of trades, 34 % of losers). Gold fell from ~5,000 to ~4,100 with wide swings in the
test months; dips bought in an H1 uptrend there were mostly the start of the next leg down.
Cut-loss only (the "stages"): fewer trades cut the USD loss (-348 -> -73) and the drawdown (423 -> 78), but R got worse;
that is smaller exposure, not a better rule.

### Round 6 - round numbers on the FX majors (`fx.py`, `fx_round2.py`; development only, not tested)

Costs: the spread column x point + 0.2 pip on the ask, 0.2 pip slippage on market fills, stops and time exits; a
limit / stop entry must trade 1 point through. (Fixed on the way: the simulator's 0.01 "through" margin was gold's
0.01 USD - for FX it is now one point; gold results unchanged.) 50-pip levels, 07:00 London .. 15:30 ET, fresh
(untouched 30 bars), 3 .. 20 pips away, valid 30 min.
- Bounce (limit at the level), 15/15 pips: worse than the placebo levels on EURUSD, GBPUSD (0/10), USDJPY (0/10),
  USDCHF; mixed on AUD/NZD; USDCAD the exception (7/10). Every pair -0.12 .. -0.20 R.
- Through (stop at the level), 15/15: beats the placebos on EURUSD 7/10, GBPUSD 8/10, USDJPY 10/10, USDCHF 9/10 (by
  0.03-0.09 R); AUD/NZD/CAD no. Still -0.05 .. -0.11 R.
- Through, wider (30/30 pips, 480 min): EURUSD -0.005 R (D 10: +0.005; 8/10 over placebo; H5 -0.12 to -0.15),
  USDJPY -0.001 (9/10), GBPUSD -0.08, USDCHF -0.05. Break-even at best, before any test.
Round numbers carry the same consistent asymmetry in gold and in four majors (Osler: price goes through a fresh
round level more often than through an arbitrary one, and bounces less), worth 0.04-0.09 R - real, but smaller than
the cost of a stop entry. Use it as context (never fade into a fresh round level), not as a setup.

### Verdict (2026-10-18)

- Limit entries: they save the 0.07 entry slippage and fill 55-85 %; they do not pick the side. Tick replay agrees
  with the M1 approximation (R +0.279 vs +0.280 on 52 trades; 98 % same exit).
- Fading stretched moves (z-scores 1-30 min, distance from 15/30/60-bar means and EMAs, Bollinger), with or without
  the H1 trend, at market or at a limit: about a coin on the design data once generalised (round 3 edge +0.015 R),
  and the rule built from the design losers (REV-A, +0.013 R design, +0.12 over the coin) lost -0.379 R on the test
  (coin -0.147). The design-data situations flipped sign on the test.
- What kept its sign in both periods (worth carrying to other agents as filters): no entry right after a bar of
  >= 1 ATR against, no entry inside a fast 15-bar leg >= 4 ATR against, no buying the first fall off a fresh 4-hour
  top (selling the first rally off a fresh 4-hour bottom); and round numbers break more than they bounce.
- Account: a 4-ATR stop capped at 10 USD gives a worst loss of 10.08 USD and an average loss of ~7 USD at 0.01 lot:
  six in a row ~42 USD - fits 100 USD, not 50 USD.
