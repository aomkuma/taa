"""Setup OWN V2 on the library of the same picture (notes.md '"The same picture" redefined' and the moments): at each
of the owner's snap times the bot finds, per layer, the pattern of earlier days that is the same picture (picture.py)
in the library of snaps and the starts of every 10 U run (moments.py, 2023-11 on), and trades the way its earlier
episodes leaned; the trade as v2b (entry TF by ATR, stop one entry-TF ATR >= 5 USD, target 10 U, 12 entry-TF bars,
the auditor's costs, one position). The cell (layers, N_MIN, THETA) is chosen walk-forward month by month.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/v2c.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from picture import KEYS, FastPictureLibrary, evidence  # noqa: E402
from v2b import LAYER_TFS, TFS, decide, plan  # noqa: E402

LONG = {"ctx": "context (H4+H1)", "set": "setup (M30+M15)", "trg": "trigger (M5+M1)"}


def lean(lib: FastPictureLibrary, row: int, day: int) -> tuple[int, float, int]:
    """picture.evidence: other episodes only (>= 7 days before the decision)."""
    return evidence(lib, row, day)


def layer_inputs(T: pd.DataFrame, SH: np.ndarray, L: str):
    from library_match import LAYERS, attrs  # noqa: PLC0415

    tfs = LAYER_TFS[L]
    idx = [TFS.index(tf) for tf in tfs]
    codes = np.column_stack(attrs(T, T, LAYERS[LONG[L]])).astype(int)
    feats = [[{k: T[f"{tf}_{k}"].iloc[i] for k in KEYS} for tf in tfs] for i in range(len(T))]
    return codes, SH[:, idx], feats


def main() -> None:
    import foundation as F  # noqa: PLC0415
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415
    from lvl2 import MINS, NS_MIN, manage  # noqa: PLC0415

    plib.gold.below_normal_priority()
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    SH = np.load(HERE / "moment_shapes_3y.npy").astype(float)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((pd.DatetimeIndex(T.t_dec).tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    snaps = np.nonzero((T.kind == "snap").to_numpy())[0]
    lv = {}
    for L in ("ctx", "set", "trg"):
        codes, shp, feats = layer_inputs(T, SH, L)
        lib = FastPictureLibrary(codes, shp, feats)
        out = np.full((len(T), 3), np.nan)
        for r in range(len(T)):  # T is in decision order
            if T.kind.iloc[r] == "snap":
                out[r] = lean(lib, r, int(day[r]))
            lib.add(r, int(day[r]), str(T.cls.iloc[r]))
        lv[L] = out
        print(L, "patterns", len(lib.patterns), "| snaps with evidence", int((out[snaps, 0] >= 1).sum()), "of", len(snaps), flush=True)
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
    for layers in (("set",), ("trg",), ("set", "trg"), ("ctx", "set", "trg")):
        for n_min in (2, 3):
            for theta in (0.2, 0.4):
                rows, busy = [], -1
                for e in snaps:
                    leans = {L: (int(np.nan_to_num(lv[L][e, 0])), lv[L][e, 1]) for L in ("ctx", "set", "trg")}
                    side = decide(leans, layers, n_min, theta)
                    j0 = int(j0s[e])
                    if side == 0 or j0 >= len(o) or j0 <= busy or ot_ns[j0] - s_ns[e] > 5 * 60 * 10**9:
                        continue
                    etf, sl, tp = plan({tf: atr_at[tf][e] for tf in atr_at}, c[j0 - 1])
                    ss = 0.20 if ny[j0] else 0.15
                    entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
                    t_end = int(ot_ns[j0] + 12 * MINS[etf] * NS_MIN)
                    x = manage(o, h, lo, c, sp, ot_ns, j0, side, entry, sl, tp, 0.0, *empty, 99.0, t_end, 0.07, ss)
                    rows.append(dict(t=m.index[j0 - 1], j0=j0, row=int(e), side=side, etf=etf, sl=sl, tp=tp, exit=x["exit"],
                                     pnl=x["pnl"], R=x["pnl"] / (sl + ss), xj=x["xj"], snap=T.name.iloc[e],
                                     **{f"{L}_n": leans[L][0] for L in ("ctx", "set", "trg")},
                                     **{f"{L}_lean": leans[L][1] for L in ("ctx", "set", "trg")},
                                     **{f"{L}_pid": int(np.nan_to_num(lv[L][e, 2], nan=-1)) for L in ("ctx", "set", "trg")}))
                    busy = x["xj"]
                if rows:
                    D = pd.DataFrame(rows)
                    D["x_t"] = wf.exit_time(m.index, D.xj.to_numpy())
                    cells[f"{'+'.join(layers)}_n{n_min}_th{theta}"] = D
    pd.set_option("display.width", 250)
    print("cells:", {k: len(v) for k, v in cells.items()})
    WF, months = wf.walk_forward(cells, "2024-02", "2026-10")
    WF.to_parquet(HERE / "v2c_wf_trades.parquet")
    months.to_csv(HERE / "v2c_wf_months.csv", index=False)
    print(months.to_string(index=False))
    Wk = wf.weekly(WF[WF.t >= plib.EXAM_START])
    Wk.to_csv(HERE / "v2c_wf_exam_weeks.csv", index=False)
    print("\nthe exam week by week (Thai weeks, Monday):")
    print(Wk.to_string(index=False))
    split, end = plib.EXAM_START, plib.EXAM_END
    for name, part, a, b in (("2023-11 .. 2026-04-17 (learning)", WF[WF.t < split], "2023-11-01", "2026-04-18"),
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
