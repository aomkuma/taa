# XAUUSD prior-session Volume Profile levels on M5

**Status:** short sample completed; main result is the five-session demonstration in `sample_2026-10-20_to_2026-10-26/REPORT.md`
**Date:** 2026-10-31 (Asia/Bangkok)
**Instrument/source:** XAUUSD, FBS-Demo local history and quote ticks

## Question

Do M5 rejection/reclaim entries at the prior completed broker session's value-area edges (VAL/VAH) or Point of Control (POC) produce useful intraday trades in the following session?

## Expectation before reveal

I expect value-edge rejections to perform better than POC-line rejections because VAL/VAH mark the boundary of the prior session's accepted range, while POC is a high-activity price that may be crossed repeatedly. I expect the POC rule to generate more touches but fewer clean reversals. This is a hypothesis, not a result.

## Frozen method

- A session is the active quote interval represented by M5 bars within a broker D1 candle: first M5 `open_time` through last M5 `close_time`. The D1 candles contain a roughly 65-minute daily market closure, so applying full 24-hour coverage checks incorrectly rejected every session. This was discovered in the first coverage-only pass (zero sessions, no trade outcomes viewed); the operational bounds are now fixed before testing. Levels for session N use only ticks within the immediately prior completed active interval N-1.
- Quote price is `(bid + ask) / 2`, assigned to the nearest $0.10 bin. Bin activity is quote-update count, not executed volume.
- POC is the most active bin. Value area is the contiguous range around POC that first includes at least 70% of quote updates; extend to the adjacent bin with the larger count, ties go to the lower-price side.
- Use these three levels: VAL, POC, VAH. A touch zone is max($0.05, 2 ? median spread in the prior session). The zone is fixed for the next session.
- Edge long: M5 bar low reaches VAL + zone and closes above VAL. Edge short: bar high reaches VAH - zone and closes below VAH.
- POC long: bar low reaches POC + zone and closes above POC. POC short: bar high reaches POC - zone and closes below POC.
- Signal is evaluated only when an M5 bar closes. Entry is the first available quote tick after that close: buy at ask, sell at bid. Stop is beyond the signal bar's low/high by max($0.05, one median prior-session spread). Target is POC for edge trades; VAH/VAL for POC trades.
- Replay quote ticks in timestamp order through the target, stop, or session close. Exit a still-open trade at the last quote before session close. No new entry while a position is open; at most one trade per level/direction/session. Skip a trade if the target is not on the profitable side of entry or the stop is not on the protective side.
- Include only sessions with complete prior and current tick coverage (first quote within 5 minutes of the first M5 open, last quote within 5 minutes of the last M5 close, and at least 90% of the median nonempty M5 bars per D1 session available). Report coverage and excluded sessions.
- Report edge and POC groups separately: number of trades, win rate, net P&L in dollars per 1 oz (price points, before commission/slippage), mean/median R, gross profit factor, exit types, and monthly split. No parameter tuning on the test interval.

## Limits

FBS-Demo quote updates are a broker-specific activity proxy, not centralized XAUUSD trade volume. This test does not model commission, latency, slippage, position sizing, or live execution. The protocol is exploratory; a positive result would need out-of-sample and robustness checks before use.
