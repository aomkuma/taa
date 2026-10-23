"""What the market did in exam week N, closed bars of that week only: per server day the sessions (Thai time) as
open -> close, high / low, and the NY window's H1 bars with their wicks and tick volume.

    solo_look.py 1
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import solo_lib as S

SESSIONS = (("Asia 04-13", 4, 13), ("London 13-19", 13, 19), ("NY 19-24", 19, 24), ("late 00-04", 24, 29))


def main(n: int) -> None:
    s, e = S.bounds(n)
    import pieces as P

    h1 = P.bars("H1")  # with the stored H1 hole (2026-10-05 ..) filled from M1
    h1 = h1[(h1.index >= s) & (h1.index + pd.Timedelta(hours=1) <= e)]
    th = h1.index.tz_convert("Asia/Bangkok")
    vol_med = h1.tick_volume.median()
    for day, g in h1.groupby(h1.index.tz_convert("Europe/Athens").date):  # the server day
        gh = g.index.tz_convert("Asia/Bangkok").hour
        gh = np.where(gh < 4, gh + 24, gh)  # 00-04 Thai of the next date: the server day's last hours
        line = [f"{pd.Timestamp(day):%a %d %b}"]
        for name, a, b in SESSIONS:
            x = g[(gh >= a) & (gh < b)]
            if len(x):
                line.append(f"{name}: {x.open.iloc[0]:.0f}->{x.close.iloc[-1]:.0f} ({x.close.iloc[-1] - x.open.iloc[0]:+.0f}) hi {x.high.max():.0f} lo {x.low.min():.0f}")
        print(" | ".join(line))
        ny = g[(gh >= 19) & (gh < 24)]
        for t, r in ny.iterrows():
            up, lo = r.high - max(r.open, r.close), min(r.open, r.close) - r.low
            print(f"     {t.tz_convert('Asia/Bangkok'):%H:%M} o {r.open:.1f} h {r.high:.1f} l {r.low:.1f} c {r.close:.1f} body {r.close - r.open:+.1f} "
                  f"wick up {up:.1f} dn {lo:.1f} vol {r.tick_volume / vol_med:.1f}x")


if __name__ == "__main__":
    main(int(sys.argv[1]))
