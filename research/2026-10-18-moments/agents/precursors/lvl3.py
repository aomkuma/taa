"""LV3 (notes.md "LV3"): LV2's context with the owner's legs as the entry - the pause's M1 peaks since its highest one,
at least N of them, the newest lower than the highest, the highest having reached the level zone (sells; mirrored).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/lvl3.py design
    ... lvl3.py window S N TARGET P            (the one window run of the cell chosen on design)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import lvl2  # noqa: E402
from fingerprint import zigzag  # noqa: E402
from lvl2 import MINS, NS_MIN, learned_buffer, outcome, setup_at  # noqa: E402

SWINGS = (1.5, 2.0)


@dataclass(frozen=True)
class Params(lvl2.Params):
    s: float = 1.5  # the M1 swing that counts as a leg, in M1 ATRs
    n: int = 5  # the legs needed (0 = adaptive: 3 when the move into the start was < 5 A, else 5)


# ---------------------------------------------------------------- pure pieces
def pause_legs(px: np.ndarray, side: int) -> np.ndarray:
    """The pause = the pause-type swings (sells: peaks) from its most extreme one on (a run through every earlier
    peak restarts the count). px in time order."""
    if len(px) == 0:
        return px
    k = len(px) - 1 - int(np.argmax(px[::-1])) if side < 0 else len(px) - 1 - int(np.argmin(px[::-1]))  # the latest extreme
    return px[k:]


def pause_trigger(legs: np.ndarray, n_req: int, level: float, near: float, side: int) -> bool:
    """>= n_req legs (counting the extreme one), the newest not beyond the extreme (sells: lower than the highest
    peak), and the extreme reached the level zone (sells: the highest peak >= level - near)."""
    if len(legs) < max(n_req, 2):
        return False
    ext, newest = legs[0], legs[-1]
    if side < 0:
        return newest < ext and ext >= level - near
    return newest > ext and ext <= level + near


def legs_needed(p: Params, move_into_start_atr: float) -> int:
    if p.n > 0:
        return p.n
    return 3 if move_into_start_atr < 5 else 5


# ---------------------------------------------------------------- the market
class Market(lvl2.Market):
    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        E = self.tf["M1"]
        self.m1zz = {}
        for s in SWINGS:
            pb, pp, pt, pc = zigzag(E["h"], E["lo"], E["atr"], s)
            conf_at = np.full(len(E["h"]), -1)
            conf_at[pc] = np.arange(len(pc))  # the pivot confirmed by the close of each M1 bar (one at most)
            self.m1zz[s] = dict(b=pb, p=pp, t=pt, c=pc, conf_at=conf_at, start=self.ot_ns[pb])


def signals(M: Market, dec: np.ndarray, p: Params) -> pd.DataFrame:
    Z = M.m1zz[p.s]
    rows, used = [], set()
    over_l, res_l, won_l = [], [], []
    for t in dec:
        if t + 1 >= len(M.o):
            continue
        q = Z["conf_at"][t]
        if q < 0:  # no M1 swing confirmed at this close
            continue
        s = setup_at(M, t, p)
        if s is None:
            continue
        side = s["side"]
        if Z["t"][q] != (1 if side < 0 else -1):  # sells wait for a new peak, buys for a new trough
            continue
        key = (s["etf"], s["t_start"], round(s["level"], 2), side)
        if key in used:
            continue
        sel = np.arange(q + 1)
        sel = sel[(Z["start"][sel] >= s["t_ext"]) & (Z["t"][sel] == Z["t"][q])]  # swings after the start's extreme
        legs = pause_legs(Z["p"][sel], side)
        E = M.tf[s["etf"]]
        kz = np.searchsorted(E["zz_known"], s["t_ns"], side="right") - 1
        move_in = abs(E["zz_p"][kz] - E["zz_p"][kz - 1]) / s["a"] if kz >= 1 else 0.0
        if not pause_trigger(legs, legs_needed(p, move_in), s["level"], p.k * s["a"], side):
            continue
        used.add(key)
        j0 = t + 1
        lv, a = s["level"], s["a"]
        entry = M.o[j0] - M.slip if side < 0 else M.o[j0] + M.sp[j0] + M.slip
        t_end = int(M.ot_ns[j0] + p.time_bars * MINS[s["etf"]] * NS_MIN)
        tgt2 = max((entry - s["t_px"]) * -side, p.min_target)
        won, over, resolved = outcome(M.o, M.h, M.lo, M.sp, M.ot_ns, j0, side, entry, lv, tgt2, t_end)
        arr_o, arr_r, arr_w = np.array(over_l), np.array(res_l, dtype=np.int64), np.array(won_l, bool)
        bufs = {qq: learned_buffer(arr_o, arr_r, arr_w, s["t_ns"], qq, p.min_history) for qq in (70.0, 80.0, 90.0)}
        closes = M.c[int(np.searchsorted(M.ot_ns, s["t_start"])):t + 1]
        rows.append(dict(t=t, j0=j0, entry=entry, tgt2=tgt2, won=won, over_A=over / a, resolved=resolved,
                         closes_max_beyond=float(((closes - lv) * -side).max()) / a if len(closes) else -np.inf,
                         legs=len(legs), move_in=move_in, **{f"b{int(qq)}": bufs[qq] for qq in bufs}, **s))
        over_l.append(over / a)
        res_l.append(resolved)
        won_l.append(won)
    return pd.DataFrame(rows)


def main() -> None:
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    mode = sys.argv[1] if len(sys.argv) > 1 else "design"
    M = Market()
    W = plib.window_mask(M.ot)
    inwin = W.any(axis=1).to_numpy()
    ny = W[[c for c in W.columns if c.startswith("NY")]].any(axis=1).to_numpy()
    split = pd.Timestamp("2026-04-18", tz="UTC")
    dec = np.nonzero(inwin & np.asarray(M.ot >= pd.Timestamp("2023-08-15", tz="UTC")))[0]
    grid = [(s, n, tg, q) for s in SWINGS for n in (3, 4, 5, 0) for tg in ("T1", "T2") for q in (80.0, 90.0)]
    if mode == "window":
        grid = [(float(sys.argv[2]), int(sys.argv[3]), sys.argv[4], float(sys.argv[5]))]
    rows = []
    for s, n in sorted({(g[0], g[1]) for g in grid}):
        S = signals(M, dec, Params(k=0.5, s=s, n=n))
        S.to_parquet(HERE / f"lvl3_signals_s{s}_n{n}.parquet")
        for tg, q in [(g[2], g[3]) for g in grid if (g[0], g[1]) == (s, n)]:
            T = lvl2.trades(M, S, Params(k=0.5, s=s, n=n, target=tg, p=q), ny)
            if T.empty:
                continue
            part = (T.t >= pd.Timestamp("2023-11-01", tz="UTC")) & (T.t < split) if mode == "design" else (T.t >= split)
            T = T[part]
            T.to_parquet(HERE / f"lvl3_{mode}_s{s}_n{n}_{tg}_p{int(q)}.parquet")
            eq = T.pnl.cumsum()
            days = np.busday_count("2023-11-01", "2026-04-18") if mode == "design" else np.busday_count("2026-04-18", "2026-10-17")
            rows.append(dict(s=s, n=n if n else "adaptive", target=tg, p=q, trades=len(T), per_wd=round(len(T) / days, 2),
                             win=round((T.exit == "win").mean(), 3), R=round(T.R.mean(), 3), usd=round(T.pnl.sum(), 1),
                             maxdd=round((eq.cummax() - eq).max(), 1), sl_med=round(T.sl.median(), 2),
                             exits=" ".join(f"{e} {v:.0%}" for e, v in T.exit.value_counts(normalize=True).items())))
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(HERE / f"lvl3_{mode}.csv", index=False)


if __name__ == "__main__":
    main()
