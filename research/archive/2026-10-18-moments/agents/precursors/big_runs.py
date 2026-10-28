"""Bigger runs (notes.md, written before it is computed; owner, 2026-10-19: "10 USD is very little - it runs that in 15
minutes"). X up before X down (and the mirror) for X = 20, 30, 50 U within a day and 50 U within three days, read in
the aligned phase (entry_tables.aligned), the aligned phase after an M5 pullback, the rest of the running phase and
all moments: the D1 way first minus against, by moments and by first moments, L1 and L2.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/big_runs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from entry_tables import RUN_ER, aligned_frame  # noqa: E402
from phase_tables import by_days  # noqa: E402

RUNS = {"20U_1d": (20, 1440), "30U_1d": (30, 1440), "50U_1d": (50, 1440), "50U_3d": (50, 4320)}


def outcomes(X: pd.DataFrame) -> pd.DataFrame:
    """The up-first / down-first flags of every run size for the moments of X (cached in big_runs_outcomes.parquet)."""
    f = HERE / "big_runs_outcomes.parquet"
    if f.exists():
        O = pd.read_parquet(f)
        if len(O) == len(X) and (O.t.to_numpy() == X.t.to_numpy()).all():
            return O
    import jlib  # noqa: PLC0415
    from runpat_check import REF, passages  # noqa: PLC0415

    m = jlib.m1_frame("XAUUSD")
    o, h, lo = m.open.to_numpy(float), m.high.to_numpy(float), m.low.to_numpy(float)
    ot = m.index.as_unit("ns").asi8
    j0 = np.searchsorted(ot, pd.DatetimeIndex(X.t).as_unit("ns").asi8)  # the first M1 bar opening at / after the moment
    O = pd.DataFrame({"t": X.t.to_numpy()})
    for name, (xu, hz) in RUNS.items():
        u, d = passages(o, h, lo, np.minimum(j0, len(o) - 1), xu * o[np.minimum(j0, len(o) - 1)] / REF, horizon=hz, chunk=3000)
        O[f"up_{name}"], O[f"dn_{name}"] = u & (j0 < len(o)), d & (j0 < len(o))
    O.to_parquet(f)
    return O


def main() -> None:
    X = aligned_frame()
    O = outcomes(X)
    X = pd.concat([X, O.drop(columns="t")], axis=1)
    X = X[X.half != "exam"].reset_index(drop=True)
    way = X.D1_way20.to_numpy()
    al = X.aligned.to_numpy()
    pull_v = X.M5_ema50.to_numpy() * way
    cut = np.nanquantile(pull_v[al & (X.half == "L1").to_numpy()], 0.4)
    groups = {"aligned + M5 pullback": al & (pull_v <= cut), "aligned": al,
              "running, not aligned": (X.D1_er20.to_numpy() >= RUN_ER) & ~al & (way != 0), "all moments": way != 0}
    print(f"the pullback: price under the M5 EMA 50 turned to the D1 way <= {cut:.3f} ATR (L1's 40th percentile inside the phase)")
    pd.set_option("display.width", 250)
    rows = []
    for name in RUNS:
        y = (np.where(way > 0, X[f"up_{name}"], X[f"dn_{name}"]).astype(float) - np.where(way > 0, X[f"dn_{name}"], X[f"up_{name}"]).astype(float))
        first = np.where(way > 0, X[f"up_{name}"], X[f"dn_{name}"])
        for g, mask in groups.items():
            rec = dict(run=name, group=g)
            for h in ("L1", "L2"):
                k = mask & (X.half == h).to_numpy()
                t = by_days(X[k], np.zeros(k.sum()), y[k])
                res = (X[f"up_{name}"] | X[f"dn_{name}"]).to_numpy()[k]
                rec |= {f"n_{h}": int(k.sum()), f"days_{h}": int(t.days.iloc[0]), f"tilt_{h}": t["mean"].iloc[0], f"first_{h}": t.day_mean.iloc[0],
                        f"win_{h}": first[k][res].mean() if res.any() else np.nan, f"resolved_{h}": res.mean()}
            rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_csv(HERE / "big_runs.csv", index=False)
    print("the D1 way first minus against (tilt: moments; first: each day's first moment); win = the D1 way's share of the "
          "moments where one side came first; resolved = the share where one did:")
    print(R[["run", "group", "n_L1", "days_L1", "tilt_L1", "first_L1", "win_L1", "resolved_L1", "n_L2", "days_L2", "tilt_L2", "first_L2",
             "win_L2", "resolved_L2"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
