"""Where does price turn when it runs toward the level in front? (owner, 2026-10-18: "real life is not that perfect -
research what the price does where it turns"). For every entry of the confluence family (B0 rows: H1 tide + at a
level + price action + 2 of 3 M5; one per minute, wide windows) with an opposing level in front (``room``, the same
six kinds), follow price for 120 M1 bars from the fill and measure:

- reach = the best price before the stop (the entry's own stop, floored at 0.5 M15 ATR), as a share of the room;
- for those that came within 0.3 room of the level: did the turn come before it (short), around it (within +-0.1
  room), or after a break beyond it (> +0.1, and how far: wick vs a real break that held 15 bars)?
- then targets at k x room (k 0.5 .. 1.3) and at room - x M1 ATR, design first, the window once.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/turn_zone.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
import rules  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)
H = 120


def paths(S: pd.DataFrame) -> pd.DataFrame:
    out = []
    for r in S.itertuples():
        e, s = int(r.e), int(r.side)
        entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
        j = np.arange(e, min(e + H, len(P.o)))
        fav = (P.h[j] - entry) if s > 0 else (entry - (P.lo[j] + P.sp[j]))
        adv = (entry - P.lo[j]) if s > 0 else (P.h[j] + P.sp[j] - entry)
        hit = np.flatnonzero(adv >= r.sl)
        k = hit[0] if len(hit) else len(j)
        reach = fav[:k].max() if k > 0 else 0.0  # the stop bar counts as stop first
        lvl = entry + s * r.room_f
        # after the best point: did price close beyond the level and stay 15 bars?
        held = False
        if k > 0:
            b = int(np.argmax(fav[:k]))
            cl = (P.c[j[b:k]] - lvl) * s
            held = bool(len(cl) >= 15 and (cl[:15] > 0).all())
        out.append(dict(t=r.t, side=s, room=r.room_f, sl=r.sl, atr1=r.atr1, reach=reach, stopped=len(hit) > 0, held=held))
    return pd.DataFrame(out)


for part in ("wdesign", "wtest"):
    P0, D = plib.load(part)
    D = D.reset_index(drop=True)
    S = rules.signals(D, rules.RULES["B0"], P)
    S = S.drop_duplicates("t")
    t = pd.to_datetime(S.t, utc=True)
    S["sl"] = np.maximum(S.sl, 0.5 * a15.reindex(t, method="ffill").to_numpy())
    fill = P.fill(S.e.to_numpy(), S.side.to_numpy())
    S["room_f"] = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * S.side.to_numpy()
    S = S[np.isfinite(S.room_f) & (S.room_f > 0)]
    X = paths(S)
    X["ratio"] = X.reach / X.room
    name = "DESIGN 2023-11 .. 2026-02" if part == "wdesign" else "WINDOW 2026-03 .. 10-14"
    print(f"\n== {name}: {len(X)} entries with a level in front; median room {X.room.median():.2f} USD"
          f" ({(X.room / X.atr1).median():.1f} M1 ATR), median stop {X.sl.median():.2f}")
    bins = [0, 0.25, 0.5, 0.7, 0.8, 0.9, 1.0, 1.1, 1.3, 2, np.inf]
    c = pd.cut(X.ratio, bins, right=False).value_counts(normalize=True).sort_index()
    print("  best price before the stop / room: " + "  ".join(f"{str(k)} {v:.0%}" for k, v in c.items()))
    near = X[X.ratio >= 0.7]
    print(f"  came within 30 % of the level: {len(near) / len(X):.0%}; of those: turned short (0.7-0.9) {((near.ratio < 0.9)).mean():.0%},"
          f" around it (0.9-1.1) {((near.ratio >= 0.9) & (near.ratio < 1.1)).mean():.0%}, beyond (>=1.1) {(near.ratio >= 1.1).mean():.0%};"
          f" closed beyond and held 15 bars {near.held.mean():.0%}")
    sh = X[(X.ratio >= 0.5) & (X.ratio < 1.0)]
    print(f"  turned before the level: median shortfall {(sh.room - sh.reach).median():.2f} USD = {((sh.room - sh.reach) / sh.atr1).median():.2f} M1 ATR"
          f" = {(1 - sh.ratio).median():.0%} of the room")
    ov = X[(X.ratio >= 1.0) & ~X.held]
    print(f"  went through and came back (wick): median overshoot {(ov.reach - ov.room).median():.2f} USD = {((ov.reach - ov.room) / ov.atr1).median():.2f} M1 ATR")
    # targets as a share of the room
    for k in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.3):
        tp = k * X.room
        win = X.reach >= tp
        # R: a win pays tp, a stop pays -sl, else (time) ~0: rough, before costs
        r = np.where(win, tp, np.where(X.stopped, -X.sl, 0.0)) / X.sl
        print(f"   target {k:.1f} x room: hit {win.mean():.0%}, avg target {tp.median():.2f} USD, rough R {r.mean():+.3f}")
