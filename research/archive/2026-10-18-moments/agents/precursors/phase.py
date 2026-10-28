"""The market's phase at each moment (notes.md "Why gold runs the way it does", next: "a phase reading known at the
moment"). On D1 and H4 (the broker's server day, indicators.bars), from the bars complete by the moment:
- the efficiency of the last N closes (Kaufman: |close now - close N bars ago| / the sum of the bar-to-bar moves;
  1 = a straight run, near 0 = back and forth): D1 over 20 days, H4 over 30 bars (5 days);
- the way over those bars (+1 up, -1 down);
- the range of the last N bars in that timeframe's ATRs (a wide range = a moving market).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/phase.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402
from indicators import at, bars  # noqa: E402

SPANS = {"D1": ("1D", 20), "H4": ("4h", 30)}


def efficiency(c: np.ndarray, n: int) -> np.ndarray:
    """Per bar: |c[i] - c[i-n]| / sum |c[j] - c[j-1]| over j in (i-n, i]; NaN before n bars or with no move."""
    c = np.asarray(c, float)
    path = pd.Series(np.abs(np.diff(c, prepend=np.nan))).rolling(n).sum().to_numpy()
    net = np.abs(c - pd.Series(c).shift(n).to_numpy())
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(path > 0, net / path, np.nan)


def way(c: np.ndarray, n: int) -> np.ndarray:
    c = np.asarray(c, float)
    return np.sign(c - pd.Series(c).shift(n).to_numpy())


def width(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    a = F.atr(h, lo, c, 14)
    hi = pd.Series(h).rolling(n).max().to_numpy()
    lw = pd.Series(lo).rolling(n).min().to_numpy()
    return (hi - lw) / a


def features(m: pd.DataFrame, t: pd.DatetimeIndex) -> pd.DataFrame:
    t_ns = t.as_unit("ns").asi8
    cols = {}
    for tf, (rule, n) in SPANS.items():
        b = bars(m, rule)
        h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
        bi = at(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, t_ns)
        ok = bi >= 0
        for name, v in (("er", efficiency(c, n)), ("way", way(c, n)), ("width", width(h, lo, c, n))):
            x = np.full(len(t), np.nan)
            x[ok] = v[bi[ok]]
            cols[f"{tf}_{name}{n}"] = x
    return pd.DataFrame(cols, index=t)


def main() -> None:
    import plib  # noqa: PLC0415

    P = pd.read_parquet(HERE / "present_3y.parquet")
    X = features(plib.load(), pd.DatetimeIndex(P.t_dec))
    X.reset_index(drop=True).to_parquet(HERE / "phase_3y.parquet")
    print(f"{len(X)} moments; the phase readings:\n{X.describe().round(3).T.to_string()}")


if __name__ == "__main__":
    main()
