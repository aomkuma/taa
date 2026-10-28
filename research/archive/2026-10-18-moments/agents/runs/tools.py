"""Round 2, step 2 (notes.md): entries, stops and targets with chart tools on the R15 RUN-A population, each
signal on its own (no one-position rule), design data only unless --window (used only for frozen rules via rules2.py).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/tools.py

Writes tools_long_design.parquet (one row per signal x entry x stop x target) and prints the summary.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import rules  # noqa: E402
import simlib  # noqa: E402
from features import htf  # noqa: E402

from app.indicators.chart_read import ChartReadFrame  # noqa: E402
from app.indicators.market_map import MapParams, ZoneKind, state_frame, zones_at  # noqa: E402

gold, jlib = rules.gold, rules.jlib
REF = 4100.0
SPLIT = pd.Timestamp("2026-03-01", tz="UTC")
HL = ["H1", "H2", "H3", "H4", "H5"]
FIB_NEXT = {0.382: 0.618, 0.5: 0.786, 0.618: 1.0}
LEVELS = (0.382, 0.5, 0.618, 0.786, 1.0)
BE, HZ = 0.6, 120


class Map:
    """The app's M15 / H1 demand-supply zones and chart-read levels, read at the last bar closed by a time."""

    def __init__(self, P: jlib.Instr) -> None:
        self.tf = {}
        for name, mins in (("M15", 15), ("H1", 60)):
            b = htf(P.m, mins)
            c = b[["open", "high", "low", "close"]].copy()
            c.index = pd.DatetimeIndex(b.end)
            st = state_frame(c, MapParams())
            self.tf[name] = (c, st, ChartReadFrame(name, c, 0.01), c.index.as_unit("ns").asi8)

    def pos(self, name: str, t_close: pd.Timestamp) -> int:
        idx = self.tf[name][3]
        return int(np.searchsorted(idx, t_close.as_unit("ns").value, side="right")) - 1

    @lru_cache(maxsize=200_000)  # noqa: B019
    def read(self, name: str, pos: int) -> tuple[tuple, tuple]:
        c, st, fr, _ = self.tf[name]
        zs = tuple((z.kind is ZoneKind.DEMAND, z.low, z.high) for z in zones_at(c, st, pos, MapParams()))
        r = fr.at(pos)
        lv = tuple(lv.price for lv in r.levels) if r is not None else ()
        return zs, lv

    def front(self, t_close: pd.Timestamp, s: int, entry: float) -> float:
        """The nearest opposing zone edge or level in front of *entry* (distance in price, inf if none)."""
        best = np.inf
        for name in self.tf:
            zs, lv = self.read(name, self.pos(name, t_close))
            for demand, lo, hi in zs:
                if s > 0 and not demand and lo > entry:
                    best = min(best, lo - entry)
                if s < 0 and demand and hi < entry:
                    best = min(best, entry - hi)
            for p in lv:
                if (p - entry) * s > 0:
                    best = min(best, (p - entry) * s)
        return best

    def held(self, t_close: pd.Timestamp, s: int, px: float, tol: float) -> float:
        """A demand (supply) zone within *tol* of the pullback extreme *px*: its far edge, else NaN."""
        out = np.nan
        for name in self.tf:
            zs, _ = self.read(name, self.pos(name, t_close))
            for demand, lo, hi in zs:
                if demand == (s > 0) and lo - tol <= px <= hi + tol:
                    edge = lo if s > 0 else hi
                    out = edge if np.isnan(out) else (min(out, edge) if s > 0 else max(out, edge))
        return out


def sess_ss(P: jlib.Instr, t: pd.Timestamp) -> float:
    return P.stop_slip_ny if t.hour >= 12 else P.stop_slip


def floor_stop(dist: float, ad: float) -> float:
    return max(dist, 0.5 * ad, 3.0)


def channel_held(P: jlib.Instr, i_s: int, xj: int, lb: int, s: int, pl: float) -> float:
    """The run's regression channel (M1 closes start..extreme): does the pullback extreme stay inside its lower
    (upper) band extended to the pullback bar? 1 / 0."""
    j = np.arange(i_s, xj + 1)
    if len(j) < 3:
        return np.nan
    b, a = np.polyfit(j - i_s, P.c[j], 1)
    line = a + b * (j - i_s)
    off = (line - P.lo[j]).max() if s > 0 else (P.h[j] - line).max()
    at = a + b * (lb - i_s)
    return float(pl >= at - off) if s > 0 else float(pl <= at + off)


def run_one(P, j0, s, entry, sl, tp, ss, fill_bar):
    x = simlib.trade(P, j0, s, entry, sl, tp, BE, HZ, ss, fill_bar=fill_bar)
    return x["exit"], x["pnl"], x["pnl"] / (sl + ss), x["kind"], x["mins"]


def mkt_rows(P, S, AD, M) -> list[dict]:
    rows = []
    for r in S.itertuples():
        s, e, u = int(r.side), int(r.e), r.u
        entry = simlib.market_entry(P, e, s)
        ad = float(AD[r.d])
        ss = sess_ss(P, r.t)
        size = (r.ext - r.start) * s
        tclose = P.ot[r.d] + pd.Timedelta(minutes=1)
        depth = (r.ext - r.pl) * s / size
        deeper = [f for f in LEVELS if f > depth + 1e-9]
        fstop = r.ext - s * (deeper[0] if deeper else 1.0) * size
        stops = {"P": (entry - (r.pl - s * 0.3 * u)) * s, "F": (entry - (fstop - s * 0.3 * u)) * s,
                 "S": (entry - (r.start - s * 0.3 * u)) * s}
        zone_edge = M.held(tclose, s, r.pl, 0.25 * r.atr15)
        if np.isfinite(zone_edge):
            stops["Z"] = (entry - (min(zone_edge, r.pl) - s * 0.3 * u if s > 0 else max(zone_edge, r.pl) + 0.3 * u)) * s
        slope = (r.pl - r.start) / max(r.lb - r.i_s, 1)
        front = M.front(tclose, s, entry)
        targets = {"T8": 8 * u, "X": (r.ext - entry) * s,
                   "E1.272": (r.start + s * 1.272 * size - entry) * s, "E1.618": (r.start + s * 1.618 * size - entry) * s,
                   "ABCD1.0": (r.pl + s * 1.0 * size - entry) * s, "ABCD1.272": (r.pl + s * 1.272 * size - entry) * s,
                   "ABCD1.618": (r.pl + s * 1.618 * size - entry) * s,
                   "CH": (r.ext + slope * (e - r.xj) - entry) * s,
                   "Z": front if 5.0 <= front <= 60.0 else np.nan}
        chan = channel_held(P, int(r.i_s), int(r.xj), int(r.lb), s, r.pl)
        base = dict(t=r.t, half=r.half, side=s, entry_kind="MKT", brk72=float(r.lvl_h72 > 0) if np.isfinite(r.lvl_h72) else 0.0,
                    big=float(r.size_atr >= 3.7), chan=chan, zone=float(np.isfinite(zone_edge)), u=u, front=front,
                    age=(r.t - r.run_t).total_seconds() / 60)
        for sn, sd in stops.items():
            sl = floor_stop(sd, ad)
            for tn, tp_raw in targets.items():
                if not np.isfinite(tp_raw):
                    continue
                tp = max(tp_raw, 5.0)
                ex, pnl, R, kind, mins = run_one(P, e, s, entry, sl, tp, ss, False)
                rows.append(base | dict(stop=sn, target=tn, sl=sl, tp=tp, tp_raw=tp_raw, exit=ex, pnl=pnl, R=R, kind=kind,
                                        mins=mins))
    return rows


def lim_rows(P, C, AD, M, h72, l72) -> list[dict]:
    rows = []
    ot = P.ot
    for r in C.itertuples():
        s = int(r.side)
        i_s = ot.searchsorted(r.t)
        a = ot.searchsorted(r.t_tgt) + 1
        k0 = ot.searchsorted(r.t_end)
        b = min(i_s + 121, k0 + 60, len(ot) - 200)
        if a >= b:
            continue
        x0 = simlib.run_x0(P, i_s, a, s)  # fixed 2026-10-18: the start bar gives only its close
        lvl72 = h72[i_s - 1] if s > 0 else l72[i_s - 1]
        for f in (0.382, 0.5, 0.618):
            got = simlib.limit_fill(P, a, b, s, r.start_px, f, x0)
            if got is None:
                continue
            jf, entry, x = got
            t = ot[jf]
            if t.hour >= 20 or t.dayofweek >= 5:
                continue
            u = P.o[jf] / REF
            ad = float(AD[jf - 1])
            ss = sess_ss(P, t)
            size = (x - r.start_px) * s
            fl = x - s * FIB_NEXT[f] * size
            stops = {"F": (entry - (fl - s * 0.3 * u)) * s, "S": (entry - (r.start_px - s * 0.3 * u)) * s}
            front = M.front(t, s, entry)  # the bars closed before the fill bar opened
            targets = {"T8": 8 * u, "X": (x - entry) * s, "E1.272": (r.start_px + s * 1.272 * size - entry) * s,
                       "E1.618": (r.start_px + s * 1.618 * size - entry) * s,
                       "Z": front if 5.0 <= front <= 60.0 else np.nan}
            base = dict(t=t, half=r.half, side=s, entry_kind=f"LIM{round(f * 1000) / 10:g}",
                        brk72=float((x - lvl72) * s > 0), big=float(size / r.atr15 >= 3.7), chan=np.nan, zone=np.nan,
                        u=u, front=front, age=(t - r.t).total_seconds() / 60)
            for sn, sd in stops.items():
                sl = floor_stop(sd, ad)
                for tn, tp_raw in targets.items():
                    if not np.isfinite(tp_raw):
                        continue
                    tp = max(tp_raw, 5.0)
                    ex, pnl, R, kind, mins = run_one(P, jf, s, entry, sl, tp, ss, True)
                    rows.append(base | dict(stop=sn, target=tn, sl=sl, tp=tp, tp_raw=tp_raw, exit=ex, pnl=pnl, R=R,
                                            kind=kind, mins=mins))
    return rows


def summary(L: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (ek, sn, tn), g in L.groupby(["entry_kind", "stop", "target"]):
        per = {h: g[g.half == h].R.mean() for h in HL}
        st = g[g.exit == "stop"]
        kd = st.kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
        out.append(dict(entry=ek, stop=sn, target=tn, n=len(g), raw5=(g.tp_raw >= 5).mean(), win=(g.exit == "win").mean(),
                        R=g.R.mean(), usd=g.pnl.sum(), sl=g.sl.median(), tp=g.tp.median(), k1=kd["1"], k2=kd["2"],
                        k3=kd["3"], hpos=int(sum(v > 0 for v in per.values() if np.isfinite(v))),
                        **{h: per[h] for h in HL}))
    return pd.DataFrame(out)


def main() -> None:
    gold.below_normal_priority()
    P = jlib.Instr("XAUUSD")
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_atr_usd"]).ad_atr_usd.reindex(P.ot).to_numpy()
    M = Map(P)
    S = pd.read_parquet(HERE / "study_R15_design.parquet")
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[(C.R == 15) & (C.t < SPLIT)].sort_values("t")
    C["half"] = pd.cut(C.t, rules.HALVES, labels=HL, right=False)
    h72 = pd.Series(P.h, index=P.ot).rolling("72h").max().to_numpy()
    l72 = pd.Series(P.lo, index=P.ot).rolling("72h").min().to_numpy()
    rows = mkt_rows(P, S, AD, M)
    print("market rows", len(rows), flush=True)
    rows += lim_rows(P, C, AD, M, h72, l72)
    L = pd.DataFrame(rows)
    L = L[L.t < SPLIT]
    L.to_parquet(HERE / "tools_long_design.parquet")
    T = summary(L)
    T.to_csv(HERE / "tools_design.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    print(T.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
