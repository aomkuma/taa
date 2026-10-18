"""Which levels hold and which break (notes.md "Which levels hold and which break", written before computing): every
LV3 signal before the exam, labelled by what came first after the entry without a stop - back to the bounce's start
(held), an entry-TF close beyond the level (broke) or neither within 12 entry-TF bars - against what the bot could
see at the signal: H-a the level's history (price had crossed it before the bounce: a broken support / resistance),
H-b the bounce's staircase on the entry TF, H-c the H1 move already made, and the window and side.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/hold_break.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402
import jlib  # noqa: E402
import plib  # noqa: E402
from lvl2 import MINS, NS_MIN, manage  # noqa: E402

RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h"}
CROSS_LOOK = 120  # M15 bars (30 hours) before the bounce's start


def main() -> None:
    plib.gold.below_normal_priority()
    m = jlib.m1_frame("XAUUSD")
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    ot_ns = m.index.tz_convert("UTC").as_unit("ns").asi8
    B = {}
    for tf, rule in RULE.items():
        b = plib.tf_bars(m, rule)
        B[tf] = dict(avail=pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, h=b.high.to_numpy(float),
                     lo=b.low.to_numpy(float), c=b.close.to_numpy(float),
                     start=pd.DatetimeIndex(b["last"]).floor(rule).as_unit("ns").asi8 if rule != "4h" else None)
    h1 = B["H1"]
    h1_atr = F.atr(h1["h"], h1["lo"], h1["c"], 14)
    win = plib.window_mask(m.index)
    wname = win.idxmax(axis=1).where(win.any(axis=1), "-").to_numpy()
    empty = (np.array([], np.int64), np.array([], float))
    out = []
    for cell in ("s1.5_n3", "s2.0_n0"):
        S = pd.read_parquet(HERE / f"lvl3_signals_3y_{cell}.parquet")
        S = S[np.asarray(m.index[S.t.to_numpy()] < plib.EXAM_START)]
        for r in S.itertuples():
            t, j0, side, etf = int(r.t), int(r.j0), int(r.side), r.etf
            E = B[etf]
            t_end = int(ot_ns[j0] + 12 * MINS[etf] * NS_MIN)
            x = manage(o, h, lo, c, sp, ot_ns, j0, side, float(r.entry), 1e6, float(r.tgt2), float(r.level), E["avail"],
                       E["c"], 99.0, t_end, 0.07, 0.15)
            label = {"win": "held", "close": "broke", "time": "neither"}[x["exit"]]
            # H-a: did price close beyond the level (on M15) in the 30 hours before the bounce began?
            m15 = B["M15"]
            k1 = int(np.searchsorted(m15["avail"], int(r.t_start), side="right"))
            k0 = max(k1 - CROSS_LOOK, 0)
            closes = m15["c"][k0:k1]
            crossed = bool(((closes - r.level) * -side > 0).any()) if len(closes) else False
            # H-b: the bounce's staircase on the entry TF - the share of its bars with a higher low (a sell's bounce
            # rises; a buy's dip: lower highs)
            kb0 = int(np.searchsorted(E["avail"], int(r.t_start), side="right"))
            kb1 = int(np.searchsorted(E["avail"], int(ot_ns[t] + NS_MIN), side="right"))
            if kb1 - kb0 >= 2:
                seq = E["lo"][kb0:kb1] if side < 0 else -E["h"][kb0:kb1]
                stair = float((np.diff(seq) > 0).mean())
            else:
                stair = np.nan
            # H-c: the H1 move already made in the trade's direction over 24 hours, in H1 ATRs
            kh = int(np.searchsorted(h1["avail"], int(ot_ns[t] + NS_MIN), side="right")) - 1
            move24 = (h1["c"][kh - 24] - h1["c"][kh]) * -side / h1_atr[kh] if kh >= 24 else np.nan
            out.append(dict(cell=cell, t=m.index[t], side=side, etf=etf, label=label, crossed=crossed,
                            stair=stair, bounce_bars=kb1 - kb0, move24=move24, window=wname[t], swings=int(r.swings),
                            has_h1=bool(r.has_h1), legs=int(r.legs)))
    D = pd.DataFrame(out)
    D["part"] = np.where(D.t < pd.Timestamp("2025-01-01", tz="UTC"), "2023-08..2024-12", "2025-01..2026-04-17")
    D.to_parquet(HERE / "hold_break.parquet")
    pd.set_option("display.width", 220)

    def tab(by):
        g = D.groupby(["cell", "part", *by], observed=True).label.agg(
            n="size", held=lambda s: (s == "held").mean(), broke=lambda s: (s == "broke").mean())
        g["held_minus_broke"] = g.held - g.broke
        return g.round(3)

    print("all signals before the exam:")
    print(tab([]).to_string())
    D["stair_bin"] = pd.cut(D.stair, [-0.01, 0.4, 0.6, 1.0], labels=["<=0.4", "0.4-0.6", ">0.6"])
    D["move24_bin"] = pd.cut(D.move24, [-99, 1.0, 3.0, 99], labels=["<1", "1-3", ">3"])
    D["swings_bin"] = np.where(D.swings >= 2, ">=2 swings", "1 swing")
    for name, by in (("H-a the level was crossed before the bounce", ["crossed"]),
                     ("H-b the bounce's staircase on the entry TF", ["stair_bin"]),
                     ("H-c the H1 move already made (H1 ATRs)", ["move24_bin"]),
                     ("side", ["side"]), ("window", ["window"]), ("the level's swings", ["swings_bin"]),
                     ("H1 in the zone", ["has_h1"])):
        print(f"\n{name}:")
        print(tab(by).to_string())


if __name__ == "__main__":
    main()
