"""H6 (docs/OWN_SETUP.md): the dollar leads gold. At every moment of both six-month windows, the dollar's first k
minutes (six USD majors, normalized) against gold's own first k minutes, and gold's next 30 / 60 minutes.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/h6_dollar.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from select_fit import group  # noqa: E402

PAIRS = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCHF": 1, "USDCAD": 1}
LO, HI = pd.Timestamp("2025-09-01", tz="UTC"), pd.Timestamp("2026-10-15", tz="UTC")


def closes(path: str) -> tuple[pd.Series, pd.Series]:
    d = pd.read_parquet(path, columns=["open_time", "open", "close"])
    d.index = pd.DatetimeIndex(pd.to_datetime(d.open_time, utc=True))
    d = d[(d.index >= LO) & (d.index < HI)].sort_index()
    return d["open"], d["close"]


def scale(c: pd.Series) -> pd.Series:
    """The median absolute 1-minute log return of the previous five days, at each minute."""
    r = np.log(c).diff().abs()
    return r.rolling("5D").median().shift(1)


def main() -> None:
    gold.below_normal_priority()
    fx = {}
    for p, sgn in PAIRS.items():
        o, c = closes(f"data/history/FBS-Demo/{p}/M1.parquet")
        fx[p] = (o, c, scale(c), sgn)
    go, gc = closes(str(gold.NEW / "M1.parquet"))
    gs = scale(gc)
    rows = []
    for name, prefix in (("earlier", "data/research/own_moments_prev"), ("latest", "data/research/own_moments")):
        f = pd.read_parquet(f"{prefix}_features.parquet")
        f = f[f.kind == "moment"]
        for r in f.itertuples():
            t = r.t
            if t not in go.index:
                continue
            for k in (1, 2, 3):
                tk = t + pd.Timedelta(minutes=k - 1)
                if tk not in gc.index:
                    continue
                zs = []
                for _p, (o, c, s, sgn) in fx.items():
                    if t in o.index and tk in c.index and np.isfinite(s.get(t, np.nan)) and s[t] > 0:
                        zs.append(sgn * np.log(c[tk] / o[t]) / (s[t] * np.sqrt(k)))
                if len(zs) < 4:
                    continue
                g_ret = np.log(gc[tk] / go[t]) / (gs[t] * np.sqrt(k)) if gs.get(t, 0) > 0 else np.nan
                rec = dict(window=name, t=t, session=group(r.tags), tags=r.tags, k=k, usd=np.mean(zs), gold_z=g_ret)
                for hz in (30, 60):
                    th = tk + pd.Timedelta(minutes=hz)
                    j = gc.index.searchsorted(th, side="right") - 1
                    rec[f"next{hz}_u"] = (gc.iloc[j] - gc[tk]) / r.u if j >= 0 else np.nan
                rows.append(rec)
    d = pd.DataFrame(rows).dropna(subset=["gold_z", "next30_u", "next60_u"])
    d["usd_dir"] = -np.sign(d.usd)  # gold's direction implied by the dollar
    d["gold_dir"] = np.sign(d.gold_z)
    pd.set_option("display.width", 220)

    def stats(g: pd.DataFrame, by: str, hz: int) -> str:
        x = g[by] * g[f"next{hz}_u"]
        return f"{len(g):4} hit {(x > 0).mean():.2f} mean {x.mean():+.3f}U"

    print("Gold's next 30 / 60 minutes signed by a predictor, in U (hit = share the right way)")
    for k in (1, 2, 3):
        for w in ("earlier", "latest"):
            g = d[(d.k == k) & (d.window == w)]
            strong = g[g.usd.abs() >= g.usd.abs().median()]
            disagree = strong[strong.usd_dir != strong.gold_dir]
            print(f"\n k={k} {w}: rows {len(g)}")
            for hz in (30, 60):
                print(f"   +{hz}m  dollar-implied (all) {stats(g, 'usd_dir', hz)} | gold's own first move {stats(g, 'gold_dir', hz)}"
                      f" | strong dollar {stats(strong, 'usd_dir', hz)} | strong, gold not yet following {stats(disagree, 'usd_dir', hz)}")
    print("\nBy session, k=2, strong dollar move, +30m (earlier | latest):")
    g = d[d.k == 2]
    for s, gg in g.groupby("session"):
        parts = []
        for w in ("earlier", "latest"):
            x = gg[gg.window == w]
            x = x[x.usd.abs() >= g[g.window == w].usd.abs().median()]
            parts.append(stats(x, "usd_dir", 30))
        print(f"   {s:7} {parts[0]} | {parts[1]}")
    print("\nCorrelation of the first k minutes, dollar vs gold (k=2):",
          {w: round(float(np.corrcoef(x.usd, x.gold_z)[0, 1]), 2) for w, x in g.groupby("window")})
    d.to_parquet("data/research/own_h6_dollar.parquet")


if __name__ == "__main__":
    main()
