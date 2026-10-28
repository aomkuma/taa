"""A POST-HOC sensitivity for the measurer, not a rule (written after the shape check showed H1 MISSED): each TF's swing
size (rule 3: max(S, ATR14 of the TF), known at the last complete TF bar) applied to the M1 path, so the order of the
extremes inside a TF bar is known, and the structure read on those swings (rule 4) at every M1 close. Shows when each TF
would read down on 2026-10-19 after 14:33. Nothing here is used by swings.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/h1_on_m1.py > research/2026-10-18-moments/agents/dev2/out_h1_on_m1.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402
from compare_ref import structure_brute  # noqa: E402

TH = "Asia/Bangkok"


def main() -> None:
    m = W.load_live()
    b1 = W.tf_bars(m, "M1")
    h, lo = b1.high.to_numpy(float), b1.low.to_numpy(float)
    t_close = W._ns(b1.avail)
    s = W.swing_size(m)
    for tf in ("M5", "M15", "M30", "H1"):
        b = W.tf_bars(m, tf)
        a = W.atr_warm(*(b[k].to_numpy(float) for k in ("high", "low", "close")))
        j = np.searchsorted(W._ns(b.avail), t_close, side="right") - 1
        thr = np.maximum(s, np.where(j >= 0, a[np.maximum(j, 0)], 0.0))
        piv = W.zigzag(h, lo, thr)
        r = W.TF(tf, b1, thr, s, piv, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        lab = np.array([structure_brute(r, h, lo, d)[2] for d in range(len(b1))])
        t = pd.DatetimeIndex(b1.avail).tz_convert(TH)
        after = t >= pd.Timestamp("2026-10-19 14:33", tz=TH)
        dn = np.where(after & (lab == -1))[0]
        first = t[dn[0]] if len(dn) else None
        stays = bool(np.all(lab[dn[0]:] == -1)) if len(dn) else None
        pv = [(pd.Timestamp(b1.t.iloc[x]).tz_convert(TH), p, k) for x, p, k in zip(piv[0], piv[1], piv[2])]
        pv = [f"{x:%H:%M} {'H' if k == 1 else 'L'} {p:.2f}" for x, p, k in pv if x >= pd.Timestamp("2026-10-19 11:00", tz=TH)]
        print(f"{tf} size on the M1 path (threshold {thr[after].min():.2f}..{thr[after].max():.2f} after 14:33): label down from"
              f" {first:%H:%M} (stays to the end: {stays}); pivots from 11:00: {', '.join(pv)}")


if __name__ == "__main__":
    main()
