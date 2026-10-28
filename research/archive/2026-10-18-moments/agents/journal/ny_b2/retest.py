"""Owner 2026-10-22: "the market fell three days and you lost every day... if day one falls hard, the worst you do the
next day is wait for the re-test and sell." The day after a strong D1 bar (|body| >= 1 D1 ATR(20), the close in the
last 30 % of the range), on M15 bars 2023-08 .. END (closed bars, nothing after):

- break: the next day trades beyond the strong day's extreme (its low after a down day)
- re-test: price comes back to that extreme (within 0.1 ATR of it) and an M15 bar closes back on the break side
- sell (buy after an up day) at that close; stop beyond the re-test swing (the highest high since the break) + 0.05 ATR;
  half off at +1 R with the rest's stop to the entry, the rest to +2.5 R or the end of the day (23:00 Thai); the stop
  first when one bar holds both; cost 0.35 USD spread a trade
One trade a day at most.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/retest.py 2026-03-21
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import week as W

SPREAD = 0.35


def manage(b: pd.DataFrame, side: int, entry: float, stop: float, last: pd.Timestamp) -> float:
    risk = abs(entry - stop)
    half, st, r = False, stop, 0.0
    for t, x in b.iterrows():
        if t > last:
            break
        adverse, fav = (x.high, x.low) if side < 0 else (x.low, x.high)
        if (adverse - st) * side <= 0:
            return r + (0.5 if half else 1.0) * (st - entry) * side / risk
        if not half and (fav - entry) * side >= risk:
            half, r, st = True, 0.5, entry
        if half and (fav - entry) * side >= 2.5 * risk:
            return r + 0.5 * 2.5
    c = b[b.index <= last].close.iloc[-1]
    return r + (0.5 if half else 1.0) * (c - entry) * side / risk


def main() -> None:
    end = pd.Timestamp(sys.argv[1], tz="UTC")
    d1 = W.Z.bars("D1")
    d1 = d1[d1.index < end]
    m15 = W.Z.bars("M15")
    m15 = m15[m15.index < end]
    pc = d1.close.shift(1)
    atr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)
    m15["day"] = m15.index.tz_convert("Europe/Athens").normalize()
    days = dict(tuple(m15.groupby("day")))
    rows = []
    for i in range(21, len(d1) - 1):
        b, a = d1.iloc[i], atr.iloc[i]
        if not np.isfinite(a) or b.high == b.low:
            continue
        side = 1 if b.close > b.open else -1
        body = (b.close - b.open) * side / a
        pos = (b.close - b.low) / (b.high - b.low) if side > 0 else (b.high - b.close) / (b.high - b.low)
        if body < 1.0 or pos < 0.7:
            continue
        key = d1.index[i + 1].tz_convert("Europe/Athens").normalize()
        if key not in days:
            continue
        g = days[key]
        last = g.index[g.index.tz_convert("Asia/Bangkok").hour < 23][-1] if (g.index.tz_convert("Asia/Bangkok").hour < 23).any() else g.index[-1]
        ext = b.low if side < 0 else b.high
        broke, swing, trade = False, None, None
        for t, x in g.iterrows():
            if t > last:
                break
            if not broke:
                if (x.low < ext) if side < 0 else (x.high > ext):
                    broke = True
                    swing = x.high if side < 0 else x.low
                continue
            swing = max(swing, x.high) if side < 0 else min(swing, x.low)
            touched = (x.high >= ext - 0.1 * a) if side < 0 else (x.low <= ext + 0.1 * a)
            closed_back = (x.close < ext) if side < 0 else (x.close > ext)
            if touched and closed_back:
                entry = x.close - side * SPREAD / 2
                stop = swing + 0.05 * a if side < 0 else swing - 0.05 * a
                if abs(entry - stop) < 1.0:
                    continue
                rest = g[g.index > t]
                if rest.empty:
                    break
                r = manage(rest, side, entry, stop, last) - SPREAD / 2 / abs(entry - stop)
                trade = dict(day=key.date(), side="SELL" if side < 0 else "BUY", entry_th=t.tz_convert("Asia/Bangkok").strftime("%H:%M"),
                             hour=t.tz_convert("Asia/Bangkok").hour, stop_usd=abs(entry - stop), r=r, usd001=r * abs(entry - stop))
                break
        rows.append(dict(day=key.date(), dir=side, broke=broke, traded=trade is not None))
        if trade:
            rows[-1].update(trade)
    R = pd.DataFrame(rows)
    T = R[R.traded]
    for s, n in ((-1, "after strong DOWN days: sell the re-test"), (1, "after strong UP days: buy the re-test")):
        S, A = T[T.dir == s], R[R.dir == s]
        print(f"{n}: {len(A)} strong days, broke {A.broke.sum()}, traded {len(S)} | {S.r.sum():+.2f} R, {S.r.mean():+.3f} a trade, "
              f"won {(S.r > 0).mean() * 100:.0f} %, {S.usd001.sum():+.1f} USD at 0.01")
        recent = S[pd.to_datetime(S.day) >= pd.Timestamp("2025-10-18")]
        print(f"   the journal's 12 months: {len(recent)} trades {recent.r.sum():+.2f} R | before: {len(S) - len(recent)} trades {(S.r.sum() - recent.r.sum()):+.2f} R")
        print(S.groupby(pd.cut(S.hour, [-1, 6, 12, 18, 24])).r.agg(["size", "sum"]).round(2).to_string())
    print("\nthe journal's period (2025-10 ..):")
    print(T[pd.to_datetime(T.day) >= pd.Timestamp("2025-10-18")][["day", "side", "entry_th", "stop_usd", "r", "usd001"]].round(2).to_string())


if __name__ == "__main__":
    main()
