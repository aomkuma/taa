"""Frame B lifts: per feature bin, how often a swing launches a run (R10 / R15) against all swings, and how often the
trade from it wins (win5 / win8), by design half-year.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/frame_b_lift.py [FILTER]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
HL = ["H1", "H2", "H3", "H4", "H5"]
SKIP = {"j", "side", "t", "u", "ext", "stop_px", "run10", "run15", "win5", "win8", "entry", "part", "half", "R5", "R8",
        "mR5", "mR8", "mwin5", "mwin8"}


def main() -> None:
    E = pd.read_parquet(HERE / "frame_b_events.parquet")
    D = E[(E.part == "design") & (E.stop_u >= 1) & (E.stop_u <= 10)].copy()
    if len(sys.argv) > 1:
        D = D.query(sys.argv[1])
    D["w5"] = (D.win5 > 0).astype(float)
    D["w8"] = (D.win8 > 0).astype(float)
    D["edge"] = D.R5 - D.mR5  # the side's R minus the mirror's R (same minute, same stop and target)
    base = {k: D.groupby("half", observed=True)[k].mean() for k in ("run10", "run15", "w5", "w8", "edge")}
    print(f"swings {len(D)}; base run10 {D.run10.mean():.3f} run15 {D.run15.mean():.3f} win5 {D.w5.mean():.3f} win8 {D.w8.mean():.3f}")
    print(f"R5 {D.R5.mean():+.3f} mirror {D.mR5.mean():+.3f} edge {D.edge.mean():+.3f}")
    print("by half: run10 " + " ".join(f"{v:.3f}" for v in base["run10"]) + " | win5 " + " ".join(f"{v:.3f}" for v in base["w5"]))
    rows = []
    for f in [c for c in D.columns if c not in SKIP and c not in ("w5", "w8", "edge")]:
        x = D[f].astype(float)
        vals = x.dropna().unique()
        if len(vals) <= 7:
            b = x
            cats = sorted(vals)
        else:
            q = np.unique(np.nanquantile(x, [0.2, 0.4, 0.6, 0.8]))
            b = pd.Series(np.digitize(x, q), index=x.index).where(x.notna())
            cats = list(range(len(q) + 1))
        for k in cats:
            sel = b == k
            if sel.sum() < 300:
                continue
            g = D[sel]
            rec = dict(feature=f, bin=k, lo=x[sel].min(), hi=x[sel].max(), n=int(sel.sum()),
                       run10=g.run10.mean(), run15=g.run15.mean(), w5=g.w5.mean(), w8=g.w8.mean())
            rec["lift10"] = rec["run10"] / D.run10.mean()
            rec["d_w5"] = rec["w5"] - D.w5.mean()
            rec["R5"], rec["mR5"], rec["edge"] = g.R5.mean(), g.mR5.mean(), g.edge.mean()
            l10, dw, ed = [], [], []
            for hf in HL:
                gh = g[g.half == hf]
                l10.append(gh.run10.mean() / base["run10"][hf] if len(gh) >= 60 else np.nan)
                dw.append(gh.w5.mean() - base["w5"][hf] if len(gh) >= 60 else np.nan)
                ed.append(gh.edge.mean() if len(gh) >= 60 else np.nan)
            rec |= {f"l10_{h}": v for h, v in zip(HL, l10, strict=True)}
            rec |= {f"dw5_{h}": v for h, v in zip(HL, dw, strict=True)}
            rec |= {f"ed_{h}": v for h, v in zip(HL, ed, strict=True)}
            rec["ed_pos"] = int(np.nansum(np.array(ed) > 0))
            rec["l10_same"] = int(np.nansum(np.sign(np.array(l10) - 1) == np.sign(rec["lift10"] - 1)))
            rec["dw5_same"] = int(np.nansum(np.sign(np.array(dw)) == np.sign(rec["d_w5"])))
            rows.append(rec)
    T = pd.DataFrame(rows)
    T.to_csv(HERE / "frame_b_lift.csv", index=False)
    pd.set_option("display.width", 250)
    T["a"] = (T.lift10 - 1).abs()
    cols = ["feature", "bin", "lo", "hi", "n", "run10", "lift10"] + [f"l10_{h}" for h in HL] + ["l10_same", "w5", "d_w5"]
    print("\n== launch lift (run10), stable >= 4 of 5 ==")
    print(T[T.l10_same >= 4].sort_values("a", ascending=False).head(40)[cols].round(3).to_string(index=False))
    T["b"] = T.d_w5.abs()
    cols = ["feature", "bin", "lo", "hi", "n", "run10", "lift10", "w5", "d_w5"] + [f"dw5_{h}" for h in HL] + ["dw5_same", "w8"]
    print("\n== trade win5 difference, stable >= 4 of 5 ==")
    print(T[T.dw5_same >= 4].sort_values("b", ascending=False).head(25)[cols].round(3).to_string(index=False))
    cols = ["feature", "bin", "lo", "hi", "n", "run10", "lift10", "w5", "R5", "mR5", "edge"] + [f"ed_{h}" for h in HL] + ["ed_pos"]
    print("\n== the side's edge over the mirror (same minute, stop, target), largest; >= 4 of 5 positive ==")
    print(T[T.ed_pos >= 4].sort_values("edge", ascending=False).head(30)[cols].round(3).to_string(index=False))
    print("\n== the most negative edges (<= 1 of 5 positive) ==")
    print(T[T.ed_pos <= 1].sort_values("edge").head(15)[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
