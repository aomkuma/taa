"""Pictures of the sets (design): for the sets seen on the most distinct days in each layer, up to 6 members (one per
day) with what followed - to check by eye that "80 % similar" looks alike, and to keep as the evidence pictures.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/gallery_sets.py [n_sets]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plib
import render
from plib import HERE

OUT = HERE / "png" / "sets"
NSETS = int(sys.argv[1]) if len(sys.argv) > 1 else 4
CLS_TH = {"ran_up": "RAN UP", "ran_dn": "RAN DOWN", "slow_up": "slow up", "slow_dn": "slow down",
          "fake_up": "FAKE up", "fake_dn": "FAKE down", "flat": "flat", "drift": "drift"}


def caption(r: pd.Series) -> str:
    th = r.S.tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %H:%M TH")
    k = "up" if r.cls.endswith("up") else "dn"
    size = r[f"r10_{k}_size"]
    extra = f" size {size:.0f} U, starts +{r[f'r10_{k}_lead']:.0f} min" if np.isfinite(size) else ""
    return (f"{th} [{r['name']}]  ->  {CLS_TH[r.cls]}{extra} | max up 30m {r.mfe_up30:.1f} U, max down 30m "
            f"{r.mfe_dn30:.1f} U")


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.load()
    S = pd.read_parquet(HERE / "snaps.parquet")
    html = ["<html><head><meta charset='utf-8'><title>Precursor sets</title></head>"
            "<body style='font-family:sans-serif'>"]
    for layer in ("setup", "trigger", "context"):
        sets = pd.read_parquet(HERE / f"sets_{layer}_80.parquet").sort_values("days", ascending=False)
        mem = pd.read_parquet(HERE / f"snap_sets_{layer}_80.parquet")
        mem = mem.merge(S, on=["S", "name"], how="left")
        mem["day"] = mem.S.dt.tz_convert("Asia/Bangkok").dt.normalize()
        for sid, st in sets.head(NSETS).iterrows():
            x = mem[mem.set == sid].groupby("day").head(1)
            x = x.sample(min(6, len(x)), random_state=1).sort_values("S")
            shares = ", ".join(f"{CLS_TH[c]} {st[c]:.0%}" for c in CLS_TH if st[c] > 0)
            html.append(f"<h2>{layer} set {sid}: {st.snaps} snaps on {st.days} days - {shares}</h2>")
            d = OUT / f"{layer}_{sid}"
            d.mkdir(parents=True, exist_ok=True)
            for k, (_, r) in enumerate(x.iterrows()):
                f = d / f"{k}.png"
                render.draw(m, r.S - pd.Timedelta(minutes=1), f, f"{layer} set {sid}: " + caption(r))
                html.append(f"<p><img src='{layer}_{sid}/{k}.png' width='1100'></p>")
            print(layer, sid, st.days, "days", flush=True)
    html.append("</body></html>")
    (OUT / "index.html").write_text("\n".join(html), encoding="utf-8")


if __name__ == "__main__":
    main()
