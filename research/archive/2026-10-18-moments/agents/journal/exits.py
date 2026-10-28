"""Round 3 exit / entry changes on a rule's entries (design data, by half-year, ours vs the coin on the same minutes):
X1 a time check (exit at minute k if the best move is under g of the target), X2 a limit entry at the retest of
the level, X3 a filter on the room to the 72-hour extreme. notes.md has the exact rules (written first).

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/journal/exits.py SYM RULE [design|test]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jlib  # noqa: E402
from rules import RULES, signals  # noqa: E402


def trade2(P: jlib.Instr, e: int, side: int, tp_px: float, sl_px: float, be: float | None, hz: int, ss: float,
           chk: tuple[int, float] | None = None, limit: float | None = None, lwin: int = 10) -> dict | None:
    """One trade with fixed target / stop *prices*. Market entry at bar e's open, or a limit at *limit* filled in
    the first *lwin* bars (None if never filled). *chk* = (k, g): at the close of the k-th bar after the entry, exit
    at market if the best move so far is under g of the planned target distance."""
    n = len(P.o)
    if limit is None:
        j0 = e
        entry = P.o[e] + (P.sp[e] + P.slip if side > 0 else -P.slip)
    else:
        j0 = None
        for j in range(e, min(e + lwin, n)):
            touch = (P.lo[j] + P.sp[j] <= limit) if side > 0 else (P.h[j] >= limit)
            if touch:
                j0 = j
                break
        if j0 is None:
            return None
        entry = min(limit, P.o[j0] + P.sp[j0]) if side > 0 else max(limit, P.o[j0])
    tp = (tp_px - entry) * side
    sl = (entry - sl_px) * side
    if tp <= 0 or sl <= 0:
        return None
    stop, armed, mfe = sl_px, False, 0.0
    end = min(j0 + hz, n - 1)
    res = None
    for j in range(j0, end):
        adv = P.lo[j] if side > 0 else P.h[j] + P.sp[j]
        fav = P.h[j] if side > 0 else P.lo[j] + P.sp[j]
        if (adv - stop) * side <= 0:
            res = ("stop" if not armed else "be", (stop - side * ss - entry) * side, j)
            break
        if (fav - entry) * side >= tp and not (limit is not None and j == j0):
            res = ("win", tp, j)
            break
        mfe = max(mfe, (fav - entry) * side)
        if be is not None and not armed and mfe >= be * tp:
            armed, stop = True, entry
        if chk is not None and j - j0 + 1 == chk[0] and mfe < chk[1] * tp:
            px = P.c[j] - (P.slip if side > 0 else -(P.sp[j] + P.slip))
            res = ("check", (px - entry) * side, j)
            break
    if res is None:
        x = end - 1
        px = P.c[x] - (P.slip if side > 0 else -(P.sp[x] + P.slip))
        res = ("time", (px - entry) * side, x)
    kind = ""
    if res[0] == "stop":
        later = range(res[2] + 1, min(j0 + 120, n))
        hit = any(((P.h[k] if side > 0 else P.lo[k] + P.sp[k]) - entry) * side >= tp for k in later)
        kind = "3" if hit else ("2" if mfe >= 0.5 * tp else "1")
    return dict(exit=res[0], pnl=res[1], mins=res[2] - e + 1, kind=kind, sl=sl, R=res[1] / (sl + ss))


def run2(sig: pd.DataFrame, P: jlib.Instr, rule: dict, var: dict, coin: np.random.Generator | None = None) -> pd.DataFrame:
    rows, free, count = [], pd.Timestamp(0, tz="UTC"), {}
    x = sig.sort_values("t").drop_duplicates("t")
    for r in x.itertuples():
        key = (r.t.normalize(), r.session)
        if r.t < free or count.get(key, 0) >= 2:
            continue
        s = int(r.side) if coin is None else int(coin.choice([-1, 1]))
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        fill = P.o[r.e] + (P.sp[r.e] + P.slip if s > 0 else -P.slip)  # the market fill the plan is built on
        tp_px = fill + s * rule["tp"] * r.unit
        sl_px = fill - s * r.sl
        limit = None
        if var.get("limit"):
            # ours: the retest of the level (+ an offset); the coin: the same distance under its own market fill
            so = int(r.side)
            fill_o = P.o[r.e] + (P.sp[r.e] + P.slip if so > 0 else -P.slip)
            d = max((fill_o - (r.level + so * var["limit"] * r.atr1)) * so, 0.0)
            limit = fill - s * d
        out = trade2(P, int(r.e), s, tp_px, sl_px, rule["be"], rule["hz"], ss, var.get("chk"), limit)
        if out is None:
            free = r.t + pd.Timedelta(minutes=10) if var.get("limit") else free
            continue
        out |= {"t": r.t, "session": r.session, "side": s}
        rows.append(out)
        free, count[key] = r.t + pd.Timedelta(minutes=int(out["mins"])), count.get(key, 0) + 1
    return pd.DataFrame(rows)


VARIANTS = {
    "W3 as is": {},
    "X1 k5 g.25": {"chk": (5, 0.25)},
    "X1 k10 g.25": {"chk": (10, 0.25)},
    "X1 k10 g.4": {"chk": (10, 0.4)},
    "X1 k15 g.25": {"chk": (15, 0.25)},
    "X1 k15 g.4": {"chk": (15, 0.4)},
    "X2 limit lvl+.5ATR": {"limit": 0.5},
    "X2 limit lvl+1ATR": {"limit": 1.0},
    "X3 room72 < .5": {"room": 0.5},
    "X3 room72 < .25": {"room": 0.25},
    "X3 room72 < .75": {"room": 0.75},
    "X3 room72 < 1": {"room": 1.0},
    "X3 + X1 k10 g.25": {"room": 0.5, "chk": (10, 0.25)},
}


def main() -> None:
    sym, name = sys.argv[1], sys.argv[2]
    part = sys.argv[3] if len(sys.argv) > 3 else "design"
    only = sys.argv[4:] or list(VARIANTS)
    jlib.gold.below_normal_priority()
    P = jlib.Instr(sym)
    D = jlib.cands(sym, part)
    D["e"] = P.e_of(D.t)
    rule = RULES[name]
    sig = signals(D, rule, P)
    p = sig.e.to_numpy() - 1
    s = sig.side.to_numpy()
    front = np.where(s > 0, np.array([P.h[i - 4320 : i - 15].max() for i in p]), np.array([P.lo[i - 4320 : i - 15].min() for i in p]))
    sig["room72_tp"] = (front - P.c[p]) * s / (rule["tp"] * sig.unit)
    windows = jlib.HALVES if part == "design" else [("TEST 2026-03..10 (SEEN)", "2026-03-01", "2026-10-14")]
    for vn in only:
        var = VARIANTS[vn]
        x0 = sig[sig.room72_tp < var["room"]] if "room" in var else sig
        print(f"\n{sym} {name} + {vn}")
        tot = []
        for hn, a, b in windows:
            x = x0[(x0.t >= pd.Timestamp(a, tz="UTC")) & (x0.t < pd.Timestamp(b, tz="UTC"))]
            r = run2(x, P, rule, var)
            cs = [run2(x, P, rule, var, np.random.default_rng(300 + k)) for k in range(10)]
            cr = np.mean([c.R.mean() for c in cs if len(c)])
            cw = np.mean([(c.exit == "win").mean() for c in cs if len(c)])
            if len(r):
                r["half"] = hn
                tot.append(r)
            print(jlib.line(hn, r, a, b, P, "USD" if sym == "XAUUSD" else "pips") + f" | coin {cr:+.3f}R win {100 * cw:.0f}%")
        if tot:
            z = pd.concat(tot)
            print(f"  ALL: {len(z)} trades, win {100 * (z.exit == 'win').mean():.0f}%, {z.R.mean():+.3f} R, halves+ "
                  f"{(z.groupby('half').R.mean() > 0).sum()}/{z.half.nunique()}; exits {z.exit.value_counts().to_dict()}")
            print("    account: " + jlib.account(z.reset_index(drop=True), P))
            if part == "test":
                z.to_parquet(HERE / f"test_{sym}_{name}_{vn.split()[0]}.parquet")


if __name__ == "__main__":
    main()
