"""The phase first, then the components inside it (notes.md, written before it is computed). The D1 phase (the 20-day
efficiency in L1's terciles) and way; inside each phase every component turned to the D1 way, the outcome turned too
(the D1 way's X first minus the other's), by the component's quintiles - by moments and by distinct days, in L1 and L2.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/phase_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PLACES = ["H4_pos", "H1_pos", "M15_pos", "M5_pos", "D1_prev_pos", "H4_bb_pos", "H1_bb_pos", "D1_bb_pos"]
SIGNED = ["H4_ema50", "H1_ema50", "H4_ema20", "H1_ema20", "M15_ema50", "H4_di", "H1_di", "M15_di", "H4_macd", "H1_macd",
          "H1_macd_sig", "move15", "move60", "D1_from_open", "H4_leg_way", "H1_leg_way", "M15_leg_way", "H4_struct", "H1_struct",
          "M15_struct", "H4_brk", "H1_brk", "M15_brk", "usd15", "usd60", "us500_60", "round50", "to_pdh", "to_pdl"]
CENTRED = {"H4_rsi": 50, "H1_rsi": 50, "M15_rsi": 50, "H4_stoch": 50, "H1_stoch": 50, "M15_stoch": 50}
PLAIN = ["vol_rel", "H4_adx", "H1_adx", "D1_atr_rel", "H1_atr_rel", "M15_atr_rel", "H4_retr", "H1_retr", "H4_er", "H1_er",
         "H4_width30", "D1_width20", "hour_utc"]
MIN_DAYS = 30


def turned(X: pd.DataFrame, col: str, way: np.ndarray) -> np.ndarray:
    """The reading as seen from the D1 way (+1 up, -1 down): a place 0..1 mirrored when D1 falls; a signed reading
    (and a structure / break / leg of +-1, 9 unknown kept apart as NaN) times the way; RSI / Stochastic centred first."""
    x = X[col].to_numpy(float)
    if col in PLACES:
        return np.where(way > 0, x, np.where(way < 0, 1.0 - x, np.nan))
    if col in CENTRED:
        return (x - CENTRED[col]) * way
    if col in SIGNED:
        x = np.where(x == 9, np.nan, x) if col.endswith(("struct", "brk")) else x
        return x * way
    return x  # not directional: read as it is


def by_days(D: pd.DataFrame, b: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    """Per bin: moments, the moment mean, distinct (Thai) days, and the mean over days of the FIRST moment of each day in
    the bin - known when it happens. (Not the mean of each day's moments: how long a reading stays in a bin depends on
    what price does next, so weighting days equally by their mean leaks the future - 2026-10-19, a 10x false lean.)"""
    day = pd.DatetimeIndex(D.t).tz_convert("Asia/Bangkok").normalize()
    g = pd.DataFrame({"b": b, "day": day, "t": pd.DatetimeIndex(D.t), "y": y}).dropna().sort_values("t", kind="mergesort")
    first = g.groupby(["b", "day"]).y.first().reset_index()
    out = pd.DataFrame({"n": g.groupby("b").size(), "mean": g.groupby("b").y.mean(), "days": first.groupby("b").size(),
                        "day_mean": first.groupby("b").y.mean()})
    return out


def main() -> None:
    W = pd.read_parquet(HERE / "why_frame.parquet")
    P = pd.read_parquet(HERE / "present_3y.parquet", columns=["t_dec"])
    ph = pd.read_parquet(HERE / "phase_3y.parquet").assign(t=pd.DatetimeIndex(P.t_dec))
    X = W.merge(ph, on="t", how="left", validate="one_to_one")
    X = X[X.half != "exam"].reset_index(drop=True)
    way = X.D1_way20.to_numpy()
    L1 = (X.half == "L1").to_numpy()
    cuts = np.nanquantile(X.D1_er20[L1], [1 / 3, 2 / 3])
    X["phase"] = np.where(X.D1_er20 >= cuts[1], "D1 running", np.where(X.D1_er20 <= cuts[0], "D1 back and forth", "between"))
    X.loc[X.D1_er20.isna() | (way == 0), "phase"] = "none"
    pd.set_option("display.width", 250, "display.max_rows", 300)
    print(f"D1 20-day efficiency terciles (L1): {cuts.round(3)}")
    for xu in (10, 5):
        y = np.where(way > 0, X[f"up{xu}"], X[f"dn{xu}"]).astype(float) - np.where(way > 0, X[f"dn{xu}"], X[f"up{xu}"]).astype(float)
        X[f"y{xu}"] = np.where(way != 0, y, np.nan)
    print("\nthe phase alone - the D1 way's X first minus the other's (moments | days):")
    for xu in (10, 5):
        for h in ("L1", "L2"):
            D = X[X.half == h]
            t = by_days(D, D.phase.to_numpy(), D[f"y{xu}"].to_numpy())
            print(f"  {xu} U {h}: " + "; ".join(f"{p}: {r['mean']:+.3f} | {r.day_mean:+.3f} ({int(r.days)} days)" for p, r in t.iterrows()))
    rows = []
    comps = PLACES + SIGNED + list(CENTRED) + PLAIN
    for ph_name in ("D1 running", "between", "D1 back and forth"):
        for col in comps:
            v = turned(X, col, way)
            k1 = L1 & (X.phase == ph_name).to_numpy()
            edges = np.unique(np.nanquantile(v[k1], [0.2, 0.4, 0.6, 0.8])) if np.isfinite(v[k1]).sum() > 100 else np.array([])
            if len(edges) < 2:
                continue
            b = np.where(np.isnan(v), np.nan, np.searchsorted(edges, v, side="right").astype(float))
            for xu in (10, 5):
                rec = dict(phase=ph_name, reading=col, X=xu)
                for h in ("L1", "L2"):
                    k = ((X.half == h) & (X.phase == ph_name)).to_numpy()
                    t = by_days(X[k], b[k], X[f"y{xu}"].to_numpy()[k])
                    lo, hi = t.index.min(), t.index.max()
                    rec |= {f"lo_{h}": t.day_mean[lo], f"hi_{h}": t.day_mean[hi], f"move_{h}": t.day_mean[hi] - t.day_mean[lo],
                            f"days_lo_{h}": int(t.days[lo]), f"days_hi_{h}": int(t.days[hi]), f"mom_move_{h}": t["mean"][hi] - t["mean"][lo]}
                rec["counts"] = bool(np.sign(rec["move_L1"]) == np.sign(rec["move_L2"]) and min(rec["days_lo_L1"], rec["days_hi_L1"],
                                                                                              rec["days_lo_L2"], rec["days_hi_L2"]) >= MIN_DAYS)
                rec["strength"] = min(abs(rec["move_L1"]), abs(rec["move_L2"])) if rec["counts"] else 0.0
                rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_csv(HERE / "phase_tables.csv", index=False)
    cols = ["reading", "lo_L1", "hi_L1", "move_L1", "days_lo_L1", "days_hi_L1", "lo_L2", "hi_L2", "move_L2", "days_lo_L2", "days_hi_L2"]
    for xu in (10, 5):
        for ph_name in ("D1 running", "between", "D1 back and forth"):
            S = R[(R.X == xu) & (R.phase == ph_name) & R.counts].sort_values("strength", ascending=False)
            print(f"\n{ph_name}, X = {xu} U - the components that count (same way by days in both halves, >= {MIN_DAYS} days a bin), "
                  f"the D1 way first minus against by days, lowest -> highest quintile; {len(S)} of {len(R[(R.X == xu) & (R.phase == ph_name)])}:")
            print(S[cols].head(12).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
