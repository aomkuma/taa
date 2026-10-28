"""FX majors on M1 (FBS-Demo): bars with the same attributes as common.Bars, features for the reversion rules,
and the round-number experiment in pips. Costs: the spread column x point + 0.2 pip on the ask, 0.2 pip slippage
on market entries, time exits and stop fills; limit fills none. Development half-years only unless --test.

    python fx.py round|tdl [--test]
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

import sim
from common import DEV, TEST, ema, gold
from sim import one_at_a_time, simulate

warnings.filterwarnings("ignore")
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]


class FXBars:
    def __init__(self, pair: str) -> None:
        m = pd.read_parquet(f"data/history/FBS-Demo/{pair}/M1.parquet")
        m.index = pd.DatetimeIndex(pd.to_datetime(m["open_time"], utc=True))
        m = m.sort_index()
        self.point = 0.001 if pair.endswith("JPY") else 0.00001
        self.pip = self.point * 10
        self.ot = m.index
        self.t64 = m.index.as_unit("ns").asi8
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * self.point
        self.n = len(self.o)
        self.gap = np.r_[999, np.diff(self.t64) // 60_000_000_000]
        ny = self.ot.tz_convert("America/New_York")
        self.ny_min = (ny.hour * 60 + ny.minute).to_numpy()
        ldn = self.ot.tz_convert("Europe/London")
        self.ldn_min = (ldn.hour * 60 + ldn.minute).to_numpy()
        self.utc_min = (self.ot.hour * 60 + self.ot.minute).to_numpy()
        self.hour = self.ot.hour.to_numpy()

    def idx(self, a: str) -> int:
        return int(self.ot.searchsorted(pd.Timestamp(a, tz="UTC")))


def h1_trend(B) -> np.ndarray:
    s = pd.Series(B.c, index=B.ot)
    h1 = s.resample("1h", label="left", closed="left").last().dropna()
    e20, e50 = h1.ewm(span=20, adjust=False).mean(), h1.ewm(span=50, adjust=False).mean()
    tr = np.where((e20.diff() > 0) & (h1 > e50), 1, np.where((e20.diff() < 0) & (h1 < e50), -1, 0))
    avail = (h1.index + pd.Timedelta(hours=1)).as_unit("ns").asi8
    pos = np.searchsorted(avail, B.t64 + 60_000_000_000, side="right") - 1
    return np.where(pos >= 0, tr[np.clip(pos, 0, None)], 0)


def contiguous(B, k: int) -> np.ndarray:
    cs = np.cumsum((B.gap > 1).astype(np.int64))
    ok = np.zeros(B.n, bool)
    ok[k:] = cs[k:] == cs[:-k]
    return ok


def table(B, d: pd.DataFrame, windows, risk_pips: np.ndarray | None = None) -> pd.DataFrame:
    rows = []
    for name, a, b in windows:
        ia, ib = B.idx(a), B.idx(b)
        t = one_at_a_time(d[(d.i >= ia) & (d.i < ib)])
        f = t[t.filled]
        r = f.usd / (f.sl + sim.COST["slip"])
        rows.append(dict(half=name[:2], n=len(f), R=r.mean(), pips=(f.usd / B.pip).sum(), win=(f.exit == "win").mean()))
    return pd.DataFrame(rows).set_index("half")


def round_exp(B, windows, step_pips=50, D=20, sl=15, tp=15, hold=240, valid=30):
    hi30 = pd.Series(B.h).rolling(30).max().to_numpy()
    lo30 = pd.Series(B.lo).rolling(30).min().to_numpy()
    win = (B.ldn_min >= 420) & (B.ny_min < 930) & contiguous(B, 60)
    out = {}
    S = step_pips * B.pip
    for nm, sh in (("round", 0.0), ("p37", 0.37), ("p63", 0.63)):
        shift = sh * S
        below = np.floor((B.c - shift) / S) * S + shift
        above = below + S
        db, da = (B.c - below) / B.pip, (above - B.c) / B.pip
        okb = (db >= 3) & (db <= D) & (lo30 > below)
        oka = (da >= 3) & (da <= D) & (hi30 < above)
        buy = okb & (~oka | (db <= da))
        sell = oka & ~buy
        i = np.flatnonzero(win & (buy | sell))
        i = i[i < B.n - 600]
        side = np.where(buy[i], 1, -1)
        off = np.where(side > 0, B.c[i] - below[i], above[i] - B.c[i])
        slp, tpp = np.full(len(i), sl * B.pip), np.full(len(i), tp * B.pip)
        bounce = simulate(B, i, side, slp, tpp, hold, off, valid)
        through = simulate(B, i, -side, slp, tpp, hold, off, valid, stop_entry=True)
        out[nm] = (table(B, bounce, windows), table(B, through, windows))
    return out


def tdl_exp(B, windows, thr=3.0, off=1.0, k=8.0, hold=240, valid=30, min_tp=15):
    atr = pd.Series(B.h - B.lo).rolling(60).mean().to_numpy()
    tp_ = (B.h + B.lo + B.c) / 3
    dv = (B.c - pd.Series(tp_).rolling(60).mean().to_numpy()) / atr
    tr = h1_trend(B)
    side_all = -np.sign(np.nan_to_num(dv)).astype(int)
    ok = (np.abs(dv) >= thr) & (side_all == tr) & (B.ldn_min >= 420) & (B.ny_min < 930) & contiguous(B, 60)
    ok &= k * atr >= min_tp * B.pip  # targets of at least min_tp pips (the auditor: 15-20+)
    i = np.flatnonzero(ok)
    i = i[i < B.n - 600]
    side = side_all[i]
    d = simulate(B, i, side, k * atr[i], k * atr[i], hold, off * atr[i], valid)
    rng = np.random.default_rng(5)
    dc = simulate(B, i, rng.choice([-1, 1], len(i)), k * atr[i], k * atr[i], hold, off * atr[i], valid)
    return table(B, d, windows), table(B, dc, windows), np.nanmedian(k * atr[i] / B.pip)


if __name__ == "__main__":
    gold.below_normal_priority()
    what = sys.argv[1]
    windows = TEST if "--test" in sys.argv else DEV
    for pair in PAIRS:
        B = FXBars(pair)
        sim.COST.update(xsp=0.2 * B.pip, stop_slip=0.2 * B.pip, stop_slip_ny=0.2 * B.pip, slip=0.2 * B.pip, tick=B.point)
        if what == "round":
            res = round_exp(B, windows)
            for j, kind in enumerate(("bounce (limit)", "through (stop)")):
                r = res["round"][j]
                p = (res["p37"][j].R + res["p63"][j].R) / 2
                beats = int((r.R > res["p37"][j].R).sum() + (r.R > res["p63"][j].R).sum())
                print(f"{pair} {kind:15} round R " + " ".join(f"{v:+.3f}" for v in r.R)
                      + f" | mean {r.R.mean():+.3f} placebo {p.mean():+.3f} beats {beats}/{2 * len(r)} | n {int(r.n.sum())}"
                      f" pips {r.pips.sum():+.0f}", flush=True)
        else:
            a, c, med = tdl_exp(B, windows)
            print(f"{pair} TDL k8 (median stop {med:.1f} pips): R " + " ".join(f"{v:+.3f}" for v in a.R)
                  + f" | mean {a.R.mean():+.3f} coin {c.R.mean():+.3f} | n {int(a.n.sum())} pips {a.pips.sum():+.0f}",
                  flush=True)
    _ = ema
