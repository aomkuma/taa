# Confirmed breakout from a true 200-bar M5 profile

**Date:** 2026-11-01 (Asia/Bangkok)  
**Question:** After the 200-bar edge-fade failed, does a close-confirmed breakout from the same balance cluster perform better?

## Frozen method

At each M5 bar, build the volume profile from the previous 200 completed M5 bars and compare its older/newer 100-bar halves. M1 FBS `tick_volume` is distributed into $0.10 price rows across each M1 candle's OHLC range. Require at least 50% half-value-area overlap, half-profile POC displacement no more than $0.50, six-hour path efficiency no more than 0.25, prior close inside value, and at least 900 M1 candles in the profile. Freeze the first qualifying cluster of the session.

Enter in the breakout direction after two consecutive M5 closes beyond the frozen VAH/VAL, using the first FBS quote strictly after confirmation (all accepted entry quotes were within one second in this sample). Stop is just back inside the broken edge with a pad of at least $0.10 or two times prior-six-hour median spread plus $0.10. Target is one VA width beyond the broken edge. Fills and exits use raw FBS bid/ask ticks.

The sample uses 264 sessions with at least 247 of the expected 274 M5 bars, split chronologically into 184 development and 80 validation sessions.

## Results

| Period | Trades | Wins | Win rate | Net R | Net price PnL | PF (R) | Targets / stops |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | 20 | 3 | 15.0% | -11.00R | -$29.04/oz | 0.36 | 3 / 16 |
| Validation | 18 | 5 | 27.8% | +3.97R | -$12.96/oz | 1.30 | 4 / 13 |

Development folds returned -8.59R (9 trades), +0.86R (7), and -3.28R (4). Only the second fold was positive. Validation's positive risk-normalized result coincided with negative aggregate price PnL and was concentrated in August 2026; July lost -4.14R and September was slightly negative at -0.63R. The method fails the predeclared selection rule because development was negative and only one fold was positive.

## Decision and limitations

**Do not select this as a candidate.** The 200-bar breakout is less uniformly negative in validation than the 200-bar fade, but the development evidence does not transfer and unweighted price PnL is negative in both periods. The later validation gain is too sparse and regime-concentrated to establish a robust edge.

This is FBS-Demo, not OANDA. M1 tick volume allocated across candle ranges is an approximate broker-specific profile; commission and extra slippage are excluded. The validation period has been reused in related research and is not a pristine holdout.

## Reproduction

Run `python test_breakout_200bar_expanded.py` from this folder's parent. Raw trades, session audit, and qualifying profile windows are in `expanded_200bar_breakout/`. Summary metrics are calculated from the raw trade CSV.
