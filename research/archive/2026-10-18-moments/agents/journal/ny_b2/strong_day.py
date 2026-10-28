"""Owner 2026-10-22 after week 22: "so the first D1 bar probably fell hard - should you look for a sell the next day if
it falls with volume?" Measured on XAUUSD 2023-08 .. 2026-03-20 (nothing after the journal's present), closed bars:

- a strong day: |body| >= 1 D1 ATR(20) and the close in the last 30 % of the range in the body's direction; "with
  volume": its tick volume >= 1.2 x the 20-day mean (MT5 tick volume - the broker has no real volume for gold)
- the next day, in the strong day's direction (dir): the whole day; the run before the NY window (open -> 20:00 Thai)
  and its H1 tick volume against the same hours of the 20 days before; the NY window 20:00-23:00 Thai (H1 bars):
  open -> close, best and worst, in D1 ATR and USD
Every day is the baseline (dir = that day's own body).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/strong_day.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import week as W

END = pd.Timestamp("2026-03-21", tz="UTC")


def main() -> None:
    d1 = W.Z.bars("D1")
    d1 = d1[d1.index < END]
    h1 = W.Z.bars("H1")
    h1 = h1[h1.index < END]
    pc = d1.close.shift(1)
    atr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)
    v20 = d1.tick_volume.rolling(20).mean().shift(1)
    h1["day"] = h1.index.tz_convert("Europe/Athens").normalize()
    h1["th"] = h1.index.tz_convert("Asia/Bangkok").hour
    days = {k: g for k, g in h1.groupby("day")}
    keys = sorted(days)
    rows = []
    for i in range(21, len(d1) - 1):
        b, a = d1.iloc[i], atr.iloc[i]
        if not np.isfinite(a) or b.high == b.low:
            continue
        dr = 1 if b.close > b.open else -1
        body = (b.close - b.open) * dr / a
        pos = (b.close - b.low) / (b.high - b.low) if dr > 0 else (b.high - b.close) / (b.high - b.low)
        strong = body >= 1.0 and pos >= 0.7
        dkey = d1.index[i + 1].tz_convert("Europe/Athens").normalize()
        if dkey not in days:
            continue
        g = days[dkey]
        pre, ny = g[g.th < 20], g[(g.th >= 20) & (g.th < 23)]
        if len(pre) < 5 or len(ny) < 3:
            continue
        j = keys.index(dkey)
        if j < 20:
            continue
        past = pd.concat([days[k] for k in keys[max(0, j - 20):j]])
        pv = pre.tick_volume.sum() / max(1, past[past.th < 20].tick_volume.sum() / 20)
        n = d1.iloc[i + 1]
        ny_o, ny_c = ny.open.iloc[0], ny.close.iloc[-1]
        rows.append(dict(t=d1.index[i], strong=strong, vol=b.tick_volume >= 1.2 * v20.iloc[i], dir=dr, body=body,
                         next_day=(n.close - n.open) * dr / a, pre_run=(ny_o - n.open) * dr / a, pre_vol=pv,
                         ny=(ny_c - ny_o) * dr / a, ny_usd=(ny_c - ny_o) * dr,
                         ny_best=((ny.high.max() - ny_o) if dr > 0 else (ny_o - ny.low.min())),
                         ny_worst=((ny_o - ny.low.min()) if dr > 0 else (ny.high.max() - ny_o)), atr=a))
    R = pd.DataFrame(rows)

    def show(name: str, m: pd.Series) -> None:
        s = R[m]
        print(f"{name:58s} n {len(s):4d} | next day {s.next_day.mean():+.2f} ATR, same way {(s.next_day > 0).mean() * 100:3.0f} % | "
              f"NY 20-23 {s.ny.mean():+.3f} ATR ({s.ny_usd.mean():+.1f} USD), same way {(s.ny > 0).mean() * 100:3.0f} %, "
              f"best {s.ny_best.mean():.1f} / worst {s.ny_worst.mean():.1f} USD")

    show("every day (baseline)", R.strong | ~R.strong)
    for side, sm in (("down", R.dir < 0), ("up", R.dir > 0), ("both", R.dir != 0)):
        st = R.strong & sm
        print(f"\n-- strong {side} days --")
        show("strong", st)
        show("strong, with volume", st & R.vol)
        show("strong, without volume", st & ~R.vol)
        pr = st & (R.pre_run > 0.15)
        show("strong + next day already running its way before NY", pr)
        show("  ... and the pre-NY tick volume >= 1.2x usual", pr & (R.pre_vol >= 1.2))
        show("  ... with volume on both days", pr & (R.pre_vol >= 1.2) & R.vol)
        show("strong + next day running back before NY", st & (R.pre_run < -0.15))
        show("strong + next day flat before NY", st & (R.pre_run.abs() <= 0.15))
    print("\nthe strong down days with volume:")
    S = R[R.strong & R.vol & (R.dir < 0)]
    print(S.assign(t=S.t.dt.tz_convert("Europe/Athens").dt.date)[["t", "body", "next_day", "pre_run", "pre_vol", "ny", "ny_usd"]].round(2).to_string())


if __name__ == "__main__":
    main()
