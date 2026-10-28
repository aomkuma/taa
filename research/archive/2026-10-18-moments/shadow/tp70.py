"""F1 with the owner's exits (2026-10-18): "set the real TP at 70 % of the target read from the chart (the next level
in front), the stop 10 % wider; if that TP is already narrow, keep the old TP".

Written before computing (the step-0 distribution, tp70_room.py: the nearest level in front of F1's design signals
is a median 2.6 U from the fill, 59 % give 0.7 x room < 3 U):
- every variant: F1's signals as frozen (C4, C5, 3-10 U stop, floor 0.5 M15 ATR), the stop x 1.1, break-even at
  0.6 of the variant's TP, out after 60 minutes; one position at a time, two a session-day (v1 exits);
- BASE   8 U, the stop as is (F1 v1);
- T70    0.7 x 8 U = 5.6 U (the fixed-target reading);
- L70-3  0.7 x the nearest level in front; when that is under 3 U ("narrow"), the old 8 U (owner's last message);
- L70-5  the same with 5 U as "narrow" (the owner's 5-pip minimum target);
- N70    0.7 x the nearest level in front that leaves at least 3 U (the next level further out), else 8 U;
- each level TP capped at 40 U (F1's runner cap).
Choice: the highest design USD at 0.01 lot among the variants that beat BASE in R in >= 4 of 5 half-years; only that
one runs on the window (2026-03-01 .. 10-14), once. The v2 runner phase is left as it is (its exits have no fixed
target), so the window run also shows v2 with the chosen TP on its non-runner trades.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/tp70.py [window VARIANT]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/weapon4"))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402

P = w.instr("XAUUSD")
WINDOW = len(sys.argv) > 2 and sys.argv[1] == "window"
per = w.WINDOW if WINDOW else w.DESIGN
tag = "window" if WINDOW else "design"
D = w.build(P, 1, *per, [(0, 20)], f"XAUUSD_M1_{tag}_fr")
h = pd.DatetimeIndex(D.t).hour
S0 = w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60)
e, side, u = S0.e.to_numpy(), S0.side.to_numpy(), S0.unit.to_numpy()
fill = P.o[e] + np.where(side > 0, P.sp[e] + P.slip, -P.slip)
shift = (fill - S0.c_dec.to_numpy()) * side  # the fill's distance past the decision close
fronts = np.vstack([S0[f"fr{k}"].to_numpy() for k in range(6)]).T - shift[:, None]  # from the fill
fronts[~np.isfinite(fronts) | (fronts <= 0)] = np.inf
near = fronts.min(1)
nxt = np.where(fronts >= 3 / 0.7 * u[:, None], fronts, np.inf).min(1)


def level_tp(dist: np.ndarray, narrow_u: float) -> np.ndarray:
    tp = np.minimum(0.7 * dist, 40 * u)
    return np.where(np.isfinite(dist) & (tp >= narrow_u * u), tp, 8 * u)


VARIANTS = {
    "BASE": (8 * u, 1.0),
    "T70": (5.6 * u, 1.1),
    "L70-3": (level_tp(near, 3), 1.1),
    "L70-5": (level_tp(near, 5), 1.1),
    "N70": (level_tp(nxt, 3), 1.1),
}


def dd(x):
    eq = np.r_[0, np.cumsum(x)]
    return float((np.maximum.accumulate(eq) - eq).max())


def make(name: str) -> pd.DataFrame:
    tp, k = VARIANTS[name]
    S = S0.copy()
    S["tp"], S["sl"] = tp, S0.sl.to_numpy() * k
    return S


def line(name: str, z: pd.DataFrame, days: int) -> str:
    wins = (z.exit == "win").mean()
    s = (f"  {name:6} {len(z):4} ({len(z) / days:.2f}/d) win {wins:4.0%} R {z.R.mean():+.3f} USD {z.usd.sum():+7.1f}"
         f" DD {dd(z.usd):5.1f} TP med {np.median(z.tp / z.u):4.1f} U")
    if not WINDOW:
        rn, n = ev.halves(z)
        s += " | " + " ".join(f"{x:+.2f}({c})" for x, c in zip(rn, n))
    else:
        s += " | " + " ".join(f"{m[5:]} {g.usd.sum():+.0f}" for m, g in z.groupby(z.t.dt.strftime("%Y-%m")))
    return s


days = w.days_in(*per)
print(f"== F1 TP70 {tag.upper()}: {len(S0)} signals; the nearest level in front from the fill, median "
      f"{np.median(near[np.isfinite(near)] / u[np.isfinite(near)]):.1f} U; the next leaving 3 U, median "
      f"{np.median(nxt[np.isfinite(nxt)] / u[np.isfinite(nxt)]):.1f} U ({np.isfinite(nxt).mean():.0%} have one)")
names = list(VARIANTS) if not WINDOW else ["BASE", sys.argv[2]]
out = {}
for name in names:
    z = w.run(make(name), P)
    out[name] = z
    print(line(name, z, days))
if not WINDOW:
    base = ev.halves(out["BASE"])[0]
    for name in names[1:]:
        better = sum(a > b for a, b in zip(ev.halves(out[name])[0], base))
        print(f"  {name}: beats BASE in {better} of 5 half-years")
else:
    for name in names:
        print(f"  {name} account: {w.account(out[name])}")
        print(f"  {name} v2 (runner phase as is):", end=" ")
        z2 = w.run_v2(make(name), P)
        print(f"{len(z2)} R {z2.R.mean():+.3f} USD {z2.usd.sum():+.1f} DD {dd(z2.usd):.1f}")
