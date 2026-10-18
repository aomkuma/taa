"""Every F1 CONF-72 loser on 2026-03 .. 10-14 with its situation at the entry, and the owner's question: would the
other side, as a scalp, have paid? The other side is tested on *all* signals (a losing side is not known in advance),
design and window. Gold, real costs.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_losers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
from portfolio import family_signals  # noqa: E402

F1 = (["C4 72-h extreme near/behind", "C5 not a fast tape"], 2)
TH = "Asia/Bangkok"


def main() -> None:
    P = plib.jlib.Instr("XAUUSD")
    out = []
    for part in ("wdesign", "wtest"):
        S = family_signals("F1", F1[0], F1[1], part).reset_index(drop=True)
        z = plib.run(S, P)
        z["t"] = pd.to_datetime(z.t, utc=True)
        rev = S.assign(side=-S.side)
        res = {}
        for name, tp, sl_mode, hz in (("other side, same exits", None, "same", None),
                                      ("other side, scalp 5 USD / same stop, 30 min", 5.0, "same", 30),
                                      ("other side, scalp 5 USD / 5 USD stop, 30 min", 5.0, "5", 30),
                                      ("other side, scalp 3 USD / 3 USD stop, 15 min", 3.0, "3", 15)):
            r2 = rev.copy()
            if tp is not None:
                r2["tp"] = tp * r2.unit
                r2["hz"] = hz
                r2["be"] = 99.0
                if sl_mode != "same":
                    r2["sl"] = float(sl_mode) * r2.unit
            zz = plib.run(r2, P)
            res[name] = zz
        print(f"\n== {part}: F1 {len(z)} trades R {z.R.mean():+.3f} {z.pnl.sum():+.1f} USD")
        for name, zz in res.items():
            print(f"   {name:46} {len(zz):4} trades win {100 * (zz.pnl > 0).mean():3.0f}% R {zz.R.mean():+.3f} {zz.pnl.sum():+7.1f} USD")
        if part == "wtest":
            j = S.set_index("t")
            for r in z.itertuples():
                f = j.loc[r.t] if r.t in j.index else None
                if isinstance(f, pd.DataFrame):
                    f = f[f.side == r.side].iloc[0]
                e = int(r.e)
                s = int(r.side)
                # how far price went the other way within 30 minutes after the entry (the other side's room)
                seg = slice(e, min(e + 30, len(P.o)))
                other = (P.o[e] - P.lo[seg].min()) if s > 0 else (P.h[seg].max() - P.o[e])
                run60_h1 = f.ret60 * f.atr1 / f.h1_atr
                mirror = P.trade(e, -s, float(r.tp), float(r.sl), None, 60, P.stop_slip)
                chase = run60_h1 >= 1.0 or f.m15_c_e20 >= 3
                logic = "ok" if (not chase and f.sl >= 1.5 * f.atr1 and f.cr_H1_leg_dir >= 0) else (
                    "chase" if chase else ("stop in noise" if f.sl < 1.5 * f.atr1 else "H1 leg against"))
                out.append(dict(
                    result="win" if r.pnl > 0.5 else ("loss" if r.pnl < -0.5 else "flat"),
                    other_side=mirror["exit"], logic=logic,
                    time=r.t.tz_convert(TH).strftime("%d/%m %H:%M"), side="BUY" if s > 0 else "SELL",
                    usd=round(r.pnl, 2), kind={"1": "wrong way", "2": "fell short", "3": "too early"}.get(str(r.kind), ""),
                    min_to_stop=int(r.mins), level=f.level_kind, pa="reclaim" if f.reclaim else ("engulf" if f.engulf else "hammer"),
                    run60_h1=round(run60_h1, 2), m15_ext=round(f.m15_c_e20, 2), h1_leg=int(f.cr_H1_leg_dir),
                    stop_m1atr=round(f.sl / f.atr1, 2), atr_ratio=round(f.atr_ratio, 2), min_in=int(f.min_in),
                    news=int(min(f.until_rel, f.since_rel)), other_way_30m=round(other, 1)))
    d = pd.DataFrame(out)
    d.to_csv("research/2026-10-18-moments/shadow/f1_test_losers.csv", index=False)
    print("\nlosers", len(d))
    print(d.to_string(index=False))


if __name__ == "__main__":
    main()
