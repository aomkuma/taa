"""V3-1's independent re-derivations on all of P1 + P2 (with the warm-up from 2025-08-01):
1. swings.zigzag against zigzag_ref.zigzag_ref (written differently) on every TF, the trade-size and the inner swings;
2. the structure (rule 4) re-derived at every TF bar from the pivot list and the running extreme computed directly
   (swings.running: the lowest low / highest high since the last pivot), against analyze()'s per-bar arrays;
3. the scale facts behind rule 1, measured after the rule was written: P1 / P2 median H1 ATR and the median S.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/compare_ref.py > research/2026-10-18-moments/agents/dev2/out_compare_ref.txt
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402
from zigzag_ref import zigzag_ref  # noqa: E402

PARTS = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}


def structure_brute(r: W.TF, h, lo, j):
    pb, pp, pk, pc = W.known_at(r.piv, j)
    peaks = pp[pk == 1].tolist()
    troughs = pp[pk == -1].tolist()
    run = W.running(r.piv, h, lo, j)
    hi = peaks[-2:] if len(peaks) >= 2 else [np.nan, np.nan]
    lw = troughs[-2:] if len(troughs) >= 2 else [np.nan, np.nan]
    if run is not None and run[2] == 1 and peaks and run[1] > peaks[-1]:
        hi = [peaks[-1], run[1]]
    if run is not None and run[2] == -1 and troughs and run[1] < troughs[-1]:
        lw = [troughs[-1], run[1]]
    def c(a, b):
        return np.nan if not (np.isfinite(a) and np.isfinite(b)) else (1.0 if b > a else -1.0 if b < a else 0.0)
    hs, ls = c(*hi), c(*lw)
    lab = np.nan if not (np.isfinite(hs) and np.isfinite(ls)) else (1.0 if hs == ls == 1 else -1.0 if hs == ls == -1 else 0.0)
    return hs, ls, lab


def main() -> None:
    t0 = time.time()
    m = W.load_learning()
    print(f"M1 bars {len(m)} from {m.index.min()} to {m.index.max()} (UTC)", flush=True)
    s = W.swing_size(m)
    a = W.h1_atr(m)
    for p, (x, y) in PARTS.items():
        k = (m.index >= pd.Timestamp(x, tz="UTC")) & (m.index < pd.Timestamp(y, tz="UTC"))
        print(f"{p}: median H1 ATR {np.nanmedian(a[k]):.2f} USD; S median {np.median(s[k]):.2f}, 10 % {np.percentile(s[k], 10):.2f},"
              f" 90 % {np.percentile(s[k], 90):.2f}; share of minutes with S = 10 (the floor): {np.mean(s[k] == 10.0):.3f}", flush=True)
    res = {}
    for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1"):
        r = W.analyze(m, tf, inner=tf in ("M1", "M5"))
        res[tf] = r
        h, lo = r.bars.high.to_numpy(float), r.bars.low.to_numpy(float)
        ref = zigzag_ref(h, lo, r.thr)
        same = all(np.array_equal(u, v) for u, v in zip(r.piv, ref))
        print(f"{tf}: {len(r.bars)} bars, {len(r.piv[0])} pivots; zigzag_ref {len(ref[0])} pivots; identical: {same}", flush=True)
        if r.inner:
            ref_in = zigzag_ref(h, lo, W.INNER * r.s)
            same_in = all(np.array_equal(u, v) for u, v in zip(r.inner, ref_in))
            print(f"{tf} inner (0.3 x S): {len(r.inner[0])} pivots; identical: {same_in}", flush=True)
        # the structure, re-derived
        n = len(r.bars)
        js = np.arange(n) if n <= 60_000 else np.unique(np.r_[np.arange(0, n, 7), r.piv[3], r.piv[3] + 1])
        js = js[js < n]
        bad = 0
        for j in js:
            hs, ls, lab = structure_brute(r, h, lo, int(j))
            got = (r.struct.highs[j], r.struct.lows[j], r.struct.label[j])
            if not all((np.isnan(u) and np.isnan(v)) or u == v for u, v in zip((hs, ls, lab), got)):
                bad += 1
        print(f"{tf} structure re-derived at {len(js)} bars: {len(js) - bad} equal, {bad} differ", flush=True)
        lab = r.struct.label.to_numpy()
        print(f"{tf} label shares: up {np.mean(lab == 1):.3f}, down {np.mean(lab == -1):.3f}, mixed {np.mean(lab == 0):.3f},"
              f" unknown {np.mean(np.isnan(lab)):.3f}; boxes {len(r.boxes)}; lines {len(r.lines)}; events {len(r.events)}", flush=True)
    m1_thr_vs_s = np.mean(res["M1"].thr > res["M1"].s + 1e-9)
    print(f"M1 bars where the M1 ATR term raised the threshold above S: {m1_thr_vs_s:.5f}")
    with open(HERE / "v31_learning.pkl", "wb") as f:
        pickle.dump(res, f)
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
