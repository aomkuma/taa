# Second short sample: prior-session POC/VA levels on XAUUSD M5

**Run date:** 2026-10-31 (Asia/Bangkok)
**Requested window:** active-session UTC dates 2026-10-07 through 2026-10-15
**Complete sessions retained:** five: Oct 7, 8, 13, 14, and 15 UTC (Bangkok dates Oct 8, 9, 14, 15, and 16).
**Source:** local FBS-Demo XAUUSD tick quotes and M5 bars.

## Coverage

Seven active sessions fell in the requested date window. Five passed the existing completeness rule; two were excluded because quote coverage at the active-session start did not meet the 5-minute limit. Each included day had 274 M5 bars. The method and parameters are unchanged from the previous five-session sample.

## Prior-session levels

| Session date (Bangkok) | VAL | POC | VAH | Median spread |
|---|---:|---:|---:|---:|
| 2026-10-08 | 4102.5 | 4133.6 | 4148.5 | 0.27 |
| 2026-10-09 | 4119.0 | 4125.0 | 4135.0 | 0.31 |
| 2026-10-14 | 4164.7 | 4185.4 | 4196.1 | 0.29 |
| 2026-10-15 | 4093.6 | 4160.6 | 4170.5 | 0.30 |
| 2026-10-16 | 4141.7 | 4157.2 | 4159.4 | 0.31 |

Levels use the prior completed session's midpoint quote-update distribution, binned at $0.10. POC is the most active bin; VAL/VAH enclose at least 70% of quote updates. These are broker-specific tick-activity proxies, not centralized traded volume.

## Results

| Setup | Trades | Winners | Net price points per 1 oz | Targets | Stops |
|---|---:|---:|---:|---:|---:|
| VAL/VAH edges | 4 | 1 (25%) | -7.63 | 1 | 3 |
| POC line | 6 | 0 (0%) | -25.57 | 0 | 6 |
| Combined | 10 | 1 (10%) | -33.20 | 1 | 9 |

Spread is reflected through ask/bid entries and exits. Commission and extra slippage are excluded. The prior short sample (Oct 20?26 UTC) was +30.13 price points across 14 trades; this sample is -33.20 points across 10. Opposite short-window outcomes show that these small samples do not establish a stable edge.

## Files

- `daily_levels.csv`: prior-session levels used each day
- `trades.csv`: trade-by-trade M5 signal, entry, exit and P&L
- `session_coverage.csv`: all seven candidate sessions and inclusion status
- `summary.csv`, `by_level.csv`, `monthly.csv`: grouped outputs

Reproduce with:

```powershell
.\.venv\Scripts\python.exe research\xauusd_poc_m5\run_poc_test.py --start 2026-10-07 --end 2026-10-15 --output-dir research\xauusd_poc_m5\sample_2026-10-07_to_2026-10-15
```
