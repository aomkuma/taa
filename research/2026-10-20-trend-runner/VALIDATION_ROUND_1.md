# TR1 frozen round-1 validation

P2 was opened once at 2026-10-20 15:01:17 Thai time using the command frozen before validation. No rule, parameter, session or exit family changed. The exam was not opened.

## Decision

**FAIL.** Frozen SPLIT passed P1 (+0.265R/trade) but produced only +0.088R/trade in P2, below the predeclared requirement of at least +0.15R/trade in each part. Frequency and sample-size gates passed. The P2 result remains positive but is not strong enough to promote or examine.

## P1 - frozen SPLIT

- 138 trades, 2.16 per scheduled weekday; mean +0.265R (95% individual-trade bootstrap -0.121 to +0.708), median -0.392R and 31.9% positive.
- Total +36.52R and +192.92 USD at 0.01 lot; +3.01 USD per scheduled weekday.
- Worst trade -1.27R / -14.94 USD; maximum drawdown 13.16R / 49.09 USD; longest losing streak 10.
- Removing the best trade: +0.147R/trade; removing the best three: -0.017R/trade.
- Median holding 23.6 minutes; total exposure 197.2 hours; 1 UTC-date crossings.
- A greedy one-position-at-a-time lane has 2 collisions and keeps 136 trades: +0.261R/trade, +35.54R; foregone +0.98R.

Session and direction cuts:

- ASIA: n=51, mean=+0.002R, total=+0.11R, USD=-20.42.
- LONDON: n=46, mean=+0.723R, total=+33.27R, USD=+162.84.
- NY0830: n=41, mean=+0.077R, total=+3.15R, USD=+50.50.
- SELL: n=58, mean=+0.320R, total=+18.56R.
- BUY: n=80, mean=+0.225R, total=+17.96R.

Weekly results:

- 2025-W43: 11 trades, +8.03R, +59.64 USD.
- 2025-W44: 14 trades, +14.80R, +67.44 USD.
- 2025-W45: 8 trades, +2.95R, +9.17 USD.
- 2025-W46: 11 trades, +0.44R, -1.86 USD.
- 2025-W47: 12 trades, -4.60R, -25.11 USD.
- 2025-W48: 14 trades, +8.22R, +45.77 USD.
- 2025-W49: 11 trades, -6.34R, -24.84 USD.
- 2025-W50: 12 trades, +9.61R, +7.12 USD.
- 2025-W51: 8 trades, -1.14R, +4.36 USD.
- 2025-W52: 10 trades, -3.44R, -11.19 USD.
- 2026-W01: 7 trades, +4.44R, +48.73 USD.
- 2026-W02: 12 trades, +3.27R, +15.89 USD.
- 2026-W03: 8 trades, +0.30R, -2.20 USD.

Monthly results:

- 2025-10: 25 trades, +0.913R/trade, +22.83R, +127.08 USD.
- 2025-11: 45 trades, +0.156R/trade, +7.00R, +27.97 USD.
- 2025-12: 47 trades, +0.088R/trade, +4.14R, +26.37 USD.
- 2026-01: 21 trades, +0.122R/trade, +2.55R, +11.50 USD.

## P2 - frozen SPLIT

- 142 trades, 2.15 per scheduled weekday; mean +0.088R (95% individual-trade bootstrap -0.202 to +0.413), median -0.489R and 33.1% positive.
- Total +12.50R and +84.20 USD at 0.01 lot; +1.28 USD per scheduled weekday.
- Worst trade -1.23R / -30.82 USD; maximum drawdown 20.24R / 186.56 USD; longest losing streak 11.
- Removing the best trade: +0.004R/trade; removing the best three: -0.098R/trade.
- Median holding 20.3 minutes; total exposure 125.4 hours; 0 UTC-date crossings.
- A greedy one-position-at-a-time lane has 0 collisions and keeps 142 trades: +0.088R/trade, +12.50R; foregone +0.00R.

Session and direction cuts:

- ASIA: n=50, mean=+0.298R, total=+14.88R, USD=+213.32.
- LONDON: n=48, mean=-0.295R, total=-14.17R, USD=-115.59.
- NY0830: n=44, mean=+0.268R, total=+11.79R, USD=-13.53.
- SELL: n=69, mean=-0.143R, total=-9.85R.
- BUY: n=73, mean=+0.306R, total=+22.35R.

Weekly results:

- 2026-W03: 3 trades, -0.78R, -1.51 USD.
- 2026-W04: 11 trades, +6.58R, +37.89 USD.
- 2026-W05: 11 trades, -2.09R, +22.42 USD.
- 2026-W06: 14 trades, +14.78R, +112.78 USD.
- 2026-W07: 11 trades, -3.89R, -18.29 USD.
- 2026-W08: 10 trades, -1.62R, -7.26 USD.
- 2026-W09: 10 trades, +8.09R, +16.63 USD.
- 2026-W10: 7 trades, -2.63R, -40.80 USD.
- 2026-W11: 8 trades, +2.06R, +23.04 USD.
- 2026-W12: 11 trades, -6.79R, -52.01 USD.
- 2026-W13: 13 trades, +1.21R, +16.71 USD.
- 2026-W14: 10 trades, -6.64R, -52.90 USD.
- 2026-W15: 10 trades, -5.96R, -39.75 USD.
- 2026-W16: 13 trades, +10.17R, +67.26 USD.

Monthly results:

- 2026-01: 25 trades, +0.148R/trade, +3.71R, +58.81 USD.
- 2026-02: 45 trades, +0.386R/trade, +17.37R, +103.86 USD.
- 2026-03: 44 trades, -0.215R/trade, -9.48R, -77.75 USD.
- 2026-04: 28 trades, +0.032R/trade, +0.89R, -0.72 USD.

## Frozen controls on the same entries

P1:
- FAST: n=138, mean=+0.011R (95% -0.214 to +0.244), total=+1.56R, USD=+4.32.
- SWING: n=138, mean=+0.386R (95% -0.156 to +1.010), total=+53.23R, USD=+281.55.
- SPLIT: n=138, mean=+0.265R (95% -0.116 to +0.716), total=+36.52R, USD=+192.92.
- STATE: n=138, mean=-0.032R (95% -0.296 to +0.255), total=-4.45R, USD=-15.10.
P2:
- FAST: n=142, mean=+0.062R (95% -0.171 to +0.299), total=+8.78R, USD=-1.30.
- SWING: n=142, mean=+0.140R (95% -0.259 to +0.601), total=+19.82R, USD=+161.46.
- SPLIT: n=142, mean=+0.088R (95% -0.203 to +0.421), total=+12.50R, USD=+84.20.
- STATE: n=142, mean=+0.115R (95% -0.194 to +0.489), total=+16.27R, USD=+69.13.

## Robustness interpretation

Pooled P1+P2 is 280 trades at +0.175R/trade, but pooling cannot override the failed per-part gate. P1's runner edge was concentrated in London and a very large winner. P2 is less concentrated but too small; adverse slippage can only reduce it, so no slippage sensitivity can rescue the primary gate.

Entry timeframe is fixed M1. No entry-time market-state filter was frozen, so a market-state cut is not reported post hoc. STATE is an exit control, not permission to select P2 winners. The controls are shown for diagnosis only and cannot replace SPLIT.

The result supports the original qualitative idea that some opening pullbacks become long runners, but round 1 does not identify them consistently enough. Work stops before exam and before any engine, DEMO, configuration or portfolio integration.
