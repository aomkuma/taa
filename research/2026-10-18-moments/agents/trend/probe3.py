"""Probe 3 (design data only): prior-range breakouts per session, with and without the H1 trend, stop at the
range's far side or a fraction of the ADR, trailing or fixed exits.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/probe3.py
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
    ev = pd.read_parquet("research/2026-10-18-moments/agents/trend/prior_events.parquet")
    ev = ev[ev.t < lab.DESIGN_END].reset_index(drop=True)
    for sess in ev.sess.unique():
        for filt in ("all", "withH1", "withH1&pre", "withH1&dl30"):
            x = ev[ev.sess == sess]
            w = np.where(x.side > 0, x.h1_up, x.h1_dn)
            if filt == "withH1":
                x = x[w]
            elif filt == "withH1&pre":
                x = x[w & (x.pre * x.side > 0)]
            elif filt == "withH1&dl30":
                x = x[w & (x.delay <= 30)]
            x = x.reset_index(drop=True)
            for stop in ("opp", "mid", "adr10", "adr15"):
                for ex in ("trail1/1", "tp2", "tp99"):
                    r = x.assign(risk=0)
                    if stop in ("opp", "mid"):
                        # a range wider than 40 % of the ADR makes the stop too far; skip those days
                        r = x[(x.rng / x.adr) < 0.4].reset_index(drop=True)
                    probe.summary(probe.evaluate(B, r, r.side.to_numpy(), stop, ex, 180), f"{sess} {filt} {stop} {ex}")


if __name__ == "__main__":
    main()
