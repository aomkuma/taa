"""The picture on an entry frame: equal lows / highs (liquidity pools), their sweeps and the squeeze (owner
2026-10-23: "you did not even notice three bottoms and then higher lows and higher highs"; PLAN §A37,
TAA-1802). Moved from research/2026-10-23-entry/picture_read.py, which now imports it. Pure functions on the
frame's last bars (closed only). Numbers from bars, not chart images.
"""

from __future__ import annotations

from typing import Any

import numpy as np

EQ_ATR = 0.35  # bar lows (highs) within this many ATR of each other are one floor (ceiling)


def clusters(points: list[tuple[int, float]], tol: float) -> list[list[tuple[int, float]]]:
    """Points (bar, price) grouped by price: each joins the group whose mean is within ``tol``; groups of two
    or more."""
    out: list[list[tuple[int, float]]] = []
    for p in sorted(points, key=lambda x: x[1]):
        if out and abs(p[1] - np.mean([q[1] for q in out[-1]])) <= tol:
            out[-1].append(p)
        else:
            out.append([p])
    return [c for c in out if len(c) >= 2]


def pools(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: float) -> list[dict[str, Any]]:
    """Equal bottoms / tops near price: bar lows (highs) lower (higher) than both neighbours, clustered within
    ``EQ_ATR`` x ATR; kept when within 2.5 ATR of the last close, touched in the last 36 bars, the touches 3+
    bars apart. ``level`` = the cluster's extreme (the pool's edge)."""
    # bars' own lows also count as touches of a floor (a swing ZigZag can merge close bottoms)
    bar_lows = [(i, float(lo[i])) for i in range(1, len(lo) - 1) if lo[i] <= lo[i - 1] and lo[i] <= lo[i + 1]]
    bar_highs = [(i, float(h[i])) for i in range(1, len(h) - 1) if h[i] >= h[i - 1] and h[i] >= h[i + 1]]
    price = float(c[-1])
    out: list[dict[str, Any]] = []
    for name, pp in (("bottoms", bar_lows), ("tops", bar_highs)):
        for cl in clusters(pp, EQ_ATR * atr):
            cl = sorted(cl)
            mean = float(np.mean([p for _, p in cl]))
            if abs(mean - price) > 2.5 * atr or cl[-1][0] < len(c) - 36 or cl[-1][0] - cl[0][0] < 3:
                continue
            level = min(p for _, p in cl) if name == "bottoms" else max(p for _, p in cl)
            out.append({"name": name, "mean": mean, "touches": cl, "level": float(level)})
    return out


def sweeps(
    pool: dict[str, Any], h: np.ndarray, lo: np.ndarray, c: np.ndarray, v: np.ndarray, atr: float
) -> list[dict[str, Any]]:
    """The bars after the pool's last touch that came from inside it, went 0.1 ATR beyond its edge and closed
    back; with the bar's volume over the frame's mean and the bar-by-bar structure since."""
    level, bottoms = pool["level"], pool["name"] == "bottoms"
    out: list[dict[str, Any]] = []
    for i in range(pool["touches"][-1][0] + 1, len(c)):
        came = c[i - 1] > level if bottoms else c[i - 1] < level
        if bottoms:
            swept = lo[i] < level - 0.1 * atr and c[i] > level
        else:
            swept = h[i] > level + 0.1 * atr and c[i] < level
        if came and swept:
            after = range(i + 1, len(c))
            out.append(
                {
                    "i": i,
                    "extreme": float(lo[i] if bottoms else h[i]),
                    "close": float(c[i]),
                    "volume": float(v[i] / v.mean()),
                    "after": len(after),
                    "up": sum(bool(lo[k] > lo[k - 1] and h[k] > h[k - 1]) for k in after),
                    "down": sum(bool(lo[k] < lo[k - 1] and h[k] < h[k - 1]) for k in after),
                }
            )
    return out


def squeeze_range(h: np.ndarray, lo: np.ndarray, atr: float, n: int = 12) -> float:
    """The last ``n`` bars' high-low range in ATR (under 3 = a squeeze)."""
    return float((h[-n:].max() - lo[-n:].min()) / atr)
