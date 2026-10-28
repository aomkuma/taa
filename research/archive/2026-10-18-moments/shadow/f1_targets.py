"""F1 CONF-72 (+ the 0.5 M15-ATR stop floor) with targets from the chart (owner, 2026-10-18: "plot channel, fibo,
zones to measure the price target, so the bot can use them"). Written before it is computed:

- T0 the fixed 8 U target (as frozen).
- T1 skip the trade when the nearest opposing level in front (``room``: today's / yesterday's / Asian extreme, the
  round number, the M15 / H1 chart-read levels - the same six kinds as the entry's level) is under 5 USD away.
- T2 the target AT that level (just before it: -0.1 U) when it is >= 5 USD away, else skip.
- T3 min(8 U, the level - 0.1 U) when >= 5 USD, else skip.
- T4 the Fibonacci extension: 1.272 x the last M15 swing (the leg into the entry's level) from the level, at least
  5 USD, at most 20 U.
Design (2023-11 .. 2026-02) first, then the window 2026-03-01 .. 10-14 once.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_targets.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
from portfolio import family_signals  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)
# the M15 swing into the entry: the highest high (BUY) / lowest low (SELL) of the last 16 M15 bars down to the low
hh16 = m15.high.rolling(16).max()
ll16 = m15.low.rolling(16).min()
hh16.index = ll16.index = m15.index + pd.Timedelta(minutes=15)

for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
    t = pd.to_datetime(S.t, utc=True)
    S["sl"] = np.maximum(S.sl, 0.5 * a15.reindex(t, method="ffill").to_numpy())
    s, u = S.side.to_numpy(), S.unit.to_numpy()
    fill = P.fill(S.e.to_numpy(), s)
    room = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * s  # from the fill
    top = np.where(s > 0, hh16.reindex(t, method="ffill").to_numpy(), ll16.reindex(t, method="ffill").to_numpy())
    leg = np.abs(top - S.level.to_numpy())
    fib = (S.level.to_numpy() + s * 1.272 * leg - fill) * s
    variants = {
        "T0 fixed 8 U": (S.tp.to_numpy(), np.ones(len(S), bool)),
        "T1 skip room < 5": (S.tp.to_numpy(), room >= 5),
        "T2 at the level": (room - 0.1 * u, room - 0.1 * u >= 5),
        "T3 min(8 U, level)": (np.minimum(S.tp.to_numpy(), room - 0.1 * u), np.minimum(S.tp.to_numpy(), room - 0.1 * u) >= 5),
        "T4 fib 1.272": (np.clip(fib, 5, 20 * u), np.isfinite(fib)),
    }
    print(f"\n== {'DESIGN 2023-11 .. 2026-02' if part == 'wdesign' else 'WINDOW 2026-03 .. 10-14'}: {len(S)} signals,"
          f" room >= 5 USD {np.mean(room >= 5):.0%}, median room {np.nanmedian(room):.1f} USD, median fib target {np.nanmedian(fib):.1f}")
    for name, (tp, ok) in variants.items():
        x = S.assign(tp=tp)[ok & np.isfinite(tp)]
        z = plib.run(x, P)
        z["t"] = pd.to_datetime(z.t, utc=True)
        eq = z.pnl.cumsum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(f"{k[5:]} {v:+.1f}" for k, v in z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum().items())
        print(f"  {name:20} {len(z):4} trades win {100 * (z.exit == 'win').mean():3.0f}% R {z.R.mean():+.3f} USD {z.pnl.sum():+7.1f}"
              f" DD {(eq.cummax() - eq).max():5.1f} kinds {plib.kinds(z)} | {per}")
