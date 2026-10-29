"""The H1 lean (BOT_RULES rule 1) hour by hour on one day, with what price did next - a check by eye.

Usage: lean_day.py 2026-10-27   (Thai date; every M5 close on the hour, and each window's start)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e  # noqa: E402


def main(day: str) -> None:
    full = bot2e.load_frames()
    m5 = full["M5"]
    ends = m5.index + pd.Timedelta(minutes=5)
    times = [f"{h:02d}:00" for h in range(24)] + ["19:30"]
    print("time   price    lean                                  next 4h: high   low    close")
    for t in sorted(times):
        now = pd.Timestamp(f"{day} {t}", tz=bot2e.TH).tz_convert("UTC")
        k = int(ends.searchsorted(now, side="right"))
        if k < 1 or ends[k - 1] != now:
            continue
        h1 = bot2e.cut({"H1": full["H1"]}, now)["H1"]
        side, text = bot2e.h1_lean(h1, bot2e._zigzag(h1))
        nxt = m5.iloc[k : k + 48]
        price = float(m5.close.iloc[k - 1])
        print(f"{t}  {price:8.2f}  {text:38}  {nxt.high.max():8.2f} {nxt.low.min():8.2f} {nxt.close.iloc[-1]:8.2f}")
    h1 = full["H1"]
    sel = h1[(h1.index >= pd.Timestamp(day, tz=bot2e.TH) - pd.Timedelta(days=2))
             & (h1.index < pd.Timestamp(day, tz=bot2e.TH) + pd.Timedelta(days=1))]
    piv = [s for s in bot2e._zigzag(h1.iloc[-2000:]) if s.pivot_at in sel.index]
    print("\nH1 fixed pivots near the day (Thai time):")
    for s in piv:
        print(f"  {s.kind.value:4} {s.price:8.2f} at {pd.Timestamp(s.pivot_at).tz_convert(bot2e.TH):%m-%d %H:%M}"
              f"  fixed {pd.Timestamp(s.confirm_at).tz_convert(bot2e.TH) + pd.Timedelta(hours=1):%m-%d %H:%M}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-10-27")
