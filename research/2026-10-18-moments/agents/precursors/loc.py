"""Where each event happens on the larger timeframes (owner, 2026-10-19: "trade at the edge of the larger timeframe,
not the middle - don't think in one layer"; notes.md "Where the event happens"). For every event of explore.py, at its
decision (closed bars only): on H1 and H4, where its price sits in that timeframe's 120-bar range (0 the low .. 1 the
high; beyond the range below 0 / above 1) and the distance to the nearest confirmed swing bottom below it and swing top
above it inside the window, in that timeframe's ATRs.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/loc.py
"""

from __future__ import annotations

import bisect
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
WIN = 120


def location(t_ns: np.ndarray, px: np.ndarray, Y: dict) -> pd.DataFrame:
    """Y: avail (ns), h, lo, atr, piv of the larger timeframe. For each decision time and price: pos, d_bot, d_top."""
    pidx, pval, ptyp, pconf = Y["piv"]
    conf = list(pconf)
    out = np.full((len(t_ns), 3), np.nan)
    for k, (t, p) in enumerate(zip(t_ns, px)):
        bi = int(np.searchsorted(Y["avail"], t, side="right")) - 1
        if bi < 0:
            continue
        a0 = max(bi - WIN + 1, 0)
        hi, lw = Y["h"][a0:bi + 1].max(), Y["lo"][a0:bi + 1].min()
        a = Y["atr"][bi]
        out[k, 0] = (p - lw) / (hi - lw) if hi > lw else 0.5
        n = bisect.bisect_right(conf, bi)  # the swings known at bi
        bots = [pval[j] for j in range(n) if ptyp[j] == -1 and pidx[j] >= a0 and pval[j] <= p]
        tops = [pval[j] for j in range(n) if ptyp[j] == 1 and pidx[j] >= a0 and pval[j] >= p]
        out[k, 1] = (p - max(bots)) / a if bots else np.nan
        out[k, 2] = (min(tops) - p) / a if tops else np.nan
    return pd.DataFrame(out, columns=["pos", "d_bot", "d_top"])


def location_grouped(t_ns: np.ndarray, px: np.ndarray, Y: dict) -> pd.DataFrame:
    """location() for many times at once (the same answers): the moments are grouped by the larger bar they fall after,
    the range and the known swings of that bar's window taken once, the nearest level below / above read for all the
    group's prices together."""
    pidx, pval, ptyp, pconf = Y["piv"]
    conf = np.asarray(pconf)
    out = np.full((len(t_ns), 3), np.nan)
    bi_all = np.searchsorted(Y["avail"], t_ns, side="right") - 1
    for bi in np.unique(bi_all):
        if bi < 0:
            continue
        k = np.nonzero(bi_all == bi)[0]
        p = px[k]
        a0 = max(bi - WIN + 1, 0)
        hi, lw = Y["h"][a0:bi + 1].max(), Y["lo"][a0:bi + 1].min()
        a = Y["atr"][bi]
        out[k, 0] = (p - lw) / (hi - lw) if hi > lw else 0.5
        n = int(np.searchsorted(conf, bi, side="right"))  # the swings known at bi (pconf sorted)
        sel = np.arange(n)[np.asarray(pidx[:n]) >= a0]
        bots = np.asarray(pval)[sel][np.asarray(ptyp)[sel] == -1]
        tops = np.asarray(pval)[sel][np.asarray(ptyp)[sel] == 1]
        if len(bots):
            below = np.where(bots[None, :] <= p[:, None], bots[None, :], -np.inf).max(axis=1)
            out[k, 1] = np.where(np.isfinite(below), (p - below) / a, np.nan)
        if len(tops):
            above = np.where(tops[None, :] >= p[:, None], tops[None, :], np.inf).min(axis=1)
            out[k, 2] = np.where(np.isfinite(above), (above - p) / a, np.nan)
    return pd.DataFrame(out, columns=["pos", "d_bot", "d_top"])


def main() -> None:
    import plib  # noqa: PLC0415
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415

    m = plib.load()
    m_av = (m.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8
    cl = m.close.to_numpy(float)
    Ys = {}
    for tf, rule in (("H1", "1h"), ("H4", "4h")):
        b = plib.tf_bars(m, rule)
        R = raw(b)
        Ys[tf] = dict(avail=pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, h=R["h"], lo=R["lo"], atr=R["atr"],
                      piv=zigzag(R["h"], R["lo"], R["atr"], ZZ_K))
    for name in ("pierces", "doubles"):
        E = pd.read_parquet(HERE / f"explore_{name}.parquet").reset_index(drop=True)
        t = pd.DatetimeIndex(E.t).as_unit("ns").asi8
        px = cl[np.searchsorted(m_av, t, side="right") - 1]  # the last M1 close at the decision (the event bar's close)
        for tf, Y in Ys.items():
            L = location(t, px, Y)
            for c in L.columns:
                E[f"{tf}_{c}"] = L[c].to_numpy()
        E["px"] = px
        E.to_parquet(HERE / f"explore_{name}.parquet")
        print(name, len(E), "located", flush=True)


if __name__ == "__main__":
    main()
