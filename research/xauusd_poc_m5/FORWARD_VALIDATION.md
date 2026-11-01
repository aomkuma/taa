# Forward validation protocol - XAUUSD M5 Volume Profile research

**Status:** no candidate selected as of 2026-10-31 (Asia/Bangkok).

## Factual corrections

The earlier studies used raw FBS quote records assigned directly to $0.10 bins. TradingView documents that Forex/CFD Volume Profile uses tick volume from lower-timeframe bars, where tick volume represents price updates. Its charting library distributes a lower-timeframe bar's volume across intersected price rows in proportion to price overlap. A corrected FBS M1 proxy was tested, but it did not validate the earlier +2R result. See `m1_tick_volume_profile_2026-10-31/REPORT.md`.

The screenshot is OANDA; the local historical source is FBS-Demo. Neither the FBS raw-tick histogram nor the M1 OHLC allocation exactly reproduces OANDA's indicator. The screenshot's custom row sizing and lookback input meanings are not confirmed. POC/VA are descriptive activity levels, not guaranteed reversal signals.

## Conditions retained

- The six-hour maximum is retained as the user's chosen research scope for the M5 idea. It is not a universal Volume Profile rule. Six hours is 72 M5 bars when the market is open; data gaps can make fewer complete bars available.
- The 70% value area is retained only because it appears in the screenshot and is a common default; it is a configurable convention, not a required fact.
- No strategy is approved for live trading. The >=2R screen is withdrawn as a candidate because its result reversed under the M1 tick-volume proxy.

## Data needed before a new forward claim

Use broker-matched OANDA lower-timeframe bars/volume and bid/ask execution if matching the screenshot is the objective. Record the exact custom indicator settings, including row sizing, session/window, volume type, and value-area calculation. If only FBS data is available, label it an FBS study and do not claim it reproduces OANDA levels. Freeze the profile construction and entry/exit rules before collecting a new chronological sample; include commission and slippage when available.

The local sample ends 2026-10-28, and its later dates have been inspected repeatedly. No further parameter selection on that same sample can establish independent profitability. Re-run only after genuinely new, feed-matched data is available, and judge it by net R, average R/trade, profit factor, drawdown, and stability across consecutive chronological blocks.

## Feed-matched OANDA acquisition path

A read-only downloader is prepared in [`oanda_feed/README.md`](oanda_feed/README.md) and [`oanda_feed/fetch_candles.py`](oanda_feed/fetch_candles.py). OANDA v20 can return M1 midpoint, bid, and ask candles plus price-update volume; its official docs require an eligible v20 account and personal token. No `OANDA_API_TOKEN` is configured in this workspace, so no OANDA download has been run. Credentials should be set locally in the process environment and never pasted into chat or committed.

OANDA candles provide M1 OHLC, not historical tick chronology. Replaying them can use quote-side candle ranges and a conservative stop-first rule when both stop and target are touched in one minute. OANDA's live stream also samples at most four prices per second, so that feed is not a complete tick tape. This is a practical route to a broker-matched study, with a clear intraminute execution limit.

An OANDA candle replay harness is prepared at [`oanda_feed/backtest_oco_m1.py`](oanda_feed/backtest_oco_m1.py). It compares the direct OCO rule with two predefined stable-POC variants using M1 bid/ask OHLC and conservative stop-first ordering for ambiguous intraminute touches. Historical OANDA candles are not a tick tape; the replay uses the same time windows as the FBS sample but selects sessions based on OANDA's M5 coverage. Run only after obtaining eligible OANDA data and recording the screenshot indicator settings.
