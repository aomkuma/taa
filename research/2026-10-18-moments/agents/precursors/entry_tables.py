"""The entry inside the aligned phase (notes.md, written before it is computed). The aligned phase: D1 running (the
20-day efficiency >= RUN_ER, L1's top tercile) + the H1 swing structure with the D1 way + H4 +DI / -DI with it. Inside
it, the M15 / M5 / M1 readings turned to the D1 way, by quintile, the D1 way's X first minus the other's - by moments
and by each day's first moment, L1 and L2.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/entry_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from phase_tables import by_days  # noqa: E402

RUN_ER = 0.264
PLACES = ["M15_pos", "M5_pos", "M1_pos", "M15_bb_pos", "M5_bb_pos"]
SIGNED = ["M15_ema20", "M15_ema50", "M5_ema20", "M5_ema50", "M15_di", "M5_di", "M15_macd", "M5_macd", "M15_macd_sig", "M5_macd_sig",
          "move15", "move60", "M5_leg_way", "M1_leg_way", "M15_leg_way", "M5_struct", "M15_struct", "M1_struct", "M5_brk",
          "M15_brk", "M1_brk", "M5_seg2", "M1_seg2", "usd15", "usd60"]
CENTRED = {"M15_rsi": 50, "M5_rsi": 50, "M15_stoch": 50, "M5_stoch": 50}
PLAIN = ["hour_utc", "vol_rel", "M5_atr_rel", "M15_atr_rel", "M5_retr", "M15_retr", "M5_leg", "M15_leg"]
MIN_DAYS = 30


def aligned_frame() -> pd.DataFrame:
    """The learning moments with the phase and the aligned-phase flag."""
    W = pd.read_parquet(HERE / "why_frame.parquet")
    P = pd.read_parquet(HERE / "present_3y.parquet", columns=["t_dec"])
    ph = pd.read_parquet(HERE / "phase_3y.parquet").assign(t=pd.DatetimeIndex(P.t_dec))
    X = W.merge(ph, on="t", how="left", validate="one_to_one").reset_index(drop=True)
    X["aligned"] = aligned(X)
    return X


def aligned(X: pd.DataFrame) -> np.ndarray:
    way = X.D1_way20.to_numpy()
    h1 = np.where(X.H1_struct.to_numpy() == 9, 0, X.H1_struct.to_numpy()) * way == 1
    return (X.D1_er20.to_numpy() >= RUN_ER) & h1 & (X.H4_di.to_numpy() * way > 0) & (way != 0)


def turn(X: pd.DataFrame, col: str, way: np.ndarray) -> np.ndarray:
    x = X[col].to_numpy(float)
    if col in PLACES:
        return np.where(way > 0, x, 1.0 - x)
    if col in CENTRED:
        return (x - CENTRED[col]) * way
    if col in SIGNED:
        if col.endswith(("struct", "brk")):
            x = np.where(x == 9, np.nan, x)
        return x * way
    return x


def main() -> None:
    X = aligned_frame()
    X = X[(X.half != "exam") & X.aligned].reset_index(drop=True)
    way = X.D1_way20.to_numpy()
    for xu in (10, 5):
        X[f"y{xu}"] = (np.where(way > 0, X[f"up{xu}"], X[f"dn{xu}"]).astype(float)
                       - np.where(way > 0, X[f"dn{xu}"], X[f"up{xu}"]).astype(float))
    L1 = (X.half == "L1").to_numpy()
    rows = []
    for col in PLACES + SIGNED + list(CENTRED) + PLAIN:
        v = turn(X, col, way)
        ok = np.isfinite(v[L1])
        if ok.sum() < 200:
            continue
        edges = np.unique(np.nanquantile(v[L1], [0.2, 0.4, 0.6, 0.8]))
        if len(edges) < 1:
            continue
        b = np.where(np.isnan(v), np.nan, np.searchsorted(edges, v, side="right").astype(float))
        for xu in (10, 5):
            rec = dict(reading=col, X=xu, bins=len(edges) + 1)
            for h in ("L1", "L2"):
                k = (X.half == h).to_numpy()
                t = by_days(X[k], b[k], X[f"y{xu}"].to_numpy()[k])
                lo, hi = t.index.min(), t.index.max()
                rec |= {f"m_lo_{h}": t["mean"][lo], f"m_hi_{h}": t["mean"][hi], f"f_lo_{h}": t.day_mean[lo], f"f_hi_{h}": t.day_mean[hi],
                        f"days_lo_{h}": int(t.days[lo]), f"days_hi_{h}": int(t.days[hi]),
                        "best_bin_" + h: int(t["mean"].idxmax()), "best_" + h: t["mean"].max()}
            mv = [np.sign(rec[f"m_hi_{h}"] - rec[f"m_lo_{h}"]) for h in ("L1", "L2")] + [np.sign(rec[f"f_hi_{h}"] - rec[f"f_lo_{h}"]) for h in ("L1", "L2")]
            rec["counts"] = bool(len(set(mv)) == 1 and mv[0] != 0
                                 and min(rec["days_lo_L1"], rec["days_hi_L1"], rec["days_lo_L2"], rec["days_hi_L2"]) >= MIN_DAYS)
            rec["strength"] = min(abs(rec["m_hi_L1"] - rec["m_lo_L1"]), abs(rec["m_hi_L2"] - rec["m_lo_L2"])) if rec["counts"] else 0.0
            rows.append(rec)
    R = pd.DataFrame(rows).sort_values(["X", "strength"], ascending=[True, False])
    R.to_csv(HERE / "entry_tables.csv", index=False)
    for xu in (10, 5):
        for h in ("L1", "L2"):
            D = X[X.half == h]
            t = by_days(D, np.zeros(len(D)), D[f"y{xu}"].to_numpy())
            print(f"aligned phase, {xu} U, {h}: {len(D)} moments, {int(t.days.iloc[0])} days, tilt {t['mean'].iloc[0]:+.3f} (first moments {t.day_mean.iloc[0]:+.3f})")
    pd.set_option("display.width", 260, "display.max_rows", 200)
    cols = ["reading", "m_lo_L1", "m_hi_L1", "f_lo_L1", "f_hi_L1", "days_lo_L1", "m_lo_L2", "m_hi_L2", "f_lo_L2", "f_hi_L2", "days_lo_L2", "days_hi_L2"]
    for xu in (10, 5):
        S = R[(R.X == xu) & R.counts]
        print(f"\nX = {xu} U: the entry readings that move the same way in both halves by moments and first moments "
              f"({len(S)} of {len(R[R.X == xu])}), lowest -> highest quintile (turned to the D1 way):")
        print(S[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
