"""The box breakout entered on the retest (owner, 2026-10-15: "apply the setups we have - wait for the entry").

After the break, wait up to ``W`` bars for price to come back to the edge it broke, then enter with the run:

- ``confirm``: a bar touches the broken edge and closes back beyond it with the run; entry at that close (a
  market order at a bar close, as the engine enters; the setup can see the break up to
  ``trigger_max_age_bars`` = 20 bars back);
- ``limit``: a limit at the broken edge, filled when a bar reaches it (the engine has no limit entries for
  setups today: measured to know what it is worth).

The retest is cancelled when a close crosses the stop level first. Stop: the box's other edge or its middle.
Everything else as ``box_harness.py`` (the bot's detector events, hours checked at the entry bar, the H1 map
with the run, the H1 level target <= 3 R with room >= 1 R, one gold position, 12-bar cooldown, real spread +
7 points, 48-bar time stop, no rollover or weekends). Walk-forward: choose on the first half, judge on the
second; the bar: second half >= +0.15 R/trade with >= 20 trades a year.

    .venv/Scripts/python research/2026-10-15-day-trade/box_retest.py
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-15-day-trade")
import box_harness as bh  # noqa: E402

Event = tuple[int, int, float, float]


def simulate(
    m: bh.Market, evs: list[Event], window: bh.Window, style: str, stop_at: str, wait: int
) -> list[tuple[pd.Timestamp, int, float, str]]:
    out: list[tuple[pd.Timestamp, int, float, str]] = []
    busy, selected = -1, -(10**9)
    for t, s, other, edge in evs:
        stop_level = other if stop_at == "other" else (other + edge) / 2
        k_in, entry = None, None
        for k in range(t + 1, min(t + 1 + wait, len(m.c))):
            if (m.c[k] - stop_level) * s <= 0:
                break  # closed through the stop level first: no retest trade
            touched = (m.lo[k] if s > 0 else m.h[k]) * s <= edge * s
            if style == "limit" and touched:
                k_in, entry = k, edge + s * m.cost[k]
                break
            if style == "confirm" and touched and (m.c[k] - edge) * s > 0:
                k_in, entry = k, m.c[k] + s * m.cost[k]
                break
        if k_in is None or entry is None:
            continue
        ts = m.times[k_in]
        if not window(ts):
            continue
        levels, h1 = m.ctx.at(ts)
        if h1 != ("UP" if s > 0 else "DOWN"):
            continue
        stop = stop_level - s * m.cost[k_in]
        risk = (entry - stop) * s
        if risk <= 0:
            continue
        ahead = sorted((lv - entry) * s for lv in levels if (lv - entry) * s > 0)
        near = ahead[0] / risk if ahead else None
        if near is not None and near < bh.ROOM_R:
            continue
        if k_in - selected < bh.COOLDOWN:
            continue
        selected = k_in
        if k_in <= busy:
            continue
        tgt_r = min(bh.CAP_R, near) if near is not None else bh.CAP_R
        target = entry + s * tgt_r * risk
        end = min(k_in + bh.TIME_STOP, len(m.c) - 1)
        r, why, j = None, "TIME", end
        # the limit fills inside the bar: from that bar on, the stop can be hit in the same bar
        first = k_in if style == "limit" else k_in + 1
        for k in range(first, end + 1):
            if (m.lo[k] if s > 0 else m.h[k]) * s <= stop * s:
                r, why, j = -1.0, "SL", k
                break
            if k > k_in and (m.h[k] if s > 0 else m.lo[k]) * s >= target * s:
                r, why, j = tgt_r, "TP", k
                break
        if r is None:
            r = (m.c[end] - entry) * s / risk
        out.append((ts, s, r, why))
        busy = j
    return out


if __name__ == "__main__":
    m = bh.Market()
    evs = bh.events(m, "wilder", "latest")  # the bot's detector as it is
    mid = m.times[len(m.times) // 2]
    rows = []
    for (wname, window), style, stop_at, wait in itertools.product(
        bh.WINDOWS.items(), ("confirm", "limit"), ("other", "middle"), (12, 20)
    ):
        tr = simulate(m, evs, window, style, stop_at, wait)
        rs = [r for _, _, r, _ in tr]
        f = [r for ts, _, r, _ in tr if ts < mid]
        s2 = [r for ts, _, r, _ in tr if ts >= mid]
        rows.append((np.mean(f) if len(f) >= 8 else -9.0, wname, style, stop_at, wait, rs, f, s2))
    print(
        f"XAUUSD M5, the bot's box detector; halves at {mid:%Y-%m-%d}; ranked by the first half (>= 8 trades)"
    )
    print("| hours (UTC) | entry | stop | wait | year R/trade | 1st half | 2nd half | passes |")
    print("|---|---|---|---|---|---|---|---|")
    for _, wname, style, stop_at, wait, rs, f, s2 in sorted(rows, key=lambda x: -x[0]):
        ok = len(s2) >= 5 and np.mean(s2) >= 0.15 and len(rs) >= 20
        print(
            f"| {wname} | {style} | {stop_at} | {wait} | {bh.stats(rs)} | {bh.stats(f)} | {bh.stats(s2)} | {'yes' if ok else ''} |"
        )
