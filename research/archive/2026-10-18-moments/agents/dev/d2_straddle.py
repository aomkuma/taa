"""Task D2: the data-minute straddle in the NY window - S2's shape (app/strategy/release_straddle.py) at every weekday's
08:30 and 10:00 New York minute, on the ticks, P1 / P2 (DEV_LOG.md "Task D - written before computing"): a buy stop
trig U above the last ask and a sell stop trig U below the last bid, live 60 s, the first hit; the stop stop_u U from
the fill; no target; out at the first tick at / after the minute + the hold. U = the reference bid / 4000.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/d2_straddle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p2_trades as P2  # noqa: E402
from sweep_detector import EXAM_START, ExamPeriodError, calendar_events, fixed_events  # noqa: E402

NS_S = 10**9
NS_MIN = 60 * NS_S
ARM_S = 30  # the reference tick may be at most 30 s before the minute (S2's arm_seconds)
LIVE_S = 60  # the stop orders live 60 s
UNIT_PRICE = 4000.0
GAP = 30 * NS_MIN
EXTRAS = (0.0, 0.5, 1.0, 2.0)
GRID = [(tr, st, hold) for tr in (1.5, 2.0, 3.0) for st in (6.0, 8.0, 10.0) for hold in (15, 30)]
CORE = [(2.0, 8.0, 15), (2.0, 8.0, 30)]


def reference(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int) -> tuple[float, float] | None:
    """The last tick before t0, no older than ARM_S seconds: (bid, ask); None otherwise."""
    k = int(np.searchsorted(t, t0, side="left")) - 1
    if k < 0 or t0 - t[k] > ARM_S * NS_S:
        return None
    return float(bid[k]), float(ask[k])


def triggered(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, up: float, dn: float) -> tuple[int, int] | None:
    """The first tick in [t0, t0 + LIVE_S) with ask >= up (a buy) or bid <= dn (a sell; the buy first on one tick):
    (tick index, side)."""
    a = int(np.searchsorted(t, t0, side="left"))
    b = int(np.searchsorted(t, t0 + LIVE_S * NS_S, side="left"))
    hit = np.nonzero((ask[a:b] >= up) | (bid[a:b] <= dn))[0]
    if not len(hit):
        return None
    j = a + int(hit[0])
    return j, (1 if ask[j] >= up else -1)


def exit_from(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, j: int, side: int, stop: float, t_limit: int) -> tuple[int, str]:
    """From the tick after the fill j: the stop at the first tick at / beyond it (a buy on the bid, a sell on the ask,
    gap included); 'time' at the first tick at / after t_limit; a gap in the ticks of more than 30 minutes (or the data's
    end) first: 'break' at the last tick before it. Returns (exit tick, reason)."""
    end = int(np.searchsorted(t, t_limit, side="left"))
    if end >= len(t):
        end, why_end = len(t) - 1, "break"
    else:
        why_end = "time"
    gaps = np.nonzero(np.diff(t[j:end + 1]) > GAP)[0]
    if len(gaps):
        end, why_end = j + int(gaps[0]), "break"
    mkt = bid if side > 0 else ask
    s = np.nonzero(side * (mkt[j + 1:end + 1] - stop) <= 0)[0]
    if len(s):
        return j + 1 + int(s[0]), "stop"
    return end, why_end


def straddle(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, trig_u: float, stop_u: float, hold: int,
             extra: float) -> dict | None:
    ref = reference(t, bid, ask, t0)
    if ref is None:
        return None
    bid0, ask0 = ref
    u = bid0 / UNIT_PRICE
    up, dn = ask0 + trig_u * u, bid0 - trig_u * u
    hit = triggered(t, bid, ask, t0, up, dn)
    if hit is None:
        return None
    j, side = hit
    entry = ask[j] + P2.SLIP + extra if side > 0 else bid[j] - P2.SLIP - extra
    stop = entry - side * stop_u * u
    x, why = exit_from(t, bid, ask, j, side, stop, int(t0 + hold * NS_MIN))
    px = float((bid if side > 0 else ask)[x])
    risk = stop_u * u
    pnl = side * (px - entry)
    return dict(side=side, up=up, dn=dn, unit=u, entry=float(entry), entry_t=int(t[j]), stop=float(stop), risk=float(risk),
                exit=why, exit_px=px, exit_t=int(t[x]), pnl=float(pnl), R=float(pnl / risk))


def run() -> pd.DataFrame:
    from m15_trades import part_of  # noqa: PLC0415

    ev = fixed_events()
    cal = calendar_events()
    names = dict(zip(pd.DatetimeIndex(cal.t).as_unit("ns").asi8, cal.names, strict=True))
    ticks = P2.Ticks()
    rows = []
    for r in ev.itertuples(index=False):
        t0 = int(pd.Timestamp(r.t).value)
        t, bid, ask = ticks.span(t0)
        for trig_u, stop_u, hold in GRID:
            for extra in EXTRAS:
                x = straddle(t, bid, ask, t0, trig_u, stop_u, hold, extra)
                if x is not None:
                    rows.append(dict(t0=t0, ny=r.ny, release=names.get(t0, ""), trig=trig_u, stop_u=stop_u, hold=hold,
                                     extra=extra, **x))
        if len(ticks.spans) > 2:
            ticks.days.clear()
            ticks.spans.clear()
    T = pd.DataFrame(rows)
    T["part"] = part_of(pd.to_datetime(T.t0, utc=True))
    if (T.exit_t >= EXAM_START.value).any():
        raise ExamPeriodError("a trade reached the exam")
    return T


def main() -> None:
    T = run()
    T.to_parquet(HERE / "d2_trades.parquet")
    print(f"trades {len(T)}; minutes with a trade (core, +0): {len(T[(T.trig == 2.0) & (T.stop_u == 8.0) & (T.hold == 30) & (T.extra == 0.0)])}")


if __name__ == "__main__":
    main()
