"""F1 CONF-72 (+ 0.5 M15-ATR floor) improvements from dead_vs_runner.py (owner, 2026-10-18). Written before computing;
thresholds near the design medians of the runners / the dead (not tuned on the window):

- G1 already moving: ret15 >= 1.0 (the last 15 minutes >= 1 M1 ATR the trade's way)
- G2 no knife: ret60 >= -2.0
- G3 cheap: spread / M1 ATR <= 0.20
- G4 G1 + G2
- X1 early scratch: after 5 bars, if the best price so far < 1 U the trade's way and the close is against the
  entry, out at that close.
- X2 early scratch after 10 bars, best < 2 U.
- X3 regime exit: when the M15 ATR is >= 1.3 x its 20-day median at the entry (a strong-volatility phase), the
  level runner (level_runner.py E1), else the fixed 8 U.
Real costs, one position at a time; design by half-year, then the window once.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_improve.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
sys.path.insert(0, "research/2026-10-18-moments/shadow")
import plib  # noqa: E402
from level_runner import runner  # noqa: E402
from portfolio import family_signals  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15_med = a15.rolling(20 * 92, min_periods=200).median()
a15.index = a15.index + pd.Timedelta(minutes=15)
a15_med.index = a15.index


def scratch(e, s, tp, sl, ss, after, need_u, u):
    """jlib's trade (BE 0.6, 60 min) with an early exit at the close of bar e+after-1 when the best so far is under
    need_u U and the close is against the entry."""
    entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
    stop, armed, mfe = entry - s * sl, False, 0.0
    end = min(e + 60, len(P.o) - 1)
    for j in range(e, end):
        adv = P.lo[j] if s > 0 else P.h[j] + P.sp[j]
        fav = P.h[j] if s > 0 else P.lo[j] + P.sp[j]
        if (adv - stop) * s <= 0:
            return (stop - s * ss - entry) * s, j - e + 1, "be" if armed else "stop"
        if (fav - entry) * s >= tp:
            return tp, j - e + 1, "win"
        mfe = max(mfe, (fav - entry) * s)
        if not armed and mfe >= 0.6 * tp:
            armed, stop = True, entry
        if j == e + after - 1 and mfe < need_u * u:
            px = P.c[j] - (P.slip if s > 0 else -(P.sp[j] + P.slip))
            if (px - entry) * s < 0:
                return (px - entry) * s, j - e + 1, "scratch"
    x = end - 1
    px = P.c[x] - (P.slip if s > 0 else -(P.sp[x] + P.slip))
    return (px - entry) * s, end - e, "time"


def run(S, exit_):
    rows, free = [], pd.Timestamp(0, tz="UTC")
    for r in S.sort_values("t").itertuples():
        if r.t < free:
            continue
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        e, s = int(r.e), int(r.side)
        if exit_ == "X1":
            pnl, mins, ex = scratch(e, s, r.tp, r.sl, ss, 5, 1.0, r.unit)
        elif exit_ == "X2":
            pnl, mins, ex = scratch(e, s, r.tp, r.sl, ss, 10, 2.0, r.unit)
        elif exit_ == "X3" and r.a15 >= 1.3 * r.a15m:
            pnl, mins, ex = runner(e, s, r.sl, r.room_f, r.atr1, r.a15, 0.6 * r.tp, 180, ss)
        else:
            o = P.trade(e, s, r.tp, r.sl, 0.6, 60, ss)
            pnl, mins, ex = o["pnl"], o["mins"], o["exit"]
        rows.append(dict(t=r.t, pnl=pnl, R=pnl / (r.sl + ss), exit=ex))
        free = r.t + pd.Timedelta(minutes=int(mins))
    return pd.DataFrame(rows)


for part in (() if "--x4" in sys.argv else ("wdesign", "wtest")):
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
    S["t"] = pd.to_datetime(S.t, utc=True)
    S["a15"] = a15.reindex(S.t, method="ffill").to_numpy()
    S["a15m"] = a15_med.reindex(S.t, method="ffill").to_numpy()
    S["sl"] = np.maximum(S.sl, 0.5 * S.a15)
    fill = P.fill(S.e.to_numpy(), S.side.to_numpy())
    S["room_f"] = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * S.side.to_numpy()
    filters = {
        "base": np.ones(len(S), bool),
        "G1 ret15 >= 1": (S.ret15 >= 1.0).to_numpy(),
        "G2 ret60 >= -2": (S.ret60 >= -2.0).to_numpy(),
        "G3 spread/ATR <= .2": (S.spread / S.atr1 <= 0.2).to_numpy(),
        "G4 G1 + G2": ((S.ret15 >= 1.0) & (S.ret60 >= -2.0)).to_numpy(),
    }
    print(f"\n== {'DESIGN 2023-11 .. 2026-02' if part == 'wdesign' else 'WINDOW 2026-03 .. 10-14'}; strong-phase share"
          f" {np.mean(S.a15 >= 1.3 * S.a15m):.0%}")
    jobs = [(k, m, "E0") for k, m in filters.items()] + [("X1 scratch 5 bars", filters["base"], "X1"),
                                                         ("X2 scratch 10 bars", filters["base"], "X2"),
                                                         ("X3 regime exit", filters["base"], "X3")]
    for name, m, ex in jobs:
        z = run(S[m], ex)
        eq = z.pnl.cumsum()
        g = z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(f"{k[5:]} {v:+.1f}" for k, v in g.items())
        print(f"  {name:22} {len(z):4} R {z.R.mean():+.3f} USD {z.pnl.sum():+7.1f} win {100 * (z.exit == 'win').mean():3.0f}%"
              f" DD {(eq.cummax() - eq).max():5.1f} | {per}")


# X4 (written after the window results above, so its window run is NOT clean): X3's regime exit + X2's scratch on the
# fixed-target trades.
def run_x4(S):
    rows, free = [], pd.Timestamp(0, tz="UTC")
    for r in S.sort_values("t").itertuples():
        if r.t < free:
            continue
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        e, s = int(r.e), int(r.side)
        if r.a15 >= 1.3 * r.a15m:
            pnl, mins, ex = runner(e, s, r.sl, r.room_f, r.atr1, r.a15, 0.6 * r.tp, 180, ss)
        else:
            pnl, mins, ex = scratch(e, s, r.tp, r.sl, ss, 10, 2.0, r.unit)
        rows.append(dict(t=r.t, pnl=pnl, R=pnl / (r.sl + ss), exit=ex))
        free = r.t + pd.Timedelta(minutes=int(mins))
    return pd.DataFrame(rows)


if "--x4" in sys.argv:
    for part in ("wdesign", "wtest"):
        S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
        S["t"] = pd.to_datetime(S.t, utc=True)
        S["a15"] = a15.reindex(S.t, method="ffill").to_numpy()
        S["a15m"] = a15_med.reindex(S.t, method="ffill").to_numpy()
        S["sl"] = np.maximum(S.sl, 0.5 * S.a15)
        fill = P.fill(S.e.to_numpy(), S.side.to_numpy())
        S["room_f"] = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * S.side.to_numpy()
        z = run_x4(S)
        eq = z.pnl.cumsum()
        g = z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(f"{k[5:]} {v:+.1f}" for k, v in g.items())
        st = 0
        mx = 0
        for v in z.pnl:
            st = st + 1 if v < 0 else 0
            mx = max(mx, st)
        print(f"X4 {part}: {len(z)} R {z.R.mean():+.3f} USD {z.pnl.sum():+7.1f} worst {z.pnl.min():.1f} streak {mx}"
              f" DD {(eq.cummax() - eq).max():5.1f} exits {z.exit.value_counts().to_dict()} | {per}")
