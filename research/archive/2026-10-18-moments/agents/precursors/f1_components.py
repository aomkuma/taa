"""F1 CONF-72's components alone (owner, 2026-10-19: "focus on the basic correctness of each component before
assembling them"; notes.md "F1 CONF-72's components alone", written before computing). Every minute of F1's
windows (UTC 00-02, 07-12, 12-17) x both sides before the exam, from the research's candidate tables - the very
definitions the bot runs (engine = research 35 / 35). Per component: does price go 8 U the side's way before 8 U the
other way within 60 minutes of the decision close? No effect = 50 %.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/f1_components.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "journal"))  # jlib, rules (the portfolio library needs them)
sys.path.insert(0, str(HERE))  # first: this folder's plib, not the portfolio agent's
import plib  # noqa: E402
from level_power import first_passage  # noqa: E402

SPLIT = pd.Timestamp("2025-01-01", tz="UTC")
TP_U, HZ, GAP = 8.0, 60, 15


def spaced(t: np.ndarray, gap_min: int) -> np.ndarray:
    """Keep a row only when at least gap_min minutes passed since the last kept row (t sorted, int64 ns)."""
    keep = np.zeros(len(t), bool)
    last = None
    for i, x in enumerate(t):
        if last is None or x - last >= gap_min * 60_000_000_000:
            keep[i] = True
            last = x
    return keep


def main() -> None:
    plib.gold.below_normal_priority()
    P, D1 = portfolio_load("wdesign")
    _, D2 = portfolio_load("wtest")
    D = pd.concat([D1, D2[D2.t < plib.EXAM_START]]).reset_index(drop=True)
    p = D.e.to_numpy() - 1  # the decision bar
    up = np.unique(p)
    fp_of = {}
    for j in up:
        x0 = P.c[j]
        d = TP_U * x0 / 4100.0
        fp_of[int(j)] = first_passage(P.h, P.lo, int(j), x0 + d, x0 - d, HZ)
    fp = np.array([fp_of[int(j)] for j in p])
    side = D.side.to_numpy()
    ok = fp != 0
    D["went"] = np.where(ok, (fp == side).astype(float), np.nan)
    pa = D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim
    ind = (D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2
    c4 = (D.front72 - D.c_dec) * D.side < 0.5 * TP_U * D.unit
    c5 = D.atr_ratio < 2
    comps = {
        "tide (H1)": D.tide,
        "at a level": D.at_level,
        "price action": pa,
        "2 of 3 M5 indicators": ind,
        "C4 72-h extreme near / behind": c4,
        "C5 not a fast tape": c5,
        "tide + level": D.tide & D.at_level,
        "tide + level + price action": D.tide & D.at_level & pa,
        "B0 (tide + level + PA + indicators)": D.tide & D.at_level & pa & ind,
        "CONF-72 (B0 + C4 + C5)": D.tide & D.at_level & pa & ind & c4 & c5,
    }
    out = []
    tns = pd.DatetimeIndex(D.t).as_unit("ns").asi8
    for name, mask in comps.items():
        for s in (1, -1):
            sel = np.nonzero(mask.to_numpy() & (side == s))[0]
            sel = sel[np.argsort(tns[sel], kind="stable")]
            sel = sel[spaced(tns[sel], GAP)]  # one row per 15 minutes per side: less overlap
            for part, pm in (("2023-11..2024-12", tns[sel] < SPLIT.value), ("2025-01..2026-04-17", tns[sel] >= SPLIT.value)):
                v = D.went.to_numpy()[sel[pm]]
                v = v[np.isfinite(v)]
                out.append(dict(component=name, side=s, part=part, n=len(v), went=v.sum(), its_way=v.mean() if len(v) else np.nan))
    R = pd.DataFrame(out).groupby(["component", "part"], sort=False).agg(n=("n", "sum"), went=("went", "sum"))
    R["its_way"] = R.went / R.n
    R["se"] = np.sqrt(R.its_way * (1 - R.its_way) / R.n)
    R["edge_in_se"] = (R.its_way - 0.5) / R.se
    pd.set_option("display.width", 200)
    print("8 U first, the side's way vs the other (60 minutes, from the decision close); no effect 50 %; both sides pooled")
    print(R.drop(columns="went").round(3).to_string())


def portfolio_load(part: str):
    """The portfolio agent's loader (its plib.py, loaded by path: this folder has a plib.py too)."""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("portfolio_plib", HERE.parents[0] / "portfolio" / "plib.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load(part)


if __name__ == "__main__":
    main()
