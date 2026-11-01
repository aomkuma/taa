# Short sample: prior-session POC/VA levels on XAUUSD M5

**Run date:** 2026-10-31 (Asia/Bangkok)
**Sample:** five consecutive, complete broker sessions; active session dates 2026-10-20 through 2026-10-26 UTC, corresponding to 2026-10-21, 22, 23, 26, and 27 in Bangkok.
**Source:** local FBS-Demo XAUUSD ticks and M5 bars.

## What this run shows

This is a compact demonstration of the method, not a performance conclusion. All 5 sampled sessions passed coverage: 274 M5 bars each, with tick quotes at the first and last active bars. The levels below are calculated from the immediately preceding completed session only.

| Active session date (Bangkok) | Prior-session VAL | POC | VAH | Median spread |
|---|---:|---:|---:|---:|
| 2026-10-21 | 4117.4 | 4122.7 | 4135.0 | 0.29 |
| 2026-10-22 | 4119.3 | 4132.1 | 4140.3 | 0.28 |
| 2026-10-23 | 4039.9 | 4091.6 | 4102.8 | 0.31 |
| 2026-10-26 | 4003.9 | 4023.9 | 4032.5 | 0.30 |
| 2026-10-27 | 4005.2 | 4017.2 | 4024.3 | 0.30 |

Profile construction: midpoint quote updates are binned in $0.10 increments; POC is the most active bin, and VAH/VAL bound a contiguous range around the POC containing at least 70% of quote updates. A touch zone is max($0.05, twice prior-session median spread). This is a broker quote-activity proxy, not centralized executed volume. TradingView's description likewise distinguishes tick volume for Forex/CFDs and defines POC/VA as the highest-activity price and a chosen share of profile activity ([reference](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/)).

## Rules replayed

- VAL long / VAH short: M5 touches the edge zone and closes back inside the edge; target POC.
- POC long / short: M5 touches the POC zone and closes on the reclaimed/rejected side; target VAH/VAL respectively.
- Entry uses the first quote after the M5 close (ask for long, bid for short). Stop sits beyond that signal bar's wick by at least one prior-session median spread.
- Quotes are replayed in time order. Only one position is open at a time; at most one trade per level and direction per session.

## Sample result

| Setup | Trades | Winners | Net price points per 1 oz | Targets | Stops |
|---|---:|---:|---:|---:|---:|
| VAL/VAH edges | 7 | 3 (42.9%) | +15.35 | 3 | 4 |
| POC line | 7 | 3 (42.9%) | +14.78 | 3 | 4 |
| Combined | 14 | 6 (42.9%) | +30.13 | 6 | 8 |

The combined gross profit factor was 2.02. Within these 14 trades, POC longs lost 17.25 points and POC shorts gained 32.03; the directional difference is an unstable observation from only 3 and 4 trades. Results include spread through ask/bid fills, but exclude commission and additional slippage. One ounce is a reporting unit, not a suggested size.

The short sample happens to be positive before commission/slippage. It does not establish an edge; the sample is only five sessions and the outcomes are direction-sensitive. The first full-window run was stopped as the basis for conclusions when the owner requested a single short period; its raw outputs are retained separately in `../diagnostic_full_window_2025-10_to_2026-10/` for transparency and are not part of this sample's result.

## Files

- `daily_levels.csv`: levels calculated for each sampled session
- `trades.csv`: entry, exit, stop, target, and per-trade outcome
- `session_coverage.csv`: session coverage checks
- `summary.csv`, `by_level.csv`, `monthly.csv`: grouped summaries
- `../../run_poc_test.py`: reusable run script

Reproduce with:

```powershell
.\.venv\Scripts\python.exe research\xauusd_poc_m5\run_poc_test.py --start 2026-10-20 --end 2026-10-26 --output-dir research\xauusd_poc_m5\sample_2026-10-20_to_2026-10-26
```
