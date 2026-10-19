"""Q4 - are the pattern trades WITH or AGAINST the larger structure, and does it matter?

The owner's own record (docs/OWNER_TRADING.md): trades 1 and 4 went with the structure (a buy at a higher low in a
rise; a sell of the first lower high after a failed retest with LH / LL on every TF) - both paid; trades 2 and 3 were
sells against an up-structure (a right shoulder; the top of a rising M30 range) - both stopped. The team's B2 set is
mostly reversal patterns at levels (W / M, H&S, sweep-turn).

Written before computing. For every B2 (P3) and W (P4) trade, news cost 0, read at its entry decision `t_entry`
(only bars complete by then):
- H1 and M15 swing structure: fractal swings (k = 2, `zones.swings`, each known when the 2nd bar after it closes);
  the last two known tops and the last two known lows: up = higher top and higher low, down = lower top and lower
  low, else mixed; turned to the trade's side (with / against / mixed);
- the move before: the M1 close at the decision minus the close 4 hours earlier, in the trade's way (with / against);
- the day so far: the close minus the server day's (Europe/Athens) first open, in the trade's way;
- H4 tide: the H4 EMA 50's slope over 5 bars, in the trade's way.
R per part for each group, with the 95 % range. No setting is chosen here; these are reads of the existing trades.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/struct_split.py > .../strategist/out_struct_split.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import slib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import foundation as F  # noqa: E402
import indicators  # noqa: E402
import zones  # noqa: E402

m = slib.m1("2025-08-01")
mt = m.index.asi8
mc = m.close.to_numpy()
m_av = mt + 60 * 10**9


def struct_reader(rule: str):
    b = indicators.bars(m, rule)
    S = zones.swings(b, 2)
    tops = S[S.kind == 1].sort_values("known")
    lows = S[S.kind == -1].sort_values("known")
    tk, tp = tops.known.to_numpy(), tops.price.to_numpy()
    lk, lp = lows.known.to_numpy(), lows.price.to_numpy()

    def at(t: int) -> int:
        i = np.searchsorted(tk, t, side="right")
        j = np.searchsorted(lk, t, side="right")
        if i < 2 or j < 2:
            return 0
        hh, hl = tp[i - 1] > tp[i - 2], lp[j - 1] > lp[j - 2]
        lh, ll = tp[i - 1] < tp[i - 2], lp[j - 1] < lp[j - 2]
        return 1 if (hh and hl) else (-1 if (lh and ll) else 0)

    return at


h1_at, m15_at = struct_reader("1h"), struct_reader("15min")
h4 = indicators.bars(m, "4h")
e50 = np.array(F.ema(h4.close.to_numpy(float), 50), float)
slope = e50 - pd.Series(e50).shift(5).to_numpy()
h4_av = pd.DatetimeIndex(h4["avail"]).as_unit("ns").asi8
dkey = m.index.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
day_open = pd.Series(m.open.to_numpy()).groupby(dkey.to_numpy()).transform("first").to_numpy()


def close_at(t: int) -> tuple[float, int]:
    i = np.searchsorted(m_av, t, side="right") - 1
    return mc[i], i


def label(v: float) -> str:
    return "with" if v > 0 else ("against" if v < 0 else "mixed")


def read(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t, s in zip(d.t_entry.to_numpy(), d.side.to_numpy()):
        c, i = close_at(int(t))
        c4, _ = close_at(int(t) - 4 * 3600 * 10**9)
        k = indicators.at(h4_av, np.array([int(t)]))[0]
        rows.append(dict(h1=label(h1_at(int(t)) * s), m15=label(m15_at(int(t)) * s), move4h=label((c - c4) * s),
                         day=label((c - day_open[i]) * s), h4tide=label(slope[k] * s if k >= 0 else 0)))
    return pd.concat([d.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


for name, d in (("B2 (P3)", slib.dev_trades("p3_trades_all.parquet", "B2")),
                ("W (P4)", slib.dev_trades("p4_trades_W_WL.parquet", "W"))):
    X = read(d)
    X.to_parquet(slib.HERE / f"struct_{name.split()[0]}.parquet")
    print(f"=== {name}")
    for col in ("h1", "m15", "move4h", "day", "h4tide"):
        for g in ("with", "against", "mixed"):
            cells = [slib.row(X[(X.part == p) & (X[col] == g)]) for p in ("P1", "P2")]
            if all(c == "n 0" for c in cells):
                continue
            print(f"  {col:7s} {g:8s} P1 {cells[0]}  |  P2 {cells[1]}")
    for lab, msk in (("H1 & M15 both with", (X.h1 == "with") & (X.m15 == "with")),
                     ("H1 & M15 both against", (X.h1 == "against") & (X.m15 == "against")),
                     ("H1 with & move4h with", (X.h1 == "with") & (X.move4h == "with")),
                     ("H1 against & move4h against", (X.h1 == "against") & (X.move4h == "against"))):
        cells = [slib.row(X[(X.part == p) & msk]) for p in ("P1", "P2")]
        print(f"  {lab:28s} P1 {cells[0]}  |  P2 {cells[1]}")
    print("  family shares by H1 relation (both parts):")
    print(pd.crosstab(X.family, X.h1).to_string())
    print()
