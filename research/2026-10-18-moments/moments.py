"""Setup OWN's moments dataset (docs/OWN_SETUP.md): every moment (and control half hour) in the window with its
relative features as of the moment, and the three playbooks' trades with the standard exits.

Window 2026-04-14 .. 2026-10-14 (the latest six months, owner 2026-10-17), warm-up from 2026-01-02. Largest
timeframe H1 (owner, 2026-10-17). Features use only bars closed by the moment ``T`` (M1 bars opening before
``T``; M5/M15/H1 bars closing at or before ``T``). Fills as ``research/2026-10-17-s1/s1_funnel.py``: entry at the
next bar's open, a BUY at the ask, stops/targets on bar highs/lows (a SELL's on the ask), both in one bar = the
stop, 7 points of slippage on entry and exit.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/moments.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, ".")
import gold  # noqa: E402

from app.indicators.chart_read import ChartRead, ChartReadFrame  # noqa: E402
from app.indicators.market_map import MapParams, state_frame  # noqa: E402

WARM = pd.Timestamp("2026-01-02", tz="UTC")
START = pd.Timestamp("2026-04-14", tz="UTC")
END = pd.Timestamp("2026-10-14", tz="UTC")
FIT_END = pd.Timestamp("2026-07-14", tz="UTC")
POINT = json.load(open(gold.NEW / "spec.json"))["spec"]["point"]
SLIP = 7 * POINT
ENTRY_MIN, HOLD, RECLAIM = 30, 60, 5
TARGET_U, STOP_PAD_U, AT_POOL_U = 0.5, 0.1, 0.25
ROUND = 50.0
OUT = "data/research/own_moments"

MOMENTS = [  # name, zone, local clock
    ("tokyo", "Asia/Tokyo", "09:00"),
    ("asia", "Asia/Shanghai", "09:00"),
    ("london", "Europe/London", "08:00"),
    ("comex", "America/New_York", "08:20"),
    ("ny_data", "America/New_York", "08:30"),
    ("ny_cash", "America/New_York", "09:30"),
]


def utc_at(day: pd.Timestamp, zone: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(f"{day.date()} {clock}").tz_localize(ZoneInfo(zone)).tz_convert("UTC")


@dataclass
class Row:
    t: pd.Timestamp
    zone: str
    clock: str
    tags: set[str]


def moment_rows(days: list[pd.Timestamp], cal: pd.DataFrame) -> list[Row]:
    rel = {(r.t): r.event for r in cal.itertuples()}
    rows: list[Row] = []
    for day in days:
        found: list[Row] = [Row(utc_at(day, z, c), z, c, {n}) for n, z, c in MOMENTS]
        for t, ev in rel.items():
            if t.normalize() == day:
                found.append(Row(t, "America/New_York", t.tz_convert(gold.NY).strftime("%H:%M"), {ev.lower()}))
        found.sort(key=lambda r: r.t)
        merged: list[Row] = []
        for r in found:  # within 15 minutes = one row, at the later time (a release's own minute)
            if merged and r.t - merged[-1].t <= pd.Timedelta(minutes=15):
                merged[-1] = Row(r.t, r.zone, r.clock, merged[-1].tags | r.tags)
            else:
                merged.append(r)
        rows += [r for r in merged if r.t.normalize() == day]
        for k in range(1, 42):  # control half hours 00:30 .. 20:30 UTC
            t = day + pd.Timedelta(minutes=30 * k)
            if all(abs(t - m.t) > pd.Timedelta(minutes=15) for m in merged):
                rows.append(Row(t, "UTC", t.strftime("%H:%M"), {"control"}))
    return rows


class Data:
    def __init__(self) -> None:
        m1 = gold.bars("M1")
        m1 = m1[m1.index >= WARM - pd.Timedelta(days=45)]
        self.m1 = m1
        self.ot = m1.index
        self.pos = {t: i for i, t in enumerate(self.ot)}
        self.o, self.h, self.lo, self.c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m1["spread"].to_numpy(float) * POINT
        n = 30
        hh = pd.Series(self.h[::-1]).rolling(n).max().to_numpy()[::-1]
        ll = pd.Series(self.lo[::-1]).rolling(n).min().to_numpy()[::-1]
        self.r30 = hh - ll  # the range of the 30 bars opening at i
        self.frames = {}
        for tf in ("M5", "M15", "H1"):
            d = pd.read_parquet(gold.NEW / f"{tf}.parquet").sort_values("close_time")
            d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
            self.frames[tf] = d[d.index >= WARM - pd.Timedelta(days=60)]
        m5 = self.frames["M5"]
        c5 = m5["close"].astype(float)
        width = 4 * c5.rolling(20).std() / c5.rolling(20).mean()
        pc = c5.shift(1)
        tr = pd.concat([m5["high"] - m5["low"], (m5["high"] - pc).abs(), (m5["low"] - pc).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        look = 20 * 276
        self.bb_pct = (width.rolling(look, min_periods=look // 2).rank(pct=True) * 100).to_numpy()
        self.atr_pct = (atr.rolling(look, min_periods=look // 2).rank(pct=True) * 100).to_numpy()
        self.m5_close_t = m5.index
        self.states = {tf: state_frame(self.frames[tf], MapParams())["state"] for tf in ("M15", "H1")}
        self.reads = {tf: ChartReadFrame(tf, self.frames[tf], POINT) for tf in ("M15", "H1")}
        athens = m1.index.tz_convert("Europe/Athens")
        day = pd.Series(athens.date, index=m1.index)
        g = m1.groupby(day.to_numpy())
        self.broker_days = pd.DataFrame({"high": g["high"].max(), "low": g["low"].min(), "start": g.apply(lambda x: x.index[0])})
        self.broker_days["range"] = self.broker_days["high"] - self.broker_days["low"]

    def last_before(self, t: pd.Timestamp) -> int:
        return int(self.ot.searchsorted(t, side="left")) - 1

    def usual_run(self, t: pd.Timestamp, zone: str, clock: str) -> float:
        vals = []
        day = t.tz_convert(ZoneInfo(zone)).normalize().tz_localize(None)
        for k in range(1, 45):
            d = day - pd.Timedelta(days=k)
            if d.weekday() > 4:
                continue
            x = utc_at(d, zone, clock)
            i = self.pos.get(x)
            if i is not None and np.isfinite(self.r30[i]):
                vals.append(self.r30[i])
            if len(vals) == 20:
                break
        return float(np.median(vals)) if len(vals) >= 10 else np.nan

    def regime(self, t: pd.Timestamp) -> float:
        bd = self.broker_days[self.broker_days["start"] < t - pd.Timedelta(hours=24)]
        return float(bd["range"].iloc[-20:].mean()) if len(bd) >= 20 else np.nan

    def read(self, tf: str, t: pd.Timestamp) -> ChartRead | None:
        fr = self.reads[tf]
        return fr.at(fr.pos_at(t))

    def pools(self, t: pd.Timestamp, i: int, reads: dict[str, ChartRead | None]) -> list[tuple[float, str]]:
        out: list[tuple[float, str]] = []
        bd = self.broker_days[self.broker_days["start"] <= t]
        if len(bd) >= 2:
            prev = bd.iloc[-2]
            out += [(prev["high"], "pdh"), (prev["low"], "pdl")]
        day = t.normalize()
        for name, a, b in (("asia", day, day + pd.Timedelta(hours=7)), ("london", day + pd.Timedelta(hours=7), t)):
            j0, j1 = int(self.ot.searchsorted(a)), min(int(self.ot.searchsorted(min(b, t))), i + 1)
            if j1 - j0 >= 30:
                out += [(self.h[j0:j1].max(), f"{name}_h"), (self.lo[j0:j1].min(), f"{name}_l")]
        pd_ = day - pd.Timedelta(days=3 if day.weekday() == 0 else 1)
        j0, j1 = int(self.ot.searchsorted(pd_ + pd.Timedelta(hours=13))), int(self.ot.searchsorted(pd_ + pd.Timedelta(hours=21)))
        if j1 - j0 >= 30:
            out += [(self.h[j0:j1].max(), "ny_h"), (self.lo[j0:j1].min(), "ny_l")]
        for tf, read in reads.items():
            if read is not None:
                out += [(lv.price, f"{tf.lower()}_lvl") for lv in read.levels]
        x = self.c[i]
        out += [(np.floor(x / ROUND) * ROUND, "round"), (np.ceil(x / ROUND) * ROUND, "round")]
        return out

    def state(self, tf: str, t: pd.Timestamp) -> str:
        s = self.states[tf]
        k = int(s.index.searchsorted(t, side="right")) - 1
        return str(s.iloc[k]) if k >= 0 else "UNKNOWN"

    # --- trades -------------------------------------------------------------------------------------

    def simulate(self, e: int, side: int, stop: float, tp_dist: float) -> tuple[float, int] | None:
        if e + HOLD >= len(self.o):
            return None
        entry = self.o[e] + (self.sp[e] + SLIP if side > 0 else -SLIP)
        risk = (entry - stop) * side
        if risk <= 0:
            return None
        tp = entry + side * tp_dist
        for j in range(e, e + HOLD):
            adverse = self.lo[j] if side > 0 else self.h[j] + self.sp[j]
            favour = self.h[j] if side > 0 else self.lo[j] + self.sp[j]
            if (adverse - stop) * side <= 0:
                return ((stop - side * SLIP) - entry) * side / risk, j
            if (favour - tp) * side >= 0:
                return (tp - entry) * side / risk, j
        x = e + HOLD - 1
        exit_px = self.c[x] - (SLIP if side > 0 else -(self.sp[x] + SLIP))
        return (exit_px - entry) * side / risk, x


def nearest(pools: list[tuple[float, str]], x: float) -> tuple[tuple[float, str] | None, tuple[float, str] | None]:
    above = [p for p in pools if p[0] > x]
    below = [p for p in pools if p[0] < x]
    return (min(above, key=lambda p: p[0]) if above else None, max(below, key=lambda p: p[0]) if below else None)


def main() -> None:
    global START, END, WARM, OUT
    args = sys.argv[1:]  # optional: --start YYYY-MM-DD --end YYYY-MM-DD --out PREFIX (another window)
    if "--start" in args:
        START = pd.Timestamp(args[args.index("--start") + 1], tz="UTC")
        WARM = START - pd.Timedelta(days=102)
    if "--end" in args:
        END = pd.Timestamp(args[args.index("--end") + 1], tz="UTC")
    if "--out" in args:
        OUT = args[args.index("--out") + 1]
    gold.below_normal_priority()
    D = Data()
    cal = gold.releases()
    days = [d for d in pd.date_range(START, END - pd.Timedelta(days=1), freq="D") if d.weekday() < 5]
    rows = moment_rows(days, cal)
    feats, trades = [], []
    for rid, r in enumerate(rows):
        i = D.last_before(r.t)  # the last M1 bar closed by T
        if i < 60 or D.ot[i] < r.t - pd.Timedelta(minutes=5) or i + 1 >= len(D.o):
            continue  # no market at T
        e0 = i + 1  # the bar opening at (or first after) T
        u = D.usual_run(r.t, r.zone, r.clock)
        if not np.isfinite(u) or u <= 0:
            continue
        x = D.c[i]
        k5 = int(D.m5_close_t.searchsorted(r.t, side="right")) - 1
        h1, m15 = D.state("H1", r.t), D.state("M15", r.t)
        reads = {tf: D.read(tf, r.t) for tf in ("M15", "H1")}
        now = {tf: (str(rd.structure_now.value) if rd and rd.structure_now else "NONE") for tf, rd in reads.items()}
        # the flow: H1's swing structure now, else M15's (the map states leave ~70 % without a flow)
        sgn = {"UP": 1, "DOWN": -1}
        flow = sgn.get(now["H1"], 0) or sgn.get(now["M15"], 0)
        clear = sgn.get(now["H1"], 0) if sgn.get(now["H1"], 0) == sgn.get(now["M15"], 0) else 0
        pools = D.pools(r.t, i, reads)
        up, dn = nearest(pools, x)
        dist_up = (up[0] - x) / u if up else np.nan
        dist_dn = (x - dn[0]) / u if dn else np.nan
        at_up, at_dn = dist_up <= AT_POOL_U, dist_dn <= AT_POOL_U
        if at_up or at_dn:
            pool_dir = 1 if (at_up and (not at_dn or dist_up <= dist_dn)) else -1
            side = "noflow" if flow == 0 else ("ahead" if pool_dir == flow else "behind")
        else:
            side = "none"
        pre = slice(i - 59, i + 1)
        pre_hi, pre_lo = D.h[pre].max(), D.lo[pre].min()
        spread = float(np.median(D.sp[i - 59 : i + 1]))
        adr = D.regime(r.t)
        w = slice(e0, min(e0 + 60, len(D.o)))
        feats.append(
            dict(
                rid=rid,
                t=r.t,
                tags=",".join(sorted(r.tags)),
                kind="control" if r.tags == {"control"} else "moment",
                u=u,
                spread=spread,
                u_spreads=u / spread,
                adr20=adr,
                adr_spreads=adr / spread,
                bb_pct=D.bb_pct[k5],
                atr_pct=D.atr_pct[k5],
                squeeze=bool(D.bb_pct[k5] <= 20),
                pre_range_u=(pre_hi - pre_lo) / u,
                h1=h1,
                m15=m15,
                h1_now=now["H1"],
                m15_now=now["M15"],
                flow=flow,
                clear=clear,
                pool_side=side,
                dist_up_u=dist_up,
                dist_dn_u=dist_dn,
                pool_up=up[1] if up else "",
                pool_dn=dn[1] if dn else "",
                run_up60_u=(D.h[w].max() - D.o[e0]) / u,
                run_dn60_u=(D.o[e0] - D.lo[w].min()) / u,
            )
        )
        tp = TARGET_U * u
        pad = STOP_PAD_U * u
        last = min(e0 + ENTRY_MIN, len(D.o) - 1)
        # P1 break-and-hold: a close beyond the nearest pool, the next bar not back; enter the bar after
        for j in range(e0, last):
            sd = 1 if up and D.c[j] > up[0] else -1 if dn and D.c[j] < dn[0] else 0
            if sd == 0:
                continue
            lvl = up[0] if sd > 0 else dn[0]
            if (D.c[j + 1] - lvl) * sd > 0 and j + 2 < len(D.o):
                res = D.simulate(j + 2, sd, lvl - sd * pad, tp)
                if res:
                    trades.append(dict(rid=rid, pb="P1", side=sd, i=j + 2, te=D.ot[j + 2], stop=lvl - sd * pad, x=res[1], r=res[0], with_flow=sd * flow))
            break
        # P2 sweep-and-reclaim: beyond a pool, back inside within 5 bars; trade back the other way
        for j in range(e0, last):
            sd = -1 if up and D.h[j] > up[0] else 1 if dn and D.lo[j] < dn[0] else 0
            if sd == 0:
                continue
            lvl = up[0] if sd < 0 else dn[0]
            for k in range(j, min(j + RECLAIM, len(D.o) - 1)):
                if (D.c[k] - lvl) * sd > 0:
                    ext = D.h[j : k + 1].max() if sd < 0 else D.lo[j : k + 1].min()
                    res = D.simulate(k + 1, sd, ext - sd * pad, tp)
                    if res:
                        trades.append(dict(rid=rid, pb="P2", side=sd, i=k + 1, te=D.ot[k + 1], stop=ext - sd * pad, x=res[1], r=res[0], with_flow=sd * flow))
                    break
            break
        # P3 with the flow at the moment
        if flow != 0:
            stop = pre_lo - pad if flow > 0 else pre_hi + pad
            res = D.simulate(e0, flow, stop, tp)
            if res:
                trades.append(dict(rid=rid, pb="P3", side=flow, i=e0, te=D.ot[e0], stop=stop, x=res[1], r=res[0], with_flow=1))
        if rid % 500 == 0:
            print(rid, len(rows), r.t, flush=True)
    f = pd.DataFrame(feats)
    t = pd.DataFrame(trades).merge(f[["rid", "t"]], on="rid")
    f.to_parquet(f"{OUT}_features.parquet")
    t.to_parquet(f"{OUT}_trades.parquet")
    print(len(f), "rows", (f.kind == "moment").sum(), "moments;", len(t), "trades")


if __name__ == "__main__":
    main()
