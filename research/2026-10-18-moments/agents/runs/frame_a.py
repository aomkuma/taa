"""Step 2, frame A (notes.md): what is over-represented a few minutes before a run starts, against random times of
the same half-year and UTC hour (and, with --atr, the same M15 ATR decile: beyond volatility clustering); which
features tell the run's side; and the trader's check of that side from the snapshot itself (at the controls: which
of +X / -X U the next bar's open mid reaches first within 60 minutes). Design data only.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/frame_a.py R OFFSET [--atr]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import gold  # noqa: E402
from catalogue import load  # noqa: E402

HALVES = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01"], utc=True)
HL = ["H1", "H2", "H3", "H4", "H5"]
CATEG_MAX = 7  # a feature with at most this many distinct values is read as categories


def bins_of(x: pd.Series, ctrl: pd.Series) -> tuple[pd.Series, list]:
    vals = ctrl.dropna().unique()
    if len(vals) <= CATEG_MAX:
        return x, sorted(vals)
    q = np.unique(np.nanquantile(ctrl.to_numpy(float), [0.2, 0.4, 0.6, 0.8]))
    b = pd.Series(np.digitize(x.to_numpy(float), q), index=x.index).where(x.notna())
    return b, list(range(len(q) + 1))


def first_hit(o, h, lo, sp, d: np.ndarray, k: np.ndarray, hz: int = 60) -> np.ndarray:
    """+1 / -1: which of +k / -k from the mid at bar d+1's open is reached first within hz bars; 0 neither/both."""
    e = d + 1
    n = len(o)
    mid = o[np.minimum(e, n - 1)] + sp[np.minimum(e, n - 1)] / 2
    res = np.zeros(len(d))
    open_ = np.ones(len(d), bool)
    for j in range(hz):
        idx = np.minimum(e + j, n - 1)
        up = (h[idx] - mid >= k) & open_
        dn = (mid - lo[idx] >= k) & open_
        res[up & ~dn] = 1
        res[dn & ~up] = -1
        open_ &= ~(up | dn)
    return res


def main() -> None:
    gold.below_normal_priority()
    R = float(sys.argv[1])
    off = int(sys.argv[2])
    by_atr = "--atr" in sys.argv
    C = pd.read_parquet(HERE / "catalogue.parquet")
    F = pd.read_parquet(HERE / "feats.parquet")
    AD = pd.read_parquet(HERE / "adaptive.parquet")
    F = F.join(AD)
    m = load()
    o, h, lo = (m[k].to_numpy(float) for k in ("open", "high", "low"))
    sp = m.spread.to_numpy(float) * 0.01
    ot = F.index
    C = C[(C.R == R) & (C.part == "design") & (C.t.dt.hour <= 20) & (C.t.dt.dayofweek < 5)].copy()
    C["half"] = pd.cut(C.t, HALVES, labels=HL, right=False)
    dec = np.nanquantile(F.atr15_u[(ot >= HALVES[0]) & (ot < HALVES[-1])], np.linspace(0.1, 0.9, 9))
    F["atr_dec"] = np.digitize(F.atr15_u.to_numpy(float), dec).astype(np.float32)
    C["atr_dec"] = F.atr_dec.to_numpy()[C.i.to_numpy() - off]
    pool = pd.DataFrame({"i": np.arange(len(ot)), "t": ot, "atr_dec": F.atr_dec.to_numpy()})
    pool["i"] += off  # a control "start" whose snapshot is the random bar
    pool = pool[(pool.t >= HALVES[0]) & (pool.t < HALVES[-1]) & (pool.t.dt.hour <= 20) & (pool.t.dt.dayofweek < 5)]
    pool = pool[pool.i < len(ot)]
    pool["half"] = pd.cut(pool.t, HALVES, labels=HL, right=False)
    pool["hour"] = pool.t.dt.hour
    rng = np.random.default_rng(7)
    keys = ["half", "hour"] + (["atr_dec"] if by_atr else [])
    C["hour"] = C.t.dt.hour
    need = C.groupby(keys, observed=True).size()
    groups = pool.groupby(keys, observed=True).i
    ctrl = []
    for key, k in need.items():
        try:
            cand = groups.get_group(key).to_numpy()
        except KeyError:
            continue
        ctrl.append(pd.DataFrame({"i": rng.choice(cand, 10 * k, replace=True), "half": key[0]}))
    K = pd.concat(ctrl, ignore_index=True)
    X = F.iloc[C.i.to_numpy() - off].reset_index(drop=True)
    X["half"], X["side"] = C.half.to_numpy(), C.side.to_numpy()
    Y = F.iloc[K.i.to_numpy() - off].reset_index(drop=True)
    Y["half"] = K.half.to_numpy()
    d = K.i.to_numpy() - off
    u = o[d] / 4100.0
    Y["first5"] = first_hit(o, h, lo, sp, d, 5 * u)
    Y["first10"] = first_hit(o, h, lo, sp, d, F.atr15_u.to_numpy()[d] * u)  # +-1 M15 ATR
    feats = [c for c in F.columns]
    rows = []
    for f in feats:
        bx, cats = bins_of(X[f], Y[f])
        by, _ = bins_of(Y[f], Y[f])
        for b in cats:
            sx, sy = bx == b, by == b
            rec = dict(feature=f, bin=b, lo=float(Y[f][sy].min()) if sy.any() else np.nan,
                       hi=float(Y[f][sy].max()) if sy.any() else np.nan,
                       n_runs=int(sx.sum()), share_runs=float(sx.mean()), share_ctrl=float(sy.mean()))
            rec["lift"] = rec["share_runs"] / rec["share_ctrl"] if rec["share_ctrl"] > 0 else np.nan
            rec["up"] = float((X.side[sx] > 0).mean()) if sx.sum() else np.nan
            y5 = Y.first5[sy]
            y10 = Y.first10[sy]
            rec["ctrl_up5"] = float((y5[y5 != 0] > 0).mean()) if (y5 != 0).sum() else np.nan
            rec["ctrl_up10"] = float((y10[y10 != 0] > 0).mean()) if (y10 != 0).sum() else np.nan
            ups, lifts, c5 = [], [], []
            for hf in HL:
                hx, hy = X.half == hf, Y.half == hf
                a = (sx & hx).sum() / max(hx.sum(), 1)
                bb = (sy & hy).sum() / max(hy.sum(), 1)
                lifts.append(a / bb if bb > 0 else np.nan)
                ups.append(float((X.side[sx & hx] > 0).mean()) if (sx & hx).sum() >= 20 else np.nan)
                z = Y.first5[sy & hy]
                c5.append(float((z[z != 0] > 0).mean()) if (z != 0).sum() >= 50 else np.nan)
            rec |= {f"lift_{h}": v for h, v in zip(HL, lifts, strict=True)}
            rec |= {f"up_{h}": v for h, v in zip(HL, ups, strict=True)}
            rec |= {f"c5_{h}": v for h, v in zip(HL, c5, strict=True)}
            rec["lift_same"] = int(np.nansum(np.sign(np.array(lifts) - 1) == np.sign(rec["lift"] - 1)))
            uu = np.array(ups)
            rec["up_same"] = int(np.nansum(np.sign(uu - 0.5) == np.sign(rec["up"] - 0.5)))
            cc = np.array(c5)
            rec["c5_same"] = int(np.nansum(np.sign(cc - 0.5) == np.sign(rec["ctrl_up5"] - 0.5)))
            rows.append(rec)
    T = pd.DataFrame(rows)
    tag = f"R{R}_off{off}{'_atr' if by_atr else ''}"
    T.to_csv(HERE / f"frame_a_{tag}.csv", index=False)
    pd.set_option("display.width", 250)
    print(f"R = {R} U, snapshot {off} min before the start, controls matched by {keys}; runs {len(C)}, controls {len(K)}")
    print(f"up-runs {100 * (C.side > 0).mean():.1f} %; controls: +5 first {100 * (Y.first5[Y.first5 != 0] > 0).mean():.1f} %")
    S = T[(T.share_ctrl >= 0.02) & (T.n_runs >= 100)].copy()
    S["abs"] = (S.lift - 1).abs()
    cols = ["feature", "bin", "lo", "hi", "n_runs", "lift"] + [f"lift_{h}" for h in HL] + ["lift_same", "up", "ctrl_up5"]
    print("\n== the largest lifts, stable in >= 4 of 5 half-years ==")
    print(S[S.lift_same >= 4].sort_values("abs", ascending=False).head(40)[cols].round(2).to_string(index=False))
    S["upd"] = (S.up - 0.5).abs()
    cols = ["feature", "bin", "lo", "hi", "n_runs", "lift", "up", "up_same", "ctrl_up5", "ctrl_up10"] + \
        [f"c5_{h}" for h in HL] + ["c5_same"]
    print("\n== the side among runs (most lopsided), with the trader's check from the snapshot (controls) ==")
    print(S.sort_values("upd", ascending=False).head(30)[cols].round(3).to_string(index=False))
    S["cd"] = (S.ctrl_up5 - 0.5).abs()
    print("\n== the trader's check: bins whose +5 / -5 first from the snapshot is most lopsided (controls) ==")
    print(S.sort_values("cd", ascending=False).head(25)[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
