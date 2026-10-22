"""The second piece of the journal from week 23 (owner 2026-10-22: "if day one falls hard, wait for the re-test and
sell the next day"): the re-test after a strong D1 bar, on ticks, beside NY-B2's realistic variant in one account.

The piece (measured on M15 2023-08 .. 2026-03 in retest.py: down days +0.283 R on 22, up days +0.453 on 45):
- a strong day: |body| >= 1 D1 ATR(20) (of the days before it) and the close in the last 30 % of its range
- the next server day, until 23:00 Thai: price trades beyond the strong day's extreme (break), comes back to within
  0.1 ATR of it and a closed M15 bar closes back on the break side (re-test) -> enter at the first tick after that
  bar, in the strong day's direction; stop beyond the re-test swing (the extreme since the break) + 0.05 ATR
- half off at +1 R with the rest's stop to the entry, the rest to +2.5 R or 23:00 Thai; one trade a day; spread only

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/retest_week.py 2026-03-23 2026-03-28
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import week as W

RETEST_FROM = pd.Timestamp("2026-03-23", tz="UTC")
MIN = 60 * 10**9


def ticks(day: pd.Timestamp):
    parts = [W.C.day_ticks(d) for d in (day - pd.Timedelta(days=1), day)]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    return tuple(np.concatenate([p[i] for p in parts]) for i in range(3))


def trades(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    d1 = W.Z.bars("D1")
    d1 = d1[d1.index < end]
    m15 = W.Z.bars("M15")
    m15 = m15[m15.index < end]
    pc = d1.close.shift(1)
    atr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)
    out = []
    for i in range(21, len(d1) - 1):
        nxt = d1.index[i + 1]
        if nxt + pd.Timedelta(days=1) < start or nxt >= end:
            continue
        b, a = d1.iloc[i], atr.iloc[i]
        if not np.isfinite(a) or b.high == b.low:
            continue
        side = 1 if b.close > b.open else -1
        body = (b.close - b.open) * side / a
        pos = (b.close - b.low) / (b.high - b.low) if side > 0 else (b.high - b.close) / (b.high - b.low)
        if body < 1.0 or pos < 0.7:
            continue
        cutoff = (nxt.tz_convert("Asia/Bangkok").normalize() + pd.Timedelta(days=1, hours=23)).tz_convert("UTC")
        g = m15[(m15.index >= nxt) & (m15.index + pd.Timedelta(minutes=15) <= cutoff)]
        ext = b.low if side < 0 else b.high
        broke, swing = False, None
        for t, x in g.iterrows():
            if not broke:
                if (x.low < ext) if side < 0 else (x.high > ext):
                    broke, swing = True, (x.high if side < 0 else x.low)
                continue
            swing = max(swing, x.high) if side < 0 else min(swing, x.low)
            if not (((x.high >= ext - 0.1 * a) and x.close < ext) if side < 0 else ((x.low <= ext + 0.1 * a) and x.close > ext)):
                continue
            stop = swing + 0.05 * a if side < 0 else swing - 0.05 * a
            tk = ticks((t + pd.Timedelta(minutes=15)).normalize())
            if tk is None:
                break
            tt, bid, ask = tk
            f = int(np.searchsorted(tt, (t + pd.Timedelta(minutes=15)).value))
            if f >= len(tt):
                break
            entry = ask[f] if side > 0 else bid[f]
            risk = (entry - stop) * side
            if risk < 1.0:
                continue
            t_end = cutoff.value
            px1, tx1, k1 = W.C.manage(tt, bid, ask, f, entry, side, stop, entry + side * risk, t_end)
            if k1 != "target":
                r = (px1 - entry) * side / risk
            else:
                f2 = int(np.searchsorted(tt, tx1))
                px2, _, _ = W.C.manage(tt, bid, ask, f2, entry, side, entry, entry + side * 2.5 * risk, t_end)
                r = 0.5 + 0.5 * (px2 - entry) * side / risk
            out.append(dict(t=pd.Timestamp(tt[f], tz="UTC"), side="BUY" if side > 0 else "SELL", entry_price=entry, sl_initial=stop,
                            r_real=r, strong_day=d1.index[i].tz_convert("Europe/Athens").date(), body=body, ext=ext, exit1=k1))
            break
    return pd.DataFrame(out)


if __name__ == "__main__":
    s, e = pd.Timestamp(sys.argv[1], tz="UTC"), pd.Timestamp(sys.argv[2], tz="UTC")
    X = W.build(e)
    B = X[["t", "side", "entry_price", "sl_initial", "r_real"]].assign(piece="B2")
    R = trades(RETEST_FROM, e)
    A = pd.concat([B, R.assign(piece="re-test")] if len(R) else [B]).sort_values("t").reset_index(drop=True)
    A = W.accounts(A, "r_real", "c")
    wk = A[(A.t >= s) & (A.t < e)]
    for r in wk.itertuples():
        risk = abs(r.entry_price - r.sl_initial)
        print(f"{r.t.tz_convert('Asia/Bangkok'):%a %d %H:%M} {r.piece:7s} {r.side:4s} entry {r.entry_price:.2f} stop {risk:.2f} | "
              f"{'skipped' if not np.isfinite(r.r_real) else f'{r.r_real:+.2f} R'} | 100 {r.usdc_100:+.2f} -> {r.balc_100:.2f}, 300 {r.usdc_300:+.2f} -> {r.balc_300:.2f}")
    if len(R):
        rw = R[(R.t >= s) & (R.t < e)]
        for r in rw.itertuples():
            print(f"  re-test detail: strong day {r.strong_day} body {r.body:.2f} ATR, its extreme {r.ext:.2f}, first exit {r.exit1}")
        print(f"re-test so far: {len(R)} trades {R.r_real.sum():+.2f} R")
    print(f"week (B2 real + re-test): {np.nansum(wk.r_real):+.2f} R | 100: {wk.usdc_100.sum():+.2f} -> {A.balc_100.iloc[len(A[A.t < e]) - 1]:.2f} | "
          f"300: {wk.usdc_300.sum():+.2f} -> {A.balc_300.iloc[len(A[A.t < e]) - 1]:.2f}")
