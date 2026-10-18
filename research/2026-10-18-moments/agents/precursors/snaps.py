"""The snaps (notes.md "Revised by the owner"): at each of the owner's 20 times a day, the chart of six timeframes
(the last 120 closed bars of each, 40-point shapes), 82 states, and what followed.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/snaps.py
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

import plib
from library import SR_BARS, indicators, sr_codes, sr_levels
from plib import HERE

T0 = time.time()
NPTS, LOOKBACK = 40, 120
TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
TH, FR, LO, NY = "Asia/Bangkok", "Europe/Berlin", "Europe/London", "America/New_York"
SNAPS = ([(TH, h, 0, f"TH{h:02d}00") for h in (7, 8, 9, 10, 11, 12)] + [(FR, 8, 0, "FR0800")]
         + [(LO, h, 0, f"LO{h:02d}00") for h in (8, 9, 10, 11, 12)]
         + [(NY, 8, 0, "NY0800"), (NY, 8, 30, "NY0830"), (NY, 9, 30, "NY0930"), (NY, 10, 0, "NY1000")]
         + [(NY, h, 0, f"NY{h:02d}00") for h in (11, 12, 13, 14)])
FIRST = pd.Timestamp("2023-11-01", tz="UTC")


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.0f}s] {msg}", flush=True)


def snap_times(m: pd.DataFrame) -> pd.DataFrame:
    """Every snap second on the zone's weekdays whose M1 bar (closing at it, <= 5 minutes old) exists."""
    rows = []
    for zone, hh, mm, name in SNAPS:
        days = pd.date_range(FIRST.tz_convert(zone).date(), m.index[-1].tz_convert(zone).date(), freq="D")
        days = days[days.dayofweek < 5]
        loc = pd.DatetimeIndex([pd.Timestamp(d.year, d.month, d.day, hh, mm) for d in days]).tz_localize(
            zone, nonexistent="shift_forward", ambiguous=False)
        rows.append(pd.DataFrame({"S": loc.tz_convert("UTC"), "name": name}))
    S = pd.concat(rows, ignore_index=True)
    S = S.groupby("S", as_index=False).agg(name=("name", "+".join))
    idx = m.index.searchsorted(S.S, side="left") - 1
    ok = idx >= 0
    last_open = m.index[np.maximum(idx, 0)]
    ok &= (S.S - last_open) <= pd.Timedelta(minutes=6)
    S["idx"] = idx
    S = S[ok & (S.S >= FIRST)].reset_index(drop=True)
    return S


def shapes(close: np.ndarray, bi: np.ndarray, L: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.linspace(0, L - 1, NPTS)
    f = np.floor(x).astype(int)
    w = x - f
    c2 = np.minimum(f + 1, L - 1)
    idx = bi[:, None] - (L - 1) + np.arange(L)[None, :]
    ok = idx.min(axis=1) >= 0
    P = close[np.maximum(idx, 0)]
    rng = P.max(axis=1) - P.min(axis=1)
    Sh = P[:, f] * (1 - w) + P[:, c2] * w
    Sh = Sh - Sh.mean(axis=1, keepdims=True)
    sd = Sh.std(axis=1, keepdims=True)
    Sh = np.where(sd > 0, Sh / np.where(sd > 0, sd, 1), 0) / np.sqrt(NPTS)
    Sh[~ok] = 0
    return Sh.astype(np.float32), rng


def labels(m: pd.DataFrame, S: pd.DataFrame, cats: dict[int, pd.DataFrame]) -> pd.DataFrame:
    tmin = plib.minutes(m.index)
    h, lo, c = (m[k].to_numpy(float) for k in ("high", "low", "close"))
    n = len(m)
    dec = S.idx.to_numpy()
    s_min = ((S.S - m.index[0]).dt.total_seconds() // 60).to_numpy().astype(np.int64)  # the snap second in minutes
    u = m.open.to_numpy(float)[dec] / plib.REF
    ref = c[dec]
    out = {"u": u, "ref": ref}
    for xu, C in cats.items():
        for side, nm in ((1, "up"), (-1, "dn")):
            Cs = C[C.side == side]
            st = Cs.i.to_numpy()
            p = np.searchsorted(st, dec + 1, side="left")
            ok = p < len(st)
            pj = np.minimum(p, len(st) - 1)
            lead = np.where(ok, tmin[st[pj]] - s_min, 10**9)
            has = ok & (lead >= 0) & (lead < 30)
            out[f"r{xu}_{nm}_lead"] = np.where(has, lead, np.nan)
            out[f"r{xu}_{nm}_size"] = np.where(has, Cs.size_u.to_numpy()[pj], np.nan)
            spx = Cs.start_px.to_numpy()[pj]
            mae = (ref - spx) if side > 0 else (spx - ref)
            out[f"r{xu}_{nm}_mae"] = np.where(has, np.maximum(mae, 0) / u, np.nan)
    for hz in (15, 30, 60):
        mu = np.zeros(len(dec))
        md = np.zeros(len(dec))
        for s in range(1, hz + 1):
            j = np.minimum(dec + s, n - 1)
            ok = (dec + s < n) & (tmin[j] - s_min < hz)
            mu = np.where(ok, np.maximum(mu, h[j] - ref), mu)
            md = np.where(ok, np.maximum(md, ref - lo[j]), md)
        out[f"mfe_up{hz}"] = mu / u
        out[f"mfe_dn{hz}"] = md / u
    for xu in (10, 5):
        X = xu * u
        first = np.zeros(len(dec))
        done = np.zeros(len(dec), bool)
        for s in range(1, 61):
            j = np.minimum(dec + s, n - 1)
            ok = (dec + s < n) & (tmin[j] - s_min < 60)
            up = ok & (h[j] >= ref + X)
            dn = ok & (lo[j] <= ref - X)
            first = np.where(~done & up & ~dn, 1, np.where(~done & dn & ~up, -1, np.where(~done & up & dn, np.nan,
                                                                                        first)))
            done |= up | dn
        out[f"first{xu}"] = first
    # the first +-3 U within 30 minutes, then 10 U before back at the snap price (60 minutes)
    k3, t10 = 3 * u, 10 * u
    side = np.zeros(len(dec))
    trig = np.full(len(dec), -1)
    for s in range(1, 31):
        j = np.minimum(dec + s, n - 1)
        ok = (dec + s < n) & (tmin[j] - s_min < 30) & (side == 0)
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
    out["start3"] = side
    out["cont10"] = cont
    L = pd.DataFrame(out, index=S.index)
    lu, ld = L.r10_up_lead, L.r10_dn_lead
    ru = lu.notna() & (ld.isna() | (lu <= ld))
    rd = ld.notna() & ~ru
    s3, c10 = L.start3, L.cont10
    L["cls"] = np.select(
        [ru, rd, (s3 == 1) & (c10 == 1), (s3 == -1) & (c10 == 1), (s3 == 1) & (c10 == 0), (s3 == -1) & (c10 == 0),
         s3 == 0],
        ["ran_up", "ran_dn", "slow_up", "slow_dn", "fake_up", "fake_dn", "flat"], "drift")
    lu5, ld5 = L.r5_up_lead, L.r5_dn_lead
    L["cls5"] = np.where(lu5.notna() & (ld5.isna() | (lu5 <= ld5)), "ran5_up", np.where(ld5.notna(), "ran5_dn", "none"))
    return L


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.load()
    S = snap_times(m)
    S["half"] = pd.cut(S.S, plib.HALVES, labels=plib.HLAB, right=False).astype(str)
    log(f"snaps {len(S)}: per half {S.half.value_counts().sort_index().to_dict()}")
    dec = S.idx.to_numpy()
    s_ts = S.S.to_numpy()
    price = m.close.to_numpy(float)[dec]
    codes = {}
    SH = np.zeros((len(S), NPTS * len(TFS)), np.float32)
    heights = {}
    for k, tf in enumerate(TFS):
        if tf == "M1":
            b = m.rename(columns={"tick_volume": "tv"}).assign(avail=m.index + pd.Timedelta(minutes=1))
            b = b.reset_index(drop=True)
            bi = dec.copy()
        else:
            b = plib.tf_bars(m, RULE[tf])
            bi = np.searchsorted(b["avail"].to_numpy(), s_ts, side="right") - 1
        cd, atr, _st = indicators(b)
        for col in cd.columns:
            codes[f"{tf}_{col}"] = cd[col].to_numpy()[bi]
        sh, rng = shapes(b.close.to_numpy(float), bi, LOOKBACK)
        SH[:, k * NPTS:(k + 1) * NPTS] = sh
        heights[tf] = rng / atr[bi]
        if tf in SR_BARS:
            lv = sr_levels(b, atr, SR_BARS[tf])
            cl = b.close.to_numpy(float)
            back = np.where(bi >= 3, cl[np.maximum(bi - 3, 0)], np.nan)
            loc, imp = sr_codes(lv, bi, price, back, atr[bi])
            codes[f"{tf}_sr_loc"] = loc
            codes[f"{tf}_sr_imp"] = imp
        log(f"{tf} done")
    design = (S.S < plib.SPLIT).to_numpy()
    for tf, hv in heights.items():
        q = np.nanquantile(hv[design], [1 / 3, 2 / 3])
        codes[f"{tf}_height"] = np.digitize(np.nan_to_num(hv, nan=q[0]), q).astype(np.int8)
    atr15 = plib.m15_atr(m)
    F = plib.m1_forms(m, atr15)
    for col in ("day_brk", "x72", "asia_brk", "yday_brk", "sweep"):
        codes[f"g_{col}"] = (F[col].fillna(0).astype(int).to_numpy()[dec] + 1).astype(np.int8)
    codes["g_box_now"] = F.box_now.fillna(0).astype(int).to_numpy()[dec].astype(np.int8)
    codes["g_r50"] = (F.r50.to_numpy()[dec] <= 0.25).astype(np.int8)
    rel = pd.DatetimeIndex(plib.gold.releases().t).sort_values()
    p = rel.searchsorted(S.S)
    to_rel = np.array([(rel[q] - t).total_seconds() / 60 if q < len(rel) else 1e9 for q, t in zip(p, S.S)])
    since = np.array([(t - rel[q - 1]).total_seconds() / 60 if q > 0 else 1e9 for q, t in zip(p, S.S)])
    codes["g_release"] = np.where(to_rel <= 30, 1, np.where(since <= 30, 2, 0)).astype(np.int8)
    C = pd.DataFrame(codes, index=S.index)
    cats = {xu: pd.read_parquet(HERE / f"runs_{xu}.parquet") for xu in (10, 5)}
    L = labels(m, S, cats)
    S["atr15_u"] = atr15[dec] / L.u.to_numpy()
    out = pd.concat([S, L, C], axis=1)
    out.to_parquet(HERE / "snaps.parquet")
    np.save(HERE / "snap_shapes.npy", SH)
    log(f"saved {out.shape}, shapes {SH.shape}, state codes {C.shape[1]}")
    d = out[out.half != "W"]
    print("\nclasses (design snaps):")
    print(d.cls.value_counts(normalize=True).round(3).to_string())
    print("\nclasses by snap name (design, share):")
    print(d.groupby("name").cls.value_counts(normalize=True).unstack().fillna(0).round(2).to_string())


if __name__ == "__main__":
    main()
