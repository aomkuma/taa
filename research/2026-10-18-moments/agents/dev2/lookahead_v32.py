"""The look-ahead check for V3-2 (rule R10): at cut moments spread over P1 / P2, every M1 bar after the cut is replaced by
another path (the bars reflected about the last close before the cut: high' = 2c - low, low' = 2c - high, ...), and
the bars end 2 days after the cut. Every entry decided by the cut must be unchanged: its decision, side, stop(s), S, H,
the alignment / side-source columns, the target candidates and the trail steps dated by the cut. With power: a planted
look-ahead (the structure read 15 minutes ahead) must fail it.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/lookahead_v32.py > research/2026-10-18-moments/agents/dev2/out_lookahead_v32.txt
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402
import v32  # noqa: E402

CUTS = ["2025-11-06 01:10", "2025-12-10 15:20", "2026-01-08 06:40", "2026-02-12 14:50", "2026-03-11 00:45", "2026-04-08 16:05"]
COLS = ["side", "stop", "stop_ext", "mirror_of", "mirror_dist", "S", "H", "window", "al_label", "al_bias", "al_label_bar",
        "al_bias_bar", "src_side", "src_side_bias", "src_side_bar", "src_side_bias_bar", "src_trend", "src_trend_bias"]


def reflect(m: pd.DataFrame, cut: pd.Timestamp) -> pd.DataFrame:
    a = m[m.index < cut]
    b = m[(m.index >= cut) & (m.index < cut + pd.Timedelta(days=2))].copy()
    c = float(a.close.iloc[-1])
    o, h, lo, cl = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
    b["open"], b["high"], b["low"], b["close"] = 2 * c - o, 2 * c - lo, 2 * c - h, 2 * c - cl
    return pd.concat([a, b])


def comparable(df: pd.DataFrame, cut_ns: int) -> pd.DataFrame:
    if not len(df) or "t_dec" not in df:
        return pd.DataFrame()
    x = df[df.t_dec <= cut_ns].copy()
    out = x[["t_dec", "j_dec"] + [c for c in COLS if c in x]].copy()
    if "cands" in x:
        out["cands"] = [tuple(sorted(round(v, 9) for v in c)) for c in x.cands]
        out["trail"] = [tuple((t, round(v, 9)) for t, v in tr if t <= cut_ns) for tr in x.trail]
    return out.sort_values(["t_dec", "side"]).reset_index(drop=True)


def equal(a: pd.DataFrame, b: pd.DataFrame) -> tuple[int, int]:
    if len(a) != len(b):
        return 0, max(len(a), len(b))
    same = 0
    for (_, r), (_, s) in zip(a.iterrows(), b.iterrows()):
        ok = True
        for c in a.columns:
            u, v = r[c], s[c]
            if isinstance(u, float) and isinstance(v, float):
                ok &= (np.isnan(u) and np.isnan(v)) or abs(u - v) < 1e-9
            else:
                ok &= u == v
        same += bool(ok)
    return same, len(a)


def run(m: pd.DataFrame, cuts, planted: bool = False) -> tuple[int, int]:
    tot_same = tot = 0
    for cs in cuts:
        cut = pd.Timestamp(cs, tz="UTC")
        cut_ns = int(cut.value)
        base = m[m.index < cut + pd.Timedelta(days=2)]
        sp_a = v32.build(v32.market(base))
        sp_b = v32.build(v32.market(reflect(m, cut)))
        same = n = 0
        for k in sp_a:
            if k in ("rec", "tur", "levels"):
                continue
            s1, n1 = equal(comparable(sp_a[k], cut_ns), comparable(sp_b[k], cut_ns))
            same += s1
            n += n1
        print(f"{'PLANTED ' if planted else ''}cut {cs} UTC: {same} of {n} entries decided by the cut unchanged", flush=True)
        tot_same += same
        tot += n
    return tot_same, tot


def main() -> None:
    t0 = time.time()
    m = W.load_learning()
    s, n = run(m, CUTS)
    print(f"ALL: {s} of {n} unchanged -> {'PASSED' if s == n else 'FAILED'} ({time.time() - t0:.0f} s)", flush=True)
    # the power: the structure read 15 minutes ahead must change readings decided by the cut
    orig = v32.reading

    def ahead(mk, tf, what, t_ns, mode="path"):
        return orig(mk, tf, what, np.asarray(t_ns, np.int64) + 15 * W.NS_MIN, mode)

    v32.reading = ahead
    s, n = run(m, CUTS[:2], planted=True)
    v32.reading = orig
    print(f"PLANTED look-ahead (the structure 15 min ahead): {s} of {n} unchanged -> {'FAILED (caught)' if s < n else 'PASSED (missed)'}")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
