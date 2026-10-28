"""Trend following: the breakout the way traders who make it pay trade it (owner, 2026-10-15: "use what they do,
then make it pay").

Intraday box breaks lose on all 8 traded symbols (box_multi.py: M5 -0.24 R/trade over 199 trades in the bot's
hours, CI below zero); trailing, tested edges and fading did not fix it (box_levers.py). The classic breakout
that pays (Donchian / Turtle style) is different on every point: a larger timeframe, many markets, a stop of a
few ATR, no target - the stop trails and the rare long trend pays for the many small losses.

Rule, on every symbol with H4 and D1 history (28 FX pairs + gold, 2024-04 .. 2026-10):
- entry: an H4 close beyond the highest high / lowest low of the previous ``N`` bars (20 or 55); one position
  per symbol, no adding;
- filter: ``none`` or ``ema200`` (the close on the trade's side of the H4 EMA 200, ~33 days);
- initial stop: 2 x ATR(20) from the entry; exit: ``chandelier`` (the stop trails 3 x ATR behind the best price)
  or ``channel`` (a close beyond the opposite N/2-bar channel), the stop never loosens;
- costs: the bar's spread + 1 point of slippage (gold 7) at the entry and at the exit.

Walk-forward: choose on the first half (by date), judge on the second; the bar: second half >= +0.15 R/trade.

    .venv/Scripts/python research/2026-10-15-day-trade/trend_follow.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "research/2026-10-15-day-trade")
import flag_rules as fr  # noqa: E402  (the stats line)

from app.indicators.volatility import atr as wilder_atr  # noqa: E402

ROOT = "data/history/FBS-Demo"
SLIPPAGE = {"XAUUSD": 7}


def symbols() -> list[str]:
    return sorted(
        s
        for s in os.listdir(ROOT)
        if all(os.path.exists(f"{ROOT}/{s}/{f}") for f in ("H4.parquet", "D1.parquet", "spec.json"))
    )


class Series:
    def __init__(self, symbol: str, tf: str = "H4") -> None:
        raw = (
            pd.read_parquet(f"{ROOT}/{symbol}/{tf}.parquet").sort_values("close_time").reset_index(drop=True)
        )
        point = float(json.load(open(f"{ROOT}/{symbol}/spec.json"))["spec"]["point"])
        self.symbol = symbol
        self.times = pd.DatetimeIndex(pd.to_datetime(raw["close_time"], utc=True))
        d = raw[["open", "high", "low", "close"]].astype(float)
        self.h, self.lo, self.c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
        self.atr = wilder_atr(d["high"], d["low"], d["close"], 20).to_numpy()
        self.ema200 = d["close"].ewm(span=200, adjust=False).mean().to_numpy()
        self.cost = (raw["spread"].to_numpy() + SLIPPAGE.get(symbol, 1)) * point
        self.hh = {n: d["high"].shift(1).rolling(n).max().to_numpy() for n in (10, 20, 27, 55)}
        self.ll = {n: d["low"].shift(1).rolling(n).min().to_numpy() for n in (10, 20, 27, 55)}


def trades(x: Series, n: int, filt: str, exit_mode: str) -> list[tuple[pd.Timestamp, float]]:
    out: list[tuple[pd.Timestamp, float]] = []
    half = n // 2
    t = max(n, 200) + 1
    while t < len(x.c) - 1:
        if not np.isfinite(x.atr[t]) or not np.isfinite(x.hh[n][t]):
            t += 1
            continue
        side = 1 if x.c[t] > x.hh[n][t] else -1 if x.c[t] < x.ll[n][t] else 0
        if side and filt == "ema200" and (x.c[t] - x.ema200[t]) * side <= 0:
            side = 0
        if not side:
            t += 1
            continue
        entry = x.c[t] + side * x.cost[t]
        risk = 2 * x.atr[t]
        stop = entry - side * risk
        best = entry
        exit_price, k = None, t
        for k in range(t + 1, len(x.c)):
            if (x.lo[k] if side > 0 else x.h[k]) * side <= stop * side:
                exit_price = stop - side * x.cost[k]
                break
            if exit_mode == "channel":
                edge = x.ll[half][k] if side > 0 else x.hh[half][k]
                if np.isfinite(edge) and (x.c[k] - edge) * side < 0:
                    exit_price = x.c[k] - side * x.cost[k]
                    break
            best = max(best, x.h[k]) if side > 0 else min(best, x.lo[k])
            if exit_mode == "chandelier":
                trail = best - side * 3 * x.atr[k]
                stop = max(stop, trail) if side > 0 else min(stop, trail)
        if exit_price is None:  # still open at the end of the data: marked at the last close
            exit_price = x.c[-1] - side * x.cost[-1]
            k = len(x.c) - 1
        out.append((x.times[t], (exit_price - entry) * side / risk))
        t = k + 1
    return out


if __name__ == "__main__":
    series = [Series(s) for s in symbols()]
    start = min(x.times[0] for x in series)
    end = max(x.times[-1] for x in series)
    mid = start + (end - start) / 2
    print(f"{len(series)} symbols, H4 {start:%Y-%m-%d} .. {end:%Y-%m-%d}; halves at {mid:%Y-%m-%d}")
    print("| N | filter | exit | trades/yr | win % | year R/trade | 1st half | 2nd half |")
    print("|---|---|---|---|---|---|---|---|")
    years = (end - start).days / 365.25
    results = []
    for n, filt, exit_mode in itertools.product((20, 55), ("none", "ema200"), ("chandelier", "channel")):
        rows = [r for x in series for r in trades(x, n, filt, exit_mode)]
        rs = [r for _, r in rows]
        f = [r for ts, r in rows if ts < mid]
        s2 = [r for ts, r in rows if ts >= mid]
        results.append((np.mean(f), n, filt, exit_mode, rs, f, s2))
    for _, n, filt, exit_mode, rs, f, s2 in sorted(results, key=lambda r: -r[0]):
        win = np.mean([r > 0 for r in rs]) * 100
        print(
            f"| {n} | {filt} | {exit_mode} | {len(rs) / years:.0f} | {win:.0f} | {fr.stats(rs)} | {fr.stats(f)} | {fr.stats(s2)} |"
        )
