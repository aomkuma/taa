"""The FOMC press conference (14:30 ET on statement days, federalreserve.gov): follow the presser's first minutes.

Decide at the close of the bar before 14:00 + k ET (k = 40 -> 10 minutes into the presser); side = the sign of
(that close - the 14:30 bar's open); enter at the next bar's open. Stop / exit variants below.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/presser.py [--test]

Without --test only A (2021-09 .. 2023-10) and B (2023-11 .. 2026-02) are computed.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import Gold, events, summary  # noqa: E402

TEST = "--test" in sys.argv


def plans():
    for k in (40, 45, 50):
        for stop in ("pre6", "pre10", "pre15", "struct", "atr2", "atr3"):
            for ex in ("t60", "t120", "t180", "r2", "r3", "trail"):
                yield k, stop, ex


def make(G: Gold, i: int, k: int, stop: str, ex: str, side_override: int | None = None):
    rng = G.h - G.lo
    pre = rng[i - 60 : i].mean()
    p0 = i + 30
    e = i + k
    mv = G.c[e - 1] - G.o[p0]
    s = 1 if mv > 0 else -1
    if side_override is not None:
        s = side_override
    fill = G.fill(e, s)
    if stop.startswith("pre"):
        sl = float(stop[3:]) * pre
    elif stop == "struct":
        ext = G.lo[p0:e].min() if s > 0 else G.h[p0:e].max() + G.sp[e - 1]
        sl = (fill - ext) * s + pre
    else:
        sl = float(stop[3:]) * rng[e - 10 : e].mean()
    sl = max(sl, 1.0 * pre)
    if ex.startswith("t") and ex != "trail":
        return e, s, sl, None, int(ex[1:]), None, abs(mv) / pre
    if ex.startswith("r"):
        return e, s, sl, float(ex[1:]) * sl, 180, None, abs(mv) / pre
    return e, s, sl, None, 180, sl, abs(mv) / pre  # trail by 1 x the stop after +1R


def main() -> None:
    G = Gold()
    ev = events(extra=True)
    ev = ev[ev.main == "PC"]
    if not TEST:
        ev = ev[ev.per != "T"]
    rows = []
    for r in ev.itertuples():
        i = int(G.pos.get(r.t - pd.Timedelta(minutes=30), -1))  # the statement minute (14:00 ET)
        if i < 0 or G.ot[i + 30] != r.t:
            print("skip (bars missing):", r.t)
            continue
        for k, stop, ex in plans():
            e0, s0, *_ = make(G, i, k, stop, ex)
            for who, so in (("rule", None), ("opp", -s0)):
                e, s, sl, tp, hz, trail, x = make(G, i, k, stop, ex, so)
                kind_tp = tp if tp is not None else 2 * sl
                out = G.trade(e, s, sl, tp, hz, trail=trail, kind_tp=kind_tp)
                rows.append(dict(t=r.t, per=r.per, k=k, stop=stop, ex=ex, who=who, x=x, sl=sl, side=s, **out))
    d = pd.DataFrame(rows)
    d.to_parquet(f"research/2026-10-18-moments/agents/news/presser_{'test' if TEST else 'design'}.parquet")
    g = d[d.who == "rule"].groupby(["k", "stop", "ex", "per"]).R.mean().unstack("per")
    o = d[d.who == "opp"].groupby(["k", "stop", "ex", "per"]).R.mean().unstack("per")
    g["minAB"] = g[["A", "B"]].min(axis=1)
    for p_ in ("A", "B"):
        g[f"coin{p_}"] = (g[p_] + o[p_]) / 2  # the coin's expectation: the average of both sides
    pd.set_option("display.width", 250)
    print(g.sort_values("minAB", ascending=False).round(3).head(40).to_string())
    print("\nmean over all plans by k / stop / exit (A, B):")
    for col in ("k", "stop", "ex"):
        print(d[d.who == "rule"].groupby([col, "per"]).R.mean().unstack().round(3).to_string())


if __name__ == "__main__":
    main()
