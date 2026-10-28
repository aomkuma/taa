"""The box breakout on every traded symbol, on M5 and M15 (owner, 2026-10-15: "find our good setup").

Gold alone gives ~37 trades a year: too few to tell an edge from luck, and every filter splits it into cells of
6-12. Traders who make breakouts pay judge them over many markets. Same rule as ``box_harness.py`` (the bot's
detector logic, the bot's limits, H1 map with the break, H1 level target <= 3 R with room >= 1 R, one position per
symbol, real spread + slippage, no rollover or weekends), per symbol and timeframe. The box, the run and the time
stop count bars, so on M15 it is the same pattern three times larger.

    .venv/Scripts/python research/2026-10-15-day-trade/box_multi.py
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "research/2026-10-15-day-trade")
import box_harness as bh  # noqa: E402
import flag_rules as fr  # noqa: E402

from app.config import AppConfig  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.indicators.chart_read import ChartReadFrame, ChartReadParams  # noqa: E402
from app.indicators.volatility import atr as wilder_atr  # noqa: E402
from app.strategy.market_maps import MapBook, map_params  # noqa: E402

ROOT = "data/history/FBS-Demo"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD"]
SLIPPAGE_POINTS = {"XAUUSD": 7}  # gold: the account spread above the history (S1); FX: the backtest's 1 point


def load(symbol: str, tf: str) -> pd.DataFrame:
    raw = pd.read_parquet(f"{ROOT}/{symbol}/{tf}.parquet").sort_values("close_time").reset_index(drop=True)
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw["close_time"], utc=True))
    return raw


class Context:
    """The symbol's H1 chart-read levels and H1 map state at a time (bars closed by then)."""

    def __init__(self, symbol: str, point: float) -> None:
        h1 = load(symbol, "H1")[["open", "high", "low", "close"]].astype(float)
        self.h1 = h1
        self.read = ChartReadFrame("H1", h1, point, ChartReadParams())
        cfg = AppConfig()
        self.book = MapBook(map_params(cfg), [Timeframe.H1], {Timeframe.H1: map_params(cfg, Timeframe.H1)})
        self.symbol = symbol
        self._cache: dict[int, tuple[list[float], str]] = {}

    def at(self, ts: pd.Timestamp) -> tuple[list[float], str]:
        pos = int(self.h1.index.searchsorted(ts, side="right")) - 1
        if pos not in self._cache:
            r = self.read.at(pos)
            levels = [] if r is None else [lv.price for lv in r.levels]
            m = self.book.at(
                self.symbol,
                {Timeframe.H1: self.h1.iloc[max(0, pos - 700) : pos + 1]},
                self.h1.index[pos].to_pydatetime(),
            )
            state = "UNKNOWN" if m is None or "H1" not in m.frames else m.frames["H1"].state.value
            self._cache[pos] = (levels, state)
        return self._cache[pos]


class Market:
    """``box_harness.Market`` for any symbol and entry timeframe."""

    def __init__(self, symbol: str, tf: str) -> None:
        raw = load(symbol, tf)
        spec = json.load(open(f"{ROOT}/{symbol}/spec.json"))["spec"]
        point = float(spec["point"])
        self.times = raw.index
        self.d = raw[["open", "high", "low", "close"]].astype(float)
        self.h, self.lo, self.c = (self.d[k].to_numpy() for k in ("high", "low", "close"))
        self.o = self.d["open"].to_numpy()
        self.vol = raw["tick_volume"].to_numpy(dtype=float)
        self.cost = (raw["spread"].to_numpy() + SLIPPAGE_POINTS.get(symbol, 1)) * point
        self.atr = {"wilder": wilder_atr(self.d["high"], self.d["low"], self.d["close"], 14).to_numpy()}
        self.ctx = Context(symbol, point)


def run(symbol: str, tf: str, window: bh.Window) -> list[tuple[pd.Timestamp, int, float, str]]:
    m = Market(symbol, tf)
    return bh.simulate(m, bh.events(m, "wilder", "latest"), window, False)  # type: ignore[arg-type]


if __name__ == "__main__":
    windows = {k: bh.WINDOWS[k] for k in ("07-20 (bot now)", "00-20:30 (+Asia)")}
    pooled: dict[tuple[str, str], list[tuple[pd.Timestamp, float]]] = {}
    print("| symbol | TF | hours | year R/trade | 1st half | 2nd half |")
    print("|---|---|---|---|---|---|")
    for tf in ("M5", "M15"):
        for symbol in SYMBOLS:
            m = Market(symbol, tf)
            evs = bh.events(m, "wilder", "latest")  # type: ignore[arg-type]
            mid = m.times[len(m.times) // 2]
            for wname, window in windows.items():
                tr = bh.simulate(m, evs, window, False)  # type: ignore[arg-type]
                rs = [r for _, _, r, _ in tr]
                f = [r for ts, _, r, _ in tr if ts < mid]
                s2 = [r for ts, _, r, _ in tr if ts >= mid]
                pooled.setdefault((tf, wname), []).extend((ts, r) for ts, _, r, _ in tr)
                print(
                    f"| {symbol} | {tf} | {wname} | {fr.stats(rs) if rs else 'n 0'} | {fr.stats(f) if f else 'n 0'} | {fr.stats(s2) if s2 else 'n 0'} |"
                )
    mid_all = pd.Timestamp("2026-04-08", tz="UTC")
    print("\n| pooled: TF | hours | year R/trade | 1st half | 2nd half |")
    print("|---|---|---|---|---|")
    for (tf, wname), rows in pooled.items():
        rs = [r for _, r in rows]
        f = [r for ts, r in rows if ts < mid_all]
        s2 = [r for ts, r in rows if ts >= mid_all]
        print(f"| {tf} | {wname} | {fr.stats(rs)} | {fr.stats(f)} | {fr.stats(s2)} |")
