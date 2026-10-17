"""Probe 2 (design data only): the New York 08:30-09:30 ET range breakout - a side-permutation test (the same
entries, the sides shuffled so the long share stays), and context splits that could mark trend days.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/probe2.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402
import probe  # noqa: E402


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    ev = pd.read_parquet(probe.EV)
    ev = ev[(ev.t < lab.DESIGN_END)].reset_index(drop=True)
    rel = lab.gold.releases()
    rel_days = set(rel[rel.time_et == "08:30"].date)
    ev["rel830"] = ev.t.dt.tz_convert(lab.NY).dt.strftime("%Y-%m-%d").isin(rel_days)
    rng = np.random.default_rng(11)
    for dl in (15, 120):
        x = ev[(ev.sess == "ny830") & (ev.f == 60) & np.where(ev.side > 0, ev.h1_up, ev.h1_dn) & (ev.delay <= dl)]
        x = x.reset_index(drop=True)
        r = probe.evaluate(B, x, x.side.to_numpy(), "opp", "trail1/1", 180)
        perm = []
        coin = []
        s = x.side.to_numpy()
        for _ in range(300):
            perm.append(probe.evaluate(B, x, rng.permutation(s), "opp", "trail1/1", 180).R.mean())
            coin.append(probe.evaluate(B, x, rng.choice([-1, 1], len(x)), "opp", "trail1/1", 180).R.mean())
        perm, coin = np.array(perm), np.array(coin)
        print(f"delay<={dl}: ours {r.R.mean():+.3f} (N {len(x)}, long share {(s > 0).mean():.2f}); permuted sides mean {perm.mean():+.3f}"
              f" sd {perm.std():.3f}, share >= ours {(perm >= r.R.mean()).mean():.3f}; coin mean {coin.mean():+.3f} sd {coin.std():.3f},"
              f" share >= ours {(coin >= r.R.mean()).mean():.3f}")
    # context splits on the wider family (no H1 filter, delay <= 120), to see what marks the good days
    x = ev[(ev.sess == "ny830") & (ev.f == 60)].reset_index(drop=True)
    r = probe.evaluate(B, x, x.side.to_numpy(), "opp", "trail1/1", 180)
    s = x.side.to_numpy()
    x["R"] = r.R
    x["withH1"] = np.where(s > 0, x.h1_up, x.h1_dn)
    x["againstH1"] = np.where(s > 0, x.h1_dn, x.h1_up)
    x["slope_adr"] = x.h1_slope * s / x.adr
    x["pre_s"] = x.pre * s
    x["rng_adr"] = x.rng / x.adr
    x["adr_rel"] = x.adr / x.groupby("sess").adr.transform(lambda a: a.rolling(100, min_periods=40).mean())
    x["dow"] = x.t.dt.dayofweek
    x["dl"] = pd.cut(x.delay, [-1, 5, 15, 30, 60, 120])
    hn = [h[0] for h in lab.HALVES]

    def show(col: str, bins=None) -> None:
        k = pd.qcut(x[col], 4, duplicates="drop") if bins == "q" else x[col]
        g = x.groupby(k, observed=True)
        t = pd.DataFrame({"N": g.size(), "R": g.R.mean(),
                          "halves+": g.apply(lambda y: (y.groupby("half").R.mean().reindex(hn) > 0).sum(), include_groups=False)})
        print(f"\n{col}:\n{t.round(3).to_string()}")

    for col in ("withH1", "againstH1", "rel830", "dow", "dl"):
        show(col)
    for col in ("slope_adr", "pre_s", "or_rel", "rng_adr", "adr_rel"):
        show(col, "q")


if __name__ == "__main__":
    main()
