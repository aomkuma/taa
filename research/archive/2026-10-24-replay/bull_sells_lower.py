"""Sells inside a bull regime, split by the H1 / H4 trend - owner 2026-10-25: "no sells in a bull market - but
trading M1, is there no sell when H1 or H4 is clearly down?" The condition to find for R08's exception.

The same mean-and-slope definition on every frame (reclaim_regime.py): down = the last closed bar's close under
its 50-bar mean AND the mean lower than 20 bars earlier; up the mirror; else mixed. D1 by UTC day, H4 / H1 from
M5 closes; each label uses bars closed before the trade's bar. Sells (and buys, for the comparison): the reclaim
of reclaim_2025.py (buffer 1.0 ATR, 0.7 R) and following the break of follow_regime.py (1.0 ATR past, 0.7 R).

    .venv/Scripts/python research/2026-10-24-replay/bull_sells_lower.py [m1]

m1: the same rules on M1 bars (levels, 6-bar close back, 24-bar hold: the same bar counts, a frame five times
smaller). Also counts the trade days: on how many bull days a BUY candidate showed in the owner's windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from follow_regime import follow  # noqa: E402
from reclaim_2025 import ROOT, m5_from_m1, signals, trade  # noqa: E402
from reclaim_regime import MEAN, SLOPE, regime_by_day  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402


def frame_state(m5: pd.DataFrame, rule: str) -> pd.Series:
    """The state per bar of *rule* (e.g. '4h'), known from the next bar's open on (closed bars only)."""
    c = m5.close.resample(rule).last().dropna()
    mean = c.rolling(MEAN).mean()
    up = (c > mean) & (mean > mean.shift(SLOPE))
    down = (c < mean) & (mean < mean.shift(SLOPE))
    lab = pd.Series(np.where(up, "up", np.where(down, "down", "mixed")), index=c.index)
    lab[mean.shift(SLOPE).isna()] = "?"
    lab.index = lab.index + pd.Timedelta(rule)  # usable once the bar has closed
    return lab


def at(lab: pd.Series, t: pd.DatetimeIndex) -> np.ndarray:
    i = lab.index.searchsorted(t, side="right") - 1  # the last label known at t (several trades share a bar)
    return np.where(i >= 0, lab.to_numpy()[np.maximum(i, 0)], "?")


def report(ev: pd.DataFrame, name: str) -> None:
    print(f"\n-- {name}: bull days only --")
    print("H4    | H1    | SELL trades, win %, avg R | BUY trades, win %, avg R")
    for h4 in ("down", "mixed", "up"):
        for h1 in ("down", "mixed", "up"):
            cells = []
            for up in (False, True):  # sells first
                e = ev[(ev.h4 == h4) & (ev.h1 == h1) & (ev.sell != up)]
                cells.append(
                    f"{len(e):5d}, {(e.r > 0).mean():4.0%}, {e.r.mean():+.3f}" if len(e) else "    -"
                )
            print(f"{h4:5s} | {h1:5s} | {cells[0]:25s} | {cells[1]}")


def main() -> None:
    m1 = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None)
    m5 = m5_from_m1(m1)
    d1, h4, h1 = regime_by_day(m5), frame_state(m5, "4h"), frame_state(m5, "1h")
    entry = m5
    if "m1" in sys.argv:
        entry = m1.assign(t=pd.to_datetime(m1.open_time, utc=True)).drop_duplicates("t", keep="last")
        entry = entry.set_index("t").sort_index()[["open", "high", "low", "close", "spread"]]
    part = entry[(entry.index >= "2023-12-31") & (entry.index < "2026-01-01")]  # 2024 + 2025, before the exam
    rec = signals(part)
    t = part.index[rec.k.to_numpy()]
    rec = rec.assign(t=t, sell=rec.up, r=[trade(part, s, 1.0, 0.7) for s in rec.itertuples()])
    fol = follow(part, 1.0).rename(columns={"r07": "r"})
    fol = fol.assign(sell=~fol.up)
    print(
        f"2024 + 2025 (before the exam), entry frame {'M1' if 'm1' in sys.argv else 'M5'}; R after the spread"
    )
    for name, ev in (("the reclaim (fade a sweep)", rec), ("following the break (1 ATR past)", fol)):
        tt = pd.DatetimeIndex(ev.t)
        ev = ev.assign(d1=d1.reindex(tt.normalize()).to_numpy(), h4=at(h4, tt), h1=at(h1, tt)).dropna(
            subset=["r"]
        )
        report(ev[ev.d1 == "bull"], name)
        bull = ev[(ev.d1 == "bull") & ~ev.sell]
        th = pd.DatetimeIndex(bull.t).tz_convert("Asia/Bangkok")
        hm = th.hour + th.minute / 60
        win = bull[((hm >= 7) & (hm < 9)) | ((hm >= 13) & (hm < 15)) | ((hm >= 19.5) & (hm < 22))]
        days = int((d1 == "bull").loc["2024":"2025"].sum())
        got = pd.DatetimeIndex(win.t).normalize().nunique()
        print(
            f"trade days: a BUY candidate in the owner's windows on {got} of {days} bull days "
            f"({got / days:.0%}), {len(win) / days:.1f} a day"
        )


if __name__ == "__main__":
    main()
