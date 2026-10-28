"""Trigger T2 (app/strategy/zone_reject.py): an independent re-derivation (SPEC.md 4.4) and its raw result.

1. The arrivals and the rejection written again as one plain pass (no shared code), compared with the app on
   every M15 bar 2023-08-15 .. 2026-10-16.
2. The raw entry measured like zone_wait.py (the same exits: the next half-step line at least 0.25 step away, the
   stop first, out after 32 bars, 0.35 USD spread), by year and by whether the wick swept the line.

    .venv/Scripts/python research/2026-10-23-entry/zone_reject_raw.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import zone_wait as ZW  # noqa: E402

from app.strategy import zone_grid as zg  # noqa: E402
from app.strategy import zone_reject as zj  # noqa: E402


def plain(o, h, lo, c, anchor, step):
    out, seen = [], {}
    for i in range(32, len(c)):
        a, s = anchor[i], step[i]
        if not (math.isfinite(a) and math.isfinite(s) and s > 0):
            continue
        band = 0.15 * s
        k = math.floor((lo[i] - band - a) / (s / 2))
        while a + k * s / 2 <= h[i] + band:
            line = a + k * s / 2
            k += 1
            if not (lo[i] <= line + band and h[i] >= line - band):
                continue
            hh, ll = h[i - 32 : i], lo[i - 32 : i]
            if max(hh.max() - line, line - ll.min()) < 0.5 * s:
                continue
            if any(ll[x] <= line + band and hh[x] >= line - band for x in range(24, 32)):
                continue
            if round(line, 2) in seen and i - seen[round(line, 2)] < 32:
                continue
            seen[round(line, 2)] = i
            came = 1 if c[i - 1] > line else -1
            for q in range(i, min(i + 3, len(c))):
                if came > 0 and c[q] < line - band or came < 0 and c[q] > line + band:
                    break
                wick = (min(o[q], c[q]) - lo[q]) if came > 0 else (h[q] - max(o[q], c[q]))
                back = c[q] > line if came > 0 else c[q] < line
                if h[q] > lo[q] and wick >= 0.5 * (h[q] - lo[q]) and back:
                    ext = min(lo[i : q + 1]) if came > 0 else max(h[i : q + 1])
                    out.append((i, round(line, 6), came, q, round(ext - 0.05 * s * came, 6)))
                    break
    return out


def main() -> None:
    d1, m = ZW.load("D1"), ZW.load("M15")
    G = zg.grid_rows(d1.index.as_unit("ns").asi8, d1.open.to_numpy(float), d1.high.to_numpy(float), d1.low.to_numpy(float),
                     d1.close.to_numpy(float))
    m = m[(m.index >= "2023-08-15") & (m.index < "2026-10-17")]
    k = np.searchsorted(G.known, m.index.as_unit("ns").asi8 + 15 * 60 * 10**9, side="right") - 1
    A, S = G.anchor[k], G.step[k]
    o, h, lo, c = (m[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    ev = zj.zone_rejections(o, h, lo, c, A, S)
    app = sorted((e.arrival, round(e.line, 6), e.side, e.entry_bar, round(e.stop, 6)) for e in ev)
    ref = sorted(plain(o, h, lo, c, A, S))
    print(f"re-derivation: app {len(app)}, plain {len(ref)}, equal {app == ref}")
    rows = []
    for e in ev:
        if e.entry_bar + 33 >= len(c):
            continue
        r = ZW.trade(h, lo, c, e.entry_bar, e.side, e.entry, e.stop, S[e.entry_bar], A[e.entry_bar])
        rows.append(dict(t=m.index[e.arrival], swept=e.swept, r=r))
    R = pd.DataFrame(rows).dropna()
    R["year"] = pd.cut(R.t, [pd.Timestamp(x, tz="UTC") for x in ("2023-09-01", "2024-09-01", "2025-09-01", "2026-04-18", "2026-10-17")],
                       labels=["23-24", "24-25", "25-26", "26 (seen)"])
    print("\nT2 raw R a trade by year (n):")
    print(R.groupby(["year", "swept"], observed=True).r.agg(n="size", R="mean").round(3).unstack().to_string())
    print(f"\nall: {len(R)} trades, {R.r.mean():+.3f} R a trade, won {(R.r > 0).mean() * 100:.0f} %; swept {R[R.swept].r.mean():+.3f} "
          f"on {R.swept.sum()}, not swept {R[~R.swept].r.mean():+.3f} on {(~R.swept).sum()}")
    print("RE-DERIVATION", "OK" if app == ref else "FAILED")


if __name__ == "__main__":
    main()
