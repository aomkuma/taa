"""Pictures for learning (notes.md): for each group, decision minutes that were followed by a 10 U run within 15
minutes AND minutes in the same group that were not - one per day, random, design only unless asked.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/gallery.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import plib
import render
from plib import HERE

OUT = HERE / "png"
COLS = ["i", "half", "win", "u", "x10_next_up", "x10_next_dn", "x10_lead_up", "x10_lead_dn", "x10_size_up",
        "x10_size_dn", "x10_mae_up", "x10_mae_dn", "x10_first", "day_brk", "spike", "box_brk", "H4_struct", "H1_struct",
        "M15_struct"]
WIN_TH = {"A07": "07:00 Tokyo", "A08": "08:00 China", "A09": "09-12 Asia", "FR13": "Frankfurt 08:00",
          "LO14": "London 08-12", "NY19": "NY 08:00", "NY1930": "NY 08:30 data", "NY2030": "NY 09:30 open",
          "NY21": "NY 10:00", "NY22": "NY 11-14"}
STRUCT = {1: "up", -1: "down", 2: "contracting", 3: "broadening", 0: "-"}


def groups(D: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "g1_ny0930": D.win == "NY2030",
        "g2_new_day_low": D.day_brk == -1,
        "g3_spike_down": D.spike == -1,
        "g4_box_break_up": D.box_brk == 1,
        "g5_asia_0900_12": D.win == "A09",
    }


def caption(r: pd.Series, t: pd.Timestamp) -> str:
    th = t.tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %H:%M TH")
    ctx = f"H4 {STRUCT.get(int(r.H4_struct), '-')}, H1 {STRUCT.get(int(r.H1_struct), '-')}, M15 {STRUCT.get(int(r.M15_struct), '-')}"
    if r.x10_next_up or r.x10_next_dn:
        sd = "UP" if r.x10_next_up and (not r.x10_next_dn or r.x10_lead_up <= r.x10_lead_dn) else "DOWN"
        k = "up" if sd == "UP" else "dn"
        res = (f"RAN {sd} {r[f'x10_size_{k}']:.0f} U, start +{r[f'x10_lead_{k}']:.0f} min, "
               f"against first {r[f'x10_mae_{k}']:.1f} U")
    else:
        res = "no 10 U run within 15 min"
    f = {1.0: "+10 first", -1.0: "-10 first", 0.0: "neither in 60 min"}.get(r.x10_first, "?")
    return f"{th}  [{WIN_TH.get(r.win, r.win)}]  {ctx}  |  {res}  |  {f}"


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.load()
    D = pd.read_parquet(HERE / "decisions.parquet", columns=COLS)
    D = D[D.half.isin(["H1", "H2", "H3", "H4", "H5"])]
    D["ran"] = D.x10_next_up | D.x10_next_dn
    D["day"] = D.index.normalize()
    rng = np.random.default_rng(11)
    html = ["<html><head><meta charset='utf-8'><title>Precursors</title></head><body style='font-family:sans-serif'>"]
    for name, mask in groups(D).items():
        g = D[mask]
        html.append(f"<h2>{name}: {len(g)} minutes, ran {g.ran.mean():.0%}</h2>")
        for ran in (True, False):
            x = g[g.ran == ran]
            x = x.groupby("day").sample(1, random_state=int(rng.integers(1e9)))
            x = x.sample(min(6, len(x)), random_state=int(rng.integers(1e9))).sort_index()
            html.append(f"<h3>{'ran' if ran else 'did not run'}</h3>")
            for k, (t, r) in enumerate(x.iterrows()):
                (OUT / name).mkdir(parents=True, exist_ok=True)
                f = OUT / name / f"{'ran' if ran else 'not'}_{k}.png"
                render.draw(m, t, f, caption(r, t))
                html.append(f"<p><img src='{name}/{f.name}' width='1100'></p>")
        print(name, "done", flush=True)
    html.append("</body></html>")
    (OUT / "index.html").write_text("\n".join(html), encoding="utf-8")


if __name__ == "__main__":
    main()
