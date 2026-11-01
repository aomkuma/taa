# Rolling six-hour M5 Volume Profile edge test

**Run date:** 2026-10-31 (Asia/Bangkok)
**Method:** see `PROTOCOL.md`, written before outcome calculation
**Sample:** 158 broker sessions with complete current and preceding-session quote coverage; 110 development sessions followed by 48 validation sessions.

## Rules tested

For every M5 signal bar, construct a Volume Profile from quote updates in the preceding six clock hours, ending before that bar opens. The profile can include at most 72 completed M5 bars; around market closures it contains fewer. POC is the price bin with the most quote updates; VAL/VAH enclose a contiguous 70% activity range. Buy a VAL rejection and sell a VAH rejection, with the signal-time rolling POC as target. Stops are beyond the signal-bar wick. Levels update as the six-hour window rolls forward.

This first implementation treats the rolling value area itself as the price cluster. It does not require the area to be compact or stable across multiple profile updates.

## Results

| Period | Trades | Wins | Stops | Net points per 1 oz | Net R | Profit factor (points) |
|---|---:|---:|---:|---:|---:|---:|
| Development | 220 | 72 | 148 | -371.66 | -72.11 | 0.54 |
| Validation | 96 | 36 | 60 | +7.52 | -4.38 | 1.05 |
| All | 316 | 108 | 208 | -364.14 | -76.49 | 0.62 |

Across the whole sample, VAL longs made 56 wins in 158 trades and netted -229.46 points; VAH shorts made 52 wins in 158 trades and netted -134.68 points. Validation was close to flat in price points before commission and extra slippage, but negative in R. The entire sample is negative by both net R and profit factor.

The strategy reached its one-long/one-short-per-session cap on every included session. That high frequency suggests a rolling profile can follow price and repeatedly trigger at its moving edges; this implementation did not isolate only stable consolidations.

The median profile window contained 58 M5 bars because of the daily market closure. A few windows near a reopen had only 3?13 bars; they were included because the protocol did not specify a minimum bar count. This is visible in `trades.csv` and `rolling_profiles.csv` and should be addressed in a separately preregistered follow-up, not retroactively used to claim better results.

## Conclusion

This six-hour rolling-profile edge strategy did not show an edge in the tested sample. It also did not fully isolate stable price clusters: its VA boundaries moved every five minutes. A separate cluster-stability rule (for example, freezing a bounded range after it forms and invalidating it on acceptance outside) would be a new strategy and needs its own frozen protocol and test.

Quote-update counts are an FBS-Demo activity proxy, not centralized executed XAUUSD volume. Bid/ask spread is reflected in fills; commission and additional slippage are excluded. The validation period is historical and not fully blind because earlier analyses inspected some of these dates.

## Files

- `PROTOCOL.md`: frozen method and expectation
- `run_rolling_6h.py`: reproducible profile calculation and tick replay
- `summary.csv`: results by chronological split
- `trades.csv`: every accepted trade
- `rolling_profiles.csv`: POC/VAH/VAL for each candidate M5 signal bar
- `session_coverage.csv`: coverage criteria
