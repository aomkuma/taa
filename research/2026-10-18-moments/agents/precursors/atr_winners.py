"""Winners vs losers by the volatility at the entry (owner 2026-10-21: "at what ATR do the winners trade, and the
losers?"). For PLAN-1's pieces (dev/plan1_every_*) and #43 / #23 (strategist/exam43_trades_*), learning + exam (every
rule here already had its one exam read; this is a description). At each entry: MT5 ATR(14) of the last CLOSED H1, M5
and M1 bar, and the stop distance in H1 ATRs. Reported: the medians for winners (R > 0) and losers, and R by H1-ATR band.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/atr_winners.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # gold.py
AG = Path(__file__).resolve().parents[1]
END = pd.Timestamp("2026-10-18", tz="UTC")


def atr_by_close(tf: str) -> pd.Series:
    """MT5 ATR(14) per bar of tf, indexed by the bar's close time (ns)."""
    import gold  # noqa: PLC0415

    m = gold.bars("M1", before=END)
    m = m[m.index >= pd.Timestamp("2025-08-01", tz="UTC")]
    b = m if tf == "M1" else m.resample({"M5": "5min", "H1": "1h"}[tf], label="left",
                                         closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pc = b.close.shift(1)
    tr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1)
    step = {"M1": 1, "M5": 5, "H1": 60}[tf]
    a = tr.rolling(14).mean()
    a.index = (b.index + pd.Timedelta(minutes=step)).as_unit("ns")
    return a.dropna()


def at(a: pd.Series, t_ns: np.ndarray) -> np.ndarray:
    i = np.searchsorted(a.index.asi8, t_ns, side="right") - 1  # the last bar closed by the entry
    return np.where(i >= 0, a.to_numpy()[np.maximum(i, 0)], np.nan)


def load() -> pd.DataFrame:
    P = pd.concat([pd.read_parquet(AG / "dev" / f"plan1_every_{k}_s0_x0.parquet").assign(src=k) for k in ("learn", "exam")])
    P = P.rename(columns={"piece": "method"})[["method", "t_in", "R", "risk", "part"]]
    S = pd.concat([pd.read_parquet(AG / "strategist" / f"exam43_trades_{k}.parquet") for k in ("learn", "exam")])
    S = S.assign(method=S.stream.map({"RT_opp": "#43 RT_opp", "RC_win": "#23 RC_win"}))[["method", "t_in", "R", "risk", "part"]]
    T = pd.concat([P, S], ignore_index=True)
    if not np.issubdtype(T.t_in.dtype, np.integer):
        T["t_in"] = pd.to_datetime(T.t_in, utc=True).astype("int64")
    return T


def main() -> None:
    T = load()
    for tf in ("H1", "M5", "M1"):
        T[f"atr_{tf}"] = at(atr_by_close(tf), T.t_in.to_numpy(np.int64))
    T["stop_in_H1atr"] = T.risk / T.atr_H1
    T["res"] = np.where(T.R > 0, "win", "loss")
    print("medians at the entry: winners | losers  (learning + exam)")
    for meth, g in T.groupby("method"):
        w, lo = g[g.R > 0], g[g.R <= 0]
        print(f"  {meth:12s} n {len(g):3d} win {len(w) / len(g):.0%} | H1 ATR {w.atr_H1.median():5.1f} | {lo.atr_H1.median():5.1f} | "
              f"M5 ATR {w.atr_M5.median():4.1f} | {lo.atr_M5.median():4.1f} | M1 ATR {w.atr_M1.median():4.2f} | {lo.atr_M1.median():4.2f} | "
              f"stop / H1 ATR {w.stop_in_H1atr.median():4.2f} | {lo.stop_in_H1atr.median():4.2f}")
    bands = [0, 12, 16, 20, 25, 999]
    T["H1band"] = pd.cut(T.atr_H1, bands, labels=["<12", "12-16", "16-20", "20-25", ">=25"], right=False)
    print("\nR per trade by the H1 ATR at the entry (trades, R)")
    tab = T.groupby(["method", "H1band"], observed=False).R.agg(["size", "mean"])
    for meth in tab.index.get_level_values(0).unique():
        print(f"  {meth:12s} " + "  ".join(f"{b}: {int(tab.loc[(meth, b), 'size']):3d} {tab.loc[(meth, b), 'mean']:+.2f}"
                                          if tab.loc[(meth, b), 'size'] else f"{b}:   - " for b in tab.loc[meth].index))
    T.to_parquet(Path(__file__).with_name("atr_winners.parquet"))


if __name__ == "__main__":
    main()
