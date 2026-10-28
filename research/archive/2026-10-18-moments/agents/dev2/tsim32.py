"""V3-2's tick simulator (rules R0 / R7 in DEV_LOG.md): one trade on the real bid / ask ticks.

- The fill: the first tick at / after t_in (none within 5 minutes: no trade). A buy at the ask + slip, a sell at the
  bid - slip (slip defaults to 0: the costs are the tick spread only, the owner 2026-10-20).
- The stop: a price, or a distance from the fill (`stop_dist`), or `mirror_of` = the price of the same-side rule's stop (the other side), whose distance from the
  same-side fill is applied from this side's fill. A fill already past the stop: no trade.
- The target: a fixed multiple of the risk (`target_r`), or the nearest candidate in `cands` at least `k_r` x the risk
  from the fill (none -> `default_r` x the risk, or no target when `default_r` is None).
- The trail: (time ns, level) steps; from the first tick at / after the time the stop is the tighter of the two.
- Tick by tick after the fill: the stop (a market exit at the tick's bid for a buy / ask for a sell, its gap
  included), then the target (a limit, filled at its price); one tick reaching both is a stop. The time: the first tick
  at / after t_out (a market exit). A gap of more than 30 minutes: out at the last tick before it ("break"). The ticks
  ending first: out at the last tick ("end").
- R = pnl / the initial risk.

The ticks: `Ticks.span(t_ns)` = the UTC day's file joined to the next day's; a day from 2026-04-18 on (the exam) is
refused, never read.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TICKS = Path(__file__).resolve().parents[4] / "data" / "ticks" / "XAUUSD"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
NS_MIN = 60_000_000_000
GAP_NS = 30 * NS_MIN
MAX_LAG_NS = 5 * NS_MIN
AFTER_NS = 60 * NS_MIN
EPS = 1e-9  # a level computed in floating point (fill + 2 x risk) still counts as reached at its own price  # "ran later": the hour after the exit


def day_ticks(day: pd.Timestamp):
    d = pd.Timestamp(day)
    d = (d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")).normalize()
    if d >= EXAM_START:
        raise RuntimeError(f"{d:%Y-%m-%d} is in the exam period: refused")
    f = TICKS / f"{d:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f, columns=["time_utc", "bid", "ask"])
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


class Ticks:
    """Day + next-day spans, cached (a few days kept). A next day in the exam period is not joined."""

    def __init__(self) -> None:
        self.days: dict = {}
        self.spans: dict = {}

    def _day(self, d: pd.Timestamp):
        if d not in self.days:
            self.days[d] = day_ticks(d) if d < EXAM_START else None
            for k in list(self.days)[:-4]:  # the oldest loaded first (insertion order); d is the newest
                del self.days[k]
        return self.days[d]

    def span(self, t_ns: int):
        d = pd.Timestamp(int(t_ns), tz="UTC").normalize()
        if d not in self.spans:
            a = self._day(d)
            b = self._day(d + pd.Timedelta(days=1)) if a is not None else None
            self.spans[d] = a if b is None else tuple(np.concatenate([x, y]) for x, y in zip(a, b))
            for k in list(self.spans)[:-2]:
                del self.spans[k]
        return self.spans[d]


def pick_target(fill: float, side: int, risk: float, cands, k_r: float, default_r: float | None) -> float:
    """The nearest candidate on the trade's side at least k_r x risk from the fill; none -> default_r x risk (NaN when
    default_r is None)."""
    c = np.asarray([x for x in cands if np.isfinite(x)], float)
    d = side * (c - fill)
    ok = d >= k_r * risk - 1e-9
    if ok.any():
        return float(fill + side * d[ok].min())
    return float(fill + side * default_r * risk) if default_r is not None else np.nan


def sim(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t_in: int, side: int, t_out: int, stop: float = np.nan,
        mirror_of: float = np.nan, stop_dist: float = np.nan, target_r: float = np.nan, cands=(), k_r: float = np.nan,
        default_r: float | None = None, trail=(), slip: float = 0.0) -> dict | None:
    f = int(np.searchsorted(t, t_in, side="left"))
    if f >= len(t) or t[f] - t_in > MAX_LAG_NS:
        return None
    fill = ask[f] + slip if side > 0 else bid[f] - slip
    if np.isfinite(mirror_of):
        same = bid[f] - slip if side > 0 else ask[f] + slip  # the other side's fill on the same tick
        stop = fill - side * abs(same - mirror_of)
    elif np.isfinite(stop_dist):
        stop = fill - side * stop_dist
    risk = side * (fill - stop)
    if not risk > 0:
        return None
    if np.isfinite(target_r):
        tgt = fill + side * target_r * risk
    elif np.isfinite(k_r):
        tgt = pick_target(fill, side, risk, cands, k_r, default_r)
    else:
        tgt = np.nan
    end = int(np.searchsorted(t, t_out, side="left"))
    kind_end = "time"
    if end >= len(t):
        end, kind_end = len(t) - 1, "end"
    gaps = np.nonzero(np.diff(t[f:end + 1]) > GAP_NS)[0]
    if len(gaps):
        end, kind_end = f + int(gaps[0]), "break"
    if end <= f:
        return None
    sl = slice(f + 1, end + 1)
    tt = t[sl]
    mkt = bid[sl] if side > 0 else ask[sl]  # where a market exit fills
    stop_arr = np.full(len(tt), stop)
    for ts, lvl in sorted(trail):
        k = int(np.searchsorted(tt, ts, side="left"))
        if k < len(tt):
            stop_arr[k:] = np.maximum(stop_arr[k:], lvl) if side > 0 else np.minimum(stop_arr[k:], lvl)
    hit_s = (mkt <= stop_arr + EPS) if side > 0 else (mkt >= stop_arr - EPS)  # EPS: a price equal to the level
    hit_t = ((mkt >= tgt - EPS) if side > 0 else (mkt <= tgt + EPS)) if np.isfinite(tgt) else np.zeros(len(tt), bool)
    i_s = int(np.argmax(hit_s)) if hit_s.any() else len(tt)
    i_t = int(np.argmax(hit_t)) if hit_t.any() else len(tt)
    if i_s < len(tt) and i_s <= i_t:
        i, why, px = i_s, "stop", mkt[i_s]
    elif i_t < len(tt):
        i, why, px = i_t, "target", tgt
    else:
        i, why, px = len(tt) - 1, kind_end, mkt[-1]
    pnl = float(side * (px - fill))
    fav = side * (mkt[: i + 1] - fill)
    # after the exit: the best excursion from the fill in the next hour (the "ran later" reason), same span only
    a = int(np.searchsorted(t, tt[i], side="right"))
    b = int(np.searchsorted(t, tt[i] + AFTER_NS, side="right"))
    after = float((side * ((bid[a:b] if side > 0 else ask[a:b]) - fill)).max()) if b > a else np.nan
    return dict(t_fill=int(t[f]), fill=float(fill), stop0=float(stop), target=float(tgt), risk=float(risk),
                exit=why, exit_t=int(tt[i]), exit_px=float(px), pnl=pnl, R=pnl / risk,
                mfe=float(fav.max()), mae=float(fav.min()), after_best=after, stop_last=float(stop_arr[i]))
