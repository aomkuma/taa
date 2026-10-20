"""Audit 4 on the real bars: the ZigZags and the zones.

A. fingerprint.zigzag as committed (git HEAD) against the fixed one (audit2's start-up fix) on the series the callers
   build: M1 / M5 / M15 / H1 from plib.START (2023-08-01) and from the developer's WARM_START (2025-09-01), ATR(14),
   k = 2 and 3, and M1 with a fixed 10-USD threshold. Which pivots differ, and when.
B. Look-ahead: at 100 random decision bars per series in the learning parts, every bar after the decision is replaced
   by its mirror around the decision close (and the ATR recomputed); the pivots confirmed by the decision bar must
   be the same. Both fingerprint.zigzag and the developer's patterns.zigzag (imported read only).
C. zones.py on the real H1 of the learning parts: every swing is known at the avail of the 2nd bar after it, and
   levels_at at 100 random moments is the same when every M1 bar after the moment is replaced by its mirror.

No exam row is read (the NEW store with open_time < 2026-04-18).

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_swings.py
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
AG = ROOT / "research" / "2026-10-18-moments" / "agents"
sys.path.insert(0, str(AG.parent))
sys.path.insert(0, str(AG / "precursors"))
sys.path.insert(0, str(AG / "dev"))
sys.path.insert(0, str(AG / "audit2"))
import fingerprint  # noqa: E402
import foundation as F  # noqa: E402
import indicators  # noqa: E402
import patterns as P  # noqa: E402  (the developer's, read only)
import plib  # noqa: E402
import zones  # noqa: E402
from check_dst import m1_before_exam  # noqa: E402

LEARN = (plib.LEARN_START, plib.EXAM_START)
WARM_START = pd.Timestamp("2025-09-01", tz="UTC")


def head_zigzag():
    src = subprocess.run(  # noqa: S603, S607 - git, read only
        ["git", "show", "HEAD:research/2026-10-18-moments/agents/precursors/fingerprint.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    mod = types.ModuleType("fingerprint_head")
    mod.__file__ = str(AG / "precursors" / "fingerprint.py")
    exec(compile(src, "fingerprint_head", "exec"), mod.__dict__)  # noqa: S102 - the committed file itself
    return mod.zigzag


def tf_series(m: pd.DataFrame, tf: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex]:
    if tf == "M1":
        h, lo, c = (m[k].to_numpy(float) for k in ("high", "low", "close"))
        t = m.index
    else:
        b = indicators.bars(m, {"M5": "5min", "M15": "15min", "H1": "1h"}[tf])
        h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
        t = pd.DatetimeIndex(b["last"])
    return h, lo, c, t


def part_a(m_all: pd.DataFrame) -> None:
    old = head_zigzag()
    print("A. fingerprint.zigzag: git HEAD against the fixed one")
    for start in (plib.START, WARM_START):
        m = m_all[m_all.index >= start]
        for tf in ("M1", "M5", "M15", "H1"):
            h, lo, c, t = tf_series(m, tf)
            atr = F.atr(h, lo, c, 14)
            cases = [(f"ATR x {k:g}", atr, k) for k in (2.0, 3.0)]
            if tf == "M1":
                cases.append(("10 USD", np.full(len(h), 5.0), 2.0))
            for name, a, k in cases:
                po, pn = old(h, lo, a, k), fingerprint.zigzag(h, lo, a, k)
                so = set(zip(*(x.tolist() for x in po), strict=True))
                sn = set(zip(*(x.tolist() for x in pn), strict=True))
                diff = so ^ sn
                self_conf = int((po[3] <= po[0]).sum())
                twice = len(po[0]) - len(np.unique(po[0]))
                last = max((t[x[0]] for x in diff), default=None)
                print(
                    f"  from {start:%Y-%m-%d} {tf:3} {name:9}: HEAD {len(po[0])} pivots (confirmed by their own bar "
                    f"{self_conf}, a bar twice {twice}); fixed {len(pn[0])}; differing {len(diff)}, the last at {last}"
                )


def mirrored(h, lo, c, d):
    """Bars after d replaced by their mirror around the close of d."""
    h2, lo2, c2 = h.copy(), lo.copy(), c.copy()
    piv = c[d]
    h2[d + 1 :], lo2[d + 1 :], c2[d + 1 :] = 2 * piv - lo[d + 1 :], 2 * piv - h[d + 1 :], 2 * piv - c[d + 1 :]
    return h2, lo2, c2


def known(p, d):
    keep = p[3] <= d
    return [x[keep].tolist() for x in p]


def part_b(m_all: pd.DataFrame) -> None:
    print("\nB. Look-ahead: the future replaced by its mirror, the pivots confirmed by the decision bar unchanged")
    m = m_all[m_all.index >= WARM_START]
    rng = np.random.default_rng(19)
    for tf in ("M1", "M5", "H1"):
        h, lo, c, t = tf_series(m, tf)
        atr = F.atr(h, lo, c, 14)
        inside = np.flatnonzero((t >= LEARN[0]) & (t < LEARN[1]))
        ds = np.sort(rng.choice(inside, 100, replace=False))
        if tf == "M1":
            h, lo, c, atr = h[: ds[-1] + 3000], lo[: ds[-1] + 3000], c[: ds[-1] + 3000], atr[: ds[-1] + 3000]
        full_fp, full_dev = fingerprint.zigzag(h, lo, atr, 2.0), P.zigzag(h, lo, atr, 2.0)
        same_fp = same_dev = changed_future = 0
        for d in ds:
            h2, lo2, c2 = mirrored(h, lo, c, d)
            a2 = F.atr(h2, lo2, c2, 14)
            assert np.allclose(a2[: d + 1], atr[: d + 1], equal_nan=True)
            same_fp += known(fingerprint.zigzag(h2, lo2, a2, 2.0), d) == known(full_fp, d)
            same_dev += known(P.zigzag(h2, lo2, a2, 2.0), d) == known(full_dev, d)
            p_after = fingerprint.zigzag(h2, lo2, a2, 2.0)
            changed_future += len(p_after[0]) != len(full_fp[0]) or not np.array_equal(p_after[0], full_fp[0])
        print(
            f"  {tf}: 100 decisions; fingerprint same {same_fp}, the developer's same {same_dev}; the replaced future "
            f"changed the whole pivot list in {changed_future} of 100 (the check has power)"
        )


def zones_y(m: pd.DataFrame) -> dict:
    b1, d1 = indicators.bars(m, "1h"), indicators.bars(m, "1D")
    h, lo, c = (b1[k].to_numpy(float) for k in ("high", "low", "close"))
    return dict(S=zones.swings(b1), avail=pd.DatetimeIndex(b1["avail"]).as_unit("ns").asi8, atr=F.atr(h, lo, c, 14),
                h=h, lo=lo, d_avail=pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8, d_high=d1.high.to_numpy(float),
                d_low=d1.low.to_numpy(float), b1=b1)


def part_c(m_all: pd.DataFrame) -> None:
    print("\nC. zones.py on the real H1 of the learning parts")
    m = m_all[(m_all.index >= WARM_START) & (m_all.index < LEARN[1])]
    Y = zones_y(m)
    S, av = Y["S"], Y["avail"]
    ok = int((S.known.to_numpy() == av[S.i.to_numpy() + zones.K]).sum())
    after = int((S.known.to_numpy() > av[S.i.to_numpy()]).sum())
    print(f"  {len(S)} swings: known at the avail of the 2nd bar after it {ok}; known after its own bar's avail {after}")
    rng = np.random.default_rng(23)
    ts = m.index[(m.index >= LEARN[0])]
    picks = np.sort(rng.choice(len(ts) - 3000, 100, replace=False))
    same = differ_power = 0
    for j in picks:
        t = ts[j] + pd.Timedelta(minutes=1)  # the decision at the close of M1 bar j
        cut = m.index <= ts[j]
        fut = m.loc[~cut].copy()
        piv = float(m.loc[ts[j], "close"])
        fut["high"], fut["low"] = 2 * piv - m.loc[~cut, "low"], 2 * piv - m.loc[~cut, "high"]
        fut["open"], fut["close"] = 2 * piv - m.loc[~cut, "open"], 2 * piv - m.loc[~cut, "close"]
        m2 = pd.concat([m.loc[cut], fut])
        Y2 = zones_y(m2)
        a, _ = zones.levels_at(Y, t.value, piv)
        b, _ = zones.levels_at(Y2, t.value, piv)
        same += a.reset_index(drop=True).equals(b.reset_index(drop=True))
        later = t + pd.Timedelta(days=3)
        a3, _ = zones.levels_at(Y, later.value, piv)
        b3, _ = zones.levels_at(Y2, later.value, piv)
        differ_power += not a3.reset_index(drop=True).equals(b3.reset_index(drop=True))
    print(f"  levels_at at 100 moments: the same with the future mirrored {same}; three days later they differ "
          f"{differ_power} of 100 (the check has power)")


def main() -> int:
    m_all = m1_before_exam()
    m_all = m_all[m_all.index >= plib.START][["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)
    part_a(m_all)
    part_b(m_all)
    part_c(m_all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
