"""Build the precursor dataset (notes.md): the 10 U / 5 U run catalogues and every focus-window decision minute with
its six-timeframe chart state and labels.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/build.py
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

import plib
from plib import HERE

T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.0f}s] {msg}", flush=True)


def labels(m: pd.DataFrame, C: pd.DataFrame, dec: np.ndarray, xu: float, tag: str) -> dict[str, np.ndarray]:
    """For decision bars `dec` (indices into m): a run of each side starting within the next 15 minutes, the
    side that reaches X first from the next open, and the early entry's adverse move before the run."""
    tmin = plib.minutes(m.index)
    o, h, lo = (m[k].to_numpy(float) for k in ("open", "high", "low"))
    n = len(m)
    out: dict[str, np.ndarray] = {}
    for side, nm in ((1, "up"), (-1, "dn")):
        st = C[C.side == side].i.to_numpy()
        st_t = tmin[st]
        p = np.searchsorted(st_t, tmin[dec] + 1, side="left")  # the first run starting after the decision bar
        ok = p < len(st)
        pj = np.minimum(p, len(st) - 1)
        gap = np.where(ok, st_t[pj] - tmin[dec], 10**9)
        has = ok & (gap >= 1) & (gap <= plib.LOOKAHEAD)
        out[f"{tag}_next_{nm}"] = has
        out[f"{tag}_lead_{nm}"] = np.where(has, gap, np.nan)
        e = o[np.minimum(dec + 1, n - 1)]
        spx = C[C.side == side].start_px.to_numpy()[pj]
        mae = (e - spx) if side > 0 else (spx - e)
        out[f"{tag}_mae_{nm}"] = np.where(has, np.maximum(mae, 0) / (e / plib.REF), np.nan)
        out[f"{tag}_size_{nm}"] = np.where(has, C[C.side == side].size_u.to_numpy()[pj], np.nan)
    # the first of +X / -X from the next open within 60 minutes
    e = o[np.minimum(dec + 1, n - 1)]
    X = xu * e / plib.REF
    first = np.zeros(len(dec))
    done = np.zeros(len(dec), bool)
    for k in range(1, plib.FIRST_HZ + 1):
        j = np.minimum(dec + k, n - 1)
        inwin = (dec + k < n) & (tmin[j] - tmin[dec] <= plib.FIRST_HZ)
        up = inwin & (h[j] >= e + X)
        dn = inwin & (lo[j] <= e - X)
        both = up & dn & ~done
        first = np.where(~done & up & ~dn, 1, np.where(~done & dn & ~up, -1, first))
        first = np.where(both, np.nan, first)
        done |= up | dn
    out[f"{tag}_first"] = first
    return out


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.load()
    log(f"M1 {len(m)} bars {m.index[0]} .. {m.index[-1]}")
    cats = {}
    for xu in (10, 5):
        C = plib.catalogue(m, xu)
        C.to_parquet(HERE / f"runs_{xu}.parquet")
        cats[xu] = C
        log(f"catalogue {xu} U: {len(C)} runs")
    W = plib.window_mask(m.index)
    inany = W.any(axis=1).to_numpy() & (m.index >= pd.Timestamp("2023-11-01", tz="UTC"))
    dec = np.nonzero(inany)[0]
    dec = dec[dec < len(m) - 1]
    log(f"decision minutes: {len(dec)}")
    D = pd.DataFrame(index=m.index[dec])
    D["i"] = dec
    for name in W.columns:
        D[f"w_{name}"] = W[name].to_numpy()[dec]
    D["win"] = W.iloc[dec].idxmax(axis=1).to_numpy()  # the first listed window it belongs to
    D["half"] = pd.cut(D.index, plib.HALVES, labels=plib.HLAB, right=False).astype(str)
    D["u"] = m.open.to_numpy()[dec] / plib.REF
    D["spread_u"] = m.spread.to_numpy()[dec] * 0.01 / D["u"]
    for xu, C in cats.items():
        for k, v in labels(m, C, dec, xu, f"x{xu}").items():
            D[k] = v
    log("labels done")
    atr15 = plib.m15_atr(m)
    D["atr15_u"] = atr15[dec] / D["u"].to_numpy()
    F = plib.m1_forms(m, atr15)
    for col in F.columns:
        D[col] = F[col].to_numpy()[dec]
    log("M1 forms done")
    # the timeframe states, as of the decision (the M1 bar's close = its open + 1 minute)
    S1 = plib.tf_state(m.reset_index(drop=True).rename(columns={"tick_volume": "tv"}).assign(
        avail=m.index + pd.Timedelta(minutes=1)), "M1")
    for col in S1.columns[1:]:
        D[col] = S1[col].to_numpy()[dec]
    key = pd.DataFrame({"t": m.index[dec] + pd.Timedelta(minutes=1)})
    for tf, rule in plib.TFS.items():
        b = plib.tf_bars(m, rule)
        s = plib.tf_state(b, tf).sort_values("avail")
        j = pd.merge_asof(key, s, left_on="t", right_on="avail", direction="backward")
        for col in s.columns[1:]:
            D[col] = j[col].to_numpy()
        D[f"{tf}_age"] = (key.t - j.avail).dt.total_seconds().to_numpy() / 60
        log(f"{tf} state done ({len(b)} bars)")
    # US releases
    rel = pd.DatetimeIndex(plib.gold.releases().t).sort_values()
    tt = D.index + pd.Timedelta(minutes=1)
    p = rel.searchsorted(tt)
    D["min_since_rel"] = [(t - rel[q - 1]).total_seconds() / 60 if q > 0 else np.nan for q, t in zip(p, tt)]
    D["min_to_rel"] = [(rel[q] - t).total_seconds() / 60 if q < len(rel) else np.nan for q, t in zip(p, tt)]
    D.to_parquet(HERE / "decisions.parquet")
    log(f"saved {D.shape}")


if __name__ == "__main__":
    main()
