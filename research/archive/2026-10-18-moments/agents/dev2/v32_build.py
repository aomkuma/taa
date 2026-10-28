"""V3-2 step 1: the learning bars -> the swings -> every entry's specs (all hours, every entry TF), and the P1 terciles
of the H1 ATR for the 'vol' entry-TF choice (R2). Writes v32_specs.pkl. No ticks, no outcome.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/v32_build.py > research/2026-10-18-moments/agents/dev2/out_v32_build.txt
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402
import v32  # noqa: E402


def terciles(mk: v32.Mkt) -> tuple[float, float]:
    """R2: the H1 ATR at every P1 M1 bar (its close) inside the four windows -> the 1/3 and 2/3 quantiles."""
    t = mk.t1
    part = v32.part_of(t)
    win = v32.window_of(t)
    k = (part == "P1") & (win != "other") & np.isfinite(mk.H)
    q1, q2 = np.quantile(mk.H[k], [1 / 3, 2 / 3])
    return float(q1), float(q2)


def main() -> None:
    t0 = time.time()
    m = W.load_learning()
    assert m.index.max() < W.EXAM_START
    mk = v32.market(m)
    print(f"bars {m.index.min()} .. {m.index.max()} ({len(m)} M1); swings in {time.time() - t0:.0f} s", flush=True)
    q1, q2 = terciles(mk)
    print(f"R2 terciles of the H1 ATR (P1, in the windows): q1 {q1:.3f}, q2 {q2:.3f} USD", flush=True)
    specs = v32.build(mk)
    for k, v in specs.items():
        if k == "levels":
            continue
        n = len(v)
        p = v.part.value_counts().to_dict() if n and "part" in v else {}
        print(f"{k:16s} {n:6d} specs (all hours, from 2025-08)  P1 {p.get('P1', 0)}  P2 {p.get('P2', 0)}", flush=True)
    with open(HERE / "v32_specs.pkl", "wb") as f:
        pickle.dump(dict(specs=specs, q=(q1, q2)), f)
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
