"""The sweep statistics of sweep_depth.py split by side and by the market state at the break - owner 2026-10-25:
"an EA set apart for sell, buy and sideways, rather than one strategy for every case?" Before splitting the
rules, measure whether the two sides and the three states differ at all.

Side: a break of a swing HIGH (price runs up through it: the sellers' stops) or of a swing LOW (runs down).
State at the break, from the 24 hours of M5 bars before the breaking bar (known then, no look-ahead):
- move = the close before the break minus the close 24 hours earlier; range = the high - low of those bars;
- efficiency = |move| / range: >= EFFICIENT is a trend (up or down by the sign of the move), below it sideways.
Fake / real, the depth (in M5 ATR) and the two-hour run are sweep_depth.py's (the same events()).

    .venv/Scripts/python research/2026-10-24-replay/sweep_sides.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sweep_depth import ROOT, events  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

DAY = 288  # M5 bars in 24 hours
EFFICIENT = 0.5  # |move| / range at or above: a trend


def states(df: pd.DataFrame, at: pd.DatetimeIndex) -> list[str]:
    c = df.close.to_numpy(float)
    roll_hi = df.high.rolling(DAY).max().to_numpy()
    roll_lo = df.low.rolling(DAY).min().to_numpy()
    pos = df.index.get_indexer(at)
    out = []
    for j in pos:
        i = j - 1  # the bar before the break
        if i < DAY:
            out.append("?")
            continue
        move, rng = c[i] - c[i - DAY], roll_hi[i] - roll_lo[i]
        if rng <= 0 or abs(move) / rng < EFFICIENT:
            out.append("sideways")
        else:
            out.append("trend up" if move > 0 else "trend down")
    return out


def table(ev: pd.DataFrame, title: str) -> None:
    print(f"\n== {title}: {len(ev)} breaks ==")
    print(
        "state      | break of | breaks | real % | fake depth ATR med/75/90 | real 2h run ATR med | "
        "real % once >= 1 ATR past"
    )
    for state in ("trend up", "trend down", "sideways"):
        for side in ("high", "low"):
            e = ev[(ev.state == state) & (ev.side == side)]
            if not len(e):
                continue
            fake, real = e[e.kind == "fake"], e[e.kind == "real"]
            q = fake.depth_atr.quantile([0.5, 0.75, 0.9]).round(2).tolist() if len(fake) else []
            run = (real.run / real.atr).median() if len(real) else np.nan
            past = e[e.depth_atr >= 1.0]
            rp = f"{(past.kind == 'real').mean():.0%} of {len(past)}" if len(past) else "-"
            print(
                f"{state:10s} | {side:8s} | {len(e):6d} | {(e.kind == 'real').mean():5.0%}  | "
                f"{str(q):24s} | {run:5.2f}               | {rp}"
            )


def main() -> None:
    m5 = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M5, None, None)
    m5 = m5.assign(t=pd.to_datetime(m5.open_time, utc=True)).drop_duplicates("t", keep="last")
    m5 = m5.set_index("t").sort_index()
    for title, part in (
        (
            "design: 2025-04-18 .. 2026-04-17 (before the exam)",
            m5[(m5.index >= "2025-04-17") & (m5.index < "2026-04-18")],
        ),
        ("the replay months 2026-07-01 .. (information only)", m5[m5.index >= "2026-06-30"]),
    ):
        ev = events(part)
        ev = ev[ev.t >= part.index[0] + pd.Timedelta(days=1)]  # the first day has no 24-hour state
        ev = ev.assign(state=states(part, pd.DatetimeIndex(ev.t)))
        table(ev[ev.state != "?"], title)


if __name__ == "__main__":
    main()
