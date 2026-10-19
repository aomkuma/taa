"""The second, separate check of P3's numbers (the owner's "right reading, wrong metric" rule). It imports none of
p2_trades / p3_trades / patterns / sweep_detector: it reads p3_trades_all.parquet, p3_metrics_all.csv, p_catches.parquet,
the raw M1 and tick files, and uses only verify_p2 (the P2 checker) and the precursors' foundation.atr and
fingerprint.zigzag. It

1. recomputes every metric per setting x part x news cost and asserts it agrees with p3_metrics_all.csv;
2. re-derives 20 trades a setting (news cost 0) from the raw ticks - the fill, every tick against the stop level as it
   stood (the break-even tick and the trailing steps included), the exit's tick and price, the USD and R - and, from
   its own bars (M1 from the file, M5 by its own grouping, foundation.atr, fingerprint.zigzag at 2 x ATR): the
   structure-exit time, the invalidation-exit time (the invalidation price from the catch) and every trailing value;
3. checks one position at a time in every setting x cost.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/verify_p3.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "precursors"))
sys.path.insert(0, str(HERE))  # first: the precursors hold the measurer's own verify_p2.py - this must be mine
import verify_p2 as V2  # noqa: E402

assert Path(V2.__file__).resolve().parent == HERE, "imported the wrong verify_p2"

ROOT = HERE.parents[3]
NS_MIN = 60 * 10**9
EXITS = ("stop", "trail", "target", "structure", "invalid", "time", "break")


def metrics(rows: list[dict], part: str) -> dict:
    m = V2.metrics(rows, part)
    for e in EXITS:
        m[f"x_{e}"] = sum(r["exit"] == e for r in rows)
    return m


class Bars:
    """Its own M1 / M5 bars from the M1 file (2025-09-01 .. before the exam), ATR(14) and the ZigZag (2 x ATR); for each
    bar the price of the last trough / peak confirmed by it."""

    def __init__(self) -> None:
        import foundation as F  # noqa: PLC0415
        import pyarrow.parquet as pq  # noqa: PLC0415
        from fingerprint import zigzag  # noqa: PLC0415

        lo_t, hi_t = pd.Timestamp("2025-09-01", tz="UTC"), V2.EXAM
        x = pq.read_table(ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet", columns=["open_time", "open", "high", "low", "close"],
                          filters=[("open_time", ">=", lo_t), ("open_time", "<", hi_t)]).to_pandas()
        x = x.drop_duplicates("open_time", keep="last").sort_values("open_time")
        self.tf = {}
        for minutes in (1, 5):
            if minutes == 1:
                b = x.rename(columns={"open_time": "t"})
            else:
                g = x.groupby(x.open_time.dt.floor("5min"), sort=True)
                b = pd.DataFrame(dict(t=g.open_time.first().index, open=g.open.first().values, high=g.high.max().values,
                                      low=g.low.min().values, close=g.close.last().values))
            t_open = pd.DatetimeIndex(b.t).as_unit("ns").asi8
            h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
            atr = F.atr(h, lo, c, 14)
            pb, pp, pk, pc = zigzag(h, lo, atr, 2.0)
            lt, lp = np.full(len(c), np.nan), np.full(len(c), np.nan)
            lt[pc[pk == -1]], lp[pc[pk == 1]] = pp[pk == -1], pp[pk == 1]
            self.tf[f"M{minutes}"] = dict(t_open=t_open, avail=t_open + minutes * NS_MIN, c=c,
                                          lt=pd.Series(lt).ffill().to_numpy(), lp=pd.Series(lp).ffill().to_numpy())

    def first_close(self, tfn: str, t_entry: int, t_limit: int, past) -> int | None:
        """The close of the first bar opening at / after t_entry and closing by t_limit for which past(bar index) holds."""
        b = self.tf[tfn]
        i0 = int(np.searchsorted(b["t_open"], t_entry, side="left"))
        i1 = int(np.searchsorted(b["avail"], t_limit, side="right"))
        for i in range(i0, i1):
            if past(i):
                return int(b["avail"][i])
        return None


def rederive3(tr: dict, tk: pd.DataFrame, bars: Bars | None, inv: float | None) -> list[str]:
    """The problems found re-deriving one P3 trade (an empty list = it agrees)."""
    bad = []
    side, t, bid, ask = tr["side"], tk.t.to_numpy(), tk.bid.to_numpy(), tk.ask.to_numpy()
    f = int(np.searchsorted(t, tr["t_entry"], side="left"))
    if f >= len(t) or t[f] != tr["entry_t"]:
        return ["the fill tick"]
    if t[f] - tr["t_entry"] > 60 * 10**9:
        bad.append("a stale fill (no tick within 60 s of the decision)")
    if abs((ask[f] + V2.SLIP if side > 0 else bid[f] - V2.SLIP) - tr["entry"]) > 1e-9:
        bad.append("the fill price")
    x = int(np.searchsorted(t, tr["exit_t"], side="left"))
    if x >= len(t) or t[x] != tr["exit_t"]:
        return [*bad, "the exit tick"]
    mkt = bid if side > 0 else ask
    risk = side * (tr["entry"] - tr["stop"])
    lv = np.full(len(t), side * tr["stop"])
    trail = tr.get("trail_t") is not None and not (isinstance(tr.get("trail_t"), float))
    if trail:
        fav = side * (mkt - tr["entry"])
        up = [i for i in range(f + 1, len(t)) if fav[i] >= risk and t[i] <= t[x]]
        be = int(t[up[0]]) if up else None
        if be != (None if pd.isna(tr.get("t_be")) else int(tr["t_be"])):
            bad.append("the break-even tick")
        if be is not None:
            st = np.asarray(tr["trail_t"], np.int64)
            sv = np.asarray(tr["trail_v"], float)
            keep = st > be
            st, sv = st[keep], np.where(np.isnan(sv[keep]), -np.inf, side * sv[keep])
            run = np.maximum.accumulate(sv) if len(sv) else sv
            for i in range(up[0], len(t)):
                k = int(np.searchsorted(st, t[i], side="right")) - 1
                lv[i] = max(side * tr["entry"], run[k] if k >= 0 else -np.inf)
    crossed = [i for i in range(f + 1, x) if side * mkt[i] <= lv[i]]
    if crossed:
        bad.append("a tick past the stop level before the exit")
    why, px = tr["exit"], tr["exit_px"]
    if why in ("stop", "trail"):
        if not side * mkt[x] <= lv[x] or abs(px - mkt[x]) > 1e-9 or ((lv[x] != side * tr["stop"]) != (why == "trail")):
            bad.append("the stop / trail tick, price or name")
    elif why == "target":
        hit = [i for i in range(f + 1, x + 1) if side * (mkt[i] - tr["target"]) >= 0]
        if not hit or hit[0] != x or abs(px - tr["target"]) > 1e-9:
            bad.append("the target")
    else:
        if abs(px - mkt[x]) > 1e-9:
            bad.append("the market exit price")
        if why in ("structure", "invalid") and not (t[x] >= tr["t_struct"] and t[x - 1] < tr["t_struct"]):
            bad.append("the close exit's tick")
        if why == "time" and not (t[x] >= tr["t_limit"] and t[x - 1] < tr["t_limit"]):
            bad.append("the time tick")
        if why == "break" and not (x == len(t) - 1 or t[x + 1] - t[x] > V2.GAP):
            bad.append("the break tick")
    usd = side * (px - tr["entry"])
    if abs(usd - tr["pnl"]) > 1e-9 or abs(usd / risk - tr["R"]) > 1e-9:
        bad.append("the USD / R")
    if bars is not None:  # the bar-based readings, from its own bars
        b = bars.tf[tr["tf"]]
        ts = tr.get("t_struct")
        ts = None if ts is None or pd.isna(ts) else int(ts)
        if tr["variant"] in ("Xa", "Xab"):
            if inv is None or abs(inv - tr["invalid"]) > 1e-9:
                bad.append("the invalidation price")
            mine = bars.first_close(tr["tf"], tr["t_entry"], tr["t_limit"], lambda i: side * (b["c"][i] - tr["invalid"]) < 0)
            if mine != ts:
                bad.append("the invalidation exit time")
        elif tr["variant"] in ("B2", "L", "ST", "LEAD") or tr.get("exit_mode") == "structure":
            ref = b["lt"] if side > 0 else b["lp"]
            mine = bars.first_close(tr["tf"], tr["t_entry"], tr["t_limit"], lambda i: side * (b["c"][i] - ref[i]) < 0)
            if mine != ts:
                bad.append("the structure exit time")
        if trail:
            i0 = int(np.searchsorted(b["t_open"], tr["t_entry"], side="left"))
            i1 = int(np.searchsorted(b["avail"], tr["t_limit"], side="right"))
            ref = b["lt"] - 0.2 * tr["atr"] if side > 0 else b["lp"] + 0.2 * tr["atr"]
            mine_t, mine_v = b["avail"][i0:i1], ref[i0:i1]
            got_t, got_v = np.asarray(tr["trail_t"], np.int64), np.asarray(tr["trail_v"], float)
            if not (np.array_equal(mine_t, got_t) and np.allclose(mine_v, got_v, equal_nan=True, rtol=0, atol=1e-9)):
                bad.append("the trailing values")
    return bad


def main() -> None:
    A = pd.read_parquet(HERE / "p3_trades_all.parquet")
    M = pd.read_csv(HERE / "p3_metrics_all.csv")
    C = pd.read_parquet(HERE / "p_catches.parquet")
    keys = ["n", "per_day", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd"] + [f"x_{e}" for e in EXITS]
    agree = total = 0
    for m in M.itertuples(index=False):
        rows = A[(A.variant == m.variant) & (A.part == m.part) & (A.news_cost == m.news_cost)].to_dict("records")
        mine = metrics(rows, m.part)
        for k in keys:
            total += 1
            a, b = mine[k], getattr(m, k)
            ok = (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1.0, abs(a))
            agree += ok
            if not ok:
                print(f"  DIFFERENT {m.variant} {m.part} +{m.news_cost} {k}: {a} vs {b}")
    print(f"1. the metrics recomputed: {agree} of {total} values agree ({len(M)} rows x {len(keys)})", flush=True)
    bars = Bars()
    rng = random.Random(20261019)
    days: dict = {}
    good = n = 0
    for v in A.variant.unique():
        rows = A[(A.variant == v) & (A.news_cost == 0.0)].to_dict("records")
        for tr in rng.sample(rows, 20):
            d = pd.Timestamp(tr["entry_t"], tz="UTC").normalize()
            for dd in (d, d + pd.Timedelta(days=1)):
                if dd not in days:
                    days[dd] = V2.raw_ticks(dd)
            tk = pd.concat([days[d], days[d + pd.Timedelta(days=1)]], ignore_index=True)
            c = C[(C.tf == tr["tf"]) & (C.t_dec == tr["t_dec"]) & (C.family == tr["family"]) & (C.side == tr["side"])].iloc[0]
            inv = float(c.box_p[0] if tr["side"] > 0 else c.box_p[1]) if tr["family"] == "base" else float(c.pts_p[-1])
            bad = rederive3(tr, tk, bars, inv)
            n += 1
            good += not bad
            if bad:
                print(f"  {v} {pd.Timestamp(tr['entry_t'], tz='UTC')} {tr['exit']}: {bad}")
    print(f"2. trades re-derived from the raw ticks and its own bars: {good} of {n} agree (20 a setting)", flush=True)
    over = {(v, c): V2.one_at_a_time(G.to_dict("records")) for (v, c), G in A.groupby(["variant", "news_cost"])}
    print(f"3. one position at a time: entries before the previous exit {sum(over.values())} in {len(over)} streams "
          f"({len(A)} trades)")
    if agree != total or good != n or sum(over.values()):
        raise SystemExit("VERIFICATION FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
