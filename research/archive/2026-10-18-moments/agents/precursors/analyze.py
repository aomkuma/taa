"""Step 1 reads on DESIGN only (notes.md): which chart states come before a 10 U / 5 U run, which way, and the
larger timeframe -> the smaller timeframe's run.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/analyze.py [10|5]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from plib import HERE

X = int(sys.argv[1]) if len(sys.argv) > 1 else 10
P = f"x{X}"
DH = ["H1", "H2", "H3", "H4", "H5"]
TFS = ["M1", "M5", "M15", "M30", "H1", "H4"]
pd.set_option("display.width", 220)


def load() -> pd.DataFrame:
    D = pd.read_parquet(HERE / "decisions.parquet")
    D = D[D.half.isin(DH)].copy()
    D["run"] = D[f"{P}_next_up"] | D[f"{P}_next_dn"]
    D["first"] = D[f"{P}_first"]
    D["day"] = D.index.normalize()
    # the expected run chance from the same half-year, window and M15-ATR decile (volatility explains most of it)
    D["adec"] = D.groupby("half").atr15_u.transform(lambda s: pd.qcut(s.rank(method="first"), 10, labels=False))
    D["exp"] = D.groupby(["half", "win", "adec"]).run.transform("mean")
    return D


def lift_rows(D: pd.DataFrame, col: str, bins: pd.Series) -> list[dict]:
    rows = []
    for b, g in D.groupby(bins, observed=True):
        if len(g) < 100:
            continue
        r = dict(feature=col, bin=str(b), n=len(g), days=g.day.nunique(), share=len(g) / len(D),
                 run=g.run.mean(), lift=g.run.mean() / g.exp.mean())
        per = g.groupby("half").apply(lambda x: x.run.mean() / x.exp.mean() if len(x) >= 30 else np.nan,
                                      include_groups=False)
        r["halves"] = " ".join(f"{per.get(h, np.nan):.2f}" for h in DH)
        r["up_n"] = int((per >= 1.3).sum())
        r["dn_n"] = int((per <= 1 / 1.3).sum())
        f = g["first"].dropna()
        f = f[f != 0]
        r["up_first"] = (f > 0).mean() if len(f) else np.nan
        rows.append(r)
    return rows


def side_rows(D: pd.DataFrame, name: str, sign: pd.Series) -> dict | None:
    """A signed state: the share of `first` going the state's way, pooled over both mirrors (drift cancels)."""
    s = sign.reindex(D.index)
    g = D[(s != 0) & s.notna() & D["first"].notna() & (D["first"] != 0)]
    if len(g) < 100:
        return None
    w = (g["first"] * s.loc[g.index]) > 0
    per = w.groupby(g.half).mean()
    upw = w[s.loc[g.index] > 0].mean()
    dnw = w[s.loc[g.index] < 0].mean()
    return dict(state=name, n=len(g), days=g.day.nunique(), with_share=w.mean(), up_side=upw, dn_side=dnw,
                halves=" ".join(f"{per.get(h, np.nan):.3f}" for h in DH), n56=int((per >= 0.56).sum()),
                n44=int((per <= 0.44).sum()))


def main() -> None:
    D = load()
    print(f"=== X = {X} U, design {D.index.min().date()} .. {D.index.max().date()}: {len(D)} decision minutes, "
          f"{D.day.nunique()} days ===")
    print("\n-- 1. how often a run starts within the next 15 minutes, by window and half-year (share of minutes) --")
    t = D.pivot_table(index="win", columns="half", values="run", aggfunc="mean")
    t["all"] = D.groupby("win").run.mean()
    t["up% of runs"] = D[D.run].groupby("win")[f"{P}_next_up"].mean() * 100
    print(t.round(3).to_string())
    C = pd.read_parquet(HERE / f"runs_{X}.parquet")
    C["half"] = pd.cut(C.t, pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01",
                                            "2026-03-01"], utc=True), labels=DH, right=False)
    C = C[C.half.notna()]
    print("\n-- runs (all hours, design): per half: count, up %, median size U, median minutes to X --")
    print(C.groupby("half", observed=True).agg(n=("i", "size"), up=("side", lambda s: (s > 0).mean()),
                                                size=("size_u", "median"), mins=("mins_to_x", "median")).round(2).to_string())

    # ---------------------------------------------------------------- single-state lifts
    rows = []
    cat = []
    cont = []
    for tf in TFS:
        cat += [f"{tf}_tide", f"{tf}_struct", f"{tf}_leg", f"{tf}_phase", f"{tf}_brk3"]
        cont += [f"{tf}_atr_pct", f"{tf}_bbw_pct", f"{tf}_pos20", f"{tf}_ema_d", f"{tf}_mom3", f"{tf}_leg_atr"]
    cat += ["box_brk", "box_now", "sweep", "stair", "spike", "day_brk", "yday_brk", "asia_brk", "x72"]
    cont += ["tvr", "mom15", "mom60", "rng30", "pos72", "r50"]
    for c in cat:
        rows += lift_rows(D, c, D[c])
    for c in cont:
        q = pd.qcut(D[c].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
        q = q.where(D[c].notna())
        rows += lift_rows(D, c, q)
    L = pd.DataFrame(rows)
    L.to_csv(HERE / f"lift_{X}.csv", index=False)
    print("\n-- 2. states that come before runs MORE often (lift >= 1.3 in >= 4/5 half-years) --")
    k = L[L.up_n >= 4].sort_values("lift", ascending=False)
    print(k[["feature", "bin", "n", "days", "share", "run", "lift", "halves", "up_first"]].round(3).to_string(index=False))
    print("\n-- states that come before runs LESS often (lift <= 0.77 in >= 4/5) --")
    k = L[L.dn_n >= 4].sort_values("lift")
    print(k[["feature", "bin", "n", "days", "share", "run", "lift", "halves"]].round(3).to_string(index=False))

    # ---------------------------------------------------------------- the side
    S = []
    for tf in TFS:
        for f in ("tide", "leg", "brk3", "bar_dir"):
            S.append(side_rows(D, f"{tf}_{f}", D[f"{tf}_{f}"]))
        st = D[f"{tf}_struct"].where(D[f"{tf}_struct"].isin([1, -1]), 0)
        S.append(side_rows(D, f"{tf}_struct", st))
        S.append(side_rows(D, f"{tf}_ema_d>1 (stretched)", np.sign(D[f"{tf}_ema_d"]).where(D[f"{tf}_ema_d"].abs() > 1, 0)))
        S.append(side_rows(D, f"{tf}_mom3>1", np.sign(D[f"{tf}_mom3"]).where(D[f"{tf}_mom3"].abs() > 1, 0)))
    for f in ("box_brk", "sweep", "stair", "spike", "day_brk", "yday_brk", "asia_brk", "x72"):
        S.append(side_rows(D, f, D[f]))
    S.append(side_rows(D, "mom15>1", np.sign(D.mom15).where(D.mom15.abs() > 1, 0)))
    S.append(side_rows(D, "mom60>2", np.sign(D.mom60).where(D.mom60.abs() > 2, 0)))
    tsum = D[["M15_tide", "M30_tide", "H1_tide", "H4_tide"]].sum(axis=1)
    S.append(side_rows(D, "tide M15..H4 all the same", np.sign(tsum).where(tsum.abs() == 4, 0)))
    S = pd.DataFrame([s for s in S if s])
    S.to_csv(HERE / f"side_{X}.csv", index=False)
    print("\n-- 3. the side: share of +X/-X first going the state's way (both mirrors pooled; 56 % bar) --")
    print(S.sort_values("with_share", ascending=False).round(3).to_string(index=False))

    # ---------------------------------------------------------------- the larger timeframe -> the run below
    print("\n-- 4. the larger timeframe's state -> the M1 run in the next 15 minutes (relative to that TF's trend) --")
    for big, small in (("H4", "H1"), ("H1", "M15"), ("M15", "M5")):
        rows = []
        tr = D[f"{big}_struct"].where(D[f"{big}_struct"].isin([1, -1]))
        for (bs, sp), g in D[tr.notna()].groupby([D[f"{big}_struct"], D[f"{small}_leg"] * D[f"{big}_struct"]]):
            if len(g) < 300:
                continue
            ref = g[f"{big}_struct"]
            rr = g[g.run]
            withr = np.where(ref.loc[rr.index] > 0, rr[f"{P}_next_up"], rr[f"{P}_next_dn"])
            f = g["first"] * ref
            f = f[f.notna() & (f != 0)]
            mae = np.where(ref.loc[rr.index] > 0, rr[f"{P}_mae_up"], rr[f"{P}_mae_dn"])
            per = (f > 0).groupby(g.loc[f.index, "half"]).mean()
            rows.append(dict(big=f"{big} {'up' if bs > 0 else 'down'}",
                             small=f"{small} leg {'with' if sp > 0 else 'against'}", n=len(g), days=g.day.nunique(),
                             run=g.run.mean(), lift=g.run.mean() / g.exp.mean(), runs_with=np.mean(withr),
                             first_with=(f > 0).mean(), halves=" ".join(f"{per.get(h, np.nan):.2f}" for h in DH),
                             mae_with=np.nanmedian(mae)))
        print(pd.DataFrame(rows).round(3).to_string(index=False))
    # the nested chain: H4 structure, H1 leg, M15 leg, M5 leg relative to H4
    print("\n-- nested chain relative to the H4 structure (H1 / M15 / M5 legs: + with H4, - against) --")
    ref = D.H4_struct.where(D.H4_struct.isin([1, -1]))
    G = D[ref.notna()].copy()
    r = G.H4_struct
    G["chain"] = [f"{a:+d}{b:+d}{c:+d}" for a, b, c in zip((G.H1_leg * r).astype(int), (G.M15_leg * r).astype(int),
                                                           (G.M5_leg * r).astype(int))]
    rows = []
    for ch, g in G.groupby("chain"):
        f = (g["first"] * g.H4_struct)
        f = f[f.notna() & (f != 0)]
        per = (f > 0).groupby(g.loc[f.index, "half"]).mean()
        rr = g[g.run]
        withr = np.where(rr.H4_struct > 0, rr[f"{P}_next_up"], rr[f"{P}_next_dn"])
        rows.append(dict(chain_H1_M15_M5=ch, n=len(g), days=g.day.nunique(), run=g.run.mean(),
                         lift=g.run.mean() / g.exp.mean(), runs_with=np.mean(withr), first_with=(f > 0).mean(),
                         halves=" ".join(f"{per.get(h, np.nan):.2f}" for h in DH)))
    print(pd.DataFrame(rows).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
