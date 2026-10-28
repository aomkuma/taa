"""No stop loss - would the account be wiped? (owner, 2026-10-19: "take the SL out, trade without a SL - I want to know
whether the account gets wiped"). The short trade's entries (pullback.py: the H1 / H4 trend, the M1 pullback, the fast
turn), one position at a time, 0.01 lot (1 USD a 1-USD move), no stop, no surrender, no time limit: out only when the
target 10 USD is reached (a swap-free account: nothing paid overnight). Every trade's deepest floating loss on the way
(the bid low for a buy, the ask high for a sell), and for starting balances the first trade whose floating loss reaches
the balance (the account gone - optimistic: a broker stops out before equity reaches 0).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/no_sl.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

TARGET, SLIP = 10.0, 0.07
BALANCES = (22.0, 50.0, 100.0, 500.0, 1000.0, 3000.0)


def hold(o, h, lo, sp, j: int, side: int, target: float = TARGET, chunk: int = 5000) -> dict:
    """In at bar j's open; out at the first bar reaching the target (a buy's bid high, a sell's ask low); the deepest
    floating loss from the entry to that bar (a buy: entry - the lowest bid low; a sell: the highest ask high - entry).
    exit -1 when the data ends first."""
    entry = o[j] + sp[j] + SLIP if side > 0 else o[j] - SLIP
    k = j
    worst = 0.0
    while k < len(o):
        e = min(k + chunk, len(o))
        fav = (h[k:e] - entry) if side > 0 else (entry - (lo[k:e] + sp[k:e]))
        adv = (entry - lo[k:e]) if side > 0 else ((h[k:e] + sp[k:e]) - entry)
        hit = np.nonzero(fav >= target)[0]
        if len(hit):
            x = k + int(hit[0])
            worst = max(worst, float(adv[: hit[0] + 1].max()))
            return dict(xj=x, mae=worst, pnl=target, entry=entry)
        worst = max(worst, float(adv.max()))
        k = e
    last = len(o) - 1
    return dict(xj=-1, mae=worst, pnl=float((lo[last] - entry) if side > 0 else (entry - h[last] - sp[last])), entry=entry)


def wiped(pnls: np.ndarray, maes: np.ndarray, balance: float) -> int:
    """The index of the first trade whose floating loss reaches the balance at its start (-1: never)."""
    bal = balance + np.r_[0.0, np.cumsum(pnls)[:-1]]
    gone = np.nonzero(maes >= bal)[0]
    return int(gone[0]) if len(gone) else -1


def main() -> None:
    import foundation as F  # noqa: PLC0415
    import plib  # noqa: PLC0415

    from indicators import at, bars  # noqa: PLC0415
    from pullback import signals, trend_at  # noqa: PLC0415

    m = plib.load()
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    done_ns = (m.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8
    trend = trend_at(m, done_ns)
    b5 = bars(m, "5min")
    a5 = F.atr(b5.high.to_numpy(), b5.low.to_numpy(), b5.close.to_numpy(), 14)
    k5 = at(pd.DatetimeIndex(b5["avail"]).as_unit("ns").asi8, done_ns)
    atr5 = np.where(k5 >= 0, a5[np.maximum(k5, 0)], np.nan)
    first = int(np.searchsorted(m.index, pd.Timestamp("2023-11-01", tz="UTC")))
    S = signals(h[first - 400:], lo[first - 400:], c[first - 400:], trend[first - 400:], atr5[first - 400:])
    S["i"] += first - 400
    S = S[S.i >= first].reset_index(drop=True)
    rows, busy = [], -1
    for r in S.itertuples():
        j = int(r.i) + 1
        if j <= busy or j >= len(o):
            continue
        x = hold(o, h, lo, sp, j, int(r.side))
        rows.append(dict(t=m.index[j], side=int(r.side), **x))
        if x["xj"] < 0:
            break  # still open at the data's end
        busy = x["xj"]
    T = pd.DataFrame(rows)
    T["exit_t"] = [m.index[x] if x >= 0 else pd.NaT for x in T.xj]
    T["hours"] = (T.exit_t - T.t).dt.total_seconds() / 3600
    T.to_parquet(HERE / "no_sl_trades.parquet")
    pd.set_option("display.width", 200)
    print(f"{len(T)} trades from {T.t.iloc[0]:%Y-%m-%d} to {T.t.iloc[-1]:%Y-%m-%d} (one at a time, out only at +10 USD); "
          f"{int((T.xj < 0).sum())} still open at the data's end")
    print("the deepest floating loss on the way (USD at 0.01 lot): median {:.1f}, 90 % {:.1f}, 99 % {:.1f}, the worst {:.1f}".format(
        *T.mae.quantile([0.5, 0.9, 0.99]).tolist(), T.mae.max()))
    for lim in (10, 22, 50, 100, 200, 500):
        print(f"  trades going {lim:>3} USD or more against first: {int((T.mae >= lim).sum())} ({(T.mae >= lim).mean():.1%})")
    print("the longest holds (hours):", T.hours.nlargest(5).round(1).tolist())
    print("\nthe 10 deepest:")
    W = T.nlargest(10, "mae")[["t", "side", "entry", "mae", "hours"]].copy()
    W["t"] = pd.DatetimeIndex(W.t).tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %H:%M Thai")
    print(W.round(2).to_string(index=False))
    print("\nstarting balances (0.01 lot): the first trade whose floating loss reaches the balance")
    pn, ma = T.pnl.to_numpy(), T.mae.to_numpy()
    for b in BALANCES:
        k = wiped(pn, ma, b)
        if k < 0:
            print(f"  {b:>6.0f} USD: never wiped; {len(T)} trades, +{pn.sum():.0f} USD at the end")
        else:
            print(f"  {b:>6.0f} USD: wiped on trade {k + 1} ({pd.Timestamp(T.t.iloc[k]).tz_convert('Asia/Bangkok'):%Y-%m-%d %H:%M} Thai), "
                  f"after +{pn[:k].sum():.0f} USD from {k} winners; that trade went {ma[k]:.0f} USD against")


if __name__ == "__main__":
    main()
