"""Probe 4 (design data only): the step-by-step table for the New York 08:30-09:30 ET range breakout and its
robustness (release days, range size vs ADR, H1 slope strength, the pre-session move, longs vs shorts, years).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/probe4.py
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
    ev = ev[(ev.t < lab.DESIGN_END) & (ev.sess == "ny830") & (ev.f == 60)].reset_index(drop=True)
    rel = lab.gold.releases()
    rel_days = set(rel[rel.time_et == "08:30"].date)
    ev["rel830"] = ev.t.dt.tz_convert(lab.NY).dt.strftime("%Y-%m-%d").isin(rel_days)
    s = ev.side.to_numpy()
    ev["withH1"] = np.where(s > 0, ev.h1_up, ev.h1_dn)
    ev["slope_adr"] = ev.h1_slope * s / ev.adr
    ev["pre_s"] = ev.pre * s
    ev["rng_adr"] = ev.rng / ev.adr
    ev["year"] = ev.t.dt.year
    print("step table (stop at the range's far side, trail 1R from +1R, 180 min):")
    steps = [
        ("0 every first close beyond the 08:30-09:30 range (to 11:30)", np.ones(len(ev), bool), "tp99"),
        ("0b the same, trail 1R from +1R", np.ones(len(ev), bool), "trail1/1"),
        ("1 + the H1 trend agrees", ev.withH1.to_numpy(), "trail1/1"),
        ("2 + the breakout by 10:00 ET (delay <= 30)", (ev.withH1 & (ev.delay <= 30)).to_numpy(), "trail1/1"),
        ("3 + the breakout by 09:45 ET (delay <= 15)", (ev.withH1 & (ev.delay <= 15)).to_numpy(), "trail1/1"),
    ]
    for name, m, ex in steps:
        x = ev[m].reset_index(drop=True)
        probe.summary(probe.evaluate(B, x, x.side.to_numpy(), "opp", ex, 180), name)
    base = ev[ev.withH1 & (ev.delay <= 15)].reset_index(drop=True)
    r = probe.evaluate(B, base, base.side.to_numpy(), "opp", "trail1/1", 180)
    base["R"], base["usd"] = r.R, r.usd
    print("\nsplits of step 3:")
    for col, bins in (("rel830", None), ("year", None), ("slope_adr", 3), ("pre_s", 3), ("rng_adr", 3), ("or_rel", 3),
                      ("delay", [-1, 0, 5, 10, 15])):
        k = base[col] if bins is None else (pd.qcut(base[col], bins) if isinstance(bins, int) else pd.cut(base[col], bins))
        g = base.groupby(k, observed=True)
        print(f"  {col}: " + "; ".join(f"{i}: N {len(v)} R {v.R.mean():+.3f}" for i, v in g))
    print("\nexit timing of step 3: exits", r.exit.value_counts().to_dict(), " median minutes", r.mins.median(),
          " risk USD median", round(r.risk.median(), 2), " risk/ADR median", round((base.rng / base.adr).median(), 3))
    print("R distribution:", np.percentile(r.R, [5, 25, 50, 75, 95]).round(2), " sd", r.R.std().round(3))


if __name__ == "__main__":
    main()
