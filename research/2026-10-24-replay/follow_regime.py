"""The reclaim's opposite: FOLLOW the break - owner 2026-10-25 (the bull market of 2025); transform before discard
(owner 2026-10-20). Selling a swept high lost in the bull years: does buying a held break of a high win there?

Level and break as reclaim_2025.py. Entry: the first M5 close at least PAST x the M5 ATR beyond the level within
30 minutes of the break, in the break's direction (a high broken: BUY, a low broken: SELL). Stop: back across the
level by 1.0 ATR (the level - 1 ATR for a buy). Target 0.7 / 1.0 R, out after two hours. Spread as before.
Split by reclaim_regime.py's big regime (D1 over/under its 50-day mean and the mean's slope).

    .venv/Scripts/python research/2026-10-24-replay/follow_regime.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reclaim_2025 import CLOSE_BACK, HOLD, LOOK, POINT, ROOT, m5_from_m1  # noqa: E402
from reclaim_regime import regime_by_day  # noqa: E402
from sweep_depth import SIDE, atr  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

PAST = (0.5, 1.0)
STOP_ATR = 1.0


def follow(df: pd.DataFrame, past: float) -> pd.DataFrame:
    h, lo, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    spr = df.spread.to_numpy(float) * POINT
    a = atr(h, lo, c)
    n, rows = len(df), []
    for i in range(SIDE, n - SIDE):
        for up in (True, False):
            x = h if up else lo
            win = x[i - SIDE : i + SIDE + 1]
            if not (x[i] == (win.max() if up else win.min()) and (win == x[i]).sum() == 1):
                continue
            level, known, sign = x[i], i + SIDE, 1.0 if up else -1.0
            j = next(
                (k for k in range(known + 1, min(n, known + 1 + LOOK)) if (x[k] - level) * sign > 0), None
            )
            if j is None or np.isnan(a[j - 1]):
                continue
            k = next(
                (b for b in range(j, min(n, j + CLOSE_BACK)) if (c[b] - level) * sign >= past * a[j - 1]),
                None,
            )
            if k is None or k + 1 >= n:
                continue
            if up:
                entry, stop = c[k] + spr[k], level - STOP_ATR * a[j - 1]
            else:
                entry, stop = c[k], level + STOP_ATR * a[j - 1]
            risk = (entry - stop) * sign
            if risk <= 0:
                continue
            rs = {}
            for tr in (0.7, 1.0):
                tp = entry + sign * tr * risk
                last, res = min(n - 1, k + HOLD), None
                for b in range(k + 1, last + 1):
                    if up:
                        if lo[b] <= stop:
                            res = -1.0
                        elif h[b] >= tp:
                            res = tr
                    else:
                        if h[b] + spr[b] >= stop:
                            res = -1.0
                        elif lo[b] + spr[b] <= tp:
                            res = tr
                    if res is not None:
                        break
                if res is None:
                    res = ((c[last] - entry) if up else (entry - c[last] - spr[last])) / risk
                rs[tr] = res
            rows.append({"t": df.index[k], "up": up, "r07": rs[0.7], "r10": rs[1.0]})
    return pd.DataFrame(rows)


def main() -> None:
    m1 = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None)
    m5 = m5_from_m1(m1)
    lab = regime_by_day(m5)
    for title, lo_, hi_ in (
        ("2024 (before the exam)", "2023-12-31", "2025-01-01"),
        ("2025 (before the exam)", "2024-12-31", "2026-01-01"),
        ("2026-07-01 .. (replay months, information only)", "2026-06-30", "2100-01-01"),
    ):
        part = m5[(m5.index >= lo_) & (m5.index < hi_)]
        print(f"\n== {title} ==")
        print("past ATR | regime | side           | trades | 0.7 R: win %, avg R | 1.0 R: win %, avg R")
        for past in PAST:
            ev = follow(part, past)
            ev = ev.assign(regime=lab.reindex(pd.DatetimeIndex(ev.t).normalize()).to_numpy())
            for reg in ("bull", "mixed", "bear"):
                for up in (True, False):
                    e = ev[(ev.regime == reg) & (ev.up == up)]
                    if len(e):
                        side = "BUY (high brk)" if up else "SELL (low brk)"
                        print(
                            f"{past:8.1f} | {reg:6s} | {side:14s} | {len(e):6d} | "
                            f"{(e.r07 > 0).mean():4.0%}, {e.r07.mean():+.3f}       | "
                            f"{(e.r10 > 0).mean():4.0%}, {e.r10.mean():+.3f}"
                        )


if __name__ == "__main__":
    main()
