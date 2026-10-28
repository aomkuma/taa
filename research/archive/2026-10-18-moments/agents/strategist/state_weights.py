"""CHECKLIST row 39, part 2 - the state weights per piece of PLAN-1, in more states than the D1 efficiency terciles.
Written before computing (2026-10-20 12:58 Thai; PROPOSALS.md "Row 39 - written before computing"):

The pieces, spread only (tsim.run, slippage 0, the rule's own cell):
- Asia B2: dev/p4_trades_W_WL.parquet variant W, news cost 0, window Asia (as precursors/combo.py);
- London ORB: dev/d1_trades.parquet core (L 15, k 2, X 60, status trade); P1 / P2 re-simulated on the ticks; O1 / O2
  are the developer's M1 trades as stored (his M1 costs: the spread column, no stop slippage) - the older-years check;
- NY straddle: news_follow.py's STRADDLE 30m at 08:30 NY (a buy stop at the ask + 2, a sell stop at the bid - 2, live
  60 s, the stop 8 USD, out 30 min after the minute), re-found here on the ticks with slippage 0.

The readings at the entry, from the bars complete before it (M1 store, never past 2026-04-17):
- (a) trend: the D1 20-day efficiency, sideways < 0.116 <= mixed <= 0.264 < trend (regime.py);
- (b) d1vol: the D1 ATR14 / its 100-day median, high >= 1.25 else normal (regime.py);
- (c) season: ADR20 (the 20-day mean D1 range) / the 120-day median D1 range, terciles from P1's weekdays (low / mid / high);
- (d) h4vol: the H4 ATR14's percentile among its last 120 values, low < 33 <= mid <= 67 < high;
- (e) d1struct: the D1 structure from 2-bar fractals (confirmed 2 bars later): up (a higher last high and a higher last
  low), down (both lower), mixed; (e') d1with: the trade's side with / against that structure (mixed = none).
The rule: per piece and reading, the weight 0.5 in a state where the piece's P1 mean R < 0 on >= 8 trades, else 1.
Reported: per piece x state x part (R, n), the weighted R a trade (sum R w / sum w) in P1 (in sample), P2, O1 / O2 (the
London ORB only); the three pieces together, alone and one position at a time (combo.stream). Also declared: per piece,
the reading whose P1 weights raise P1 the most (in sample), then judged on P2.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/state_weights.py > .../strategist/out_state_weights.txt
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import slib
import tsim

AG = slib.HERE.parent
sys.path.insert(0, str(AG / "precursors"))
import foundation as F  # noqa: E402
from indicators import at, bars  # noqa: E402
from phase import efficiency  # noqa: E402

MIN = tsim.NS_MIN
READINGS = ("trend", "d1vol", "season", "h4vol", "d1struct", "d1with")


def piece_specs() -> dict[str, pd.DataFrame]:
    P = pd.read_parquet(AG / "dev" / "p4_trades_W_WL.parquet")
    P = P[(P.variant == "W") & (P.news_cost == 0.0) & (P.window == "Asia") & P.part.isin(["P1", "P2"])]
    asia = pd.DataFrame(dict(t_in=P.t_entry.astype("int64").to_numpy(), side=P.side.to_numpy(), stop_px=P.stop.to_numpy(),
                             tgt_px=P.target.to_numpy(float), t_out=P.t_limit.astype("int64").to_numpy(),
                             t_struct=pd.to_numeric(P.t_struct, errors="coerce").astype(float).to_numpy(), part=P.part.to_numpy()))
    D = pd.read_parquet(AG / "dev" / "d1_trades.parquet")
    D = D[(D.L == 15) & (D.k == 2.0) & (D.X == 60) & (D.status == "trade")]
    Dt = D[D.part.isin(["P1", "P2"]) & (D.src == "ticks")]  # P1 / P2 are stored twice (ticks and M1): the ticks
    london = pd.DataFrame(dict(t_in=Dt.t_dec.astype("int64").to_numpy(), side=Dt.side.astype(int).to_numpy(), stop_px=Dt.stop.to_numpy(),
                               tgt_px=np.nan, tgt_r=2.0, t_out=Dt.t_dec.astype("int64").to_numpy() + 60 * MIN, part=Dt.part.to_numpy()))
    return {"Asia B2": asia, "London ORB": london, "NY straddle": straddle()}, D[D.part.isin(["O1", "O2"])]


def straddle() -> pd.DataFrame:
    rows = []
    for day in pd.bdate_range("2025-10-20", "2026-04-17", tz="UTC"):
        x = slib.ticks(day)
        if x is None or len(x) < 1000:
            continue
        t = x.t.dt.as_unit("ns").astype("int64").to_numpy()
        bid, ask = x.bid.to_numpy(float), x.ask.to_numpy(float)
        t0 = pd.Timestamp(f"{day:%Y-%m-%d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value
        if t0 < t[0] + 600 * 10**9 or t0 + 1800 * 10**9 > t[-1]:
            continue
        i0 = np.searchsorted(t, t0, side="left") - 1
        up, dn = ask[i0] + 2, bid[i0] - 2
        k, k_end = np.searchsorted(t, t0, side="left"), np.searchsorted(t, t0 + 60 * 10**9, side="left")
        for j in range(k, k_end):
            s = 1 if ask[j] >= up else (-1 if bid[j] <= dn else 0)
            if s:
                rows.append(dict(t_in=int(t[j]), side=s, stop_d=8.0, tgt_px=np.nan, t_out=t0 + 30 * MIN,
                                 part=slib.part_of(pd.DatetimeIndex([pd.Timestamp(t0, tz="UTC")]))[0]))
                break
    return pd.DataFrame(rows)


def fractal_structure(h: np.ndarray, lo: np.ndarray) -> np.ndarray:
    """Per D1 bar k: +1 up / -1 down / 0 mixed from the 2-bar fractals confirmed by bar k (a pivot at i needs bars i+1,
    i+2, so it is known at bar i + 2)."""
    n = len(h)
    out = np.zeros(n)
    ph, pl = [], []
    for k in range(n):
        i = k - 2
        if i >= 2:
            if h[i] > max(h[i - 2], h[i - 1]) and h[i] >= max(h[i + 1], h[i + 2]):
                ph.append(h[i])
            if lo[i] < min(lo[i - 2], lo[i - 1]) and lo[i] <= min(lo[i + 1], lo[i + 2]):
                pl.append(lo[i])
        if len(ph) >= 2 and len(pl) >= 2:
            if ph[-1] > ph[-2] and pl[-1] > pl[-2]:
                out[k] = 1
            elif ph[-1] < ph[-2] and pl[-1] < pl[-2]:
                out[k] = -1
    return out


def states(m: pd.DataFrame, t_ns: np.ndarray, side: np.ndarray, season_edges: tuple[float, float] | None) -> pd.DataFrame:
    d1 = bars(m, "1D")
    h, lo, c = (d1[k].to_numpy(float) for k in ("high", "low", "close"))
    er = efficiency(c, 20)
    atr = F.atr(h, lo, c, 14)
    vrel = atr / pd.Series(atr).rolling(100, min_periods=50).median().to_numpy()
    rng = h - lo
    season = pd.Series(rng).rolling(20).mean().to_numpy() / pd.Series(rng).rolling(120, min_periods=60).median().to_numpy()
    st = fractal_structure(h, lo)
    k = np.maximum(at(pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8, t_ns), 0)
    h4 = bars(m, "4h")
    a4 = F.atr(h4.high.to_numpy(float), h4.low.to_numpy(float), h4.close.to_numpy(float), 14)
    pct = pd.Series(a4).rolling(120, min_periods=60).apply(lambda w: 100.0 * np.mean(w <= w[-1]), raw=True).to_numpy()
    k4 = np.maximum(at(pd.DatetimeIndex(h4["avail"]).as_unit("ns").asi8, t_ns), 0)
    e, v, s, p4, sk = er[k], vrel[k], season[k], pct[k4], st[k]
    out = pd.DataFrame(dict(er=e, vrel=v, season_v=s, h4pct=p4, struct=sk))
    out["trend"] = np.where(e < 0.116, "sideways", np.where(e > 0.264, "trend", "mixed"))
    out["d1vol"] = np.where(v >= 1.25, "high", "normal")
    if season_edges is not None:
        out["season"] = np.where(s < season_edges[0], "low", np.where(s > season_edges[1], "high", "mid"))
    out["h4vol"] = np.where(p4 < 33, "low", np.where(p4 > 67, "high", "mid"))
    out["d1struct"] = np.where(sk > 0, "up", np.where(sk < 0, "down", "mixed"))
    out["d1with"] = np.where(sk == 0, "none", np.where(sk * side > 0, "with", "against"))
    return out


def season_edges_p1(m: pd.DataFrame) -> tuple[float, float]:
    d1 = bars(m, "1D")
    h, lo = d1.high.to_numpy(float), d1.low.to_numpy(float)
    rng = h - lo
    season = pd.Series(rng).rolling(20).mean().to_numpy() / pd.Series(rng).rolling(120, min_periods=60).median().to_numpy()
    av = pd.DatetimeIndex(d1["avail"])
    sel = (av >= slib.P1[0]) & (av < slib.P1[1])
    q = np.nanquantile(season[sel], [1 / 3, 2 / 3])
    return float(q[0]), float(q[1])


def wR(g: pd.DataFrame, w: np.ndarray) -> float:
    return float(np.sum(g.R.to_numpy() * w) / np.sum(w)) if len(g) else np.nan


def main() -> None:
    tsim.idle()
    pd.set_option("display.width", 220)
    m = slib.m1("2022-06-01")
    edges = season_edges_p1(m)
    print(f"season terciles from P1's weekdays: {edges[0]:.3f} / {edges[1]:.3f}")
    specs, old = piece_specs()
    T = []
    for name, S in specs.items():
        X = tsim.run(S, sides=("same",), stops=(1.0,), targets=("orig",))
        X["piece"] = name
        T.append(X)
    O = pd.DataFrame(dict(piece="London ORB", entry_t=old.t_dec.astype("int64").to_numpy(), side=old.side.astype(int).to_numpy(),
                          R=old.R.to_numpy(), pnl=old.pnl.to_numpy(), part=old.part.to_numpy(),
                          exit_t=old.exit_t.astype("int64").to_numpy()))
    T = pd.concat(T + [O], ignore_index=True)
    T = pd.concat([T.reset_index(drop=True), states(m, T.entry_t.to_numpy(), T.side.to_numpy(), edges)], axis=1)
    T.to_parquet(slib.HERE / "state_weights_trades.parquet")
    print("\nthe pieces, spread only (rule cell):")
    for (pc, p), g in T.groupby(["piece", "part"]):
        print(f"  {pc:12s} {p}: n {len(g):3d} R {g.R.mean():+.3f} win {(g.pnl > 0).mean():.2f} USD {g.pnl.sum():+.1f}")
    parts = ["P1", "P2", "O1", "O2"]
    W_all = {}
    for rd in READINGS:
        print(f"\n== {rd}: R (n) per piece x state x part")
        tab = T.groupby(["piece", rd, "part"]).R.agg(["mean", "size"]).unstack("part")
        tab = tab.reindex(columns=pd.MultiIndex.from_product([["mean", "size"], [p for p in parts if p in T.part.unique()]]))
        print(tab.round(3).to_string())
        P1 = T[T.part == "P1"]
        W = {(pc, s): 0.5 for (pc, s), g in P1.groupby(["piece", rd]) if len(g) >= 8 and g.R.mean() < 0}
        W_all[rd] = W
        print(f"   the weights from P1: {W}")
        for pc, G in T.groupby("piece"):
            line = []
            for p in parts:
                g = G[G.part == p]
                if not len(g):
                    continue
                w = np.array([W.get((pc, s), 1.0) for s in g[rd]])
                line.append(f"{p} {g.R.mean():+.3f} -> {wR(g, w):+.3f}")
            print(f"   {pc:12s} unweighted -> weighted: " + " | ".join(line))
    print("\n== the three pieces together (P1 / P2), each reading's P1 weights; alone and one position at a time")
    from combo import stream  # noqa: PLC0415  (precursors/combo.py: one position at a time)

    base = T[T.part.isin(["P1", "P2"])].copy()
    base["t_in"] = pd.to_datetime(base.entry_t, utc=True)
    base["t_out"] = pd.to_datetime(base.exit_t, utc=True)
    one = {p: stream(base[base.part == p]) for p in ("P1", "P2")}
    for rd in ("none",) + READINGS:
        W = W_all.get(rd, {})
        line = []
        for p in ("P1", "P2"):
            for lab, g in (("alone", base[base.part == p]), ("1-at-a-time", one[p])):
                w = np.array([W.get((pc, s), 1.0) for pc, s in zip(g.piece, g[rd] if rd != "none" else g.piece, strict=True)])
                line.append(f"{p} {lab} {wR(g, w):+.3f} (n {len(g)}, USD {np.sum(g.pnl * w):+.0f})")
        print(f"  {rd:9s} " + " | ".join(line))
    mech = {("Asia B2", "trend"): 0.5, ("London ORB", "trend"): 0.5, ("NY straddle", "sideways"): 0.5, ("NY straddle", "mixed"): 0.5}
    line = []
    for p in ("P1", "P2"):
        g = one[p]
        w = np.array([mech.get((pc, s), 1.0) for pc, s in zip(g.piece, g.trend, strict=True)])
        line.append(f"{p} {wR(g, w):+.3f}")
    print(f"  PLAN-1 mechanism weights (trend reading), one at a time, spread only: " + " | ".join(line))
    print("\n== per piece, the reading whose P1 weights raise P1 the most (in sample), judged on P2")
    for pc, G in T[T.part.isin(["P1", "P2"])].groupby("piece"):
        gains = {}
        for rd in READINGS:
            g = G[G.part == "P1"]
            w = np.array([W_all[rd].get((pc, s), 1.0) for s in g[rd]])
            gains[rd] = wR(g, w) - g.R.mean()
        best = max(gains, key=gains.get)
        g2 = G[G.part == "P2"]
        w2 = np.array([W_all[best].get((pc, s), 1.0) for s in g2[best]])
        print(f"  {pc:12s} best on P1: {best} (+{gains[best]:.3f} in P1); P2 {g2.R.mean():+.3f} -> {wR(g2, w2):+.3f}")


if __name__ == "__main__":
    main()
