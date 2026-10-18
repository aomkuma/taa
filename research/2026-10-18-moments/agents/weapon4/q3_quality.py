"""Q3: F1 restricted to the round 50 (forms a / b / c) and the size tilt (full at the round, half elsewhere), design;
`window` repeats on the window (SEEN by window_diag.py - not a clean test).

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/q3_quality.py [window]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402


def dd(x):
    eq = np.r_[0, np.cumsum(x)]
    return float((np.maximum.accumulate(eq) - eq).max())


def main():
    w.jlib.gold.below_normal_priority()
    P = w.instr("XAUUSD")
    window = len(sys.argv) > 1 and sys.argv[1] == "window"
    per = w.WINDOW if window else w.DESIGN
    tag = "window" if window else "design"
    D = w.build(P, 1, *per, [(0, 20)], f"XAUUSD_M1_{tag}")
    R = w.build_round_multi(P, *per, [(0, 20)], f"XAUUSD_M1_{tag}_rgrid", 50.0, [0.0])[0.0]
    h = pd.DatetimeIndex(D.t).hour
    S = w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60)
    rk = set(zip(R[R.pa].t, R[R.pa].side))
    fa = np.array([(t, s) in rk for t, s in zip(S.t, S.side)])
    fb = (S.level_kind == 3).to_numpy()
    fill = P.fill(S.e.to_numpy(), S.side.to_numpy())
    stop = fill - S.side.to_numpy() * S.sl.to_numpy()
    rr = np.where(S.side > 0, np.floor(fill / 50) * 50, np.ceil(fill / 50) * 50)
    fc = ((rr - stop) * S.side.to_numpy() > 0)
    days = w.days_in(*per)
    print(f"== Q3 {tag.upper()}{' (SEEN - not clean)' if window else ''}")
    for v2 in (False, True):
        run = (lambda X: w.run_v2(X, P)) if v2 else (lambda X: w.run(X, P))
        base = run(S)
        print(f"\n  exits {'v2' if v2 else 'v1'}")
        for name, m in (("F1 as is", np.ones(len(S), bool)), ("F1R-a round frame fires", fa), ("F1R-b nearest level round", fb),
                        ("F1R-c a 50 between stop and entry", fc)):
            z = run(S[m])
            line = f"    {name:34} {len(z):4} ({len(z) / days:.2f}/d) R {z.R.mean():+.3f} USD {z.usd.sum():+7.1f} DD {dd(z.usd):5.1f}"
            if not window:
                rn, n = ev.halves(z)
                line += f" | [{' '.join(f'{x:+.2f}({k})' for x, k in zip(rn, n))}]"
            else:
                line += " | " + " ".join(f"{k[5:]} {g.usd.sum():+.0f}" for k, g in z.groupby(z.t.dt.strftime("%Y-%m")))
            print(line)
        # the tilt: F1's own trades, size 1 when form a holds at the entry minute, 0.5 otherwise
        key = dict(zip(zip(S.t, S.side), fa))
        wt = np.array([1.0 if key.get((t, s), False) else 0.5 for t, s in zip(base.t, base.side)])
        usd = base.usd.to_numpy() * wt
        print(f"    T1 tilt (1 at the round, 0.5 else)      {len(base):4} R per unit risk {np.sum(base.R * wt) / wt.sum():+.3f}"
              f" USD {usd.sum():+7.1f} DD {dd(usd):5.1f} (as is: USD {base.usd.sum():+.1f} DD {dd(base.usd):.1f};"
              f" USD / DD {usd.sum() / max(dd(usd), 1e-9):.2f} vs {base.usd.sum() / max(dd(base.usd), 1e-9):.2f})")


if __name__ == "__main__":
    main()
