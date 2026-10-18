"""F1 CONF-72 (+ 0.5 M15-ATR floor) exits after the turn-zone study (shadow/turn_zone.py: 81-86 % of the entries that
come near the level in front go through it; turns at the level are 6-9 %). Written before it is computed:

- E0 as frozen: target 8 U, break-even at 0.6, 60 min.
- E1 runner over the level: no fixed target; break-even at 0.6 x 8 U; once an M1 bar CLOSES beyond the level in front
  (``room`` from the fill), the stop moves to the level - 0.5 M1 ATR (the broken level as support), and from then on
  it trails 1 M15 ATR behind the best close; 180 min.
- E2 half at 8 U (as E0), the other half as E1 (reported as one trade at 0.01 lot: the average of the halves).
- E3 E1 but only when the room is >= 5 USD (else E0).
Real costs, one position at a time; design then the window once.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/level_runner.py
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


def runner(e, s, sl, room, atr1, a15v, be_at, hz, ss):
    entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
    stop, armed, broke, best = entry - s * sl, False, False, -np.inf
    lvl = entry + s * room if np.isfinite(room) else np.nan
    end = min(e + hz, len(P.o) - 1)
    for j in range(e, end):
        adv = P.lo[j] if s > 0 else P.h[j] + P.sp[j]
        if (adv - stop) * s <= 0:
            return (stop - s * ss - entry) * s, j - e + 1, "stop" if not (armed or broke) else "trail"
        fav = (P.h[j] - entry) if s > 0 else (entry - P.lo[j] - P.sp[j])
        if not armed and fav >= be_at:
            armed, stop = True, entry if (entry - stop) * s > 0 else stop
        cl = P.c[j] if s > 0 else P.c[j] + P.sp[j]
        if np.isfinite(lvl) and not broke and (cl - lvl) * s > 0:
            broke = True
            ns = lvl - s * 0.5 * atr1
            if (ns - stop) * s > 0:
                stop = ns
        if broke:
            best = max(best, (cl - entry) * s)
            ns = entry + s * (best - a15v)
            if (ns - stop) * s > 0:
                stop = ns
    x = end - 1
    px = P.c[x] - (P.slip if s > 0 else -(P.sp[x] + P.slip))
    return (px - entry) * s, end - e, "time"


def run(S, mode):
    rows, free = [], pd.Timestamp(0, tz="UTC")
    for r in S.sort_values("t").itertuples():
        if r.t < free:
            continue
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        base = P.trade(int(r.e), int(r.side), float(r.tp), float(r.sl), 0.6, 60, ss)
        use_runner = mode in ("E1", "E2") or (mode == "E3" and r.room_f >= 5)
        if mode == "E0" or not use_runner:
            pnl, mins, ex = base["pnl"], base["mins"], base["exit"]
        else:
            rp, rm, rx = runner(int(r.e), int(r.side), float(r.sl), float(r.room_f), float(r.atr1), float(r.a15),
                                0.6 * float(r.tp), 180, ss)
            if mode == "E2":
                pnl, mins, ex = 0.5 * (base["pnl"] + rp), max(base["mins"], rm), rx
            else:
                pnl, mins, ex = rp, rm, rx
        rows.append(dict(t=r.t, pnl=pnl, R=pnl / (r.sl + ss), exit=ex))
        free = r.t + pd.Timedelta(minutes=int(mins))
    return pd.DataFrame(rows)


for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
    S["t"] = pd.to_datetime(S.t, utc=True)
    S["a15"] = a15.reindex(S.t, method="ffill").to_numpy()
    S["sl"] = np.maximum(S.sl, 0.5 * S.a15)
    fill = P.fill(S.e.to_numpy(), S.side.to_numpy())
    S["room_f"] = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * S.side.to_numpy()
    print(f"\n== {'DESIGN 2023-11 .. 2026-02' if part == 'wdesign' else 'WINDOW 2026-03 .. 10-14'}")
    for mode in ("E0", "E1", "E2", "E3"):
        z = run(S, mode)
        eq = z.pnl.cumsum()
        g = z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(f"{k[5:]} {v:+.1f}" for k, v in g.items())
        print(f"  {mode} {len(z):4} trades R {z.R.mean():+.3f} USD {z.pnl.sum():+7.1f} best {z.pnl.max():6.1f} DD {(eq.cummax() - eq).max():5.1f}"
              f" exits {z.exit.value_counts().to_dict()} | {per}")
