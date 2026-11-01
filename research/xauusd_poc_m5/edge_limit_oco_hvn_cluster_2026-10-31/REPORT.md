# High-volume concentration around POC: OCO test

## Question
Does a visibly dense price cluster help the six-hour M5 edge-reversion OCO idea? Operationally, define a dense cluster as at least 25% of estimated six-hour tick volume within a narrow band around POC.

## Rule tested
This run copies the quote-audited OCO backtest and adds one gate. For each rolling six-hour profile, compute `band_half_width = max($0.10, 5% × (VAH − VAL))`; `poc_band_share` is tick volume in bins whose midpoints are within that distance of POC, divided by profile tick volume. Activate the frozen VA/POC edge setup only when `poc_band_share >= 25%` and the existing profile qualification passes (at least 48 M5 bars, at least 24 bars in each half, and >=50% overlap between half-profile value areas). Entries remain buy at VAL / sell at VAH; stop is spread-padded beyond the edge; target is POC; one trade per session. Bid/ask quote ticks determine fills and exits.

The histogram is a proxy built by spreading each M1 tick-volume count over the M1 OHLC price range in $0.10 bins. It is not centralized traded volume and may differ from TradingView's displayed rows.

## Results

- Sessions: 158 total (110 chronological development, 48 validation); qualifying profile bars: 119 across 20 sessions.
- Trades: 17 total (12 development, 5 validation). All 17 stopped; there were no POC targets.
- Development: **-6.42R**, 0/12 wins. Three folds: -2.03R, -2.85R, -1.54R.
- Validation: **-2.52R**, 0/5 wins.
- Selection: **not a candidate**. It fails the minimum 20 development-trade requirement as well as positive development folds and positive validation.

## Interpretation and limits
The 25% POC-concentration threshold did not rescue this buy-VAL/sell-VAH reversion rule; this sample's qualifying trades all stopped before reaching POC. The low trade count also makes the magnitude uncertain. This does not establish that dense clusters are never useful; it rejects this exact proxy, threshold, and execution setup on this FBS sample. Validation has already been inspected repeatedly in this research, so it is exploratory rather than a clean holdout. FBS results do not reproduce the user's OANDA TradingView volume profile. Quotes are historical FBS bid/ask; commissions and additional slippage are absent.

See `test_oco_limit.py` and the generated CSV files for the frozen rules and trade audit. A feed-matched study needs OANDA M1 data plus the actual profile row settings.
