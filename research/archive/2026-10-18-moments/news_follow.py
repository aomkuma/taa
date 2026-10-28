"""Round 10b (docs/OWN_SETUP_ROUNDS.md): after a US release (the official calendar), does gold's first one or two minutes'
move continue over the next 15 / 30 / 60 minutes? The first move is the market's reading of the surprise.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/news_follow.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

SPLIT = pd.Timestamp("2026-03-01", tz="UTC")


def main() -> None:
    m1 = gold.bars("M1")
    m1 = m1[m1.index >= pd.Timestamp("2023-10-01", tz="UTC")]
    o, h, lo, c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m1["spread"].to_numpy(float) * 0.01
    pos = pd.Series(np.arange(len(m1)), index=m1.index)
    atr = pd.Series(h - lo).rolling(60).mean().to_numpy()
    cal = gold.releases()
    cal = cal[cal.t >= pd.Timestamp("2023-11-01", tz="UTC")]
    # one row per release minute (several events at 08:30 ET share it)
    ev = cal.groupby("t").event.apply(lambda x: "+".join(sorted(set(x)))).reset_index()
    rows = []
    for t, name in zip(ev.t, ev.event, strict=True):
        i = pos.get(t)
        if i is None or i + 61 >= len(o) or i < 61:
            continue
        for k in (1, 2):
            first = c[i + k - 1] - o[i]
            base = c[i + k - 1]
            s = np.sign(first)
            rec = dict(t=t, event=name, k=k, first=first, first_atr=abs(first) / atr[i - 1], side=s)
            for hz in (15, 30, 60):
                rec[f"next{hz}"] = (c[i + k - 1 + hz] - base) * s
            # a trade: entry at the next bar's open in the first move's direction, the cost of a round trip
            e = i + k
            entry = o[e] + (sp[e] + 0.07 if s > 0 else -0.07)
            rec["chase"] = (entry - base) * s  # how much of the move the entry already gave away
            for hz in (15, 30):
                x = e + hz - 1
                ex = c[x] - (0.07 if s > 0 else -(sp[x] + 0.07))
                rec[f"trade{hz}"] = (ex - entry) * s
            rows.append(rec)
    d = pd.DataFrame(rows)
    d["part"] = np.where(d.t < SPLIT, "2023-11 .. 2026-02", "TEST 2026-03 .. 10")
    d["big"] = d.first_atr >= 3
    pd.set_option("display.width", 220)
    for k in (1, 2):
        x = d[d.k == k]
        print(f"\n== first {k} minute(s): mean continuation (USD, signed by the first move) and share continuing")
        g = x.groupby(["part", "big"]).agg(
            n=("first", "size"), first=("first", lambda v: v.abs().median()),
            next15=("next15", "mean"), next30=("next30", "mean"), next60=("next60", "mean"),
            cont30=("next30", lambda v: (v > 0).mean()), trade15=("trade15", "mean"), trade30=("trade30", "mean"),
        )
        print(g.round(2).to_string())
        x2 = x[x.big]
        print("  big first moves (>= 3 x the hour's 1-minute range) by event:")
        main_ev = x2.assign(ev=x2.event.str.split("+").str[0])
        print(main_ev.groupby(["ev", "part"]).agg(n=("first", "size"), next30=("next30", "mean"),
                                                  cont30=("next30", lambda v: (v > 0).mean()),
                                                  trade30=("trade30", "mean")).round(2).to_string())
    d.to_parquet("data/research/own_news_follow.parquet")


if __name__ == "__main__":
    main()
