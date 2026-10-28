"""Would an earlier signal leave room to run? (owner, 2026-10-18). Written before computing.

A. Hindsight room (an upper bound, NOT tradable: the moments are picked because F1 fired later): for every F1 trade
   (CONF-72 + the 0.5 M15-ATR floor), the run into it = the lowest low (BUY; highest high SELL) of the 60 M1 bars
   before the entry bar. Room = the F1 fill - that low. Also: entered at the run low's bar + 3 (a count-three
   confirmation), stop 0.5 M1 ATR beyond the run low (at least 3 U), F1's exits (8 U, BE 0.6, 60 min) - the result.

B. EARLY, tradable (no look-ahead), decided at an M1 close inside the wide windows:
   - H1 tide with the side, C5 (not a fast tape);
   - the 72-hour extreme in front 4 .. 20 U away (not near yet: C4 would still say no);
   - a count-three turn on M1: the lowest low of the last 15 bars (BUY; mirrored) was made 3 or more bars ago, no
     lower low since, and this close is the first above that low bar's high;
   - stop 0.5 M1 ATR beyond the 15-bar low, at least 0.5 M15 ATR, 3-12 U else no trade;
   - EARLY-a: F1's exits (8 U target, BE 0.6, 60 min); EARLY-b: target the 72-h extreme (at least 5 USD), BE at
     0.6 of it, 120 min.
   One position at a time, real costs; design by half-year, then the window once. Coverage: the share of F1's
   window trades whose 60-minute run had an EARLY signal before the F1 entry.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/earlier.py
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
h, lo, c = P.h, P.lo, P.c


def label(part):
    return "DESIGN 2023-11 .. 2026-02" if part == "wdesign" else "WINDOW 2026-03-01 .. 10-14"


# ---------------------------------------------------------------- A. hindsight room before F1's trades
print("A. HINDSIGHT (upper bound, not tradable)")
for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
    S["t"] = pd.to_datetime(S.t, utc=True)
    S["sl"] = np.maximum(S.sl, 0.5 * a15.reindex(S.t, method="ffill").to_numpy())
    z = plib.run(S, P)
    rows = []
    for r in z.itertuples():
        e, s = int(r.e), int(r.side)
        seg = np.arange(e - 60, e)
        j = seg[np.argmin(lo[seg])] if s > 0 else seg[np.argmax(h[seg])]
        fill = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
        room = (fill - (lo[j] if s > 0 else h[j])) * s
        k = j + 4  # entered after three bars confirmed the low
        res = None
        if k < e:
            atr1 = float(pd.Series(np.maximum(h - lo, np.abs(np.r_[np.nan, c[:-1]] - h))[k - 15 : k]).mean())
            u = c[k - 1] / plib.jlib.REF
            entry_k = P.o[k] + (P.sp[k] + P.slip if s > 0 else -P.slip)
            sl = max(((entry_k - (lo[j] if s > 0 else h[j])) * s) + 0.5 * atr1, 3 * u)
            ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
            o = P.trade(k, s, 8 * u, sl, 0.6, 60, ss)
            res = (o["pnl"], o["exit"], (entry_k - fill) * -s)
        rows.append(dict(room=room, room_u=room / (c[e - 1] / plib.jlib.REF), f1=r.pnl, mins=e - j,
                         early_usd=res[0] if res else np.nan, early_exit=res[1] if res else "", gain=res[2] if res else np.nan))
    X = pd.DataFrame(rows)
    print(f"  {label(part)}: {len(X)} F1 trades; run into the entry: median {X.room.median():.1f} USD ({X.room_u.median():.1f} U),"
          f" {X.mins.median():.0f} min long; room >= 8 U in {np.mean(X.room_u >= 8):.0%}")
    ok = X.early_exit != ""
    print(f"    entered 3 bars after the run low: {ok.sum()} trades, win {np.mean(X.early_exit[ok] == 'win'):.0%},"
          f" {X.early_usd[ok].sum():+.1f} USD vs F1 itself {X.f1.sum():+.1f} USD; the earlier entry was {X.gain[ok].median():.1f} USD better priced")

# ---------------------------------------------------------------- B. a tradable early signal
print("\nB. EARLY (tradable)")
win = np.lib.stride_tricks.sliding_window_view
lo_w, hi_w = win(lo, 15), win(h, 15)
argmin15 = np.full(len(lo), -1)
argmax15 = np.full(len(lo), -1)
argmin15[14:] = np.arange(len(lo_w)) + lo_w.argmin(1)
argmax15[14:] = np.arange(len(hi_w)) + hi_w.argmax(1)
f1_window = None
for part in ("wdesign", "wtest"):
    _, D = plib.load(part)
    D = D.reset_index(drop=True)
    p = D.e.to_numpy() - 1
    s = D.side.to_numpy()
    room72 = ((D.front72 - D.c_dec) * D.side / D.unit).to_numpy()
    j = np.where(s > 0, argmin15[p], argmax15[p])
    ext = np.where(s > 0, lo[j], h[j])
    turn_px = np.where(s > 0, h[j], lo[j])
    age = p - j
    first = ((c[p] - turn_px) * s > 0) & ((c[p - 1] - turn_px) * s <= 0)
    trig = (age >= 3) & first
    base = D.tide.to_numpy(bool) & plib.MENU["C5 not a fast tape"](D).to_numpy(bool) & (room72 >= 4) & (room72 <= 20) & trig
    stop_px = ext - s * 0.5 * D.atr1.to_numpy()
    sl = (P.fill(D.e.to_numpy(), s) - stop_px) * s
    sl = np.maximum(sl, 0.5 * a15.reindex(pd.to_datetime(D.t, utc=True), method="ffill").to_numpy())
    u = D.unit.to_numpy()
    ok = base & (sl >= 3 * u) & (sl <= 12 * u)
    E = D[ok].assign(sl=sl[ok], room72_u=room72[ok])
    days = pd.bdate_range(*(("2023-11-01", "2026-02-28") if part == "wdesign" else ("2026-03-01", "2026-10-13"))).size
    print(f"  {label(part)}: {ok.sum()} signal minutes")
    for name, tp_u, be, hz in (("EARLY-a 8 U", None, 0.6, 60), ("EARLY-b to the 72-h extreme", "x72", 0.6, 120)):
        tp = 8 * E.unit if tp_u is None else np.maximum(E.room72_u * E.unit, 5.0)
        Z = E.assign(tp=tp, be=be, hz=hz, trail=False)
        z = plib.run(Z, P, per_sess=99)
        z["t"] = pd.to_datetime(z.t, utc=True)
        eq = z.pnl.cumsum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(
            f"{k[5:]} {v:+.0f}" for k, v in z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum().items())
        kinds = plib.kinds(z) if "kind" in z else ""
        print(f"    {name:28} {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}% R {z.R.mean():+.3f}"
              f" USD {z.pnl.sum():+7.1f} DD {(eq.cummax() - eq).max():5.1f} losers 1/2/3 {kinds} | {per}")
    if part == "wtest":
        S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, "wtest").reset_index(drop=True)
        S["t"] = pd.to_datetime(S.t, utc=True)
        et = pd.to_datetime(E.t, utc=True)
        cov = [((et < t) & (et >= t - pd.Timedelta(minutes=60)) & (E.side == sd)).any() for t, sd in zip(S.t, S.side)]
        print(f"  coverage: {np.mean(cov):.0%} of F1's window signals had an EARLY signal in the 60 minutes before")
