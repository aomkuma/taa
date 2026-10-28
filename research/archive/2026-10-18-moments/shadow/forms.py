"""Round 15 (docs/OWN_SETUP_ROUNDS.md): the owner's M1 chart forms - box breaks (touches, slope: sideways-up / -down / flat)
and 3-ATR runs that snap back - and what followed (which side reached 5 USD first within 60 minutes).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/forms.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as win

sys.path.insert(0, str(Path("research/2026-10-18-moments/agents/journal")))
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

REF = 4100.0
START, SPLIT = pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")
HALVES = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01"], utc=True)


def load() -> pd.DataFrame:
    m = gold.bars("M1")
    return m[(m.index >= pd.Timestamp("2023-10-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-17", tz="UTC"))]


def first5(o, h, lo, sp0, e, side, k, hz=60):
    """+1 if the side reached k first from the mid at bar e's open, -1 if the other side did, 0 if neither."""
    n = len(o)
    out = np.zeros(len(e), int)
    for i, (ei, s, kk) in enumerate(zip(e, side, k, strict=True)):
        if ei + hz >= n:
            continue
        mid = o[ei] + sp0[ei] / 2
        hh, ll = h[ei : ei + hz], lo[ei : ei + hz]
        up = np.nonzero(hh - mid >= kk)[0]
        dn = np.nonzero(mid - ll >= kk)[0]
        fu = up[0] if len(up) else 10**6
        fd = dn[0] if len(dn) else 10**6
        if fu == fd:
            continue
        won_up = fu < fd
        out[i] = 1 if (won_up and s > 0) or (not won_up and s < 0) else -1
    return out


def main() -> None:
    gold.below_normal_priority()
    m = load()
    ot = m.index
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp0 = m["spread"].to_numpy(float) * 0.01
    n = len(c)
    m15 = m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min"}).dropna()
    a15 = (m15.high - m15.low).rolling(14).mean()
    a15.index = a15.index + pd.Timedelta(minutes=15)
    atr15 = a15.reindex(ot, method="ffill").to_numpy()
    h1 = m.resample("60min", label="left", closed="left").agg({"close": "last"}).dropna()
    e20, e50 = h1.close.ewm(span=20, adjust=False).mean(), h1.close.ewm(span=50, adjust=False).mean()
    tide = pd.Series(np.where((e20 > e20.shift(3)) & (h1.close > e50), 1, np.where((e20 < e20.shift(3)) & (h1.close < e50), -1, 0)),
                     index=h1.index + pd.Timedelta(minutes=60))
    tide_m1 = tide.reindex(ot, method="ffill").fillna(0).to_numpy()
    sess = np.where(ot.hour < 7, "Asia", np.where(ot.hour < 12, "London", np.where(ot.hour < 20, "NY", "late")))
    # swing extremes of 5 bars (known 2 bars later; only used inside windows that ended before the decision)
    sh = np.zeros(n, bool)
    sl = np.zeros(n, bool)
    sh[2:-2] = (h[2:-2] >= win(h, 5).max(1)[:-0 or None][: n - 4])
    sl[2:-2] = (lo[2:-2] <= win(lo, 5).min(1)[: n - 4])
    rows = []
    for W in (30, 60):
        hiW = pd.Series(h).rolling(W).max().shift(1).to_numpy()
        loW = pd.Series(lo).rolling(W).min().shift(1).to_numpy()
        hgt = hiW - loW
        ok = (hgt > 0) & (hgt <= atr15) & np.isfinite(atr15)
        up_brk = ok & (c > hiW + 0.1 * hgt) & (np.r_[np.nan, c[:-1]] <= hiW) & (np.r_[np.nan, c[:-1]] >= loW)
        dn_brk = ok & (c < loW - 0.1 * hgt) & (np.r_[np.nan, c[:-1]] <= hiW) & (np.r_[np.nan, c[:-1]] >= loW)
        for j in np.nonzero(up_brk | dn_brk)[0]:
            if j < W + 5 or ot[j] < START or j + 62 >= n or sess[j] == "late":
                continue
            a, b = j - W, j - 2  # swings confirmed before the decision
            tol = 0.15 * hgt[j]
            idx_h = np.nonzero(sh[a:b] & (h[a:b] >= hiW[j] - tol))[0]
            idx_l = np.nonzero(sl[a:b] & (lo[a:b] <= loW[j] + tol))[0]

            def distinct(ix: np.ndarray) -> int:
                cnt, last = 0, -99
                for x in ix:
                    if x - last >= 5:
                        cnt, last = cnt + 1, x
                return cnt

            yy = c[j - W : j]
            slope = np.polyfit(np.arange(W), yy, 1)[0] * W / hgt[j]
            rows.append(dict(t=ot[j], j=j, W=W, side=1 if up_brk[j] else -1, height=hgt[j], h_atr=hgt[j] / atr15[j],
                             top=distinct(idx_h), bottom=distinct(idx_l),
                             slope="sideways-up" if slope > 0.5 else ("sideways-down" if slope < -0.5 else "flat"),
                             session=sess[j], tide=tide_m1[j]))
    B = pd.DataFrame(rows)
    B["e"] = B.j + 1
    B["k"] = c[B.j] / REF * 5
    B["res"] = first5(o, h, lo, sp0, B.e.to_numpy(), B.side.to_numpy(), B.k.to_numpy())
    B["form"] = "box"
    # 3-ATR runs, faded
    e20m = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - pc), np.abs(lo - pc)], axis=1)
    atr1 = pd.Series(tr).rolling(14).mean().shift(1).to_numpy()
    ext = (c - e20m) / atr1
    cross = (np.abs(ext) >= 3) & (np.abs(np.r_[0, ext[:-1]]) < 3)
    jj = np.nonzero(cross)[0]
    jj = jj[(ot[jj] >= START) & (jj + 62 < n) & (sess[jj] != "late")]
    R = pd.DataFrame(dict(t=ot[jj], j=jj, side=-np.sign(ext[jj]).astype(int), session=sess[jj], tide=tide_m1[jj],
                          ext=np.abs(ext[jj])))
    R["e"] = R.j + 1
    R["k"] = c[R.j] / REF * 5
    R["res"] = first5(o, h, lo, sp0, R.e.to_numpy(), R.side.to_numpy(), R.k.to_numpy())
    R["form"] = "3atr_snap"
    R["with_tide"] = np.where(R.tide == 0, "no tide", np.where(R.side == R.tide, "snap with the H1 tide", "snap against the H1 tide"))
    for D in (B, R):
        D["half"] = pd.cut(D.t, HALVES, labels=["H1", "H2", "H3", "H4", "H5"], right=False)
        D["part"] = np.where(D.t < SPLIT, "design", "window")
    B.to_parquet("data/research/own_forms_box.parquet")
    R.to_parquet("data/research/own_forms_snap.parquet")

    def share(x: pd.DataFrame) -> str:
        y = x[x.res != 0]
        return f"{100 * (y.res > 0).mean():5.1f}% (n {len(y)})" if len(y) else "-"

    B["touch_opp"] = np.where(B.side > 0, B.bottom, B.top)  # touches of the edge opposite to the break
    B["touch_brk"] = np.where(B.side > 0, B.top, B.bottom)  # touches of the edge that broke
    B["opp3"] = np.where(B.touch_opp >= 3, "3+ on the other edge", "<3 on the other edge")
    B["brk3"] = np.where(B.touch_brk >= 3, "3+ on the broken edge", "<3 on the broken edge")
    B["tide_rel"] = np.where(B.tide == 0, "no tide", np.where(B.side == B.tide, "break with the H1 tide", "break against"))
    B["slope_rel"] = np.where(B.slope == "flat", "flat", np.where((B.slope == "sideways-up") == (B.side > 0), "break the slope's way", "break against the slope"))
    print("BOX BREAKS - the break direction reached 5 USD first (among cases with a run):")
    for part in ("design", "window"):
        x = B[B.part == part]
        print(f"\n == {part}: all {share(x)}")
        for f in ("W", "brk3", "opp3", "slope", "slope_rel", "tide_rel", "session"):
            print(f"   {f}: " + " | ".join(f"{k}: {share(g)}" for k, g in x.groupby(f)))
    print("\n 3+ touches on the broken edge, by half-year (design):")
    x = B[(B.part == "design") & (B.touch_brk >= 3)]
    print("   " + " ".join(f"{k}: {share(g)}" for k, g in x.groupby("half", observed=True)))
    x = B[(B.part == "design") & (B.touch_opp >= 3)]
    print(" 3+ touches on the other edge, by half-year (design):")
    print("   " + " ".join(f"{k}: {share(g)}" for k, g in x.groupby("half", observed=True)))
    print("\n3-ATR RUNS - the snap back reached 5 USD first:")
    for part in ("design", "window"):
        x = R[R.part == part]
        print(f" == {part}: all {share(x)}")
        for f in ("with_tide", "session"):
            print(f"   {f}: " + " | ".join(f"{k}: {share(g)}" for k, g in x.groupby(f)))
        if part == "design":
            print("   by half-year: " + " ".join(f"{k}: {share(g)}" for k, g in x.groupby("half", observed=True)))


if __name__ == "__main__":
    main()
