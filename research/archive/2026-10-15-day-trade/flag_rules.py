"""The flag rule before code (owner, 2026-10-15): a run, a box drifting with it, then the higher timeframe's
resistance as the ceiling. Walk-forward: choose on the first half, judge on the second.

XAUUSD, entries on ENTRY_TF (M5 by default; ``--tf M1`` for M1). No look-ahead: the box, the run, the H1 read and
the H1 map use bars closed by the box's last bar only.

- Box: the last ``box`` bars, height <= ``tight`` x ATR(14); the run before it: >= ``run`` ATR over RUN bars, in
  sign s; the box drifts with the run (its last close beyond its first in sign s).
- Entry: ``inbox`` (the box's last close) or ``break`` (the first close beyond the box edge in sign s within
  HORIZON bars; the other edge first: no trade). Spread paid on entry.
- Stop: the box's other edge. Target: ``1R`` or ``level``: the nearest H1 chart-read level beyond the entry in
  sign s (capped at 3 R; none: 3 R). ``room``: skip when that level is closer than ``room`` R (0: off).
- H1 screen: ``any`` or ``with`` (the H1 market-map state is the run's direction) or ``not_against``.
- Exit: stop or target on bar highs/lows (both in one bar: stop), else the close HORIZON bars after entry.

    .venv/Scripts/python research/2026-10-15-day-trade/flag_rules.py [--tf M1]
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import AppConfig
from app.core.enums import Timeframe
from app.indicators.chart_read import ChartReadFrame, ChartReadParams
from app.strategy.market_maps import MapBook, map_params

H = "data/history/FBS-Demo/XAUUSD"
RUN_BARS, HORIZON, SPREAD = {"M5": 24, "M1": 60}, {"M5": 48, "M1": 60}, 0.30


def load(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(f"{H}/{tf}.parquet").sort_values("close_time")
    d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    return d[["open", "high", "low", "close"]].astype(float)


def atr(d: pd.DataFrame, n: int = 14) -> np.ndarray:
    pc = d["close"].shift()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


@dataclass(frozen=True)
class Box:
    t: int  # the box's last bar
    at: pd.Timestamp
    sign: int
    top: float
    bot: float


def boxes(d: pd.DataFrame, a: np.ndarray, box: int, tight: float, run: float, run_bars: int, horizon: int) -> list[Box]:
    hi, lo, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    out: list[Box] = []
    t = box + run_bars + 20
    while t < len(d) - horizon - 1:
        b0 = t - box + 1
        top, bot = hi[b0 : t + 1].max(), lo[b0 : t + 1].min()
        if np.isfinite(a[t]) and top - bot <= tight * a[t]:
            mv = (c[b0] - c[b0 - run_bars]) / a[t]
            sign = 1 if mv >= run else -1 if mv <= -run else 0
            if sign and (c[t] - c[b0]) * sign > 0:
                out.append(Box(t, d.index[t], sign, top, bot))
                t += box
                continue
        t += 1
    return out


class Context:
    """H1 read levels and H1 map state at a time, from H1 bars closed by then."""

    def __init__(self) -> None:
        self.h1 = load("H1")
        spec = json.load(open(f"{H}/spec.json"))["spec"]
        self.read = ChartReadFrame("H1", self.h1, float(spec["point"]), ChartReadParams())
        cfg = AppConfig()
        tfs = [Timeframe.H1]
        self.book = MapBook(map_params(cfg), tfs, {tf: map_params(cfg, tf) for tf in tfs})
        self.frame = self.h1  # already the candle_frame form: close-time index, OHLC floats
        self._cache: dict[int, tuple[list[float], str]] = {}

    def at(self, ts: pd.Timestamp) -> tuple[list[float], str]:
        pos = int(self.h1.index.searchsorted(ts, side="right")) - 1
        if pos not in self._cache:
            r = self.read.at(pos)
            levels = [] if r is None else [lv.price for lv in r.levels if lv.role.value != "SPENT"]
            m = self.book.at("XAUUSD", {Timeframe.H1: self.frame.iloc[max(0, pos - 700) : pos + 1]}, self.h1.index[pos].to_pydatetime())
            state = "UNKNOWN" if m is None or "H1" not in m.frames else m.frames["H1"].state.value
            self._cache[pos] = (levels, state)
        return self._cache[pos]


def trade(d: pd.DataFrame, b: Box, entry_mode: str, target_mode: str, room: float, horizon: int, ctx: Context) -> float | None:
    hi, lo, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    s = b.sign
    if entry_mode == "inbox":
        at, entry = b.t, c[b.t]
    else:
        at = None
        for j in range(b.t + 1, b.t + 1 + horizon):
            if (c[j] - (b.top if s > 0 else b.bot)) * s > 0:
                at = j
                break
            if (c[j] - (b.bot if s > 0 else b.top)) * s < 0:
                return None
        if at is None:
            return None
        entry = c[at]
    entry += SPREAD * s
    stop = b.bot if s > 0 else b.top
    risk = (entry - stop) * s
    if risk <= 0:
        return None
    levels, _ = ctx.at(d.index[at])
    beyond = sorted((lv - entry) * s for lv in levels if (lv - entry) * s > 0)
    nearest_r = beyond[0] / risk if beyond else None
    if room and nearest_r is not None and nearest_r < room:
        return None
    tgt_r = 1.0 if target_mode == "1R" else min(3.0, nearest_r) if nearest_r is not None else 3.0
    target = entry + tgt_r * risk * s
    end = min(at + horizon, len(d) - 1)
    for j in range(at + 1, end + 1):
        if (lo[j] if s > 0 else hi[j]) * s <= stop * s:
            return -1.0
        if (hi[j] if s > 0 else lo[j]) * s >= target * s:
            return tgt_r
    return (c[end] - entry) * s / risk


def stats(rs: list[float]) -> str:
    if len(rs) < 5:
        return f"n {len(rs)}"
    x = np.array(rs)
    se = x.std(ddof=1) / np.sqrt(len(x))
    return f"{x.mean():+.3f} (n {len(x)}, CI90 {x.mean() - 1.645 * se:+.2f}..{x.mean() + 1.645 * se:+.2f})"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="M5", choices=["M5", "M1"])
    tf = ap.parse_args().tf
    d = load(tf)
    a = atr(d)
    ctx = Context()
    mid = d.index[len(d) // 2]
    rows = []
    for box, tight, run in itertools.product((12,), (2.0, 2.5, 3.0), (3.0, 5.0)):
        bs = boxes(d, a, box, tight, run, RUN_BARS[tf], HORIZON[tf])
        for entry_mode, target_mode, room, screen in itertools.product(("inbox", "break"), ("1R", "level"), (0.0, 1.0), ("any", "with", "not_against")):
            first, second = [], []
            for b in bs:
                state = ctx.at(b.at)[1]
                want = "UP" if b.sign > 0 else "DOWN"
                against = "DOWN" if b.sign > 0 else "UP"
                if (screen == "with" and state != want) or (screen == "not_against" and state == against):
                    continue
                r = trade(d, b, entry_mode, target_mode, room, HORIZON[tf], ctx)
                if r is not None:
                    (first if b.at < mid else second).append(r)
            rows.append((tight, run, entry_mode, target_mode, room, screen, first, second))
    print(f"XAUUSD {tf} {d.index[0]:%Y-%m-%d} .. {d.index[-1]:%Y-%m-%d}; halves at {mid:%Y-%m-%d}; spread {SPREAD}")
    print("| tight | run | entry | target | room | H1 | 1st half R/trade | 2nd half R/trade |")
    print("|---|---|---|---|---|---|---|---|")
    ranked = sorted(rows, key=lambda r: -(np.mean(r[6]) if len(r[6]) >= 20 else -9))
    for tight, run, e, tg, room, sc, f, s in ranked[:15]:
        print(f"| {tight} | {run} | {e} | {tg} | {room:g} | {sc} | {stats(f)} | {stats(s)} |")
