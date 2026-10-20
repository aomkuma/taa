"""An independent second swing detector for V3-1 (rule 2 of DEV_LOG.md), written differently from swings.zigzag: leg by
leg with prefix maxima / minima (numpy), never with a bar-by-bar state machine. Used only to cross-check
swings.zigzag pivot for pivot (`compare_ref.py`).

The rule, as written: before the first pivot, the first bar i where the highest high and the lowest low so far (the
first bar keeping a tie) sit on different bars at least thr[i] apart; the earlier is the first pivot. Then a peak
leg tracked from bar e: at a bar i, the peak so far is max(h[e..i-1]); bar i extends it when h[i] is above; otherwise
it confirms the peak when the peak - lo[i] >= thr[i]. The peak = the first bar holding max(h[e..i-1]); the trough leg
then starts at bar i. Mirrored for troughs.
"""

from __future__ import annotations

import numpy as np


def _first_arg_running(x: np.ndarray, larger: bool) -> np.ndarray:
    """For each i, the first index holding the running max (larger) / min of x[0..i]."""
    run = np.maximum.accumulate(x) if larger else np.minimum.accumulate(x)
    prev = np.r_[-np.inf if larger else np.inf, run[:-1]]
    new = x > prev if larger else x < prev
    return np.maximum.accumulate(np.where(new, np.arange(len(x)), 0))


def zigzag_ref(h: np.ndarray, lo: np.ndarray, thr: np.ndarray):
    n = len(h)
    out: list[tuple[int, float, int, int]] = []
    if n == 0:
        return _pack(out)
    amax, amin = _first_arg_running(h, True), _first_arg_running(lo, False)
    ok = (amax != amin) & (h[amax] - lo[amin] >= thr)
    if not ok.any():
        return _pack(out)
    i0 = int(np.argmax(ok))
    a, b = int(amax[i0]), int(amin[i0])
    if b < a:  # the trough first
        out.append((b, float(lo[b]), -1, i0))
        kind, e = 1, a  # now tracking a peak from bar a
    else:
        out.append((a, float(h[a]), 1, i0))
        kind, e = -1, b
    start = i0 + 1
    while start < n:
        found = _leg(h, lo, thr, kind, e, start)
        if found is None:
            break
        piv_bar, conf = found
        out.append((piv_bar, float(h[piv_bar] if kind == 1 else lo[piv_bar]), kind, conf))
        kind, e, start = -kind, conf, conf + 1
    return _pack(out)


def _leg(h, lo, thr, kind, e, start):
    """The confirming bar of a leg tracked from bar e, scanning from `start`; windows grow by doubling."""
    n = len(h)
    w = 256
    while True:
        stop = min(n, start + w)
        if kind == 1:
            seg = np.r_[h[e], h[start:stop]]  # position 0 = the extreme so far (bar e)
            prior = np.maximum.accumulate(seg)[:-1]  # the peak before each scanned bar
            cur = h[start:stop]
            ext = cur > prior
            conf = ~ext & (prior - lo[start:stop] >= thr[start:stop])
        else:
            seg = np.r_[lo[e], lo[start:stop]]
            prior = np.minimum.accumulate(seg)[:-1]
            cur = lo[start:stop]
            ext = cur < prior
            conf = ~ext & (h[start:stop] - prior >= thr[start:stop])
        if conf.any():
            k = int(np.argmax(conf))
            i = start + k
            # the pivot: the first bar of e, start..i-1 holding the extreme
            bars = np.r_[e, np.arange(start, i)]
            vals = h[bars] if kind == 1 else lo[bars]
            best = int(np.argmax(vals)) if kind == 1 else int(np.argmin(vals))
            return int(bars[best]), i
        if stop >= n:
            return None
        w *= 2


def _pack(out):
    p = np.array(out, dtype=float).reshape(-1, 4)
    return p[:, 0].astype(np.int64), p[:, 1], p[:, 2].astype(np.int64), p[:, 3].astype(np.int64)
