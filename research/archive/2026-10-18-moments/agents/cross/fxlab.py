"""Agent "cross": instruments, costs and the trade simulator for gold and the seven majors (the brief's conventions
with the auditor's real costs, 2026-10-17).

- Decide at a bar's close; enter at the next bar's open. BUY at the ask = open + spread column + extra + entry slip;
  SELL at the bid = open - entry slip. Stops/targets on bar highs/lows; a SELL's on the ask (bid + spread + extra).
  Stop and target inside one bar = the stop. A stop pays the stop slip; a limit target none; a time exit at the
  last bar's close (bid for a buy, ask for a sell) with the entry slip. Break-even: at *be* x the target the stop
  moves to the entry (from the next bar).
- Costs. Gold: extra 0.08 USD (the column is the minute's minimum), entry slip 0.07, stop slip 0.15 (0.20 in
  12-17 UTC). FX: extra 0.25 pip, entry slip 0.2 pip, stop slip 0.3 pip.
- R = P&L / (stop distance + stop slip). Units: pips (gold: USD = gold pips; at 0.01 lot USD = price move x 1).
- The losers' three kinds (the owner's), from the path up to 120 minutes after the entry.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

PIP = {"XAUUSD": 1.0, "EURUSD": 1e-4, "GBPUSD": 1e-4, "AUDUSD": 1e-4, "NZDUSD": 1e-4, "USDCHF": 1e-4, "USDCAD": 1e-4, "USDJPY": 1e-2}
POINT = {"XAUUSD": 0.01, "USDJPY": 0.001}
LO, HI = pd.Timestamp("2023-09-01", tz="UTC"), pd.Timestamp("2026-10-15", tz="UTC")


class Inst:
    def __init__(self, sym: str) -> None:
        self.sym = sym
        if sym == "XAUUSD":
            m = gold.bars("M1")
        else:
            m = pd.read_parquet(f"data/history/FBS-Demo/{sym}/M1.parquet")
            m.index = pd.DatetimeIndex(pd.to_datetime(m.open_time, utc=True))
        m = m[~m.index.duplicated()].sort_index()
        m = m[(m.index >= LO) & (m.index < HI)]
        self.ot = m.index
        self.tmin = m.index.as_unit("ns").asi8 // 60_000_000_000
        pip = PIP[sym]
        # everything in pips from here on
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) / pip for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * POINT.get(sym, 1e-5) / pip
        if sym == "XAUUSD":
            self.extra, self.eslip = 0.08, 0.07
            hrs = m.index.hour.to_numpy()
            self.sslip = np.where((hrs >= 12) & (hrs < 17), 0.20, 0.15)
        else:
            self.extra, self.eslip = 0.25, 0.2
            self.sslip = np.full(len(m), 0.3)
        self.ask_add = self.sp + self.extra

    def index_at(self, ts: pd.DatetimeIndex) -> np.ndarray:
        """The bar index of each decision time (bar open time), -1 where the bar is missing."""
        i = self.ot.get_indexer(ts)
        return i

    def trade(self, d: int, side: int, tp: float, sl: float, be: float | None, hz: int) -> dict | None:
        """Decision at the close of bar d, entry at the open of d+1 (which must be the next minute)."""
        e = d + 1
        if e + 2 >= len(self.o) or self.tmin[e] - self.tmin[d] != 1:
            return None
        entry = self.o[e] + (self.ask_add[e] + self.eslip if side > 0 else -self.eslip)
        end = e
        while end < len(self.o) - 1 and self.tmin[end] - self.tmin[e] < hz:
            end += 1
        sl_ = slice(e, end)
        adv = self.lo[sl_] if side > 0 else self.h[sl_] + self.ask_add[sl_]
        fav = self.h[sl_] if side > 0 else self.lo[sl_] + self.ask_add[sl_]
        a = (adv - entry) * side  # adverse excursion (negative = against)
        f = (fav - entry) * side
        n = len(a)
        stop_hit = np.flatnonzero(a <= -sl)
        tgt_hit = np.flatnonzero(f >= tp)
        js = stop_hit[0] if len(stop_hit) else n
        jt = tgt_hit[0] if len(tgt_hit) else n
        armed = False
        if be is not None:
            arm = np.flatnonzero(f >= be * tp)
            ja = arm[0] if len(arm) else n
            if ja < min(js, jt):  # armed at ja (after that bar's checks): the stop is the entry from ja + 1
                bes = np.flatnonzero(a[ja + 1:] <= 0)
                jb = ja + 1 + bes[0] if len(bes) else n
                js, armed = jb, True  # the entry stop is hit no later than the original one
        mfe_before = lambda j: f[:j].max() if j > 0 else 0.0  # noqa: E731
        if js < n and js <= jt:
            px_stop = entry - side * (0 if armed else sl)
            pnl = (px_stop - side * self.sslip[e + js] - entry) * side
            exit_, j = ("be" if armed else "stop"), js
        elif jt < n:
            pnl, exit_, j = tp, "win", jt
        else:
            x = end - 1
            px = self.c[x] - (self.eslip if side > 0 else -(self.ask_add[x] + self.eslip))
            pnl, exit_, j = (px - entry) * side, "time", n - 1
        kind = ""
        if exit_ == "stop":
            k_end = e
            while k_end < len(self.o) - 1 and self.tmin[k_end] - self.tmin[e] < 120:
                k_end += 1
            later = slice(e + js + 1, k_end)
            fl = (self.h[later] if side > 0 else self.lo[later] + self.ask_add[later]) - entry
            hit = bool(len(fl) and (fl * side >= tp).any())
            mfe = max(mfe_before(js), 0.0)
            kind = "3" if hit else ("2" if mfe >= 0.5 * tp else "1")
        return dict(exit=exit_, pnl=pnl, R=pnl / (sl + self.sslip[e]), mins=int(self.tmin[e + j] - self.tmin[e]) + 1,
                    kind=kind, e=e)


def run(inst: Inst, dec_idx: np.ndarray, sides: np.ndarray, tp: float, sl: float, be: float | None, hz: int,
        times: pd.DatetimeIndex) -> pd.DataFrame:
    """Sequential trades, one position at a time on this instrument."""
    rows, free = [], -1
    for d, s, t in zip(dec_idx, sides, times):
        if d < 0 or d + 1 <= free:
            continue
        r = inst.trade(int(d), int(s), tp, sl, be, hz)
        if r is None:
            continue
        r |= {"t": t, "side": int(s)}
        rows.append(r)
        free = r["e"] + r["mins"]
    return pd.DataFrame(rows)


def kinds(z: pd.DataFrame) -> str:
    if not len(z):
        return "-"
    v = z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    return f"{100 * v['1']:3.0f}/{100 * v['2']:3.0f}/{100 * v['3']:3.0f}%"
