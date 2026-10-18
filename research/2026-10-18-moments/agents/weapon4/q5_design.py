"""W11 follow-up (notes.md): skip 17-20 UTC (a), a session extreme younger than 60 min (b1 London / b2 everywhere),
the busy tape (c); design with placebo grids and the beyond-F1 part; `window VARIANT` runs one frozen variant once.

    PYTHONPATH=../../../.. PYTHONDONTWRITEBYTECODE=1 ../../../../.venv/Scripts/python q5_design.py [window VARIANT]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402

P = w.instr("XAUUSD")


def session_age(D):
    """Minutes from the bar that set the session's running extreme (as read at i-16) to the decision bar."""
    A = w.anchor_arrays(P)
    key = A["_skey"]
    if "_ages" not in A:
        out = {}
        for s, arr in ((1, P.h), (-1, -P.lo)):
            cm = pd.Series(arr).groupby(key).cummax().to_numpy()
            idx = np.where(arr >= cm, np.arange(len(arr)), -1)
            out[s] = pd.Series(idx).replace(-1, np.nan).groupby(key).ffill().to_numpy()
        A["_ages"] = out
    p = D.e.to_numpy() - 1
    q = p - 16
    s = D.side.to_numpy()
    at = np.where(s > 0, A["_ages"][1][q], A["_ages"][-1][q])
    return p - at


def variant_mask(S, v):
    h = pd.DatetimeIndex(S.t).hour.to_numpy()
    age = S.as_age.to_numpy()
    london = (h >= 7) & (h < 12)
    as_ok = (S.d_AS < 4).to_numpy().copy()
    if "b1" in v:
        as_ok &= ~(london & (age < 60))
    if "b2" in v:
        as_ok &= age >= 60
    near = as_ok.copy()
    for a in ("A72", "A24", "AW"):
        near |= (S[f"d_{a}"] < 4).to_numpy()
    m = near
    if "a" in v.split("+"):
        m &= h < 17
    if "c" in v.split("+"):
        m &= (S.atr_ratio > 1.2).to_numpy()
    return m


VARIANTS = ["W11", "a", "b1", "b2", "a+b1", "a+b2", "c", "c+a", "c+a+b2"]


def signals_for(T):
    S = w.signals(w.add_anchors(T, P), 3, 10, 8, 0.6, 60, c4=None)
    S["as_age"] = session_age(S)
    return S


def main():
    w.jlib.gold.below_normal_priority()
    if len(sys.argv) > 2 and sys.argv[1] == "window":
        import window_run as wr

        v = sys.argv[2]
        a, b = w.WINDOW
        D = w.build(P, 1, a, b, [(0, 20)], "XAUUSD_M1_window")
        f1, s1, s2 = wr.others(D)
        S = signals_for(w.build_round_multi(P, a, b, [(0, 20)], "XAUUSD_M1_window_rgrid", 50.0, [0.0])[0.0])
        S = S[variant_mask(S, v)].reset_index(drop=True)
        z = wr.report(f"W11-{v} (FROZEN; window seen once for W11)", S, f1, s1, s2)
        z.to_csv(HERE / f"window_W11-{v}_trades.csv", index=False)
        return
    T = w.build_round_multi(P, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design_rgrid", 50.0, [0.0, 10.0, 20.0, 25.0, 30.0, 40.0])
    Sg = {o: signals_for(d) for o, d in T.items()}
    Dd = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
    hd = pd.DatetimeIndex(Dd.t).hour
    f1 = w.run(w.signals(Dd[((hd >= 0) & (hd < 2)) | ((hd >= 7) & (hd < 17))], 3, 10, 8, 0.6, 60), P)
    days = w.days_in(*w.DESIGN)
    for v in VARIANTS:
        S = Sg[0.0][variant_mask(Sg[0.0], v)].reset_index(drop=True)
        print(f"\n== {v}")
        z = ev.report(v, S, P, f1=f1)
        pl = []
        for o in (10.0, 20.0, 25.0, 30.0, 40.0):
            So = Sg[o][variant_mask(Sg[o], v)]
            pl.append(w.run(So, P).R.mean())
        print(f"      placebo grids R: {' '.join(f'{x:+.2f}' for x in pl)} (mean {np.mean(pl):+.3f}); kinds {w.plib.kinds(z)}; {w.account(z)}")


if __name__ == "__main__":
    main()
