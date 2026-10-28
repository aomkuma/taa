"""Smart money's draw on liquidity (owner, 2026-10-17: "we still look opposite to the big players; change the
view"), tested against a random walk, not mined.

At each moment and control half hour (both six-month windows) where the previous broker day's high (PDH) and low
(PDL) are both still untaken today and the price lies between them: a driftless random walk hits PDH first with
p = (price - PDL) / (PDH - PDL). Measured: which one the rest of the broker day hits first. A draw shows as
actual - p away from zero, overall and given the H1/M15 swing-structure flow, the session and the side the day
has already run.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/draw_liquidity.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from select_fit import group  # noqa: E402


def main() -> None:
    gold.below_normal_priority()
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= pd.Timestamp("2025-09-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-16", tz="UTC"))]
    ot = m1.index
    h, lo, c = (m1[k].to_numpy(float) for k in ("high", "low", "close"))
    bday = pd.Index(ot.tz_convert("Europe/Athens").date)
    starts = pd.Series(np.arange(len(ot))).groupby(bday).agg(["min", "max"])
    days = list(starts.index)
    rows = []
    for name, prefix in (("earlier", "data/research/own_moments_prev"), ("latest", "data/research/own_moments")):
        f = pd.read_parquet(f"{prefix}_features.parquet")
        for r in f.itertuples():
            i = int(ot.searchsorted(r.t)) - 1  # the last closed bar
            if i < 0:
                continue
            d = bday[i]
            k = days.index(d) if d in starts.index else -1
            if k < 1:
                continue
            p0, p1 = starts.iloc[k - 1]
            s0, s1 = starts.iloc[k]
            pdh, pdl = h[p0 : p1 + 1].max(), lo[p0 : p1 + 1].min()
            day_hi, day_lo = h[s0 : i + 1].max(), lo[s0 : i + 1].min()
            x = c[i]
            if day_hi >= pdh or day_lo <= pdl or not (pdl < x < pdh):
                continue
            up = np.nonzero(h[i + 1 : s1 + 1] >= pdh)[0]
            dn = np.nonzero(lo[i + 1 : s1 + 1] <= pdl)[0]
            fu, fd = (up[0] if len(up) else 10**9), (dn[0] if len(dn) else 10**9)
            if fu == fd:
                hit = np.nan if fu == 10**9 else np.nan
            else:
                hit = float(fu < fd)
            day_pos = (x - day_lo) / (day_hi - day_lo) if day_hi > day_lo else 0.5
            rows.append(
                dict(
                    window=name,
                    t=r.t,
                    kind=r.kind,
                    session=group(r.tags) if r.kind == "moment" else "control",
                    flow=r.flow,
                    p=(x - pdl) / (pdh - pdl),
                    hit_h=hit,
                    any_hit=float(min(fu, fd) < 10**9),
                    width_u=(pdh - pdl) / r.u,
                    day_pos=day_pos,
                )
            )
    d = pd.DataFrame(rows)
    d = d.drop_duplicates(["window", "t"])
    print(f"rows {len(d)} (both PDH and PDL untaken, price between); one of them hit later that day: {d.any_hit.mean():.2f}")
    e = d.dropna(subset=["hit_h"])
    print(f"with a hit: {len(e)}")

    def line(name: str, g: pd.DataFrame) -> str:
        return (f"  {name:42} n {len(g):5}  random walk p {g.p.mean():.3f}  actual {g.hit_h.mean():.3f}"
                f"  draw up {g.hit_h.mean() - g.p.mean():+.3f} (se {g.hit_h.std() / np.sqrt(max(len(g), 1)):.3f})")

    for w, g in e.groupby("window"):
        print(f"\n== {w} six months")
        print(line("all", g))
        for col, labels in (
            ("flow", {1: "flow up (H1/M15 structure)", -1: "flow down", 0: "no flow"}),
            ("session", None),
        ):
            for key, gg in g.groupby(col):
                print(line(str(labels[key] if labels else key), gg))
        g = g.assign(pos=pd.cut(g.day_pos, [-0.01, 0.33, 0.67, 1.01], labels=["low third of the day", "middle", "high third"]))
        for key, gg in g.groupby("pos", observed=True):
            print(line(f"price in the day's {key}", gg))
        g = g.assign(pb=pd.cut(g.p, [0, 0.25, 0.5, 0.75, 1], labels=["p 0-0.25", "0.25-0.5", "0.5-0.75", "0.75-1"]))
        for key, gg in g.groupby("pb", observed=True):
            print(line(f"nearer side {key}", gg))
    d.to_parquet("data/research/own_draw_liquidity.parquet")


if __name__ == "__main__":
    main()
