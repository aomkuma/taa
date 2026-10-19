"""Trade short, turn early, keep the big trend - part 1 (notes.md, written before it is computed; owner, 2026-10-19:
"use the short way - find a fast reversal signal, trade the small timeframe, but do not drop the big trend, so the
trade can be held far"). At every M1 close: the big trend (H1 swing structure, H4 not against), a pullback against
it on M1, the fast turn back (a close beyond the 3 bars before); in at the next open, the stop beyond the pullback's
extreme, the surrender, the target 3 R0, out after 4 hours; one position at a time; on M1 the stop first.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/pullback.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

HIGH_BARS, LOW_BARS, TURN_BARS = 30, 10, 3
DEPTH_ATR, BUFFER, R_MIN, R_MAX = 1.0, 0.3, 2.0, 8.0
SURRENDER_MIN, TARGET_R, HOLD_MIN, SLIP = 5, 3.0, 240, 0.07


def trend_at(m: pd.DataFrame, t_ns: np.ndarray) -> np.ndarray:
    """The big trend at each time (bars complete by it): +1 when the H1 swing structure is up and H4's is not down,
    -1 the mirror, 0 otherwise (picture.struct_brk on the 3-ATR ZigZag of each timeframe's last 120 bars)."""
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415
    from picture import WIN, struct_brk  # noqa: PLC0415

    from indicators import at, bars  # noqa: PLC0415

    out = {}
    for tf, rule in (("H1", "1h"), ("H4", "4h")):
        b = bars(m, rule)
        R = raw(b.rename(columns={}))
        piv = zigzag(R["h"], R["lo"], R["atr"], ZZ_K)
        st = np.array([struct_brk(R["h"], R["lo"], float(R["c"][i]), piv, i, max(i - WIN + 1, 0))[0] for i in range(len(b))])
        bi = at(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, t_ns)
        out[tf] = np.where(bi >= 0, st[np.maximum(bi, 0)], 9)
    h1, h4 = out["H1"], out["H4"]
    return np.where((h1 == 1) & (h4 != -1), 1, np.where((h1 == -1) & (h4 != 1), -1, 0))


def signals(h: np.ndarray, lo: np.ndarray, c: np.ndarray, trend: np.ndarray, atr5: np.ndarray) -> pd.DataFrame:
    """At each M1 bar i (its close): a buy when the trend is up, the highest high of bars i-29 .. i came before the
    lowest low of bars i-9 .. i, that drop is >= DEPTH_ATR x the M5 ATR, and c[i] > max(h[i-3 .. i-1]); the sell mirrored.
    Returns i, side and the pullback's extreme (the low for a buy)."""
    n = len(c)
    rows = []
    for i in range(HIGH_BARS, n):
        tr = trend[i]
        if tr == 0 or not np.isfinite(atr5[i]):
            continue
        if tr > 0:
            w_hi = h[i - HIGH_BARS + 1:i + 1]
            w_lo = lo[i - LOW_BARS + 1:i + 1]
            k_hi = i - HIGH_BARS + 1 + int(np.argmax(w_hi))
            k_lo = i - LOW_BARS + 1 + int(np.argmin(w_lo))
            if k_lo > k_hi and (w_hi.max() - w_lo.min()) >= DEPTH_ATR * atr5[i] and c[i] > h[i - TURN_BARS:i].max():
                rows.append((i, 1, float(w_lo.min())))
        else:
            w_lo = lo[i - HIGH_BARS + 1:i + 1]
            w_hi = h[i - LOW_BARS + 1:i + 1]
            k_lo = i - HIGH_BARS + 1 + int(np.argmin(w_lo))
            k_hi = i - LOW_BARS + 1 + int(np.argmax(w_hi))
            if k_hi > k_lo and (w_hi.max() - w_lo.min()) >= DEPTH_ATR * atr5[i] and c[i] < lo[i - TURN_BARS:i].min():
                rows.append((i, -1, float(w_hi.max())))
    return pd.DataFrame(rows, columns=["i", "side", "extreme"])


def manage(o, h, lo, c, sp, ny, j: int, side: int, extreme: float, target_r: float = TARGET_R,
           surrender_min: int = SURRENDER_MIN, hold_min: int = HOLD_MIN) -> dict | None:
    """In at the open of bar j; the stop BUFFER beyond the pullback's extreme (None when the risk is outside R_MIN ..
    R_MAX); per bar: the stop first (a buy's on the bid low, a sell's on the ask high), then the target; at the close of
    bar j + surrender_min - 1, out unless it has gone +1 R0 at some point; out at the close after hold_min bars."""
    entry = o[j] + sp[j] + SLIP if side > 0 else o[j] - SLIP
    stop = extreme - BUFFER if side > 0 else extreme + BUFFER
    r0 = (entry - stop) * side
    if not (R_MIN <= r0 <= R_MAX):
        return None
    ss = 0.20 if ny[j] else 0.15
    best = -np.inf
    last = min(j + hold_min, len(o)) - 1
    for x in range(j, last + 1):
        adv = lo[x] if side > 0 else h[x] + sp[x]
        fav = h[x] if side > 0 else lo[x] + sp[x]
        if (adv - stop) * side <= 0:
            return dict(exit="stop", pnl=(stop - entry) * side - ss, xj=x, r0=r0)
        if (fav - entry) * side >= target_r * r0:
            return dict(exit="win", pnl=target_r * r0, xj=x, r0=r0)
        best = max(best, (fav - entry) * side)
        if x == j + surrender_min - 1 and best < r0:
            px = c[x] - SLIP if side > 0 else c[x] + sp[x] + SLIP
            return dict(exit="surrender", pnl=(px - entry) * side, xj=x, r0=r0)
    px = c[last] - SLIP if side > 0 else c[last] + sp[last] + SLIP
    return dict(exit="time", pnl=(px - entry) * side, xj=last, r0=r0)


def main() -> None:
    import foundation as F  # noqa: PLC0415
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415

    from indicators import at, bars  # noqa: PLC0415
    from m15_trades import PARTS  # noqa: PLC0415

    m = plib.load()
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    ny = plib.ny_mask(m.index)
    done_ns = (m.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8  # each M1 bar's close
    trend = trend_at(m, done_ns)
    b5 = bars(m, "5min")
    a5 = F.atr(b5.high.to_numpy(), b5.low.to_numpy(), b5.close.to_numpy(), 14)
    k5 = at(pd.DatetimeIndex(b5["avail"]).as_unit("ns").asi8, done_ns)
    atr5 = np.where(k5 >= 0, a5[np.maximum(k5, 0)], np.nan)
    first = int(np.searchsorted(m.index, pd.Timestamp(PARTS["P1"][0], tz="UTC")))
    last = int(np.searchsorted(m.index, pd.Timestamp(PARTS["P2"][1], tz="UTC")))
    S = signals(h[first - 400:last], lo[first - 400:last], c[first - 400:last], trend[first - 400:last], atr5[first - 400:last])
    S["i"] += first - 400
    S = S[S.i >= first].reset_index(drop=True)
    rows, busy = [], -1
    for r in S.itertuples():
        j = int(r.i) + 1
        if j <= busy or j >= len(o):
            continue
        x = manage(o, h, lo, c, sp, ny, j, int(r.side), float(r.extreme))
        if x is None:
            continue
        rows.append(dict(t=m.index[j], side=int(r.side), R=x["pnl"] / x["r0"], **x))
        busy = x["xj"]
    T = pd.DataFrame(rows)
    T["part"] = np.where(T.t < pd.Timestamp(PARTS["P2"][0], tz="UTC"), "P1", "P2")
    print(f"signals {len(S)}; trades {len(T)}")
    for p in ("P1", "P2"):
        D = T[T.part == p]
        eq = D.pnl.cumsum()
        print(f"{p}: {len(D)} trades ({len(D) / np.busday_count(*PARTS[p]):.2f} a weekday), win {(D.exit == 'win').mean():.3f}, R {D.R.mean():+.3f}, "
              f"USD {D.pnl.sum():+.1f}, risk median {D.r0.median():.2f} USD, max DD {(eq.cummax() - eq).max():.1f}, streak "
              f"{wf.longest_run(D.pnl.to_numpy() < 0)}, exits {D.exit.value_counts().to_dict()}, buys {int((D.side > 0).sum())} / sells {int((D.side < 0).sum())}")
    T.to_parquet(HERE / "pullback_trades.parquet")


if __name__ == "__main__":
    main()
