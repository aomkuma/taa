"""V2's entry, after v2s (2026-10-19 01:50 Thai): the trigger situation's lean told the way of the next 10 U run, but
entering at the snap lost - when the lean was right the run started a median 6 minutes later from a dip of a median
5 USD against the trade (75 %: 11 USD, the learning half), and the stop (~6.5 USD) went first in half of them. Two
entries that wait for the dip, against the snap entry, with the lean, the cells and the walk-forward of v2s:
- limit: a limit order D USD beyond the snap's price the lean's way (a buy D below), valid 30 minutes; the stop S
  USD from the fill;
- turn: after the snap, the running extreme against the lean (a buy: the lowest low); the first M1 close beyond the
  extreme bar's other end (a buy: above that bar's high) enters at the next open, the stop beyond the extreme by
  0.3 USD; skipped when that stop is over MAX_STOP; the signal valid 30 minutes;
the target 10 U, out after H minutes, the auditor's costs, one position at a time. After both lost on the learning
half (2026-10-19 02:05 Thai), a third that enters only once price moves the lean's way:
- stop: a stop order D USD beyond the snap's price the lean's way (a buy stop D above), valid 30 minutes, filled with
  the slip; the stop S USD from the fill; the target 5 or 10 U;
The variant is chosen on the learning half only (`v2e.py`); the exam runs once with the chosen variant
(`v2e.py exam NAME`).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/v2e.py [exam VARIANT]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

NS_MIN = 60 * 10**9
WAIT = 30  # minutes an order or a turn signal is valid after the snap
BUF = 0.3  # the turn's stop beyond the extreme, USD
VARIANTS = {f"limit_D{d}_S{s}_H{hh}": ("limit", d, s, hh, 10) for d in (3, 5) for s in (5, 8) for hh in (15, 30)}
VARIANTS |= {f"turn_max{s}_H{hh}": ("turn", 0, s, hh, 10) for s in (5, 8) for hh in (15, 30)}
VARIANTS |= {f"stop_D{d}_S{s}_T{tu}_H{hh}": ("stop", d, s, hh, tu) for d in (1, 3) for s in (3, 5) for tu in (5, 10)
             for hh in (15, 30)}


def limit_fill(o, h, lo, sp, ot_ns, j0: int, side: int, limit: float, t_last: int) -> tuple[int, float]:
    """A buy limit fills when the ask reaches it (the bid low + spread <= limit), a sell limit when the bid does (the
    high >= limit), on the M1 bars from j0 opening before t_last; a bar opening beyond the limit fills at its open
    (the ask for a buy). (-1, nan) when it does not fill."""
    j = j0
    while j < len(o) and ot_ns[j] < t_last:
        if side > 0:
            if o[j] + sp[j] <= limit:
                return j, float(o[j] + sp[j])
            if lo[j] + sp[j] <= limit:
                return j, float(limit)
        else:
            if o[j] >= limit:
                return j, float(o[j])
            if h[j] >= limit:
                return j, float(limit)
        j += 1
    return -1, float("nan")


def stop_fill(o, h, lo, sp, ot_ns, j0: int, side: int, level: float, t_last: int, slip: float) -> tuple[int, float]:
    """A buy stop fills when the ask reaches it (the high + spread >= level), a sell stop when the bid does (the low <=
    level), on the M1 bars from j0 opening before t_last; a bar opening beyond the level fills at its open (the ask for
    a buy); the slip against the trade. (-1, nan) when it does not fill."""
    j = j0
    while j < len(o) and ot_ns[j] < t_last:
        if side > 0:
            if o[j] + sp[j] >= level:
                return j, float(o[j] + sp[j] + slip)
            if h[j] + sp[j] >= level:
                return j, float(level + slip)
        else:
            if o[j] <= level:
                return j, float(o[j] - slip)
            if lo[j] <= level:
                return j, float(level - slip)
        j += 1
    return -1, float("nan")


def turn_entry(o, h, lo, c, sp, ot_ns, j0: int, side: int, t_last: int, max_stop: float, slip: float) -> tuple[int, float, float]:
    """The running extreme against the side from bar j0 (a buy: the lowest low; a sell: the highest ask high); a bar
    making a new extreme restarts the wait; the first later bar closing beyond the extreme bar's other end (a buy:
    above its high; a sell: below its low) signals, entering at the next bar's open (a buy at the ask) + slip, the
    stop BUF beyond the extreme. (entry bar, entry, stop distance); (-1, nan, nan) when no signal before t_last or
    the stop distance is over max_stop."""
    ext, j = j0, j0 + 1
    while j + 1 < len(o) and ot_ns[j] < t_last:
        if side > 0:
            if lo[j] < lo[ext]:
                ext = j
            elif c[j] > h[ext]:
                entry = o[j + 1] + sp[j + 1] + slip
                sl = entry - (lo[ext] - BUF)
                return (j + 1, float(entry), float(sl)) if 0 < sl <= max_stop else (-1, float("nan"), float("nan"))
        else:
            if h[j] + sp[j] > h[ext] + sp[ext]:
                ext = j
            elif c[j] < lo[ext]:
                entry = o[j + 1] - slip
                sl = (h[ext] + sp[ext] + BUF) - entry
                return (j + 1, float(entry), float(sl)) if 0 < sl <= max_stop else (-1, float("nan"), float("nan"))
        j += 1
    return -1, float("nan"), float("nan")


def trades_for(variant: tuple, lv: pd.DataFrame, cell: tuple, mk: dict) -> pd.DataFrame:
    """One cell's trades under one entry variant, every snap in order, one attempt or position at a time."""
    from lvl2 import manage  # noqa: PLC0415
    from v2s import side_of  # noqa: PLC0415

    mode, d, s, hh, tgt_u = variant
    level, n_min, theta = cell
    o, h, lo, c, sp, ot_ns, ny = (mk[k] for k in ("o", "h", "lo", "c", "sp", "ot_ns", "ny"))
    empty = (np.array([], np.int64), np.array([], float))
    rows, free_at = [], -1  # free_at: the first M1 bar a new attempt may use
    for r in lv.itertuples():
        side = side_of(getattr(r, f"{level}_n"), getattr(r, f"{level}_lean"), n_min, theta)
        j0 = int(r.j0)
        if side == 0 or j0 >= len(o) or j0 < free_at or ot_ns[j0] - r.s_ns > 5 * NS_MIN:
            continue
        t_last = int(ot_ns[j0] + WAIT * NS_MIN)
        ref = c[j0 - 1]
        if mode == "limit":
            je, entry = limit_fill(o, h, lo, sp, ot_ns, j0, side, ref - side * d, t_last)
            sl = float(s)
        elif mode == "stop":  # managed from its fill bar, the stop first (the bar's low may have come before the fill)
            je, entry = stop_fill(o, h, lo, sp, ot_ns, j0, side, ref + side * d, t_last, 0.07)
            sl = float(s)
        else:
            je, entry, sl = turn_entry(o, h, lo, c, sp, ot_ns, j0, side, t_last, float(s), 0.07)
        if je < 0:
            free_at = int(np.searchsorted(ot_ns, t_last))  # the attempt ends with its window
            continue
        tp = tgt_u * ref / 4100.0
        ss = 0.20 if ny[je] else 0.15
        t_end = int(ot_ns[je] + hh * NS_MIN)
        if mode == "limit":  # filled inside bar je: its stop counts, its target not (the high may have come first)
            hit = lo[je] <= entry - sl if side > 0 else h[je] + sp[je] >= entry + sl
            x = dict(exit="stop", pnl=-sl - ss, xj=je) if hit else manage(o, h, lo, c, sp, ot_ns, je + 1, side, entry, sl, tp,
                                                                         0.0, *empty, 99.0, t_end, 0.07, ss)
        else:
            x = manage(o, h, lo, c, sp, ot_ns, je, side, entry, sl, tp, 0.0, *empty, 99.0, t_end, 0.07, ss)
        rows.append(dict(t=mk["index"][je], j0=j0, je=je, row=int(r.row), side=side, entry=entry, sl=sl, tp=tp,
                         exit=x["exit"], pnl=x["pnl"], R=x["pnl"] / (sl + ss), xj=x["xj"], n_days=int(getattr(r, f"{level}_n")),
                         lean=float(getattr(r, f"{level}_lean"))))
        free_at = max(int(x["xj"]) + 1, int(np.searchsorted(ot_ns, t_last)))
    return pd.DataFrame(rows)


def main() -> None:
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415
    from v2s import CELLS  # noqa: PLC0415

    plib.gold.below_normal_priority()
    exam = len(sys.argv) > 2 and sys.argv[1] == "exam"
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    lv = pd.read_parquet(HERE / "v2s_leans.parquet")
    m = jlib.m1_frame("XAUUSD")
    mk = dict(o=m.open.to_numpy(float), h=m.high.to_numpy(float), lo=m.low.to_numpy(float), c=m.close.to_numpy(float),
              sp=m.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=m.index.tz_convert("UTC").as_unit("ns").asi8,
              ny=plib.ny_mask(m.index), index=m.index)
    lv["s_ns"] = pd.DatetimeIndex(T.t_dec.to_numpy()[lv.row]).as_unit("ns").asi8
    lv["j0"] = np.searchsorted(mk["ot_ns"], lv.s_ns.to_numpy())
    names = [sys.argv[2]] if exam else list(VARIANTS)
    pd.set_option("display.width", 220)
    res = []
    for name in names:
        cells = {}
        for cell in CELLS:
            D = trades_for(VARIANTS[name], lv, cell, mk)
            if len(D):
                D["x_t"] = wf.exit_time(m.index, D.xj.to_numpy())
                cells[f"{cell[0]}_n{cell[1]}_th{cell[2]}"] = D
        WF, months = wf.walk_forward(cells, "2024-05", "2026-10")
        learn = WF[WF.t < plib.EXAM_START]
        res.append(dict(variant=name, trades=len(learn), per_weekday=len(learn) / np.busday_count("2024-05-01", "2026-04-18"),
                        win=(learn.exit == "win").mean(), R=learn.R.mean(), usd=learn.pnl.sum(),
                        worst=learn.pnl.min(), streak=wf.longest_run(learn.pnl.to_numpy() < 0)))
        print(res[-1], flush=True)
        if exam:
            WF.to_parquet(HERE / f"v2e_{name}_wf_trades.parquet")
            print(months.to_string(index=False))
            ex = WF[(WF.t >= plib.EXAM_START) & (WF.t < plib.EXAM_END)]
            print("\nthe exam week by week (Thai weeks, Monday):")
            print(wf.weekly(ex).to_string(index=False))
            eq = ex.pnl.cumsum()
            print(f"the exam: {len(ex)} trades ({len(ex) / np.busday_count('2026-04-18', '2026-10-17'):.2f} a weekday), win "
                  f"{(ex.exit == 'win').mean():.3f}, R {ex.R.mean():+.3f}, USD {ex.pnl.sum():+.1f}, max DD "
                  f"{(eq.cummax().clip(lower=0) - eq).max():.1f}, worst {ex.pnl.min():+.2f}, longest losing streak "
                  f"{wf.longest_run(ex.pnl.to_numpy() < 0)}")
    if not exam:
        print("\nthe learning half (2024-05 .. 2026-04-17) only:")
        print(pd.DataFrame(res).sort_values("R", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
