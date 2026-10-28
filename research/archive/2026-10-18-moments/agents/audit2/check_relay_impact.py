"""What the relayed ZigZag start-up fix would change in the first developer's own swings (dev/ is read only: the fixed
copy lives in memory here, the file is never touched).

The developer's inputs: P.load_m1() (2025-09-01 .. the exam start, its own exam-refusing reader); TF(m, 1 / 5 / 15) =
tf_bars + ATR(14), k = ZZ_K (2); P5's Chart = M1 with H = the last complete H1 bar's ATR(14) and k = K_IN (0.3), and
K_MAIN (0.6) for its main swings. The pivots of the current zigzag against the fixed one.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_relay_impact.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

AG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AG / "precursors"))
sys.path.insert(0, str(AG / "journal"))
sys.path.insert(0, str(AG / "dev"))
import p5_patterns as P5  # noqa: E402
import patterns as P  # noqa: E402

OLD = "            if h[hi_i] - lo[lo_i] >= thr:\n"
NEW = "            if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr:\n"


def fixed_zigzag():
    src = (AG / "dev" / "patterns.py").read_text(encoding="utf-8")
    if src.count(OLD) != 1:
        raise SystemExit(f"the start-up line is not found once ({src.count(OLD)})")
    mod = types.ModuleType("patterns_fixed")
    mod.__file__ = str(AG / "dev" / "patterns.py")
    exec(compile(src.replace(OLD, NEW), mod.__file__, "exec"), mod.__dict__)  # noqa: S102 - the developer's own file
    return mod.zigzag


def compare(name: str, t: pd.DatetimeIndex, h, lo, a, k, zz_new) -> None:
    po, pn = P.zigzag(h, lo, a, k), zz_new(h, lo, a, k)
    so = set(zip(*(x.tolist() for x in po), strict=True))
    sn = set(zip(*(x.tolist() for x in pn), strict=True))
    diff = so ^ sn
    last = max((t[x[0]] for x in diff), default=None)
    print(f"  {name:28}: current {len(po[0])} pivots (confirmed by their own bar {int((po[3] <= po[0]).sum())}, a bar "
          f"twice {len(po[0]) - len(np.unique(po[0]))}); fixed {len(pn[0])}; differing {len(diff)}, the last at {last}")


def main() -> int:
    zz_new = fixed_zigzag()
    m = P.load_m1()
    print(f"the developer's M1: {len(m)} bars {m.index.min()} .. {m.index.max()}")
    for minutes in (1, 5, 15):
        tf = P.TF(m, minutes)
        compare(f"TF M{minutes} (ATR x {P.ZZ_K:g})", tf.b.index, tf.h, tf.lo, tf.atr, P.ZZ_K, zz_new)
    H = P5.h1_atr_m1(m)
    h, lo = m.high.to_numpy(float), m.low.to_numpy(float)
    for k, label in ((P5.K_IN, "K_IN"), (P5.K_MAIN, "K_MAIN")):
        compare(f"P5 M1 (H1 ATR x {k:g}, {label})", m.index, h, lo, H, k, zz_new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
