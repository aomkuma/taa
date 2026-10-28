"""Task D's tables from d1_trades.parquet and d2_trades.parquet: per part, pooled P1 + P2, the neighbours, the readings,
week by week (Thai weeks from Monday 00:00 Thai).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/d_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import d1_orb as D1  # noqa: E402

METRICS: list[dict] = []  # every printed cell, for the second computation (d_metrics.csv)


def line(G: pd.DataFrame, part: str | None, label: str = "") -> str:
    if not len(G):
        return "n 0"
    s = D1.stats(G, part)
    METRICS.append(dict(label=label, part=part, **{k: s[k] for k in ("n", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd")}))
    ex = G.exit.value_counts().to_dict()
    return (f"n {s['n']:3d} ({s['per_day']:.2f}/wd)  win {s['win']:.2f}  R {s['R']:+.3f} ({s['R_lo']:+.3f}..{s['R_hi']:+.3f})  "
            f"USD {s['usd']:+8.2f}  DD {s['dd']:7.2f}  worst {s['worst']:+7.2f}  streak {s['streak']} ({s['streak_usd']:+.2f})  {ex}")


def pooled(G: pd.DataFrame) -> str:
    r = G.R.to_numpy(float)
    if len(r) < 2:
        return "n < 2"
    half = 1.96 * r.std(ddof=1) / np.sqrt(len(r))
    return f"pooled P1 + P2: n {len(r)}  R {r.mean():+.3f} ({r.mean() - half:+.3f}..{r.mean() + half:+.3f})  USD {G.pnl.sum():+.2f}"


def weekly(G: pd.DataFrame) -> pd.DataFrame:
    th = pd.DatetimeIndex(pd.to_datetime(G.entry_t, utc=True)).tz_convert("Asia/Bangkok")
    wk = (th.normalize() - pd.to_timedelta(th.dayofweek, unit="D")).tz_localize(None)
    g = G.assign(week=wk.date).groupby("week", sort=True)
    W = pd.DataFrame({"trades": g.size(), "win": g.pnl.agg(lambda x: (x > 0).mean()).round(2), "R_trade": g.R.mean().round(3),
                      "R": g.R.sum().round(2), "usd": g.pnl.sum().round(2), "worst": g.pnl.min().round(2)})
    W.insert(W.columns.get_loc("worst"), "usd_total", W.usd.cumsum().round(2))
    return W.reset_index()


def d1(A: pd.DataFrame) -> None:
    print("=== D1 - the opening-range break at 13:00 Thai (06:00 UTC)")
    core = A[(A.L == 15) & (A.k == 2.0) & (A.X == 60)]
    for src, parts in (("ticks", ("P1", "P2")), ("m1", ("O1", "O2", "P1", "P2"))):
        C = core[core.src == src]
        print(f"\n-- the days (core, {src}): " + "; ".join(
            f"{p} " + ", ".join(f"{k} {v}" for k, v in C[C.part == p].status.value_counts().items()) for p in parts))
    T = core[core.traded.fillna(False).astype(bool)].copy()
    T["L_ok"] = T.level_ahead.isna()
    T["S_ok"] = T.adr20 >= D1.ADR_Y
    for name, sel in (("D1", T.L_ok | True), ("D1L", T.L_ok), ("D1 + S", T.S_ok), ("D1L + S", T.L_ok & T.S_ok)):
        print(f"\n-- {name}")
        X = T[sel]
        for src, parts in (("ticks", ("P1", "P2")), ("m1", ("O1", "O2", "P1", "P2"))):
            for p in parts:
                print(f"  {src:5s} {p}: {line(X[(X.src == src) & (X.part == p)], p, f'D1|{name}|{src}')}")
        print("  " + pooled(X[(X.src == "ticks") & X.part.isin(["P1", "P2"])]))
    print("\n-- the neighbours (18 cells; R per part, n in brackets; ticks for P1 / P2, M1 for O1 / O2)")
    G = A[A.traded.fillna(False).astype(bool)]
    pos = {p: 0 for p in ("O1", "O2", "P1", "P2")}
    for (L, k, X), H in G.groupby(["L", "k", "X"]):
        cells = []
        for p in ("O1", "O2", "P1", "P2"):
            src = "ticks" if p in ("P1", "P2") else "m1"
            x = H[(H.part == p) & (H.src == src)]
            pos[p] += bool(len(x) and x.R.mean() > 0)
            line(x, p, f"D1grid|{L}|{k}|{X}|{src}")
            cells.append(f"{p} {x.R.mean():+.3f} ({len(x)})")
        mark = " <- core" if (L, k, X) == D1.CORE else ""
        print(f"  L {L:2d} k {k:.1f} X {X:3d}: " + " | ".join(cells) + mark)
    print("  cells > 0: " + ", ".join(f"{p} {v} of 18" for p, v in pos.items()))
    print("\n-- the core on the ticks, week by week (Thai weeks):")
    print(weekly(T[T.src == "ticks"].sort_values("entry_t")).to_string(index=False))


def d2(B: pd.DataFrame) -> None:
    print("\n\n=== D2 - the data-minute straddle (S2's shape at every weekday 08:30 / 10:00 NY)")
    for hold in (15, 30):
        C = B[(B.trig == 2.0) & (B.stop_u == 8.0) & (B.hold == hold)]
        print(f"\n-- trigger 2 U, stop 8 U, held {hold} minutes")
        for extra in (0.0, 0.5, 1.0, 2.0):
            X = C[C.extra == extra]
            print(f"  +{extra:.1f} USD:")
            for p in ("P1", "P2"):
                print(f"    {p}: {line(X[X.part == p], p, f'D2|2.0|8.0|{hold}|{extra}')}")
            print("    " + pooled(X))
        X = C[C.extra == 0.5]
        print("  readings at +0.5 USD (R, n):")
        for p in ("P1", "P2"):
            Y = X[X.part == p]
            parts = [f"{ny} {Y[Y.ny == ny].R.mean():+.3f} ({(Y.ny == ny).sum()})" for ny in ("08:30", "10:00")]
            rel = Y.release != ""
            parts += [f"a release {Y[rel].R.mean():+.3f} ({rel.sum()})", f"none {Y[~rel].R.mean():+.3f} ({(~rel).sum()})"]
            parts += [f"buys {Y[Y.side > 0].R.mean():+.3f} ({(Y.side > 0).sum()})", f"sells {Y[Y.side < 0].R.mean():+.3f} ({(Y.side < 0).sum()})"]
            print(f"    {p}: " + "; ".join(parts))
    print("\n-- the neighbours at +0.5 USD (R per part, n in brackets)")
    pos = {"P1": 0, "P2": 0}
    for (tr, st, hold), H in B[B.extra == 0.5].groupby(["trig", "stop_u", "hold"]):
        cells = []
        for p in ("P1", "P2"):
            x = H[H.part == p]
            pos[p] += bool(len(x) and x.R.mean() > 0)
            line(x, p, f"D2grid|{tr}|{st}|{hold}|0.5")
            cells.append(f"{p} {x.R.mean():+.3f} ({len(x)})")
        mark = " <- core" if (tr, st, hold) in D2_CORE else ""
        print(f"  trig {tr:.1f} U stop {st:4.1f} U hold {hold:2d}: " + " | ".join(cells) + mark)
    print("  cells > 0: " + ", ".join(f"{p} {v} of 18" for p, v in pos.items()))
    X = B[(B.trig == 2.0) & (B.stop_u == 8.0) & (B.hold == 30) & (B.extra == 0.5)]
    print("\n-- held 30 minutes at +0.5 USD, week by week (Thai weeks):")
    print(weekly(X.sort_values("entry_t")).to_string(index=False))


D2_CORE = [(2.0, 8.0, 15), (2.0, 8.0, 30)]


def main() -> None:
    pd.set_option("display.width", 200)
    d1(pd.read_parquet(HERE / "d1_trades.parquet"))
    d2(pd.read_parquet(HERE / "d2_trades.parquet"))
    pd.DataFrame(METRICS).to_csv(HERE / "d_metrics.csv", index=False)


if __name__ == "__main__":
    main()
