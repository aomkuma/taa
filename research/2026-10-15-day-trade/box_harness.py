"""The box breakout as the engine trades it, fast enough for a walk-forward grid (owner, 2026-10-15).

Why: ``flag_rules.py`` measured +0.41 R/trade, but 7 of its 55 trades at 21:40-22:45 UTC (the rollover) made
16.1 of its 22.4 R, and the bot's detector (``chart.box_break``) under the bot's limits measured -0.21 in the
bot's hours (07-20 UTC). Judging variants needs the engine's own rule; the backtester takes ~10 minutes a
month, this harness a few minutes for the year. Parity: in the bot's mode it reproduces the engine's March
2026 backtest (``data/backtests/inv/box_2026-03/trades.csv``) trade for trade; it checks that first.

Mirrors the engine (``setup_breakout_box`` in a lane, ``data/research/config_box.yaml``):
- events: the detector's break bars; ``latest`` = the latest qualifying box per breaking bar (the detector),
  ``first`` = the research's greedy non-overlapping boxes (no new box inside a used one); ATR Wilder (the
  detector's) or the plain mean;
- the setup: the hours window on the bar's close time, the H1 market-map state with the break (H4 not against
  when asked), the target at the nearest H1 chart-read level at most 3 R away, room to it >= 1 R;
- the arbiter: one selection per 12 bars (strategy, symbol), counted even when the decision then refuses;
- the decision: one gold position at a time;
- fills: entry at the close plus the bar's spread plus 7 points of slippage, the stop beyond the box edge by
  the same, stop/target on bar highs/lows (both in one bar: the stop), else the close 48 bars after entry.

The rollover (20:30-23:00 UTC) and weekends are never traded (fills there are not realistic).

    .venv/Scripts/python research/2026-10-15-day-trade/box_harness.py
"""

from __future__ import annotations

import csv
import itertools
import sys
from collections.abc import Callable

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "research/2026-10-15-day-trade")
import flag_rules as fr  # noqa: E402  (the H1 read and map context, the stats line)

from app.config import AppConfig  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.indicators.volatility import atr as wilder_atr  # noqa: E402
from app.strategy.market_maps import MapBook, map_params  # noqa: E402

H = "data/history/FBS-Demo/XAUUSD"
BOX, TIGHT, RUN, RUN_BARS, HORIZON = 12, 3.0, 5.0, 24, 48
SLIPPAGE, POINT = 0.07, 0.01
COOLDOWN, TIME_STOP, CAP_R, ROOM_R = 12, 48, 3.0, 1.0
ENGINE_MARCH = "data/backtests/inv/box_2026-03/trades.csv"

Window = Callable[[pd.Timestamp], bool]


def _rollover(ts: pd.Timestamp) -> bool:
    minutes = ts.hour * 60 + ts.minute
    return 20 * 60 + 30 <= minutes < 23 * 60


WINDOWS: dict[str, Window] = {
    "07-20 (bot now)": lambda ts: ts.weekday() < 5 and 7 <= ts.hour < 20,
    "00-20:30 (+Asia)": lambda ts: (
        ts.weekday() < 5 and not _rollover(ts) and ts.hour < 21 and not (ts.weekday() == 4 and ts.hour >= 20)
    ),
    "00-07 (Asia)": lambda ts: ts.weekday() < 5 and ts.hour < 7,
}


class Market:
    def __init__(self) -> None:
        raw = pd.read_parquet(f"{H}/M5.parquet").sort_values("close_time").reset_index(drop=True)
        self.times = pd.DatetimeIndex(pd.to_datetime(raw["close_time"], utc=True))
        self.d = raw[["open", "high", "low", "close"]].astype(float).set_index(self.times)
        self.h, self.lo, self.c = (self.d[k].to_numpy() for k in ("high", "low", "close"))
        self.cost = raw["spread"].to_numpy() * POINT + SLIPPAGE
        self.atr = {
            "wilder": wilder_atr(self.d["high"], self.d["low"], self.d["close"], 14).to_numpy(),
            "mean": fr.atr(self.d),
        }
        self.ctx = fr.Context()  # H1 chart-read levels and H1 map state
        h4 = fr.load("H4")
        self.h4 = h4
        cfg = AppConfig()
        self.book4 = MapBook(map_params(cfg), [Timeframe.H4], {Timeframe.H4: map_params(cfg, Timeframe.H4)})
        self._h4: dict[int, str] = {}

    def h4_state(self, ts: pd.Timestamp) -> str:
        pos = int(self.h4.index.searchsorted(ts, side="right")) - 1
        if pos not in self._h4:
            m = self.book4.at(
                "XAUUSD",
                {Timeframe.H4: self.h4.iloc[max(0, pos - 700) : pos + 1]},
                self.h4.index[pos].to_pydatetime(),
            )
            self._h4[pos] = "UNKNOWN" if m is None or "H4" not in m.frames else m.frames["H4"].state.value
        return self._h4[pos]


def events(m: Market, atr_kind: str, choice: str) -> list[tuple[int, int, float, float]]:
    """(break bar, sign, the box's other edge, the broken edge), in time order."""
    a, h, lo, c, n = m.atr[atr_kind], m.h, m.lo, m.c, len(m.c)
    top = np.full(n, np.nan)
    bot = np.full(n, np.nan)
    top[BOX - 1 :] = np.lib.stride_tricks.sliding_window_view(h, BOX).max(axis=1)
    bot[BOX - 1 :] = np.lib.stride_tricks.sliding_window_view(lo, BOX).min(axis=1)

    def qualifies(b: int) -> int:
        b0 = b - BOX + 1
        if not np.isfinite(a[b]) or a[b] <= 0 or top[b] - bot[b] > TIGHT * a[b]:
            return 0
        run = (c[b0] - c[b0 - RUN_BARS]) / a[b]
        sign = 1 if run >= RUN else -1 if run <= -RUN else 0
        return sign if sign and (c[b] - c[b0]) * sign > 0 else 0

    def breaks(b: int, sign: int) -> int | None:
        for t in range(b + 1, min(n, b + 1 + HORIZON)):
            if (c[t] - (bot[b] if sign > 0 else top[b])) * sign < 0:
                return None
            if (c[t] - (top[b] if sign > 0 else bot[b])) * sign > 0:
                return t
        return None

    found: dict[int, tuple[int, float, float]] = {}
    b = BOX + RUN_BARS
    while b < n:
        sign = qualifies(b)
        if not sign:
            b += 1
            continue
        t = breaks(b, sign)
        other, broken = (float(bot[b]), float(top[b])) if sign > 0 else (float(top[b]), float(bot[b]))
        if choice == "latest":
            if t is not None:
                found[t] = (sign, other, broken)  # boxes come in order: a later box on the same bar replaces
            b += 1
        else:  # "first": the research's greedy boxes; the next box starts after this one
            if t is not None and t not in found:
                found[t] = (sign, other, broken)
            b += BOX
    return [(t, s, inv, edge) for t, (s, inv, edge) in sorted(found.items())]


def simulate(
    m: Market, evs: list[tuple[int, int, float, float]], window: Window, h4: bool
) -> list[tuple[pd.Timestamp, int, float, str]]:
    out: list[tuple[pd.Timestamp, int, float, str]] = []
    busy, selected = -1, -(10**9)
    for t, s, inv, _ in evs:
        ts = m.times[t]
        if not window(ts):
            continue
        levels, h1 = m.ctx.at(ts)
        if h1 != ("UP" if s > 0 else "DOWN"):
            continue
        if h4 and m.h4_state(ts) == ("DOWN" if s > 0 else "UP"):
            continue
        entry = m.c[t] + s * m.cost[t]
        stop = inv - s * m.cost[t]
        risk = (entry - stop) * s
        if risk <= 0:
            continue
        ahead = sorted((lv - entry) * s for lv in levels if (lv - entry) * s > 0)
        near = ahead[0] / risk if ahead else None
        if near is not None and near < ROOM_R:
            continue
        # a signal: the arbiter, then the decision (one gold position)
        if t - selected < COOLDOWN:
            continue
        selected = t
        if t <= busy:
            continue
        tgt_r = min(CAP_R, near) if near is not None else CAP_R
        target = entry + s * tgt_r * risk
        end = min(t + TIME_STOP, len(m.c) - 1)
        r, why, j = None, "TIME", end
        for k in range(t + 1, end + 1):
            if (m.lo[k] if s > 0 else m.h[k]) * s <= stop * s:
                r, why, j = -1.0, "SL", k
                break
            if (m.h[k] if s > 0 else m.lo[k]) * s >= target * s:
                r, why, j = tgt_r, "TP", k
                break
        if r is None:
            r = (m.c[end] - entry) * s / risk
        out.append((ts, s, r, why))
        busy = j
    return out


def parity(m: Market) -> bool:
    """The bot's mode must reproduce the engine's March 2026 backtest trade for trade."""
    mine = [
        (ts, s, r, why)
        for ts, s, r, why in simulate(m, events(m, "wilder", "latest"), WINDOWS["07-20 (bot now)"], False)
        if ts.year == 2026 and ts.month == 3
    ]
    rows = list(csv.DictReader(open(ENGINE_MARCH, encoding="utf-8")))
    engine = [
        (
            pd.Timestamp(r["entry_time"]),
            1 if r["side"] == "BUY" else -1,
            float(r["r_multiple"]),
            r["exit_reason"],
        )
        for r in rows
    ]
    # the engine's entry time is the next bar's open = the signal bar's close time
    same = len(mine) == len(engine) and all(
        a[0] == b[0] and a[1] == b[1] and a[3] == b[3] and abs(a[2] - b[2]) < 0.05
        for a, b in zip(mine, engine, strict=True)
    )
    print("parity with the engine's March 2026:", "OK" if same else "MISMATCH")
    for a, b in itertools.zip_longest(mine, engine):
        print(
            "  harness",
            None if a is None else (a[0].strftime("%m-%d %H:%M"), a[1], round(a[2], 2), a[3]),
            "| engine",
            None if b is None else (b[0].strftime("%m-%d %H:%M"), b[1], round(b[2], 2), b[3]),
        )
    return same


def stats(rs: list[float]) -> str:
    return fr.stats(rs) if rs else "n 0"


if __name__ == "__main__":
    m = Market()
    if not parity(m):
        sys.exit("stop: the harness does not match the engine; fix that before any grid")
    mid = m.times[len(m.times) // 2]
    print(f"\nXAUUSD M5 {m.times[0]:%Y-%m-%d} .. {m.times[-1]:%Y-%m-%d}; halves at {mid:%Y-%m-%d}")
    print("| hours (UTC) | box | ATR | H4 not against | year R/trade | 1st half | 2nd half |")
    print("|---|---|---|---|---|---|---|")
    rows = []
    cache: dict[tuple[str, str], list[tuple[int, int, float, float]]] = {}
    for (wname, window), choice, atr_kind, h4 in itertools.product(
        WINDOWS.items(), ("latest", "first"), ("wilder", "mean"), (False, True)
    ):
        key = (atr_kind, choice)
        if key not in cache:
            cache[key] = events(m, atr_kind, choice)
        tr = simulate(m, cache[key], window, h4)
        rs = [r for _, _, r, _ in tr]
        f = [r for ts, _, r, _ in tr if ts < mid]
        s2 = [r for ts, _, r, _ in tr if ts >= mid]
        rows.append((np.mean(f) if len(f) >= 8 else -9.0, wname, choice, atr_kind, h4, rs, f, s2))
    for score, wname, choice, atr_kind, h4, rs, f, s2 in sorted(rows, key=lambda x: -x[0]):
        print(
            f"| {wname} | {choice} | {atr_kind} | {'yes' if h4 else 'no'} | {stats(rs)} | {stats(f)} | {stats(s2)} |"
        )
