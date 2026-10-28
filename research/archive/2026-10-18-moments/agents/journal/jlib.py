"""The journal agent's shared pieces: M1 arrays per instrument, the one-trade simulation (a copy of ny_lab.M1.trade
with the instrument's slippage), the candidate tables built by build.py, and the selection loop of confluence.py
(one position at a time, at most two trades per day and session).

Design data ends before 2026-03-01; ``cands(sym, "design")`` refuses to return later rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/2026-10-18-moments"))
import gold  # noqa: E402

HERE = Path(__file__).resolve().parent
DESIGN_END = pd.Timestamp("2026-03-01", tz="UTC")
TEST_START, TEST_END = pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-10-14", tz="UTC")
REF = 4100.0  # gold price the USD sizes refer to (scaled by price / REF, as ny_lab)
# per instrument: pip (the owner's unit), point (spread column), slippage each way (price units)
SPEC = {
    # slip: market entry / time exit; extra: added to the M1 spread column (the minute's minimum); stop_slip /
    # stop_slip_ny: a stop fill (the auditor's real costs, BRIEF.md "Real costs", 2026-10-17)
    "XAUUSD": dict(pip=1.0, point=0.01, slip=0.07, extra=0.08, stop_slip=0.15, stop_slip_ny=0.20, round_step=50.0),
    "EURUSD": dict(pip=0.0001, point=0.00001, slip=0.00002, extra=0.000025, stop_slip=0.00003, stop_slip_ny=0.00003, round_step=0.0050),
    "USDJPY": dict(pip=0.01, point=0.001, slip=0.002, extra=0.0025, stop_slip=0.003, stop_slip_ny=0.003, round_step=0.50),
    "GBPUSD": dict(pip=0.0001, point=0.00001, slip=0.00002, extra=0.000025, stop_slip=0.00003, stop_slip_ny=0.00003, round_step=0.0050),
}
SESS = {0: "Asia", 1: "London", 2: "New York"}
HALVES = [
    ("2023-11 .. 2024-04", "2023-11-01", "2024-05-01"),
    ("2024-05 .. 2024-10", "2024-05-01", "2024-11-01"),
    ("2024-11 .. 2025-04", "2024-11-01", "2025-05-01"),
    ("2025-05 .. 2025-08", "2025-05-01", "2025-09-01"),
    ("2025-09 .. 2026-02", "2025-09-01", "2026-03-01"),
]


def m1_frame(sym: str) -> pd.DataFrame:
    if sym == "XAUUSD":
        m = gold.bars("M1")
    else:
        m = pd.read_parquet(ROOT / f"data/history/FBS-Demo/{sym}/M1.parquet")
        m.index = pd.DatetimeIndex(pd.to_datetime(m["open_time"], utc=True))
        m = m[~m.index.duplicated(keep="last")].sort_index()
    m = m[(m.index >= pd.Timestamp("2023-08-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


class Instr:
    def __init__(self, sym: str) -> None:
        self.sym = sym
        s = SPEC[sym]
        self.pip, self.point, self.slip, self.round_step = s["pip"], s["point"], s["slip"], s["round_step"]
        self.stop_slip, self.stop_slip_ny = s["stop_slip"], s["stop_slip_ny"]
        m = m1_frame(sym)
        self.m = m
        self.ot = m.index
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.v = m["tick_volume"].to_numpy(float)
        self.sp0 = m["spread"].to_numpy(float) * self.point  # the column (minimum in the minute)
        self.sp = self.sp0 + s["extra"]  # the real spread (auditor)

    def gross(self) -> None:
        """No costs at all (to compare periods before costs)."""
        self.sp = np.zeros_like(self.sp)
        self.slip = self.stop_slip = self.stop_slip_ny = 0.0

    def fill(self, e: np.ndarray, side: np.ndarray) -> np.ndarray:
        return self.o[e] + np.where(side > 0, self.sp[e] + self.slip, -self.slip)

    def e_of(self, t: pd.Series) -> np.ndarray:
        e = self.ot.searchsorted(pd.DatetimeIndex(t))
        assert (self.ot[e] == pd.DatetimeIndex(t)).all()
        return e

    def trade(self, e: int, side: int, tp: float, sl: float, be: float | None, hz: int, ss: float | None = None) -> dict:
        """ny_lab.M1.trade with this instrument's real costs: target tp, stop sl (price units from the fill); *be*: at
        that share of the target the stop moves to the entry; *ss* the stop slippage. Stopped losers in the owner's
        three kinds."""
        SLIP = self.slip
        SS = self.stop_slip if ss is None else ss
        entry = self.o[e] + (self.sp[e] + SLIP if side > 0 else -SLIP)
        stop, armed, mfe, mae = entry - side * sl, False, 0.0, 0.0
        end = min(e + hz, len(self.o) - 1)
        res = None
        for j in range(e, end):
            adv = self.lo[j] if side > 0 else self.h[j] + self.sp[j]
            fav = self.h[j] if side > 0 else self.lo[j] + self.sp[j]
            mae = max(mae, (entry - adv) * side)
            if (adv - stop) * side <= 0:
                px = stop - side * SS
                res = ("stop" if not armed else "be", (px - entry) * side, j)
                break
            if (fav - entry) * side >= tp:
                res = ("win", tp, j)
                break
            mfe = max(mfe, (fav - entry) * side)
            if be is not None and not armed and mfe >= be * tp:
                armed, stop = True, entry
        if res is None:
            x = end - 1
            px = self.c[x] - (SLIP if side > 0 else -(self.sp[x] + SLIP))
            res = ("time", (px - entry) * side, x)
        kind = ""
        if res[0] == "stop":
            later = range(res[2] + 1, min(e + 120, len(self.o)))
            hit = any(((self.h[k] if side > 0 else self.lo[k] + self.sp[k]) - entry) * side >= tp for k in later)
            kind = "3" if hit else ("2" if mfe >= 0.5 * tp else "1")
        return dict(exit=res[0], pnl=res[1], mins=res[2] - e + 1, kind=kind, entry=entry, mfe=mfe, mae=mae, xj=res[2])


def cands(sym: str, part: str) -> pd.DataFrame:
    d = pd.read_parquet(HERE / f"cand_{sym}_{part}.parquet")
    d["t"] = pd.to_datetime(d.t, utc=True)
    if part.endswith("design"):
        assert d.t.max() < DESIGN_END, "design table holds test rows"
    return d


def run(sig: pd.DataFrame, P: Instr, tp_u: float, be: float | None, hz: int, unit: np.ndarray | None = None,
        coin: np.random.Generator | None = None, per_sess: int = 2, once: bool = False) -> pd.DataFrame:
    """The confluence selection loop. *sig* rows need t, e, side, session, sl (price units); *tp_u* the target in
    units of *unit* (per row; gold: price / REF USD) - sl is already in price units. *once*: one attempt per 72-h
    extreme (the signal's side and its front72 price) a day."""
    rows, free, count, tried = [], pd.Timestamp(0, tz="UTC"), {}, set()
    x = sig.sort_values("t").drop_duplicates("t")
    u = x["unit"].to_numpy() if "unit" in x else np.ones(len(x))
    for i, r in enumerate(x.itertuples()):
        key = (r.t.normalize(), r.session)
        if r.t < free or count.get(key, 0) >= per_sess:
            continue
        if once:
            ek = (r.t.normalize(), int(r.side), round(float(r.front72), 2))
            if ek in tried:
                continue
            tried.add(ek)
        s = int(r.side) if coin is None else int(coin.choice([-1, 1]))
        tp = tp_u * u[i]
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        out = P.trade(int(r.e), s, tp, float(r.sl), be, hz, ss)
        out |= {"t": r.t, "session": r.session, "side": s, "sl": float(r.sl), "tp": tp, "e": int(r.e),
                "R": out["pnl"] / (float(r.sl) + ss), "idx": r.Index, "pnl_u": out["pnl"] / u[i]}
        rows.append(out)
        free, count[key] = r.t + pd.Timedelta(minutes=int(out["mins"])), count.get(key, 0) + 1
    return pd.DataFrame(rows)


def account(r: pd.DataFrame, P: Instr) -> str:
    """The owner's account check at 0.01 lot: worst single loss, longest losing streak, max drawdown, 6 average
    losses vs a 50 / 100 USD account (gold: P&L in USD = price x 1; a USD major ~0.10 USD a pip)."""
    # 0.01 lot = 1000 units: EURUSD / GBPUSD 0.10 USD a pip; USDJPY 10 JPY a pip ~ 0.067 USD near 150
    per_pip = {"EURUSD": 0.10, "GBPUSD": 0.10, "USDJPY": 0.067}.get(P.sym, 1.0)
    usd = (r.pnl * (1.0 if P.sym == "XAUUSD" else per_pip / P.pip)).to_numpy()
    eq = np.cumsum(usd)
    dd = float((np.maximum.accumulate(eq) - eq).max())
    streak = mx = 0
    for v in usd:
        streak = streak + 1 if v < 0 else 0
        mx = max(mx, streak)
    st = usd[(r.exit == "stop").to_numpy()]
    avg_loss = float(-st.mean()) if len(st) else 0.0  # the average full (stopped) loss
    six = 6 * avg_loss
    extra = ""
    if P.sym == "XAUUSD" and "pnl_u" in r:
        u = r.pnl_u.to_numpy()
        equ = np.cumsum(u)
        stu = u[(r.exit == "stop").to_numpy()]
        extra = (f" | at gold 4100 (U): worst {u.min():.2f}, max DD {float((np.maximum.accumulate(equ) - equ).max()):.1f},"
                 f" 6 avg losses {6 * float(-stu.mean()) if len(stu) else 0:.1f}")
    return (f"worst {usd.min():.2f} USD, longest losing streak {mx}, max DD {dd:.1f} USD, avg loss {avg_loss:.2f}"
            f" -> 6 in a row {six:.1f} USD ({'fits' if six < 50 else 'NOT'} 50, {'fits' if six < 100 else 'NOT'} 100)" + extra)


def kinds(z: pd.DataFrame) -> str:
    if not len(z):
        return "  -/  -/  -"
    v = z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    return f"{100 * v['1']:3.0f}/{100 * v['2']:3.0f}/{100 * v['3']:3.0f}"


def coin_stats(sig: pd.DataFrame, P: Instr, tp_u: float, be: float | None, hz: int, seeds: int = 20, **kw) -> dict:
    """Coin-flip side on the same minutes, averaged over *seeds*."""
    rs, ks, n = [], [], []
    for s in range(seeds):
        z = run(sig, P, tp_u, be, hz, coin=np.random.default_rng(100 + s), **kw)
        if len(z):
            rs.append(z.R.mean())
            n.append(len(z))
            v = z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
            ks.append(v.to_numpy())
    k = np.mean(ks, 0) if ks else np.zeros(3)
    return dict(R=float(np.mean(rs)) if rs else np.nan, sd=float(np.std(rs)) if rs else np.nan,
                kinds=f"{100 * k[0]:3.0f}/{100 * k[1]:3.0f}/{100 * k[2]:3.0f}", n=float(np.mean(n)) if n else 0)


def line(name: str, r: pd.DataFrame, a: str, b: str, P: Instr, unit_name: str = "USD") -> str:
    days = pd.bdate_range(a, b, inclusive="left").size
    if not len(r):
        return f"  {name:20} 0 trades"
    by_m = r.pnl.groupby(r.t.dt.strftime("%Y-%m")).sum()
    scale = 1.0 if P.sym == "XAUUSD" else 1.0 / P.pip
    return (f"  {name:20} {len(r):4} {len(r) / days:4.2f} {100 * (r.exit == 'win').mean():4.0f}%"
            f"  {r.R.mean():+.3f}R  {scale * r.pnl.sum():+8.1f} {unit_name}  m+ {(by_m > 0).sum()}/{len(by_m)}"
            f"  kinds {kinds(r)}")
