"""Why the NY 08:30 straddle holds (notes.md, written before computing, 2026-10-20 18:13 Thai): splits by the day
(release / Thursday claims / other), the side against gold's D1 20-day direction, the weekday, the path R at +5 .. +30
minutes with MFE / MAE, and the exit. P1 / P2 / exam (the exam already read for PLAN-1: a description, not a test).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/ny_study.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import check_plan1 as C

ROOT = Path(__file__).resolve().parents[4]
C.EXAM = pd.Timestamp("2026-10-18", tz="UTC")  # the measurer reads the exam trades already read for PLAN-1
DEV = Path(__file__).parents[1] / "dev"
MIN = 60 * 10**9


def trades() -> pd.DataFrame:
    A = pd.concat([pd.read_parquet(DEV / f"plan1_every_{k}_s0_x0.parquet") for k in ("learn", "exam")])
    A = A[A.piece == "NY straddle"].copy()
    for c in ("t_in", "t_out", "t_dec"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    return A.sort_values("t_in").reset_index(drop=True)


def day_kind(T: pd.DataFrame) -> pd.Series:
    cal = pd.read_csv(ROOT / "app/news/us_releases.csv")
    rel = set(cal[cal.time_et == "08:30"].date)
    ny = pd.to_datetime(T.t_dec, utc=True).dt.tz_convert("America/New_York")
    d = ny.dt.strftime("%Y-%m-%d")
    return pd.Series(np.where(d.isin(rel), "release", np.where(ny.dt.dayofweek == 3, "thursday", "other")), index=T.index)


def d1_dir(T: pd.DataFrame) -> np.ndarray:
    d1 = pd.read_parquet(C.HIST / "D1.parquet").drop_duplicates("open_time", keep="last").sort_values("open_time")
    ct, cl = d1.close_time.astype("int64").to_numpy(), d1.close.to_numpy(float)
    k = np.searchsorted(ct, T.t_in.to_numpy(np.int64), side="right") - 1  # the last D1 bar closed by the fill
    return np.sign(cl[k] - cl[k - 20])


def path(T: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in T.itertuples():
        t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
        f = int(np.searchsorted(t, r.t_in, side="left"))
        end = int(np.searchsorted(t, r.t_out, side="right"))
        px = (bid if r.side > 0 else ask)[f + 1:end]
        tt = t[f + 1:end]
        Rp = (px - r.entry) * r.side / r.risk
        out = {}
        for m in (5, 10, 15, 20, 30):
            i = int(np.searchsorted(tt, r.t_in + m * MIN, side="left"))
            out[f"R{m}"] = Rp[min(i, len(Rp) - 1)] if i < len(Rp) else r.R  # exited before: the final R
        out["MFE"] = Rp.max() if len(Rp) else 0.0
        out["MAE"] = Rp.min() if len(Rp) else 0.0
        rows.append(out)
    return pd.DataFrame(rows, index=T.index)


def show(T: pd.DataFrame, by: str) -> None:
    g = T.groupby([by, "part"]).R.agg(["size", "mean", "sum"]).unstack("part")
    print(f"\n-- by {by}: trades / R per trade / summed R (P1, P2, exam)")
    for k in g.index:
        cells = [f"{int(g.loc[k, ('size', p)]) if not np.isnan(g.loc[k, ('size', p)]) else 0:3d} "
                 f"{g.loc[k, ('mean', p)]:+.3f} {g.loc[k, ('sum', p)]:+6.1f}" for p in ("P1", "P2", "exam") if ("size", p) in g]
        print(f"  {str(k):10s} " + " | ".join(cells))


def main() -> None:
    T = trades()
    T["day"] = day_kind(T)
    T["vs_d1"] = np.where(d1_dir(T) * T.side > 0, "with D1", "against D1")
    T["weekday"] = pd.to_datetime(T.t_dec, utc=True).dt.tz_convert("America/New_York").dt.day_name().str[:3]
    T = pd.concat([T, path(T)], axis=1)
    print(f"NY straddle trades: {len(T)}; per part {T.part.value_counts().to_dict()}")
    for by in ("day", "vs_d1", "weekday", "exit"):
        show(T, by)
    print("\n-- the path: mean R at +5 / +10 / +15 / +20 / +30 min, MFE, MAE (P1, P2, exam)")
    for p in ("P1", "P2", "exam"):
        x = T[T.part == p]
        print(f"  {p:4s} " + "  ".join(f"{c} {x[c].mean():+.3f}" for c in ("R5", "R10", "R15", "R20", "R30", "MFE", "MAE")))
    for p in ("P1", "P2", "exam"):
        x = T[T.part == p]
        print(f"  {p:4s} median MFE {x.MFE.median():+.3f}; share with MFE >= 0.5 R {np.mean(x.MFE >= 0.5):.2f}, >= 1 R "
              f"{np.mean(x.MFE >= 1):.2f}; share stopped {np.mean(x.exit == 'stop'):.2f}")
    T.to_parquet(Path(__file__).with_name("ny_study.parquet"))


if __name__ == "__main__":
    main()
