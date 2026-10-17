"""Agent "fx": the seven USD majors on H1-scale holds (1-8 hours), M1 fills.

Conventions (the brief's, with the auditor's FX costs):
- Decide at an M1 bar's close; enter at the next bar's open. BUY at the ask = open + spread column + EXTRA + SLIP;
  SELL at the bid = open - SLIP. A BUY's stop/target on the bid lows/highs, a SELL's on the ask (bid + spread +
  EXTRA). Stop and target inside one bar = the stop. A stop pays SLIP; a limit target none; a time exit at the
  bar's close (bid for a buy, ask for a sell) with SLIP.
- EXTRA = 0.25 pip (the column is the minute's minimum spread), SLIP = 0.2 pip on entries, stops and time exits.
- Rollover: no entries 20:00-23:00 UTC; every position is closed at the close of the 20:49 UTC bar at the latest.
- R = pips / (stop distance + SLIP). USD at 0.01 lot = pips x pip value (0.10 USD for xxxUSD, 0.10/price for
  USDxxx, 10/price for USDJPY).
- Losers' kinds (the owner's), path up to 120 minutes after entry: 1 wrong way, 2 fell short, 3 too early.
"""

from __future__ import annotations

import ctypes
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
PIP = {p: (0.01 if p == "USDJPY" else 1e-4) for p in PAIRS}
POINT = {p: (0.001 if p == "USDJPY" else 1e-5) for p in PAIRS}
USD_BASE = {"USDJPY", "USDCHF", "USDCAD"}
EXTRA, SLIP = 0.25, 0.2
LON, NYC = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")
HALVES = [
    ("23H2", "2023-11-01", "2024-05-01"),
    ("24H1", "2024-05-01", "2024-11-01"),
    ("24H2", "2024-11-01", "2025-05-01"),
    ("25H1", "2025-05-01", "2025-11-01"),
    ("25H2", "2025-11-01", "2026-03-01"),
]
DESIGN = ("2023-11-01", "2026-03-01")
TEST = ("2026-03-01", "2026-10-15")


def below_normal_priority() -> None:
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def half_of(t: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    t = pd.DatetimeIndex(t)
    out = np.full(len(t), "", dtype=object)
    for name, a, b in HALVES:
        out[(t >= pd.Timestamp(a, tz="UTC")) & (t < pd.Timestamp(b, tz="UTC"))] = name
    out[(t >= pd.Timestamp(TEST[0], tz="UTC")) & (t < pd.Timestamp(TEST[1], tz="UTC"))] = "TEST"
    return out


class Pair:
    def __init__(self, sym: str) -> None:
        self.sym = sym
        m = pd.read_parquet(f"data/history/FBS-Demo/{sym}/M1.parquet")
        m.index = pd.DatetimeIndex(pd.to_datetime(m.open_time, utc=True))
        m = m[~m.index.duplicated()].sort_index()
        self.ot = m.index
        self.tmin = m.index.as_unit("ns").asi8 // 60_000_000_000
        pip = PIP[sym]
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) / pip for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * POINT[sym] / pip
        self.ask_add = self.sp + EXTRA
        px = m["close"].to_numpy(float)
        if sym == "USDJPY":
            self.usd_pip = 10.0 / px
        elif sym in USD_BASE:
            self.usd_pip = 0.1 / px
        else:
            self.usd_pip = np.full(len(px), 0.1)
        hr = m.index.hour.to_numpy()
        self.mod = (hr * 60 + m.index.minute.to_numpy())  # minute of the UTC day
        # the forced exit: the last bar that may be held is 20:49 UTC (closes 20:50)
        self.n = len(self.o)

    def h1(self) -> pd.DataFrame:
        """H1 bid bars from M1 (open time = the hour's start), with the M1 index of the hour's last bar."""
        key = self.ot.floor("h")
        df = pd.DataFrame({"o": self.o, "h": self.h, "l": self.lo, "c": self.c, "i": np.arange(self.n)}, index=self.ot)
        g = df.groupby(key)
        out = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last(), "ilast": g.i.last(),
                            "n": g.o.size()})
        return out

    def trade(self, d: int, side: int, tp: float | None, sl: float, hz: int, be: float | None = None,
              trail: tuple[float, float] | None = None, exit_mod: int = 20 * 60 + 49) -> dict | None:
        """Decision at the close of bar d, entry at the open of d+1 (must be the next minute). tp/sl in pips from the
        fill (tp None = no target). be: at be x tp (or be pips if tp is None) the stop moves to the entry. trail
        (start, dist): once the best move reaches *start* pips, the stop trails *dist* pips behind the best bid/ask
        (checked from the next bar). Hold at most hz minutes, never past exit_mod (minute of the UTC day)."""
        e = d + 1
        if e + 2 >= self.n or self.tmin[e] - self.tmin[d] != 1:
            return None
        entry = self.o[e] + (self.ask_add[e] + SLIP if side > 0 else -SLIP)
        # the last bar held
        end = e
        t0 = self.tmin[e]
        day_end = t0 - (t0 % 1440) + exit_mod  # the cut-off on the entry's UTC day
        if self.mod[e] > exit_mod:
            day_end += 1440
        last_t = min(t0 + hz - 1, day_end)
        end = int(np.searchsorted(self.tmin, last_t, side="right"))  # exclusive
        end = min(end, self.n)
        if end <= e:
            return None
        s = slice(e, end)
        adv = (self.lo[s] if side > 0 else self.h[s] + self.ask_add[s])
        fav = (self.h[s] if side > 0 else self.lo[s] + self.ask_add[s])
        a = (adv - entry) * side
        f = (fav - entry) * side
        n = len(a)
        if be is None and trail is None:
            js_ = np.flatnonzero(a <= -sl)
            js = js_[0] if len(js_) else n
            if tp is not None:
                jt_ = np.flatnonzero(f >= tp)
                jt = jt_[0] if len(jt_) else n
            else:
                jt = n
            stop_px = -sl
            armed = False
        else:
            stop_lvl = -sl  # relative to entry
            best = -1e9
            js, jt, armed = n, n, False
            arm_at = (be * tp if tp is not None else be) if be is not None else None
            for j in range(n):
                if a[j] <= stop_lvl:
                    js = j
                    break
                if tp is not None and f[j] >= tp:
                    jt = j
                    break
                best = max(best, f[j])
                if arm_at is not None and best >= arm_at and stop_lvl < 0:
                    stop_lvl, armed = 0.0, True
                if trail is not None and best >= trail[0]:
                    nl = best - trail[1]
                    if nl > stop_lvl:
                        stop_lvl, armed = nl, True
            stop_px = stop_lvl
        if js < n and js <= jt:
            pnl = stop_px - SLIP
            exit_, j = ("trail" if armed else "stop"), js
        elif jt < n:
            pnl, exit_, j = tp, "win", jt
        else:
            x = end - 1
            px = self.c[x] - (SLIP if side > 0 else -(self.ask_add[x] + SLIP))
            pnl, exit_, j = (px - entry) * side, "time", n - 1
        kind = ""
        if exit_ == "stop":
            ref = tp if tp is not None else 2 * sl
            kend = int(np.searchsorted(self.tmin, t0 + 120, side="left"))
            later = slice(e + js + 1, kend)
            fl = ((self.h[later] if side > 0 else self.lo[later] + self.ask_add[later]) - entry) * side
            hit = bool(len(fl) and (fl >= ref).any())
            mfe = max(f[:js].max() if js > 0 else 0.0, 0.0)
            kind = "3" if hit else ("2" if mfe >= 0.5 * ref else "1")
        mfe_all = float(f[: j + 1].max())
        mae_all = float(a[: j + 1].min())
        return dict(exit=exit_, pips=pnl, R=pnl / (sl + SLIP), usd=pnl * self.usd_pip[e],
                    mins=int(self.tmin[e + j] - self.tmin[e]) + 1, kind=kind, e=e, xi=e + j, entry=entry,
                    mfe=mfe_all, mae=mae_all)


def run(P: Pair, dec: np.ndarray, sides: np.ndarray, **kw) -> pd.DataFrame:
    """Sequential trades, at most one position at a time on this pair. *kw*: per-trade arrays allowed for tp/sl."""
    rows, free = [], -1
    tp, sl = kw.pop("tp"), kw.pop("sl")
    for k, (d, s) in enumerate(zip(dec, sides)):
        if d < 0 or d + 1 <= free:
            continue
        t_ = (tp[k] if np.ndim(tp) else tp)
        s_ = (sl[k] if np.ndim(sl) else sl)
        r = P.trade(int(d), int(s), None if t_ is None else float(t_), float(s_), **kw)
        if r is None:
            continue
        r |= {"t": P.ot[int(d) + 1], "side": int(s), "k": k, "sl": float(s_), "tp": t_}
        rows.append(r)
        free = r["xi"]
    return pd.DataFrame(rows)


def kinds(z: pd.DataFrame) -> str:
    if not len(z):
        return "  -/  -/  -"
    st = z[z.exit == "stop"]
    if not len(st):
        return "  -/  -/  -"
    v = st.kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    return f"{100 * v['1']:3.0f}/{100 * v['2']:3.0f}/{100 * v['3']:3.0f}"


def summary(z: pd.DataFrame, days: float | None = None) -> dict:
    if not len(z):
        return dict(n=0, win=np.nan, pips=0.0, usd=0.0, R=np.nan, Rsum=0.0)
    return dict(n=len(z), win=100 * (z.pips > 0).mean(), pips=z.pips.sum(), usd=z.usd.sum(), R=z.R.mean(),
                Rsum=z.R.sum(), per_day=(len(z) / days if days else np.nan))
