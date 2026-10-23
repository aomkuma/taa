"""The owner's hypothesis (2026-10-23): "when price comes down to a zone (a main or a half line), wait for it to
consolidate a while and then look for the trade - better than trading the moment it reaches the zone; near a zone
that is not broken but wobbling, wait until the picture is clear; if price breaks straight through the zone, wait
until it comes back near the zone and then trade."

Definitions fixed before any result (not tuned): the zone grid of the bot's code (app/strategy/zone_grid.py), lines
every half step; band = 0.15 step. M15 bars. An **arrival** = the first M15 bar touching a line's band after price
was at least 0.5 step from that line within the last 32 bars (and not in the band in the 8 bars before). From each
arrival:
- **A, at once:** enter the bounce at the arrival bar's close; stop 0.05 step beyond the farther of the bar's
  extreme and the band.
- **B, consolidate then trade:** within 48 bars, 8+ consecutive bars inside a box at most 0.3 step tall that
  overlaps the band, then the first close out of the box -> enter that way (bounce or through); stop 0.05 step
  beyond the box.
- **C, broken then back:** a close beyond the line by more than the band (before any B box), then within 48 bars
  price comes back into the band and a bar closes again on the break side -> enter the break's way; stop 0.05 step
  beyond the extreme since the break.
Exits for all: the next line beyond the entry at least 0.25 step away (the target), the stop (first when a bar holds
both), or 32 bars; cost 0.35 USD spread a trade. Results in R, per period.

    .venv/Scripts/python research/2026-10-23-entry/zone_wait.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from app.strategy import zone_grid as zg  # noqa: E402

BAND, AWAY, LOOK, WAIT, BOX_N, BOX_H, PAD, HOLD, SPREAD = 0.15, 0.5, 32, 48, 8, 0.3, 0.05, 32, 0.35
PERIODS = [
    ("2023-09 .. 2024-08", "2023-09-01", "2024-09-01"),
    ("2024-09 .. 2025-08", "2024-09-01", "2025-09-01"),
    ("2025-09 .. 2026-04-17", "2025-09-01", "2026-04-18"),
    ("2026-04-18 .. 10-16 (seen)", "2026-04-18", "2026-10-17"),
]


def load(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(ROOT / f"data/history/FBS-Demo/XAUUSD/{tf}.parquet")
    d["t"] = pd.to_datetime(d.open_time, utc=True)
    return d.drop_duplicates("t", keep="last").set_index("t").sort_index()


def trade(h, lo, c, i, side, entry, stop, step, anchor):
    """From bar i+1: the target = the next half-step line at least 0.25 step away, the stop first, out after HOLD."""
    risk = (entry - stop) * side
    if risk <= 0.05 * step:
        return np.nan
    target = zg.next_line(zg.GridState(anchor, step / 2, 0, 0), entry, side, 0.5)  # 0.5 half step = 0.25 step
    for j in range(i + 1, min(i + 1 + HOLD, len(c))):
        if (lo[j] <= stop) if side > 0 else (h[j] >= stop):
            return -1.0 - SPREAD / risk
        if (h[j] >= target) if side > 0 else (lo[j] <= target):
            return (target - entry) * side / risk - SPREAD / risk
    j = min(i + HOLD, len(c) - 1)
    return (c[j] - entry) * side / risk - SPREAD / risk


def main() -> None:
    d1, m = load("D1"), load("M15")
    t1 = d1.index.as_unit("ns").asi8
    G = zg.grid_rows(t1, d1.open.to_numpy(float), d1.high.to_numpy(float), d1.low.to_numpy(float), d1.close.to_numpy(float))
    m = m[(m.index >= "2023-08-15") & (m.index < "2026-10-17")]
    avail = m.index.as_unit("ns").asi8 + 15 * 60 * 10**9
    h, lo, c = m.high.to_numpy(float), m.low.to_numpy(float), m.close.to_numpy(float)
    k = np.searchsorted(G.known, avail, side="right") - 1
    anchor, step = G.anchor[k], G.step[k]
    rows = []
    last_arrival: dict[float, int] = {}
    for i in range(LOOK, len(c) - 2 * WAIT - HOLD):
        a, s = anchor[i], step[i]
        if not (np.isfinite(a) and np.isfinite(s) and s > 0):
            continue
        half = s / 2
        for kk in range(int(np.floor((lo[i] - BAND * s - a) / half)), int(np.ceil((h[i] + BAND * s - a) / half)) + 1):
            line = a + kk * half
            if not (lo[i] <= line + BAND * s and h[i] >= line - BAND * s):
                continue
            prev_h, prev_l = h[i - LOOK : i], lo[i - LOOK : i]
            far = max(prev_h.max() - line, line - prev_l.min()) >= AWAY * s
            near_before = bool(((prev_l <= line + BAND * s) & (prev_h >= line - BAND * s))[-8:].any())
            key = round(line, 2)
            if not far or near_before or (key in last_arrival and i - last_arrival[key] < LOOK):
                continue
            last_arrival[key] = i
            bounce = 1 if c[i - 1] > line else -1  # came from above (into support): the bounce is a buy
            stop = (min(lo[i], line - BAND * s) - PAD * s) if bounce > 0 else (max(h[i], line + BAND * s) + PAD * s)
            rows.append(dict(t=m.index[i], kind="A at once (bounce)", r=trade(h, lo, c, i, bounce, c[i], stop, s, a)))
            for j in range(i + 1, i + WAIT):
                if (c[j] - line) * (-bounce) > BAND * s:  # closed through the line by more than the band
                    ext = c[j]
                    for q in range(j + 1, j + WAIT):
                        ext = max(ext, h[q]) if bounce > 0 else min(ext, lo[q])  # the extreme against the break
                        back = lo[q] <= line + BAND * s if bounce > 0 else h[q] >= line - BAND * s
                        if back and (c[q] - line) * (-bounce) > 0:
                            stop = ext + PAD * s if bounce > 0 else ext - PAD * s
                            r = trade(h, lo, c, q, -bounce, c[q], stop, s, a)
                            rows.append(dict(t=m.index[i], kind="C broken, back, then trade", r=r))
                            break
                    break
                if j - i + 1 >= BOX_N:
                    box_h, box_l = h[j - BOX_N + 1 : j + 1].max(), lo[j - BOX_N + 1 : j + 1].min()
                    overlaps = box_l <= line + BAND * s and box_h >= line - BAND * s
                    if box_h - box_l <= BOX_H * s and overlaps:
                        for q in range(j + 1, j + WAIT):
                            if c[q] > box_h or c[q] < box_l:
                                side = 1 if c[q] > box_h else -1
                                stop = box_l - PAD * s if side > 0 else box_h + PAD * s
                                way = "bounce" if side == bounce else "through"
                                r = trade(h, lo, c, q, side, c[q], stop, s, a)
                                rows.append(dict(t=m.index[i], kind=f"B consolidate, then {way}", r=r))
                                break
                            box_h, box_l = max(box_h, h[q]), min(box_l, lo[q])
                        break
    R = pd.DataFrame(rows).dropna()
    out = []
    for name, a0, b0 in PERIODS:
        P = R[(R.t >= a0) & (R.t < b0)]
        g = P.groupby("kind").r.agg(n="size", R_per_trade="mean")
        g["period"] = name
        out.append(g.reset_index())
    X = pd.concat(out)
    pd.set_option("display.width", 220)
    print("R a trade by period (after the 0.35 USD spread):")
    print(X.pivot(index="kind", columns="period", values="R_per_trade")[[p[0] for p in PERIODS]].round(3).to_string())
    print("\ntrades by period:")
    print(X.pivot(index="kind", columns="period", values="n")[[p[0] for p in PERIODS]].to_string())
    print("\nall periods:")
    print(R.groupby("kind").r.agg(n="size", R_per_trade="mean", win=lambda x: (x > 0).mean() * 100).round(3).to_string())


if __name__ == "__main__":
    main()
