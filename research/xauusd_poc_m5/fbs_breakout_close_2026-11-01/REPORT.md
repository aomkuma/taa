# FBS 12-hour balance breakout with expanded session coverage

**Date:** 2026-11-01 (Asia/Bangkok)  
**Purpose:** Check whether the earlier 158-session FBS result was mainly caused by an unnecessarily strict session-coverage gate.

## Frozen setup

The 12-hour profile-breakout rule was kept unchanged: estimate a $0.10-row profile from FBS M1 `tick_volume` allocated uniformly across each candle's OHLC range; require a balanced cluster (at least 50% overlap between older and newer 70% value areas, POC displacement no more than $0.50, six-hour path efficiency no more than 0.25, and prior M5 close inside value); freeze the first qualifying cluster; enter after two consecutive M5 closes outside value. The stop is just inside the broken edge with a pad of at least $0.10 or two times the prior-hour median FBS spread plus $0.10. The target is one value-area width beyond the broken edge. Quotes are replayed tick by tick with FBS bid/ask execution.

## Coverage audit and expanded sample

The earlier 158-session sample required both the current and previous daily segment to pass coverage checks, including ticks within five minutes of both ends. That excluded some sessions whose own M5 data was complete simply because the previous segment failed.

This sensitivity run used 264 sessions with at least 247 of the expected 274 M5 bars. It removed the previous-session dependency and the session-open tick-gap exclusion. A trade was accepted only if the first executable quote after the confirming M5 close arrived within 60 seconds. All 264 selected sessions had the last tick within five minutes of the segment close; the four trades exited at session close had quote gaps below one second. The session audit found no entry rejected for the 60-second delay.

## Results

| Period | Trades | Win rate | Net R | PF (R) | Targets / stops |
|---|---:|---:|---:|---:|---:|
| Development (184 sessions) | 62 | 35.5% | +27.51R | 1.67 | 20 / 40 |
| Validation (80 sessions) | 33 | 24.2% | -6.02R | 0.76 | 7 / 24 |

The three chronological development folds returned -7.91R, +5.64R, and +29.78R. The first fold was negative and the last fold supplied most of the gain. Expanding coverage increased the sample from 58 to 95 trades but did not improve validation. The earlier 158-session run had +17.90R development and -3.23R validation; neither split supports selecting this setup.

## Decision and limitations

**Reject as a candidate.** The larger FBS sample still loses in validation and shows marked time dependence. The validation interval has also been reused during related strategy exploration, so it is not a pristine holdout.

This is a broker-specific FBS-Demo study, not a replication of the user's TradingView OANDA profile. FBS M1 tick volume and uniform allocation through candle ranges are only a proxy for the indicator's volume-at-price rows. Raw FBS bid/ask quotes are used for fills, but commissions and extra slippage are not included. Results are historical and do not establish a profitable live method.

## Reproduction

Run `python run_fbs_breakout_expanded.py` from this folder's parent research workspace. Outputs are in `expanded_coverage/`; the original 158-session run is preserved at the folder root.
