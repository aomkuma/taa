# Setup OWN - the owner's own trade: the moments when gold runs

The owner's goals and principles are in `docs/OWNER_GOALS.md`; the setup's place among the owner's trades in
`docs/OWNER_TRADING.md` ("Setup OWN"). This file holds the method, the hypotheses (written down before any outcome
is computed) and the results, month by month as they finish. Results describe the past, never a promise.

## Data and years

Gold (XAUUSD, FBS-Demo), M1 for the paths and M5/M15/H1/H4/D1 for the context: `data/history_old` (2020-09 ..
2023-10) and `data/history` (2023-08 .. 2026-10). Years: E 2021-10 .. 2022-09, D 2022-10 .. 2023-09, C 2023-10 ..
2024-09, A 2024-10 .. 2025-09, B 2025-10 .. 2026-09. **Development uses only predictions for A and B** (their
training windows reach back into C); **E, D and C are judged once, after the method is frozen.**

## The moments

All clock times DST-aware (zoneinfo), on weekdays:

| Moment | Local time | Note |
|---|---|---|
| Asia | 09:00 Asia/Shanghai (01:00 UTC) | the Asian peak in every year |
| Tokyo | 09:00 Asia/Tokyo | |
| London | 08:00 Europe/London | |
| COMEX | 08:20 America/New_York | gold futures open |
| New York data | 08:30 America/New_York | the release slot |
| New York cash | 09:30 America/New_York | |
| Release | its time (CPI, Employment Situation, PPI, PCE, GDP advance 08:30 ET; FOMC 14:00 ET) | official calendar, `data/news/us_releases.csv` |

Moments within 15 minutes of each other on a day are one row with all their tags. Control rows: the same
features at every other half hour of the trading day, for base rates.

## Measures (relative, as of the moment, from closed bars only)

- **Usual run U:** the median, over the previous 20 trading days, of the 30-minute high-low range after this
  moment's clock time. Every distance below is in units of U unless named otherwise.
- **Contraction:** the M5 Bollinger(20) width and ATR(14) as percentiles of the previous 20 trading days of M5
  bars; the 60 minutes before the moment as a share of U. **Squeeze** = BB-width percentile at most 20.
- **Pools:** the previous broker day's and week's high/low, the Asian range so far (00:00-07:00 UTC), the
  previous session's range, the H1 and H4 chart-read levels (`ChartReadFrame` levels), round numbers (multiples of
  10 and 50 USD). **At a pool** = the nearest pool within 0.25 U of the price.
- **Flow:** the H4 market map's state (tide) and the H1's (wave), from the last closed bars. The flow's direction
  = H4's if it trends, else H1's if it trends, else none.
- **Pool side:** a pool *ahead* lies in the flow's direction from the price, *behind* against it.
- **Regime:** the 20-day average daily range and that range over the median spread.

## The three playbooks and their exits

| Playbook | Entry (within 30 minutes of the moment, M1 closes) | Stop |
|---|---|---|
| P1 break-and-hold | a close beyond the nearest pool, and the next bar does not close back | beyond the pool's other side + 0.1 U |
| P2 sweep-and-reclaim | price trades beyond a pool, then closes back inside within 5 bars: trade back the other way | beyond the sweep's extreme + 0.1 U |
| P3 with the flow | at the moment, in the flow's direction | beyond the pre-moment hour's range + 0.1 U |

Target 0.5 U (half the usual run: the quick profit); time stop 60 minutes; one position at a time; fills as the
engine (next bar's open, a BUY at the ask, stops and targets on bar highs/lows with a SELL's on the ask, both in
one bar = the stop) with 7 points of slippage each way (`research/2026-10-17-s1/s1_funnel.py`).

## Hypotheses (fixed 2026-10-17, before any outcome is computed)

- **H1:** squeeze, at a pool ahead (the flow's side) -> P1 in the flow's direction pays after costs, and more than
  at the same moments without a squeeze.
- **H2:** squeeze, at a pool behind -> P2 (the sweep against the flow, then back with it) pays after costs.
- **H3:** no squeeze and no pool within 0.25 U -> no playbook pays after costs (stand aside).
- **H4:** the paying playbooks' R grows with the 20-day range over the spread.

## The selector (how the system chooses in the present)

- Context cell = moment type x squeeze (yes/no) x pool side (ahead / behind / none) x flow (up / down / none) x
  regime (tertiles of the range over the spread in the training window).
- For each cell and playbook: the mean R shrunk toward the playbook's mean in the window (empirical Bayes,
  weight 20 trades, as `app/advisory/calibration.py`); the cell trades its best playbook only when that mean
  minus one standard error clears +0.05 R; otherwise it stands aside.
- Re-fitted at each month's start on the previous 12 months; each month is predicted only from the past.

## Gate to the engine

Five years walk-forward: at least +0.15 R a trade (tolerance +0.10), at least one trade a day on average, at
least 60 % of months positive, at least breakeven in the quiet years E and D. Below it: report the gap, add
candidate causes and try again - with each new rule written down here first.

## Results

(none yet)
