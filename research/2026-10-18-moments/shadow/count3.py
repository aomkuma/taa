"""Round 12 (docs/OWN_SETUP.md): "count three on M1, check again, then enter" on F1 CONF-72 and on the CPI / NFP
release (S2-C3). Design first, then the seen window 2026-03-01 .. 10-14, then the fresh days (2026-10-14 ..).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/count3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
import plib  # noqa: E402
from portfolio import family_signals  # noqa: E402

F1 = (["C4 72-h extreme near/behind", "C5 not a fast tape"], 2)


def count3(S: pd.DataFrame, P, hold_level: bool) -> pd.DataFrame:
    """Shift each signal three bars: enter at e+3 if the 3 bars kept the trade alive; the same stop price."""
    rows = []
    for r in S.itertuples():
        e, s = int(r.e), int(r.side)
        if e + 4 >= len(P.o):
            continue
        fill0 = float(P.fill(np.array([e]), np.array([s]))[0])
        stop_px = fill0 - s * float(r.sl)
        lows, highs = P.lo[e : e + 3], P.h[e : e + 3] + P.sp[e : e + 3]
        adverse = lows.min() if s > 0 else highs.max()
        if (adverse - stop_px) * s <= 0:  # touched the stop
            continue
        if (P.c[e + 2] - P.c[e - 1]) * s < 0:  # not at / beyond the signal close
            continue
        if hold_level and (adverse - float(r.level)) * s < 0:
            continue
        fill3 = float(P.fill(np.array([e + 3]), np.array([s]))[0])
        sl = (fill3 - stop_px) * s
        if not (3 * r.unit <= sl <= 10 * r.unit):
            continue
        rows.append(r._asdict() | {"e": e + 3, "sl": sl, "t": r.t + pd.Timedelta(minutes=3)})
    return pd.DataFrame(rows).drop(columns="Index") if rows else S.iloc[0:0]


def report(name: str, z: pd.DataFrame, part: str) -> None:
    if not len(z):
        print(f"  {name}: 0 trades")
        return
    z = z.copy()
    z["t"] = pd.to_datetime(z.t, utc=True)
    eq = z.pnl.cumsum()
    streak = mx = 0
    for v in z.pnl:
        streak = streak + 1 if v < 0 else 0
        mx = max(mx, streak)
    per = plib.by_half(z) if part == "wdesign" else " ".join(
        f"{k[5:]} {v.pnl.sum():+.1f}({len(v)})" for k, v in z.groupby(z.t.dt.strftime("%Y-%m")))
    print(f"  {name}: {len(z)} trades, win {100 * (z.exit == 'win').mean():.0f}%, R {z.R.mean():+.3f}, {z.pnl.sum():+.1f} USD,"
          f" worst {z.pnl.min():.2f}, streak {mx}, max DD {(eq.cummax() - eq).max():.1f} | {per}")


def f1_part(part: str) -> None:
    P = plib.jlib.Instr("XAUUSD")
    S = family_signals("F1", F1[0], F1[1], part)
    print(f"\n== F1 CONF-72 ({part}), signals {len(S)}")
    report("F1 as frozen", plib.run(S, P), part)
    for name, hl in (("F1-C3a", False), ("F1-C3b", True)):
        report(name, plib.run(count3(S, P, hl), P), part)


def s2c3() -> None:
    m1 = gold.bars("M1")
    m1 = m1[m1.index >= pd.Timestamp("2021-08-01", tz="UTC")]
    ot = m1.index
    o, h, lo, c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m1["spread"].to_numpy(float) * 0.01 + 0.08
    cal = gold.releases()
    cal = cal[cal.event.isin(["CPI", "NFP"])]
    rows = []
    for t0, ev in zip(cal.t, cal.event, strict=True):
        i = int(ot.searchsorted(t0))
        if i + 40 >= len(o) or ot[i] != t0 or ot[i + 3] != t0 + pd.Timedelta(minutes=3):
            continue
        k = c[i - 1] / 4000
        move = c[i + 2] - o[i]
        s = int(np.sign(move))
        if abs(move) < 3 * k or (c[i + 2] - o[i + 2]) * s <= 0:
            continue
        e = i + 3
        entry = o[e] + (sp[e] + 0.07 if s > 0 else -0.07)
        ext = lo[i : i + 3].min() if s > 0 else h[i : i + 3].max() + sp[i]
        sl = max((entry - ext) * s, 4 * k)
        if sl > 12 * k:
            continue
        stop = entry - s * sl
        for name, tp, hz in (("S2-C3", 8 * k, 15), ("S2-C3x", None, 30)):
            res = None
            for j in range(e, e + hz):
                adv = lo[j] if s > 0 else h[j] + sp[j]
                fav = h[j] if s > 0 else lo[j] + sp[j]
                if (adv - stop) * s <= 0:
                    res = ("stop", (stop - s * 0.20 - entry) * s)
                    break
                if tp is not None and (fav - (entry + s * tp)) * s >= 0:
                    res = ("win", tp)
                    break
            if res is None:
                x = e + hz - 1
                res = ("time", (c[x] - (0.07 if s > 0 else -(sp[x] + 0.07)) - entry) * s)
            rows.append(dict(rule=name, t=t0, ev=ev, side=s, sl=sl, exit=res[0], pnl=res[1], R=res[1] / (sl + 0.20)))
    d = pd.DataFrame(rows)
    d["per"] = np.select([d.t < pd.Timestamp("2023-09-01", tz="UTC"), d.t < pd.Timestamp("2026-03-01", tz="UTC"),
                          d.t < pd.Timestamp("2026-10-14", tz="UTC")], ["2021-23", "2023-26", "seen 2026-03..10"], "FRESH")
    print("\n== S2-C3 (gold M1, CPI + NFP): R and USD at 0.01 lot")
    for (rule, per), g in d.groupby(["rule", "per"]):
        eq = g.pnl.cumsum()
        print(f"  {rule:7} {per:17} {len(g):3} trades, win {100 * (g.pnl > 0).mean():3.0f}%, R {g.R.mean():+.3f}, {g.pnl.sum():+7.1f} USD,"
              f" worst {g.pnl.min():6.2f}, max DD {(eq.cummax() - eq).max():5.1f}")
    print(d[d.per != "2021-23"][d.rule == "S2-C3"].tail(16)[["t", "ev", "side", "sl", "exit", "pnl", "R"]].round(2).to_string(index=False))


def main() -> None:
    gold.below_normal_priority()
    f1_part("wdesign")
    f1_part("wtest")
    s2c3()


if __name__ == "__main__":
    main()
