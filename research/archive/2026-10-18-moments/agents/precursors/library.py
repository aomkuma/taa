"""The evidence library (notes.md "The evidence library"): for every focus-window decision minute, the price set of
six timeframes (24-point shapes), 82 state codes (indicators, structure, levels, support / resistance of M15 .. H4)
and what followed (the owner's classes). Closed bars only.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/library.py
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import plib
from plib import HERE

T0 = time.time()
NPTS = 24
LOOK = {"M1": 90, "M5": 72, "M15": 64, "M30": 64, "H1": 72, "H4": 60}
RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
SR_BARS = {"M15": 384, "M30": 192, "H1": 240, "H4": 180}
SR_MERGE, SR_NEAR = 0.25, 0.3


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.0f}s] {msg}", flush=True)


# ---------------------------------------------------------------- indicators on a timeframe's bars
def indicators(b: pd.DataFrame) -> pd.DataFrame:
    """The state codes of a timeframe's bars from the MT5-exact indicators (foundation.py)."""
    import foundation as F  # noqa: PLC0415

    hv, lv_, cv = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
    atr = pd.Series(F.atr(hv, lv_, cv, 14), index=b.index)
    rsi = pd.Series(F.rsi(cv, 14), index=b.index)
    line, _sig = F.macd(cv)
    hist = pd.Series(line, index=b.index)  # MT5 draws the MACD line as the histogram
    k_, d_ = F.stochastic(hv, lv_, cv, 14, 3, 3)
    k, dd = pd.Series(k_, index=b.index), pd.Series(d_, index=b.index)
    mid_, up_, _lo = F.bands(cv, 20, 2.0)
    mid, sd = pd.Series(mid_, index=b.index), pd.Series((up_ - mid_) / 2.0, index=b.index)
    c = b.close
    pdi_, ndi_, adx_ = F.adx(hv, lv_, cv, 14)
    pdi, ndi, adx = (pd.Series(x, index=b.index) for x in (pdi_, ndi_, adx_))
    st = plib.tf_state(b.assign(tv=0), "x")
    codes = pd.DataFrame(index=b.index)
    codes["tide"] = st.x_tide.map({-1: 0, 0: 1, 1: 2}).to_numpy()
    codes["struct"] = st.x_struct.map({0: 0, 1: 1, -1: 2, 2: 3, 3: 4}).to_numpy()
    codes["leg"] = st.x_leg.map({-1: 0, 0: 1, 1: 2}).to_numpy()
    codes["rsi"] = np.digitize(rsi.fillna(50), [30, 45, 55, 70])
    codes["macd"] = (hist > 0).astype(int) * 2 + (hist > hist.shift(1)).astype(int)
    codes["stoch"] = np.digitize(k.fillna(50), [20, 80.0001]) * 2 + (k > dd).astype(int)
    codes["bb"] = np.where(c < mid - 2 * sd, 0, np.where(c < mid, 1, np.where(c <= mid + 2 * sd, 2, 3)))
    codes["adx"] = np.where(adx < 20, 0, np.where(pdi > ndi, 1, 2))
    codes["atrp"] = np.digitize(st.x_atr_pct.fillna(0.5).to_numpy(), [1 / 3, 2 / 3])
    codes["pos"] = np.digitize(st.x_pos20.fillna(0.5).to_numpy(), [1 / 3, 2 / 3])
    codes = codes.fillna(0).astype(np.int8)
    return codes, atr.to_numpy(), st


# ---------------------------------------------------------------- support / resistance of a timeframe
def sr_levels(b: pd.DataFrame, atr: np.ndarray, nbars: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """For every bar: the levels (prices, swings) of the confirmed 7-bar fractals (3 each side, known 3 bars later) of
    the last `nbars` bars, merged into levels no wider than SR_MERGE x that bar's ATR (foundation.merge_levels)."""
    import foundation as F  # noqa: PLC0415

    h, lo = b.high.to_numpy(float), b.low.to_numpy(float)
    ph, pl = F.fractals(h, lo, 3)
    piv = np.r_[ph, pl]
    val = np.r_[h[ph], lo[pl]]
    order = np.argsort(piv + 3, kind="stable")
    known, piv, val = (piv + 3)[order], piv[order], val[order]
    out = []
    for bi in range(len(b)):
        hi_k = np.searchsorted(known, bi, side="right")  # swings confirmed by the close of bar bi
        sel = piv[:hi_k] >= bi - nbars
        tol = SR_MERGE * atr[bi] if np.isfinite(atr[bi]) else 0.0
        out.append(F.merge_levels(val[:hi_k][sel], tol))
    return out


def sr_codes(levels, bi: np.ndarray, price: np.ndarray, back: np.ndarray, atr_b: np.ndarray):
    loc = np.zeros(len(bi), np.int8)
    imp = np.zeros(len(bi), np.int8)
    order = np.argsort(bi, kind="stable")
    bs = bi[order]
    cuts = np.r_[0, np.nonzero(np.diff(bs))[0] + 1, len(bs)]
    for a, z in zip(cuts[:-1], cuts[1:]):
        b0 = bs[a]
        idx = order[a:z]
        if b0 < 0:
            continue
        lv, cnt = levels[b0]
        if len(lv) == 0:
            continue
        p, q, tol = price[idx], back[idx], SR_NEAR * atr_b[idx]
        j = np.searchsorted(lv, p)
        below = np.where(j > 0, lv[np.maximum(j - 1, 0)], -np.inf)
        above = np.where(j < len(lv), lv[np.minimum(j, len(lv) - 1)], np.inf)
        ib = np.where(j > 0, cnt[np.maximum(j - 1, 0)], 0)
        ia = np.where(j < len(lv), cnt[np.minimum(j, len(lv) - 1)], 0)
        # a level crossed since that timeframe's close three bars back
        jq = np.searchsorted(lv, q)
        up_cross = (j > jq) & np.isfinite(q)
        dn_cross = (j < jq) & np.isfinite(q)
        db, da = p - below, above - p
        near_b, near_a = db <= tol, da <= tol
        lc = np.where(up_cross, 3, np.where(dn_cross, 4, np.where(near_b & (~near_a | (db <= da)), 1,
                                                                    np.where(near_a, 2, 0))))
        nearest_imp = np.where(near_b & (~near_a | (db <= da)), ib, np.where(near_a, ia, 0))
        loc[idx] = lc
        imp[idx] = np.minimum(nearest_imp, 3)
    return loc, imp


# ---------------------------------------------------------------- shapes
def shapes(close: np.ndarray, bi: np.ndarray, L: int) -> np.ndarray:
    """24-point z-normalised close path of the last L bars up to bi (inclusive), / sqrt(24) so a dot is a
    correlation; the path's height is returned in the second output by the caller (range)."""
    out = np.zeros((len(bi), NPTS), np.float32)
    rng = np.zeros(len(bi), np.float32)
    x = np.linspace(0, L - 1, NPTS)
    f = np.floor(x).astype(int)
    w = (x - f).astype(np.float32)
    c2 = np.minimum(f + 1, L - 1)
    for a in range(0, len(bi), 50_000):
        b = bi[a:a + 50_000]
        idx = b[:, None] - (L - 1) + np.arange(L)[None, :]
        ok = idx.min(axis=1) >= 0
        idx = np.maximum(idx, 0)
        P = close[idx].astype(np.float64)
        rng[a:a + 50_000] = P.max(axis=1) - P.min(axis=1)
        S = P[:, f] * (1 - w) + P[:, c2] * w
        S = S - S.mean(axis=1, keepdims=True)
        sd = S.std(axis=1, keepdims=True)
        S = np.where(sd > 0, S / np.where(sd > 0, sd, 1), 0) / np.sqrt(NPTS)
        S[~ok] = 0
        out[a:a + 50_000] = S.astype(np.float32)
    return out, rng


# ---------------------------------------------------------------- labels
def outcome(m: pd.DataFrame, dec: np.ndarray, u: np.ndarray) -> pd.DataFrame:
    tmin = plib.minutes(m.index)
    h, lo, c = (m[k].to_numpy(float) for k in ("high", "low", "close"))
    n = len(m)
    ref = c[dec]
    res = {}
    for hz in (15, 60):
        mu = np.zeros(len(dec))
        md = np.zeros(len(dec))
        for s in range(1, hz + 1):
            j = np.minimum(dec + s, n - 1)
            ok = (dec + s < n) & (tmin[j] - tmin[dec] <= hz)
            mu = np.where(ok, np.maximum(mu, h[j] - ref), mu)
            md = np.where(ok, np.maximum(md, ref - lo[j]), md)
        res[f"mfe_up{hz}"] = mu / u
        res[f"mfe_dn{hz}"] = md / u
    k3, t10 = 3 * u, 10 * u
    side = np.zeros(len(dec))
    trig = np.full(len(dec), -1)
    for s in range(1, 31):
        j = np.minimum(dec + s, n - 1)
        ok = (dec + s < n) & (tmin[j] - tmin[dec] <= 30) & (side == 0)
        up = ok & (h[j] >= ref + k3)
        dn = ok & (lo[j] <= ref - k3)
        side = np.where(up & ~dn, 1, np.where(dn & ~up, -1, np.where(up & dn, np.nan, side)))
        trig = np.where(ok & (up | dn), j, trig)
    have = np.isfinite(side) & (side != 0)
    sg = np.nan_to_num(side)
    tgt = ref + sg * t10
    cont = np.full(len(dec), np.nan)
    done = ~have
    tr0 = np.maximum(trig, 0)
    for s in range(0, 61):
        j = np.minimum(tr0 + s, n - 1)
        ok = have & (tr0 + s < n) & (tmin[j] - tmin[tr0] <= 60)
        ht = np.where(sg > 0, h[j] >= tgt, lo[j] <= tgt)
        hs = np.where(sg > 0, lo[j] <= ref, h[j] >= ref) if s > 0 else np.zeros(len(dec), bool)
        new = ok & ~done & (ht | hs)
        cont[new] = np.where(ht[new] & ~hs[new], 1.0, 0.0)
        done |= new
    res["start3"] = side
    res["cont10"] = cont
    return pd.DataFrame(res)


def classes(L: pd.DataFrame) -> np.ndarray:
    lu, ld = L.x10_lead_up, L.x10_lead_dn
    ru = lu.notna() & (ld.isna() | (lu <= ld))
    rd = ld.notna() & ~ru
    s3, c10 = L.start3, L.cont10
    cls = np.select(
        [ru, rd, (s3 == 1) & (c10 == 1), (s3 == -1) & (c10 == 1), (s3 == 1) & (c10 == 0), (s3 == -1) & (c10 == 0),
         s3 == 0],
        ["ran_up", "ran_dn", "slow_up", "slow_dn", "fake_up", "fake_dn", "flat"], "drift")
    return cls


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.load()
    keep = ["i", "half", "win", "u", "atr15_u", "x10_next_up", "x10_next_dn", "x10_lead_up", "x10_lead_dn",
            "x10_size_up", "x10_size_dn", "x10_mae_up", "x10_mae_dn", "x10_first", "x5_next_up", "x5_next_dn",
            "x5_lead_up", "x5_lead_dn", "x5_size_up", "x5_size_dn", "x5_first", "day_brk", "x72", "asia_brk",
            "yday_brk", "box_now", "sweep", "r50", "min_since_rel", "min_to_rel"] + \
        [c for c in pq.read_schema(HERE / "decisions.parquet").names if c.startswith("w_")]
    D = pd.read_parquet(HERE / "decisions.parquet", columns=keep)
    dec = D.i.to_numpy()
    n = len(D)
    log(f"cases {n}")
    t_dec = (m.index[dec] + pd.Timedelta(minutes=1)).to_numpy()
    price = m.close.to_numpy(float)[dec]
    codes = {}
    SH = np.zeros((n, NPTS * len(LOOK)), np.float32)
    for k, tf in enumerate(("H4", "H1", "M30", "M15", "M5", "M1")):
        if tf == "M1":
            b = m.rename(columns={"tick_volume": "tv"}).assign(avail=m.index + pd.Timedelta(minutes=1))
            b = b.reset_index(drop=True)
            bi = dec.copy()
        else:
            b = plib.tf_bars(m, RULE[tf])
            bi = np.searchsorted(b["avail"].to_numpy(), t_dec, side="right") - 1
        cd, atr, st = indicators(b)
        for col in cd.columns:
            codes[f"{tf}_{col}"] = cd[col].to_numpy()[bi]
        S, rng = shapes(b.close.to_numpy(float), bi, LOOK[tf])
        SH[:, k * NPTS:(k + 1) * NPTS] = S
        codes[f"{tf}_height"] = np.digitize(np.nan_to_num(rng / atr[bi], nan=0.0), [3, 6, 10]).astype(np.int8)
        if tf in SR_BARS:
            lv = sr_levels(b, atr, SR_BARS[tf])
            cl = b.close.to_numpy(float)
            back = np.where(bi >= 3, cl[np.maximum(bi - 3, 0)], np.nan)
            loc, imp = sr_codes(lv, bi, price, back, atr[bi])
            codes[f"{tf}_sr_loc"] = loc
            codes[f"{tf}_sr_imp"] = imp
        log(f"{tf} done ({len(b)} bars)")
    g = {}
    for col in ("day_brk", "x72", "asia_brk", "yday_brk", "sweep"):
        g[col] = (D[col].fillna(0).astype(int) + 1).to_numpy()
    g["box_now"] = D.box_now.fillna(0).astype(int).to_numpy()
    g["r50"] = (D.r50 <= 0.25).astype(int).to_numpy()
    g["release"] = np.where(D.min_to_rel <= 30, 1, np.where(D.min_since_rel <= 30, 2, 0))
    for k2, v in g.items():
        codes[f"g_{k2}"] = v.astype(np.int8)
    C = pd.DataFrame(codes, index=D.index)
    O = outcome(m, dec, D.u.to_numpy())
    O.index = D.index
    L = pd.concat([D, O], axis=1)
    L["cls"] = classes(L)
    out = pd.concat([L, C], axis=1)
    out.to_parquet(HERE / "lib_cases.parquet")
    np.save(HERE / "lib_shapes.npy", SH.astype(np.float16))
    log(f"saved cases {out.shape}, shapes {SH.shape}; state codes {C.shape[1]}")
    print(out.groupby("half").cls.value_counts(normalize=True).unstack().round(3).to_string())


if __name__ == "__main__":
    main()
