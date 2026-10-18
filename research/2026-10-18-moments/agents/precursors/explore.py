"""M, W and stop hunts read from how price really moves (owner, 2026-10-19: "don't read them from theory - read them from
the market's real price movement"; notes.md "M and W only"). Events are collected wide, never picked by what followed:
- every first pierce of a confirmed swing level (the latest top or bottom of the 3-ATR ZigZag): its depth beyond the
  level, whether the bar closed back inside, the level's age; the reversal's side is against the pierce;
- every double bottom / top (three alternating swings): the second extreme against the first (in ATRs and in shares of
  the height), the bars between, the height; two entries - the second extreme's turn (its confirmation) and the first
  close beyond the neckline;
and what price did next from the following M1 open: the furthest the event's way and against it within 60 minutes, in
the timeframe's ATRs, and the first passage at 1 and 2 ATRs. Tables on the learning half; the exam confirms once.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/explore.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mw import first_passage  # noqa: E402

TFS = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h"}
HORIZON = 60  # M1 bars


def pierces(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: np.ndarray, piv: tuple) -> pd.DataFrame:
    """For each swing, the first bar after its confirmation whose high goes above it (a top) or low below it (a bottom),
    before the next swing of its kind is confirmed: the bar, the level, the depth beyond it and where the close is
    (both in ATRs of that bar, positive = back inside for the close), the level's age in bars."""
    pidx, pval, ptyp, pconf = piv
    out = []
    for k in range(len(pidx)):
        typ = int(ptyp[k])
        nxt = next((m for m in range(k + 1, len(pidx)) if ptyp[m] == typ), None)
        end = int(pconf[nxt]) if nxt is not None else len(c)
        lvl = float(pval[k])
        for i in range(int(pconf[k]) + 1, end):
            if (typ == 1 and h[i] > lvl) or (typ == -1 and lo[i] < lvl):
                a = atr[i]
                depth = (h[i] - lvl) / a if typ == 1 else (lvl - lo[i]) / a
                inside = (lvl - c[i]) / a if typ == 1 else (c[i] - lvl) / a
                out.append(dict(i=i, level_type=typ, side=-typ, level=lvl, depth=depth, back=inside, closed_back=inside > 0,
                                age=i - int(pidx[k])))
                break
    return pd.DataFrame(out, columns=["i", "level_type", "side", "level", "depth", "back", "closed_back", "age"])


def doubles(c: np.ndarray, atr: np.ndarray, piv: tuple) -> pd.DataFrame:
    """Every three alternating swings A, B, C (W: trough, peak, trough; M: the mirror): the second extreme against the
    first in ATRs (at C) and in shares of the height (positive = the second bottom higher / the second top lower), the
    bars between A and C, the height in ATRs; the entries: C's confirmation bar ('turn') and the first close beyond B
    while A, B, C are the latest swings ('neck', -1 when none)."""
    pidx, pval, ptyp, pconf = piv
    out = []
    for x in range(2, len(pidx)):
        a, b = x - 2, x - 1
        side = 1 if ptyp[x] == -1 else -1  # a W ends on a trough: a buy
        height = (pval[b] - min(pval[a], pval[x])) if side > 0 else (max(pval[a], pval[x]) - pval[b])
        second = (pval[x] - pval[a]) * side  # > 0: the second bottom higher (W) / the second top lower (M)
        last = int(pconf[x + 1]) - 1 if x + 1 < len(pconf) else len(c) - 1
        beyond = np.nonzero((c[int(pconf[x]):last + 1] - pval[b]) * side > 0)[0]
        neck = int(pconf[x]) + int(beyond[0]) if len(beyond) else -1
        if neck >= 0 and ((c[int(pidx[x]) + 1:int(pconf[x])] - pval[b]) * side > 0).any():
            neck = -1  # broken before C was known: not a fresh break
        a_c = atr[int(pidx[x])]
        out.append(dict(kind="W" if side > 0 else "M", side=side, second_atr=second / a_c, second_share=second / height,
                        gap=int(pidx[x] - pidx[a]), height_atr=height / a_c, turn=int(pconf[x]), neck=neck, b=float(pval[b])))
    return pd.DataFrame(out, columns=["kind", "side", "second_atr", "second_share", "gap", "height_atr", "turn", "neck", "b"])


def excursions(o1: np.ndarray, h1: np.ndarray, l1: np.ndarray, j0: np.ndarray, side: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """From the M1 open of j0: the furthest price went the event's way and against it within horizon bars (j0 included)."""
    fav, adv = np.full(len(j0), np.nan), np.full(len(j0), np.nan)
    for k, (j, s) in enumerate(zip(j0, side)):
        if j >= len(o1):
            continue
        hi, lw = h1[j:j + horizon].max(), l1[j:j + horizon].min()
        fav[k], adv[k] = ((hi - o1[j]), (o1[j] - lw)) if s > 0 else ((o1[j] - lw), (hi - o1[j]))
    return fav, adv


def outcomes(E: pd.DataFrame, bar: str, m: dict, tf_avail: np.ndarray, atr: np.ndarray) -> pd.DataFrame:
    """Add, for the decision at the close of tf bar E[bar]: the M1 entry bar, the excursions and the first passages."""
    E = E[E[bar] >= 0].copy()
    t = tf_avail[E[bar].to_numpy()]
    E["t"] = pd.to_datetime(t, utc=True)
    E["j0"] = np.searchsorted(m["ot"], t)
    a = atr[E[bar].to_numpy()]
    fav, adv = excursions(m["o"], m["h"], m["l"], E.j0.to_numpy(), E.side.to_numpy(), HORIZON)
    E["fav"], E["adv"] = fav / a, adv / a
    for d in (1, 2):
        E[f"fp{d}"] = [first_passage(m["o"], m["h"], m["l"], int(j), int(s), float(d * x), HORIZON * 4) if j < len(m["o"]) else "none"
                       for j, s, x in zip(E.j0, E.side, a)]
    return E


def main() -> None:
    import plib  # noqa: PLC0415
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415

    plib.gold.below_normal_priority()
    mm = plib.load()
    m = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), l=mm.low.to_numpy(float), ot=mm.index.as_unit("ns").asi8)
    P, D = [], []
    for tf, rule in TFS.items():
        b = plib.tf_bars(mm, rule)
        R = raw(b)
        piv = zigzag(R["h"], R["lo"], R["atr"], ZZ_K)
        avail = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
        e = outcomes(pierces(R["h"], R["lo"], R["c"], R["atr"], piv), "i", m, avail, R["atr"])
        e["tf"] = tf
        P.append(e)
        dd = doubles(R["c"], R["atr"], piv)
        for entry in ("turn", "neck"):
            x = outcomes(dd, entry, m, avail, R["atr"])
            x["tf"], x["entry"] = tf, entry
            D.append(x)
        print(tf, "pierces", len(e), "doubles", len(dd), flush=True)
    Pi = pd.concat(P, ignore_index=True)
    Do = pd.concat(D, ignore_index=True)
    first = pd.Timestamp("2023-11-01", tz="UTC")
    Pi, Do = Pi[Pi.t >= first], Do[Do.t >= first]
    Pi.to_parquet(HERE / "explore_pierces.parquet")
    Do.to_parquet(HERE / "explore_doubles.parquet")
    print("saved", len(Pi), len(Do))


if __name__ == "__main__":
    main()
