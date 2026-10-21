"""The spread around PLAN-1's straddle fills on P1 / P2 (measurer, 2026-10-21 Q3): at each fill tick of the bot's
straddle trades (plan1_app_trades_learn.parquet), at the trigger tick (the tick before the fill) and the widest
in the 30 s before the fill, in points (0.01 USD) from the raw ticks; max, p99, p95, median. Also the ORB's fill
ticks for comparison. Nothing at / after 2026-04-18 is read.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_spreads.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from app.market_data.tick_store import TickStore  # noqa: E402

EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
POINT = 0.01


def main() -> None:
    A = pd.read_parquet(HERE / "plan1_app_trades_learn.parquet")
    store = TickStore(ROOT / "data/ticks", end=EXAM_START.to_pydatetime())
    rows = []
    for r in A.itertuples():
        t_in = pd.Timestamp(int(r.t_in), tz="UTC")
        if t_in >= EXAM_START:
            raise SystemExit("a trade at / after 2026-04-18")
        t, bid, ask = store.between("XAUUSD", (t_in - pd.Timedelta(seconds=30)).to_pydatetime(),
                                    (t_in + pd.Timedelta(milliseconds=1)).to_pydatetime())
        if not len(t):
            continue
        spr = (ask - bid) / POINT
        rows.append(dict(piece=r.piece, t_in=t_in, fill=spr[-1], trigger=spr[-2] if len(spr) > 1 else np.nan,
                         max30=spr.max()))
    S = pd.DataFrame(rows)
    for pc, g in S.groupby("piece"):
        print(f"{pc}: {len(g)} fills")
        for col in ("fill", "trigger", "max30"):
            x = g[col].dropna()
            print(f"  {col:8s} max {x.max():6.1f}  p99 {x.quantile(0.99):6.1f}  p95 {x.quantile(0.95):6.1f}  "
                  f"median {x.median():6.1f} points")
        top = g.sort_values("max30", ascending=False).head(5)
        for q in top.itertuples():
            print(f"    widest: {q.t_in.tz_convert('Asia/Bangkok'):%Y-%m-%d %H:%M:%S} Thai fill {q.fill:.0f} "
                  f"trigger {q.trigger:.0f} max30 {q.max30:.0f}")
    print(f"fills over 40 points (the XAUUSD cap now): "
          f"{S[(S.piece == 'NY straddle') & ((S.fill > 40) | (S.trigger > 40))].shape[0]} straddle, "
          f"{S[(S.piece == 'London ORB') & (S.fill > 40)].shape[0]} ORB")


if __name__ == "__main__":
    main()
