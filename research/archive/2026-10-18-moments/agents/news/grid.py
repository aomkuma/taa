"""News agent, step 3 (design only: A = 2021-09 .. 2023-10, B = 2023-11 .. 2026-02): rule families per event.

Families (s = the sign of the move from the release minute's open to the decision bar's close):
  follow k  - decide at the close of minute k after the release, trade with s
  fade k    - the same, against s; the stop beyond the extreme since the release
  pullback  - the first k0 minutes set the impulse (s, its extreme P, its size I); wait up to W minutes for a bar
              whose close is back by at least f x I from P; enter with s at the next open; the stop beyond the
              release open by a buffer
Stops in units of `pre` (the pre-release hour's mean 1-minute range; scale-free 2021-2026); targets as R
multiples or a time exit only. Score: R a trade in A and in B separately.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/grid.py
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from lab import SLIP, Gold, events  # noqa: E402


def fast(G: Gold, e: int, side: int, sl: float, tp: float | None, hz: int) -> float:
    """R of one trade (no break-even), the bot's conventions."""
    entry = G.fill(e, side)
    end = min(e + hz, len(G.o) - 1)
    if side > 0:
        adv, fav = G.lo[e:end], G.h[e:end]
    else:
        adv, fav = G.h[e:end] + G.sp[e:end], G.lo[e:end] + G.sp[e:end]
    stop = entry - side * sl
    hs = np.flatnonzero((adv - stop) * side <= 0)
    js = hs[0] if len(hs) else 10**9
    jt = 10**9
    if tp is not None:
        ht = np.flatnonzero((fav - entry) * side >= tp)
        jt = ht[0] if len(ht) else 10**9
    if js <= jt and js < 10**9:
        usd = -sl - SLIP
    elif jt < 10**9:
        usd = tp
    else:
        x = end - 1
        px = G.c[x] - (SLIP if side > 0 else -(G.sp[x] + SLIP))
        usd = (px - entry) * side
    return usd / (sl + SLIP)


def setups(G: Gold, i: int, pre: float):
    """Yield (family key, e, side, stop distance from the fill or None, extra) for one release at bar i."""
    o0 = G.o[i]
    for k in (1, 2, 3, 5, 10, 15, 30):
        e = i + k
        mv = G.c[e - 1] - o0
        s = 1 if mv > 0 else -1
        x = abs(mv) / pre
        hi, lo = G.h[i:e].max(), G.lo[i:e].min()
        yield ("follow", k), e, s, None, x
        # fade: the stop beyond the extreme since the release by 1 pre
        side = -s
        ext = hi if side < 0 else lo
        fill = G.fill(e, side)
        yield ("fade", k), e, side, (ext - fill) * -side + pre * 1.0 if side < 0 else (fill - ext) + pre, x
    for k0, f, w in itertools.product((1, 2, 3), (0.5, 0.75, 1.0), (20,)):
        mv = G.c[i + k0 - 1] - o0
        s = 1 if mv > 0 else -1
        P = G.h[i : i + k0].max() if s > 0 else G.lo[i : i + k0].min()
        size = (P - o0) * s
        lvl = P - s * f * size
        for j in range(i + k0, i + k0 + w):
            if (G.c[j] - lvl) * s <= 0:
                e = j + 1
                fill = G.fill(e, s)
                stop = o0 - s * 1.0 * pre
                yield ("pullback", k0, f), e, s, (fill - stop) * s, size / pre
                break


def main() -> None:
    gold.below_normal_priority()
    G = Gold()
    ev = events(extra=True)
    ev = ev[ev.per != "T"]
    rng = G.h - G.lo
    rows = []
    for r in ev.itertuples():
        i = int(G.pos.get(r.t, -1))
        if i < 200 or i + 300 >= len(G.o):
            continue
        j = i - 30 if r.main == "PC" else i
        pre = rng[j - 60 : j].mean()
        for fam, e, side, sl0, x in setups(G, i, pre):
            stops = [("pre", m, m * pre) for m in (3, 6, 10)]
            if sl0 is not None:
                stops = [("struct", 0, sl0)]
            for stype, m, sl in stops:
                if not (0 < sl < 40 * pre):
                    continue
                for tpm, hz in ((1.0, 120), (1.5, 120), (2.0, 120), (3.0, 180), (None, 30), (None, 60), (None, 120)):
                    tp = None if tpm is None else tpm * sl
                    R = fast(G, e, side, sl, tp, hz)
                    rows.append((r.t, r.main, r.per, fam, stype, m, tpm, hz, x, R, sl))
    d = pd.DataFrame(rows, columns=["t", "main", "per", "fam", "stype", "m", "tpm", "hz", "x", "R", "sl"])
    d["fam"] = d.fam.astype(str)
    d.to_parquet("research/2026-10-18-moments/agents/news/grid_design.parquet")
    print(len(d), "simulated trades")


if __name__ == "__main__":
    main()
