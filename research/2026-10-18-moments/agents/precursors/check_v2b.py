"""An independent re-derivation of Setup OWN V2 (v2b.py), written apart from it: the library recounted from the raw
attribute codes (equality, not one-hot dot products) and np.corrcoef for the outlines; the entry timeframe's ATR from
its own bars; every walk-forward trade walked again bar by bar. Every value must agree.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_v2b.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import jlib  # noqa: E402
from library_match import LAYERS, attrs  # noqa: E402

TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
LAYER_TFS = {"ctx": ("H4", "H1"), "set": ("M30", "M15"), "trg": ("M5", "M1")}
SHORT = {"context (H4+H1)": "ctx", "setup (M30+M15)": "set", "trigger (M5+M1)": "trg"}
MIN_OF = {"M1": 1, "M5": 5, "M15": 15, "M30": 30}


def pearson(A: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The Pearson correlation of every row of A with b, from the definition (centred, divided by both norms)."""
    Ac = A - A.mean(axis=-1, keepdims=True)
    bc = b - b.mean()
    return (Ac @ bc) / (np.sqrt((Ac ** 2).sum(axis=-1)) * np.sqrt((bc ** 2).sum()))


def recount(codes: np.ndarray, shapes: np.ndarray, day: np.ndarray, cls: np.ndarray, rho) -> np.ndarray:
    """(earlier days, up - down) for every snap, the greedy library rebuilt from scratch: raw code equality for the
    similarity, the Pearson correlation of each timeframe's path for the outline, the first best on ties."""
    up = np.isin(cls, ["ran_up", "slow_up"])
    dn = np.isin(cls, ["ran_dn", "slow_dn"])
    lc = np.zeros((0, codes.shape[1]), int)
    ls = np.zeros((0, shapes.shape[1], shapes.shape[2]))
    ld = np.zeros(0, int)
    occ: list[list[int]] = []  # snap rows counted into each pattern (once a day)
    out = np.full((len(codes), 2), np.nan)
    order = sorted(range(len(codes)), key=lambda e: (day[e], e))

    def best(e, before):
        if len(lc) == 0:
            return -1, -1.0
        sim = (lc == codes[e]).mean(axis=1)
        ok = np.ones(len(lc), bool) if before is None else ld < before
        if rho is not None:
            worst = np.min(np.stack([pearson(ls[:, i, :], shapes[e][i]) for i in range(shapes.shape[1])]), axis=0)
            ok &= worst >= rho - 1e-6
        sim = np.where(ok, sim, -1.0)
        k = int(np.argmax(sim))
        return (k, float(sim[k])) if sim[k] >= 0 else (-1, -1.0)

    for e in order:
        k, sim = best(e, int(day[e]))
        if k >= 0 and sim >= 0.8 - 1e-6:
            rows = [r for r in occ[k] if day[r] < day[e]]
            out[e] = (len(rows), up[rows].mean() - dn[rows].mean()) if rows else (0, np.nan)
        else:
            out[e] = (0, np.nan)
        k, sim = best(e, None)
        if k >= 0 and sim >= 0.8 - 1e-6:
            if day[occ[k][-1]] != day[e]:
                occ[k].append(e)
        else:
            lc = np.vstack([lc, codes[e][None]])
            ls = np.concatenate([ls, shapes[e][None]])
            ld = np.r_[ld, day[e]]
            occ.append([e])
    return out


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    SH = np.load(HERE / "snap_shapes.npy").reshape(len(S), len(TFS), 40)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((S.S.dt.tz_convert("Asia/Bangkok").dt.normalize() - day0).dt.days).to_numpy()
    cls = S.cls.to_numpy()
    T = pd.read_parquet(HERE / "v2b_wf_trades.parquet")
    need = {(c.split("_")[0], c.split("_")[1]) for c in T.cell.unique()}
    lean = {}
    for layer, tfs in LAYERS.items():
        L = SHORT[layer]
        codes = np.column_stack(attrs(FS, S, tfs)).astype(int)
        idx = [TFS.index(tf) for tf in LAYER_TFS[L]]
        for rho_name in {g for lay, g in need if L in lay.split("+")}:
            rho = None if rho_name == "codes" else float(rho_name.replace("shape", ""))
            lean[(L, rho_name)] = recount(codes, SH[:, idx], day, cls, rho)
            print("recounted", L, rho_name, flush=True)
    # the entry timeframe's ATR from bars built here
    m = jlib.m1_frame("XAUUSD")
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    atr_of = {}
    for tf, n in MIN_OF.items():
        g = m.groupby(m.index.floor(f"{n}min"))
        b = pd.DataFrame({"h": g.high.max(), "l": g.low.min(), "c": g.close.last(), "end": g.apply(lambda x: x.index[-1])})
        pc = b.c.shift(1)
        tr = np.maximum(b.h, pc) - np.minimum(b.l, pc)
        b["atr"] = tr.rolling(14).mean()
        b["done"] = b.end + pd.Timedelta(minutes=1)
        atr_of[tf] = b.set_index("done").atr
    et = m.index.tz_convert("America/New_York")
    mins = et.hour * 60 + et.minute
    ny = (((mins >= 475) & (mins < 510)) | ((mins >= 505) & (mins < 540)) | ((mins >= 565) & (mins < 600))
          | ((mins >= 595) & (mins < 630)) | ((mins >= 660) & (mins < 840))) & (et.dayofweek < 5)
    snap_of = {pd.Timestamp(s): i for i, s in enumerate(S.S)}
    bad = 0
    for r in T.itertuples():
        layers_s, gate, n_s, th_s = r.cell.split("_")
        n_min, theta = int(n_s[1:]), float(th_s[2:])
        # the snap this trade came from: the latest snap second at or before the entry bar's open
        e = max(i for s, i in snap_of.items() if s <= m.index[r.j0])
        total, ok = 0.0, True
        for L in layers_s.split("+"):
            n_e, x = lean[(L, gate)][e]
            if not (n_e >= n_min and np.isfinite(x)):
                ok = False
            else:
                total += x
        side = (1 if total >= theta - 1e-9 else (-1 if total <= -theta + 1e-9 else 0)) if ok else 0
        a = {tf: atr_of[tf][atr_of[tf].index <= S.S.iloc[e]].iloc[-1] for tf in MIN_OF}
        etf = next((tf for tf in ("M1", "M5", "M15", "M30") if np.isfinite(a[tf]) and a[tf] >= 5.0), "M30")
        sl, tp = max(a[etf], 5.0), 10.0 * c[r.j0 - 1] / 4100.0
        ss = 0.20 if ny[r.j0] else 0.15
        j0 = int(r.j0)
        entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
        end = m.index[j0] + pd.Timedelta(minutes=12 * MIN_OF[etf])
        ex, pnl, xj, j = "time", None, None, j0
        while j < len(o) and m.index[j] < end:
            if side > 0:
                if lo[j] <= entry - sl:
                    ex, pnl, xj = "stop", -sl - ss, j
                    break
                if h[j] >= entry + tp:
                    ex, pnl, xj = "win", tp, j
                    break
            else:
                if h[j] + sp[j] >= entry + sl:
                    ex, pnl, xj = "stop", -sl - ss, j
                    break
                if lo[j] + sp[j] <= entry - tp:
                    ex, pnl, xj = "win", tp, j
                    break
            j += 1
        if pnl is None:
            x = max(j - 1, j0)
            pnl = (c[x] - 0.07 - entry) if side > 0 else (entry - (c[x] + sp[x] + 0.07))
            xj = x
        probs = []
        if side != r.side:
            probs.append(f"side {side} vs {r.side}")
        if etf != r.etf or abs(sl - r.sl) > 1e-9 or abs(tp - r.tp) > 1e-9:
            probs.append(f"plan {etf} {sl:.4f} {tp:.4f} vs {r.etf} {r.sl:.4f} {r.tp:.4f}")
        if ex != r.exit or abs(pnl - r.pnl) > 1e-9 or xj != r.xj:
            probs.append(f"exit {ex} {pnl:.4f} @{xj} vs {r.exit} {r.pnl:.4f} @{r.xj}")
        if probs:
            bad += 1
            print("MISMATCH", r.t, r.cell, "; ".join(probs))
    print(f"trades: {len(T)} checked, {bad} with a mismatch")


if __name__ == "__main__":
    main()
