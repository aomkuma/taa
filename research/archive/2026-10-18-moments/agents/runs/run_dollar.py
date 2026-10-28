"""Did the dollar (six USD majors) and US500 move with the run while it ran (start bar open -> target bar close)?
Adds usd_run (+ = the dollar moved the way that fits the gold run: down for a gold up-run) and spx_run (US500 the
run's way) to the catalogue (catalogue_ext.parquet); then RUN-A3 / A4 design trades by those bins against their
mirror.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/run_dollar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import gold  # noqa: E402
from features import PAIRS  # noqa: E402

HL = ["H1", "H2", "H3", "H4", "H5"]


def series(sym: str) -> tuple[pd.Series, pd.Series]:
    x = pd.read_parquet(ROOT / f"data/history/FBS-Demo/{sym}/M1.parquet", columns=["open_time", "open", "close"])
    x.index = pd.DatetimeIndex(pd.to_datetime(x.open_time, utc=True))
    x = x[~x.index.duplicated(keep="last")].sort_index()
    lc = np.log(x.close.astype(float))
    sc = lc.diff().abs().rolling(1440).mean().shift(1)
    return np.log(x.open.astype(float)), lc, sc


def zmove(sym: str, t0: pd.DatetimeIndex, t1: pd.DatetimeIndex, mins: np.ndarray) -> np.ndarray:
    lo_, lc, sc = series(sym)

    def at(x: pd.Series, t: pd.DatetimeIndex) -> np.ndarray:
        p = x.index.searchsorted(t, side="right") - 1
        ok = (p >= 0) & ((t - x.index[np.maximum(p, 0)]) <= pd.Timedelta(minutes=3))
        return np.where(ok, x.to_numpy()[np.maximum(p, 0)], np.nan)

    a, b, s = at(lo_, t0), at(lc, t1), at(sc, t0)
    return (b - a) / (s * np.sqrt(np.maximum(mins, 1)))


def main() -> None:
    gold.below_normal_priority()
    C = pd.read_parquet(HERE / "catalogue.parquet")
    t0, t1 = pd.DatetimeIndex(C.t), pd.DatetimeIndex(C.t_tgt)
    mins = C.mins_to_R.to_numpy()
    z = np.nanmean(np.vstack([sg * zmove(p, t0, t1, mins) for p, sg in PAIRS.items()]), axis=0)
    C["usd_run"] = -z * C.side.to_numpy()  # + = the dollar against the gold run's way (fits)
    C["spx_run"] = zmove("US500", t0, t1, mins) * C.side.to_numpy()
    C["gold_run_z"] = np.nan
    C.to_parquet(HERE / "catalogue_ext.parquet")
    for R, g in C.groupby("R"):
        d = g[g.part == "design"]
        print(f"R{R}: usd_run median {d.usd_run.median():+.2f}, share > 0 {100 * (d.usd_run > 0).mean():.0f} %;"
              f" spx_run share > 0 {100 * (d.spx_run > 0).mean():.0f} %")
    for name in ("A3", "A4"):
        p = HERE / f"causes_{name}.parquet"
        if not p.exists():
            continue
        T = pd.read_parquet(p)
        cat = C[C.R == 15].set_index("t")
        T["run_t"] = T.why.str.extract(r"run (\d\d:\d\d)")[0]
        # find the run by the time of its start on the trade's day (the run starts before the trade)
        rt = []
        for r in T.itertuples():
            day = r.t.normalize()
            hh, mm = map(int, r.run_t.split(":"))
            cand = day + pd.Timedelta(hours=hh, minutes=mm)
            if cand > r.t:
                cand -= pd.Timedelta(days=1)
            rt.append(cand)
        T["run_start"] = rt
        T = T.join(cat[["usd_run", "spx_run", "size_u", "mins_to_R"]], on="run_start")
        print(f"\n{name}: matched {T.usd_run.notna().mean():.2f}")
        for f in ("usd_run", "spx_run", "size_u", "mins_to_R"):
            q = np.nanquantile(T[f], [0.2, 0.4, 0.6, 0.8])
            b = np.digitize(T[f], q)
            for k in range(5):
                g = T[b == k]
                per = [g[g.half == h].R.mean() - g[g.half == h].mR.mean() for h in HL]
                print(f"  {f:10} bin {k} [{g[f].min():+6.2f},{g[f].max():+6.2f}] n {len(g):4} R {g.R.mean():+.3f}"
                      f" mirror {g.mR.mean():+.3f} edge/half " + " ".join(f"{v:+.2f}" for v in per))


if __name__ == "__main__":
    main()
