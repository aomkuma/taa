"""Step table: the design rule, then each filter from the loser diagnosis applied to the signals before the
one-position selection. Development half-years (or --test once a step set is frozen in notes.md).

    python steps.py GEOM [--test]     GEOM in diag.RULES
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

from common import DEV, TEST, gold
from diag import RULES, situations, trades
from exp import Lab

warnings.filterwarnings("ignore")


def masks(L: Lab, S: pd.DataFrame) -> dict:
    """Each filter as a function (F, side) -> bool array over all bars (side = the fade's side per bar)."""
    m15 = S.m15_slope.to_numpy()
    pos = S.pos240.to_numpy()
    ses = S.ses.to_numpy()
    leg = S.h1_leg3.to_numpy()
    rd = S.round10_d.to_numpy()
    ru = S.round10_u.to_numpy()
    top = S.top60_is_4h.to_numpy(bool)
    bot = S.bot60_is_4h.to_numpy(bool)
    mv15 = S.move15.to_numpy()
    gap = S.h1_gap_e50.to_numpy()
    return {
        "not off a fresh 4h extreme": lambda F, s: ~np.where(s > 0, top, bot),
        "15-bar move against < 4 ATR": lambda F, s: ~(mv15 * s <= -4),
        "H1 not flat": lambda F, s: np.abs(gap) >= 0.85,
        "no London": lambda F, s: ses != 1,
        "M15 slope not against": lambda F, s: ~(m15 * s < 0),
        "upper half of 4h range": lambda F, s: np.where(s > 0, pos, 1 - pos) >= 0.5,
        "H1 3h leg not against": lambda F, s: ~(leg * s < 0),
        "round 10 behind entry (<= 2 ATR)": lambda F, s: np.where(s > 0, rd, ru) <= 2,
    }


W = ["no London", "M15 slope not against", "upper half of 4h range"]
STEPS = [
    ("W = no London + M15 + upper half 4h", W),
    ("W + not off a fresh 4h extreme", W + ["not off a fresh 4h extreme"]),
    ("W + 15-bar move < 4 ATR", W + ["15-bar move against < 4 ATR"]),
    ("W + H1 not flat", W + ["H1 not flat"]),
    ("W + not off 4h extreme + 15-bar", W + ["not off a fresh 4h extreme", "15-bar move against < 4 ATR"]),
    ("W + all three", W + ["not off a fresh 4h extreme", "15-bar move against < 4 ATR", "H1 not flat"]),
    ("no London + M15 + not off 4h extreme", ["no London", "M15 slope not against", "not off a fresh 4h extreme"]),
    ("no London + M15 + not off + 15-bar", ["no London", "M15 slope not against", "not off a fresh 4h extreme",
                                            "15-bar move against < 4 ATR"]),
]
STEPS_R1 = [
    ("baseline", []),
    ("no London", ["no London"]),
    ("no London + M15 not against", ["no London", "M15 slope not against"]),
    ("no London + M15 + upper half 4h", ["no London", "M15 slope not against", "upper half of 4h range"]),
    ("no London + upper half 4h", ["no London", "upper half of 4h range"]),
    ("M15 not against", ["M15 slope not against"]),
    ("upper half 4h", ["upper half of 4h range"]),
    ("no London + M15 + H1 leg", ["no London", "M15 slope not against", "H1 3h leg not against"]),
    ("no London + M15 + round behind", ["no London", "M15 slope not against", "round 10 behind entry (<= 2 ATR)"]),
]


def account(t: pd.DataFrame) -> dict:
    u = t.sort_values("t").usd.to_numpy()
    eq = np.cumsum(u)
    dd = (np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max() if len(u) else 0
    streak = best = 0
    for v in u:
        streak = streak + 1 if v < 0 else 0
        best = max(best, streak)
    los = u[u < 0]
    return dict(worst=u.min() if len(u) else 0, avg_loss=los.mean() if len(los) else 0, streak=best, maxdd=dd)


def run(L: Lab, S: pd.DataFrame, geom: str, names: list[str], windows) -> pd.DataFrame:
    M = masks(L, S)
    cfg = dict(RULES[geom])
    fs = [M[n] for n in names]
    base_extra = lambda F, s: (L.B.ny_min < 930) & (L.B.ldn_min >= 420)  # noqa: E731

    def extra(F, side):
        ok = base_extra(F, side)
        for f in fs:
            ok &= f(F, side)
        return ok

    cfg["extra_override"] = extra
    return trades_with(L, cfg, windows)


def trades_with(L: Lab, cfg: dict, windows) -> pd.DataFrame:
    # diag.trades adds the base window itself; pass the full mask through 'extra' instead
    from sim import one_at_a_time
    from common import SLIP

    c = {k: v for k, v in cfg.items() if k != "extra_override"} | dict(extra=cfg["extra_override"])
    i, side = L.candidates(c)
    if c.get("sl_cap"):
        keep = c["sl"] * L.F.atr.to_numpy(float)[i] <= c["sl_cap"]
        i, side = i[keep], side[keep]
    d = L.sim(c, i, side)
    out = []
    for name, a, b in windows:
        ia, ib = L.B.idx(a), L.B.idx(b)
        t = one_at_a_time(d[(d.i >= ia) & (d.i < ib)])
        t = t[t.filled].copy()
        t["half"] = name[:2] if not name.startswith("TEST") else "T"
        out.append(t)
    t = pd.concat(out)
    t["R"] = t.usd / (t.sl + SLIP)
    t["t"] = L.B.ot[t.i.to_numpy()]
    return t


if __name__ == "__main__":
    gold.below_normal_priority()
    geom = sys.argv[1]
    L = Lab()
    S = situations(L)
    day = L.B.t64 // 86_400_000_000_000
    ndays = {n[:2]: np.unique(day[L.B.idx(a):L.B.idx(b)]).size for n, a, b in DEV}
    WIN = TEST if "--test" in sys.argv else DEV
    if "--test" in sys.argv:
        ndays = {"T": np.unique(day[L.B.idx("2026-03-01"):L.B.idx("2026-10-15")]).size}
    print(f"### {geom} ({'TEST' if WIN is TEST else 'development'}, real costs)")
    for label, names in STEPS_R1[:4] + STEPS:
        t = run(L, S, geom, names, WIN)
        by = t.groupby("half").R.mean()
        a = account(t)
        print(f"{label:40} n {len(t):5} ({len(t) / sum(ndays.values()):.2f}/d) R {t.R.mean():+.3f} | "
              + " ".join(f"{v:+.3f}" for v in by) + f" | +{int((by > 0).sum())}/{len(by)} | win {(t.exit == 'win').mean():.2f}"
              f" USD {t.usd.sum():+7.0f} worst {a['worst']:.1f} avg loss {a['avg_loss']:.1f} streak {a['streak']}"
              f" maxDD {a['maxdd']:.0f}", flush=True)
    _ = (trades, TEST)
