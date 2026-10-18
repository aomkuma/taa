"""Setup OWN V2 on the trigger situation (2026-10-19). The same picture almost never repeats (coverage_3y.py,
rarity.py), but the same situation on M5 and M1 does, and it leaned the way of the next 10 U run in both halves
(rarity_lean.py; lean_check.py: recounted independently 300 / 300, the error by day barely larger, the same lean
against the day before / after: nothing). Here the bot trades that lean: at every snap, the earlier moments of the
library (>= 7 days before; snaps and the starts of 10 U runs) in the same M5 + M1 situation, one per day, their
lean (up share - down share); trade it with >= N_MIN days and |lean| >= THETA. The situation, fixed before this run
(from the learning half of rarity_lean.py): L3 = smoothness within 0.1, the deepest pullbacks alike, the same close
against the last top / bottom; L6 = L3 + the same 120-bar way, sizes within 1.4x, positions within 0.2 and the same
edge. The trade as v2b (entry TF by ATR, stop one entry-TF ATR >= 5 USD, target 10 U, 12 entry-TF bars, the auditor's
costs, one position at a time); the cell (level, N_MIN, THETA) chosen walk-forward month by month (wf.walk_forward).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/v2s.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from picture import EPISODE_DAYS, KEYS, as_arrays  # noqa: E402
from rarity import part_masks, thirds  # noqa: E402
from rarity_lean import day_lean  # noqa: E402

TRG = ("M5", "M1")
LEVELS = {"L3": ("smoothness", "pullback", "last top/bottom"),
          "L6": ("smoothness", "pullback", "last top/bottom", "120 bars' way", "size", "position")}
CELLS = [(lv, n, th) for lv in LEVELS for n in (5, 10) for th in (0.2, 0.4)]


def situation_leans(T: pd.DataFrame, SH: np.ndarray, day: np.ndarray, cls: np.ndarray, rows: np.ndarray,
                    tf_idx: list[int]) -> dict[str, np.ndarray]:
    """Per level, (matching days, lean) for each of rows: the moments of days <= the row's day - EPISODE_DAYS in the
    same M5 + M1 situation, each day's first (rarity_lean.day_lean). SH[:, tf_idx] = the M5 and M1 outlines."""
    A = as_arrays([[{k: T[f"{tf}_{k}"].iloc[i] for k in KEYS} for tf in TRG] for i in range(len(T))])
    shp = SH[:, tf_idx]
    segs = thirds(shp)
    out = {lv: np.full((len(rows), 2), np.nan) for lv in LEVELS}
    for j, r in enumerate(rows):
        cand = np.nonzero(day <= day[r] - EPISODE_DAYS)[0]
        m = part_masks(A, shp, segs, int(r), cand)
        for lv, parts in LEVELS.items():
            acc = np.logical_and.reduce([m[p].all(axis=1) for p in parts])
            out[lv][j] = day_lean(day[cand[acc]], cls[cand[acc]])
    return out


def side_of(n: float, lean: float, n_min: int, theta: float) -> int:
    """The side to trade: >= n_min matching days and the lean at least theta either way; else 0."""
    if not (n >= n_min and np.isfinite(lean)):
        return 0
    return 1 if lean >= theta - 1e-9 else (-1 if lean <= -theta + 1e-9 else 0)


def main() -> None:
    import foundation as F  # noqa: PLC0415
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415
    from lvl2 import MINS, NS_MIN, manage  # noqa: PLC0415
    from v2b import TFS, plan  # noqa: PLC0415

    plib.gold.below_normal_priority()
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    SH = np.load(HERE / "moment_shapes_3y.npy").astype(float)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((pd.DatetimeIndex(T.t_dec).tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    cls = T.cls.to_numpy().astype(str)
    snaps = np.nonzero((T.kind == "snap").to_numpy())[0]
    lv = situation_leans(T, SH, day, cls, snaps, [TFS.index(tf) for tf in TRG])
    L = pd.DataFrame({"row": snaps, **{f"{k}_n": v[:, 0] for k, v in lv.items()}, **{f"{k}_lean": v[:, 1] for k, v in lv.items()}})
    L.to_parquet(HERE / "v2s_leans.parquet")
    # the same leans as rarity_lean.py's for the snaps it measured (levels 3 and 6 of the trigger layer)
    D = pd.read_parquet(HERE / "rarity_lean_snaps.parquet")
    D = D[(D.layer == "trg") & D.level.str.strip().isin(["3 +last top/bottom", "6 +position"])]
    for lev, name in (("L3", "3 +last top/bottom"), ("L6", "6 +position")):
        d = D[D.level.str.strip() == name].merge(L, on="row")
        assert len(d) and (d.n_days == d[f"{lev}_n"]).all(), lev
        assert np.allclose(d.lean, d[f"{lev}_lean"], equal_nan=True, atol=1e-12), lev
    print("leans: every snap", len(snaps), "; equal to rarity_lean's where it measured", flush=True)
    m = jlib.m1_frame("XAUUSD")
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    ot_ns = m.index.tz_convert("UTC").as_unit("ns").asi8
    ny = plib.ny_mask(m.index)
    s_ns = pd.DatetimeIndex(T.t_dec).as_unit("ns").asi8
    atr_at = {}
    for tf, rule in (("M1", None), ("M5", "5min"), ("M15", "15min"), ("M30", "30min")):
        if rule is None:
            hh, ll, cc, av = h, lo, c, ot_ns + NS_MIN
        else:
            b = plib.tf_bars(m, rule)
            hh, ll, cc = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
            av = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
        a = F.atr(hh, ll, cc, 14)
        k = np.searchsorted(av, s_ns, side="right") - 1
        atr_at[tf] = np.where(k >= 0, a[np.maximum(k, 0)], np.nan)
    j0s = np.searchsorted(ot_ns, s_ns)
    empty = (np.array([], np.int64), np.array([], float))
    cells = {}
    for level, n_min, theta in CELLS:
        rows, busy = [], -1
        for j, e in enumerate(snaps):
            n, x = lv[level][j]
            side = side_of(n, x, n_min, theta)
            j0 = int(j0s[e])
            if side == 0 or j0 >= len(o) or j0 <= busy or ot_ns[j0] - s_ns[e] > 5 * 60 * 10**9:
                continue
            etf, sl, tp = plan({tf: atr_at[tf][e] for tf in atr_at}, c[j0 - 1])
            ss = 0.20 if ny[j0] else 0.15
            entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
            t_end = int(ot_ns[j0] + 12 * MINS[etf] * NS_MIN)
            x_ = manage(o, h, lo, c, sp, ot_ns, j0, side, entry, sl, tp, 0.0, *empty, 99.0, t_end, 0.07, ss)
            rows.append(dict(t=m.index[j0 - 1], j0=j0, row=int(e), side=side, etf=etf, sl=sl, tp=tp, exit=x_["exit"],
                             pnl=x_["pnl"], R=x_["pnl"] / (sl + ss), xj=x_["xj"], snap=T.name.iloc[e], n_days=int(n),
                             lean=float(x)))
            busy = x_["xj"]
        if rows:
            Dc = pd.DataFrame(rows)
            Dc["x_t"] = wf.exit_time(m.index, Dc.xj.to_numpy())
            cells[f"{level}_n{n_min}_th{theta}"] = Dc
    pd.set_option("display.width", 250)
    print("cells:", {k: len(v) for k, v in cells.items()})
    for k, v in cells.items():  # every cell over each half, before the walk-forward picks among them
        for name, part in (("learning", v[v.t < plib.EXAM_START]), ("exam", v[v.t >= plib.EXAM_START])):
            print(f"  {k} {name}: {len(part)} trades, win {(part.exit == 'win').mean():.3f}, R {part.R.mean():+.3f}, "
                  f"USD {part.pnl.sum():+.1f}")
    WF, months = wf.walk_forward(cells, "2024-05", "2026-10")
    WF.to_parquet(HERE / "v2s_wf_trades.parquet")
    months.to_csv(HERE / "v2s_wf_months.csv", index=False)
    print(months.to_string(index=False))
    Wk = wf.weekly(WF[WF.t >= plib.EXAM_START])
    Wk.to_csv(HERE / "v2s_wf_exam_weeks.csv", index=False)
    print("\nthe exam week by week (Thai weeks, Monday):")
    print(Wk.to_string(index=False))
    split, end = plib.EXAM_START, plib.EXAM_END
    for name, part, a, b in (("2024-05 .. 2026-04-17 (learning)", WF[WF.t < split], "2024-05-01", "2026-04-18"),
                             ("2026-04-18 .. 2026-10-16 (the exam)", WF[(WF.t >= split) & (WF.t < end)], "2026-04-18", "2026-10-17")):
        if part.empty:
            print(f"{name}: no trades")
            continue
        eq = part.pnl.cumsum()
        print(f"{name}: {len(part)} trades ({len(part) / np.busday_count(a, b):.2f} a weekday), win "
              f"{(part.exit == 'win').mean():.3f}, R {part.R.mean():+.3f}, USD {part.pnl.sum():+.1f}, max DD "
              f"{(eq.cummax() - eq).max():.1f}, worst {part.pnl.min():+.2f}, longest losing streak "
              f"{wf.longest_run(part.pnl.to_numpy() < 0)}")


if __name__ == "__main__":
    main()
