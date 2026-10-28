"""Read the "ended vs continued" study (design only): per feature bin, the share continued among the decided
(continued / (continued + ended)) against the random-walk expectation from where the decision close sits between the
run's start and its extreme (p_geo = (close - start) / (extreme - start)), A7's trade R and the mirror's, and the
stability by half-year (the bin minus the half-year's population, same sign in how many of the five).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/study_read.py [R15|A25]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402

HL = ["H1", "H2", "H3", "H4", "H5"]
CATS = {"session", "wave", "new3h", "div_rsi5", "div_macd5", "div_rsi15", "div_macd15", "usd_confirm", "rel_in_run",
        "h1_tide", "m15_tide"}
SKIP = {"d", "e", "t", "side", "start", "ext", "run_t", "t_ext", "i_s", "xj", "k0", "pl", "lb", "size", "dur", "atr15",
        "u", "part", "half", "label", "R", "mR", "sl", "exit", "kind", "pnl", "pgeo", "cont", "dec", "adr_usd"}


def load(tag: str) -> pd.DataFrame:
    z = pd.read_parquet(HERE / f"study_{tag}_design.parquet")
    P = rules.jlib.Instr("XAUUSD") if "P" not in globals() else globals()["P"]
    globals()["P"] = P
    cd = P.c[z.d.to_numpy()]
    z["pgeo"] = (cd - z.start) * z.side / ((z.ext - z.start) * z.side)
    z["dec"] = z.label != "neither"
    z["cont"] = (z.label == "continued").astype(float)
    z["wave"] = z.wave.clip(upper=4)
    # the random-walk expectation calibrated on the design pool: the continued share among the decided in the same
    # p_geo ventile (the plain p_geo is biased where the decision close sits near or beyond the extreme)
    d = z[z.dec]
    q = np.unique(np.nanquantile(d.pgeo, np.linspace(0, 1, 21)[1:-1]))
    cal = d.groupby(np.digitize(d.pgeo, q)).cont.mean()
    z["pgeo"] = cal.reindex(np.digitize(z.pgeo, q)).to_numpy()
    return z


def table(z: pd.DataFrame) -> pd.DataFrame:
    base = {}
    for h in HL:
        g = z[z.half == h]
        d = g[g.dec]
        base[h] = (d.cont.mean() - d.pgeo.mean(), g.R.mean())
    rows = []
    for f in [c for c in z.columns if c not in SKIP]:
        x = z[f].astype(float)
        if f in CATS or x.dropna().nunique() <= 6:
            b = x
            cats = sorted(x.dropna().unique())
        else:
            q = np.unique(np.nanquantile(x, [0.2, 0.4, 0.6, 0.8]))
            b = pd.Series(np.digitize(x, q), index=x.index).where(x.notna())
            cats = list(range(len(q) + 1))
        for k in cats:
            sel = b == k
            if sel.sum() < 60:
                continue
            g = z[sel]
            d = g[g.dec]
            ex, xs, rs = [], [], []
            for h in HL:
                gh = g[g.half == h]
                dh = gh[gh.dec]
                if len(dh) >= 15:
                    ex.append(dh.cont.mean() - dh.pgeo.mean() - base[h][0])
                if gh.R.notna().sum() >= 15:
                    rs.append(gh.R.mean() - base[h][1])
            ex, rs = np.array(ex), np.array(rs)
            rows.append(dict(feature=f, bin=k, lo=x[sel].min(), hi=x[sel].max(), n=int(sel.sum()),
                             cont=d.cont.mean(), pgeo=d.pgeo.mean(), excess=d.cont.mean() - d.pgeo.mean(),
                             ended=(g.label == "ended").mean(), R=g.R.mean(), mR=g.mR.mean(), nR=int(g.R.notna().sum()),
                             ex_pos=f"{int((ex > 0).sum())}/{len(ex)}", R_pos=f"{int((rs > 0).sum())}/{len(rs)}",
                             ex_min=ex.min() if len(ex) else np.nan, R_min=rs.min() if len(rs) else np.nan))
    return pd.DataFrame(rows)


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "R15"
    z = load(tag)
    d = z[z.dec]
    print(f"== {tag} design: {len(z)} signals; decided {len(d)}: continued {d.cont.mean():.3f} vs random-walk p_geo"
          f" {d.pgeo.mean():.3f} (excess {d.cont.mean() - d.pgeo.mean():+.3f}); trade R {z.R.mean():+.3f} mirror {z.mR.mean():+.3f}")
    for h in HL:
        g = z[z.half == h]
        dd = g[g.dec]
        print(f"   {h}: n {len(g)}, continued {dd.cont.mean():.3f} p_geo {dd.pgeo.mean():.3f} excess"
              f" {dd.cont.mean() - dd.pgeo.mean():+.3f}; R {g.R.mean():+.3f} ({g.R.notna().sum()}) mirror {g.mR.mean():+.3f}")
    T = table(z)
    T.to_csv(HERE / f"study_{tag}_bins.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 400)
    cols = ["feature", "bin", "lo", "hi", "n", "cont", "pgeo", "excess", "ended", "ex_pos", "R", "mR", "nR", "R_pos"]
    print("\n== every bin ==")
    print(T[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
