"""When a 10-USD move is about to start (notes.md, written before it is computed). At the M15 closes inside the owner's
windows: does price move 10 USD either way within 15 / 45 minutes from the next M1 open? By the side-free readings,
by quintile (P1's edges), by moments and by each day's first moment, P1 (2025-10-18 .. 2026-01-15) and P2
(2026-01-16 .. 2026-04-17).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/burst.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from entry_tables import aligned_frame  # noqa: E402
from m15_trades import part_of  # noqa: E402
from phase_tables import by_days  # noqa: E402

READINGS = ["vol_rel", "M5_atr_rel", "M15_atr_rel", "H1_atr_rel", "D1_atr_rel", "M5_bb_width", "M15_bb_width", "H1_bb_width",
            "abs_move15", "abs_move60", "abs_t_fix_am", "abs_t_fix_pm", "abs_t_comex", "abs_t_us_data", "abs_t_ny_open", "hour_utc",
            "weekday", "D1_er20", "H4_er30", "H4_width30", "D1_width20", "M15_adx", "H1_adx"]


def frame() -> pd.DataFrame:
    import jlib  # noqa: PLC0415
    from runpat_check import passages  # noqa: PLC0415

    X = aligned_frame()
    X["part"] = part_of(pd.DatetimeIndex(X.t))
    t = pd.DatetimeIndex(X.t)
    X = X[(X.part != "") & (t.minute % 15 == 0)].reset_index(drop=True)
    for c in ("move15", "move60", "t_fix_am", "t_fix_pm", "t_comex", "t_us_data", "t_ny_open"):
        X[f"abs_{c}"] = X[c].abs()
    m = jlib.m1_frame("XAUUSD")
    o, h, lo = m.open.to_numpy(float), m.high.to_numpy(float), m.low.to_numpy(float)
    j0 = np.searchsorted(m.index.as_unit("ns").asi8, pd.DatetimeIndex(X.t).as_unit("ns").asi8)
    ok = j0 < len(o)
    X = X[ok].reset_index(drop=True)
    j0 = j0[ok]
    for hz in (15, 45):
        u, d = passages(o, h, lo, j0, np.full(len(j0), 10.0), horizon=hz)
        X[f"up{hz}m"], X[f"dn{hz}m"] = u, d
        X[f"burst{hz}m"] = (u | d).astype(float)
    return X


def main() -> None:
    X = frame()
    P1 = (X.part == "P1").to_numpy()
    pd.set_option("display.width", 250, "display.max_rows", 200)
    for hz in (15, 45):
        print(f"10 USD within {hz} minutes: P1 {X.loc[P1, f'burst{hz}m'].mean():.3f}, P2 {X.loc[X.part == 'P2', f'burst{hz}m'].mean():.3f}, "
              f"exam (not read beyond this base) -")
    rows = []
    for col in READINGS:
        v = X[col].to_numpy(float)
        edges = np.unique(np.nanquantile(v[P1], [0.2, 0.4, 0.6, 0.8]))
        b = np.where(np.isnan(v), np.nan, np.searchsorted(edges, v, side="right").astype(float))
        for hz in (15, 45):
            rec = dict(reading=col, minutes=hz)
            for p in ("P1", "P2"):
                k = (X.part == p).to_numpy()
                tb = by_days(X[k], b[k], X[f"burst{hz}m"].to_numpy()[k])
                rec |= {f"{p}_bins": " ".join(f"{x:.2f}" for x in tb["mean"]), f"{p}_first": " ".join(f"{x:.2f}" for x in tb.day_mean),
                        f"{p}_lo": tb["mean"].iloc[0], f"{p}_hi": tb["mean"].iloc[-1], f"{p}_days_min": int(tb.days.min())}
            same = np.sign(rec["P1_hi"] - rec["P1_lo"]) == np.sign(rec["P2_hi"] - rec["P2_lo"])
            rec["steady"] = bool(same)
            rec["spread"] = min(abs(rec["P1_hi"] - rec["P1_lo"]), abs(rec["P2_hi"] - rec["P2_lo"])) if same else 0.0
            rows.append(rec)
    R = pd.DataFrame(rows).sort_values(["minutes", "spread"], ascending=[True, False])
    R.to_csv(HERE / "burst.csv", index=False)
    for hz in (15, 45):
        print(f"\n10 USD within {hz} minutes, by quintile lowest -> highest (moments | each day's first moment):")
        print(R[R.minutes == hz][["reading", "P1_bins", "P1_first", "P2_bins", "P2_first", "P2_days_min", "steady"]].to_string(index=False))
    X.to_parquet(HERE / "burst_frame.parquet")


if __name__ == "__main__":
    main()
