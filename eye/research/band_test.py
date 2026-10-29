"""Which levels does gold respect - the bands of BOT_RULES rule 8, against a control.

The owner, 2026-10-29: "find the answers by testing and proof" - which levels are major enough to block the
take-profit. Bands as rule 8 builds them: fixed ZigZag pivots of the timeframe (H1 or H4), from the last 500
bars, at least 24 h old, each a band of +- 0.10 x the median of the last 20 legs. Every time an M5 bar reaches
a band from outside (from below: its high at or above the lower edge after a close below it; from above the
mirror), which comes first within 24 h: a turn - W back beyond the near edge - or a break - W beyond the far
edge (W = 2 x the half-width; a bar touching both is not counted). The control: the same procedure on bands
centred at the midpoints of the same legs. Split by how many of the timeframe's eligible pivots lie inside the
band. Pivots come from one ZigZag over the whole stored frame, used from their confirmation bar's close (the
research scripts' convention). Expectation: lean_levels/EXPECTATION.md.
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e  # noqa: E402

OUT = HERE / "lean_levels"
HORIZON, LEVEL_BARS, AGE_H, BAND_FRAC, LEGS = 288, 500, 24.0, 0.10, 20


def bands_at(piv: list, ends: pd.DatetimeIndex, now: pd.Timestamp, n_now: int):
    """(real bands [(lo, hi, touches)], control bands, half) at ``now``."""
    known = [s for s in piv if ends[s.confirm_pos] <= now]
    if len(known) < LEGS + 1:
        return [], [], 0.0
    legs = [abs(b.price - a.price) for a, b in pairwise(known)][-LEGS:]
    half = BAND_FRAC * float(np.median(legs))
    limit = now - pd.Timedelta(hours=AGE_H)
    elig = [s for s in known if s.pivot_pos >= n_now - LEVEL_BARS and pd.Timestamp(s.pivot_at) <= limit]
    prices = np.array([s.price for s in elig])
    real = [(q - half, q + half, int(np.sum(np.abs(prices - q) <= half))) for q in prices]
    mids = [(a.price + b.price) / 2 for a, b in pairwise(elig)]
    ctrl = [(q - half, q + half, int(np.sum(np.abs(prices - q) <= half))) for q in mids]
    return real, ctrl, half


def outcome(hi, lo, j: int, from_below: bool, b_lo: float, b_hi: float, w: float) -> str:
    for i in range(j, min(j + HORIZON, len(hi))):
        if from_below:
            turn, brk = lo[i] <= b_lo - w, hi[i] >= b_hi + w
        else:
            turn, brk = hi[i] >= b_hi + w, lo[i] <= b_lo - w
        if turn and brk:
            return "both"
        if turn:
            return "turn"
        if brk:
            return "break"
    return "none"


def main() -> None:
    full = bot2e.load_frames()
    m5 = full["M5"]
    hi, lo, cl = (m5[c].to_numpy(np.float64) for c in ("high", "low", "close"))
    m5_end = m5.index + pd.Timedelta(minutes=5)
    rows = []
    for tf in ("H1", "H4"):
        df = full[tf]
        ends = df.index + bot2e.STEP[tf]
        piv = bot2e._zigzag(df)
        hours = pd.date_range(m5.index[0].ceil("h"), m5_end[-1], freq="h")
        for h0, h1 in pairwise(hours):
            n_now = int(ends.searchsorted(h0, side="right"))
            real, ctrl, half = bands_at(piv, ends, h0, n_now)
            if not real:
                continue
            a = int(m5_end.searchsorted(h0, side="right"))  # first M5 bar ending after h0
            b = int(m5_end.searchsorted(h1, side="right"))
            for kind, bands in (("real", real), ("control", ctrl)):
                best: dict[tuple[int, bool], tuple[float, float, int]] = {}
                for j in range(max(a, 1), min(b, len(hi))):
                    for b_lo, b_hi, n in bands:
                        if cl[j - 1] < b_lo <= hi[j]:
                            key = (j, True)
                        elif cl[j - 1] > b_hi >= lo[j]:
                            key = (j, False)
                        else:
                            continue
                        if key not in best or n > best[key][2]:
                            best[key] = (b_lo, b_hi, n)
                for (j, fb), (b_lo, b_hi, n) in best.items():
                    rows.append(
                        {
                            "tf": tf,
                            "kind": kind,
                            "at": m5.index[j],
                            "from_below": fb,
                            "touches": n,
                            "half": round(half, 2),
                            "result": outcome(hi, lo, j, fb, b_lo, b_hi, 2 * half),
                        }
                    )
    ev = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    ev.to_csv(OUT / "band_events.csv", index=False)
    lines = [f"events: {len(ev)}  M5 {m5.index[0]} .. {m5.index[-1]}", ""]
    for tf in ("H1", "H4"):
        lines.append(f"{tf}: turn rate (turn / (turn + break)), n, +/- 95 %")
        for kind in ("real", "control"):
            for grp, sel in (("all", None), ("1 pivot", 1), ("2 pivots", 2), ("3+ pivots", 3)):
                s = ev[(ev.tf == tf) & (ev.kind == kind) & ev.result.isin(["turn", "break"])]
                if sel is not None:
                    s = s[s.touches >= 3] if sel == 3 else s[s.touches == sel]
                if len(s) == 0:
                    continue
                r = float(np.mean(s.result == "turn"))
                ci = 1.96 * np.sqrt(r * (1 - r) / len(s))
                lines.append(f"  {kind:7} {grp:9}: {r:.3f} n {len(s):5} +/- {ci:.3f}")
        lines.append("")
    text = "\n".join(lines)
    (OUT / "band_summary.txt").write_bytes(text.encode("utf-8"))
    print(text)


if __name__ == "__main__":
    main()
