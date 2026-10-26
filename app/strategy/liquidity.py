"""The liquidity map: where the stops sit around price, where the volume traded and where a stop beyond the
structure goes (owner 2026-10-24: "find the liquidation zones; if there is no volume, pull more"; the
2026-07-08 14:05 replay sell put its stop ON the nearest tops pool, swept by 0.3 before a 48 USD fall).

FBS sends no real volume and no depth of market (TAA-L001, 2026-10-06): the volume here is the bars' tick
volume (how often the price changed). Pure functions on closed bars - the same in replays and live.

- pools: equal tops / bottoms (``picture.pools`` on M5 and M15), the M15 swing highs / lows of the trading
  day, the day's high / low, yesterday's D1 high / low, the Asia range (07:00-13:00 Thai) once London
  opened, and the round numbers - each with its distance and whether price has traded through it since it
  formed.
- volume nodes: the last 24 hours of M1 tick volume spread over each bar's range in ``bucket`` steps; the
  busiest steps are where positions were built, their stops sit beyond.
- the structure's top / bottom: the highest high / lowest low of the last ``STRUCTURE_M5`` closed M5 bars; a
  stop beyond the structure sits past it by ``BUFFER_ATR`` x the M5 ATR, and past any pool that lies within
  ``POOL_REACH_ATR`` x ATR beyond it. When price stands at that edge itself (within ``POOL_REACH_ATR`` x ATR -
  the move is still making the structure, 2026-07-08 18:44), the stop goes past the first untaken pool beyond
  the edge too. The busiest volume steps are bands the stop goes through, and pools chain: the stop goes
  past the whole liquidation zone, not into it (owner 2026-10-24).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.strategy import behaviors as bh
from app.strategy import picture as pc

TH = "Asia/Bangkok"
STRUCTURE_M5 = 24  # two hours of M5 bars: the pattern a trade is built on
STRUCTURE_MIN_M5 = 12  # fewer bars than this: no structure (an hour of M5)
# a stop sits this many M5 ATRs past the liquidation zone: 2025-04-18 .. 2026-04-17, 6,352 breaks of M5 swing
# levels - 79 % closed back within 30 min (fake, median 0.39 ATR past, 75 % within 0.86); once 1.0 ATR past,
# 56 % were real (1.5 ATR 69 %, 2.0 ATR 78 %): past 1 ATR the idea is more often wrong than swept
# (research/2026-10-24-replay/sweep_depth.py)
BUFFER_ATR = 1.0
EDGE_JUMP_ATR = 1.0  # at the edge: the next untaken pool is part of the zone only this close
ZONE_MAX_ATR = 2.0  # the liquidate zone ends at most this far past the structure (the buffer comes after)
POOL_REACH_ATR = 0.5  # a pool this close beyond the structure is taken with it: the stop goes past both
NEAR_ATR = 3.0  # pools within this many H1 ATRs of price are listed
ROUND_STEP = 50.0  # gold's round numbers (4,100 / 4,150)
BUCKET = 5.0  # volume-profile step in price units (5 USD on gold; 1 USD spread the volume too thin)


@dataclass(frozen=True)
class Pool:
    price: float
    kind: str
    taken: bool  # price traded through it after it formed


def atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> float:
    """The simple mean true range of the last ``n`` bars."""
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(np.abs(h - prev), np.abs(lo - prev)))
    return float(tr[-n:].mean())


def closed(df: pd.DataFrame, minutes: int, as_of: pd.Timestamp) -> pd.DataFrame:
    """The bars of a frame indexed by their open that have closed by ``as_of``."""
    return df[df.index + pd.Timedelta(minutes=minutes) <= as_of]


def taken_after(level: float, above: bool, h: np.ndarray, lo: np.ndarray, start: int) -> bool:
    """Has any bar from ``start`` on traded through ``level`` (above it for a level above price)?"""
    return bool((h[start:] > level).any()) if above else bool((lo[start:] < level).any())


def pools(
    m5: pd.DataFrame, m15: pd.DataFrame, d1: pd.DataFrame, as_of: pd.Timestamp, round_step: float = ROUND_STEP
) -> list[Pool]:
    """Every pool known at ``as_of`` (bars closed by it), unsorted."""
    out: list[Pool] = []
    for name, frame, minutes in (("M5", m5, 5), ("M15", m15, 15)):
        x = closed(frame, minutes, as_of).iloc[-300:]
        if len(x) < 20:
            continue
        h, lo, c = (x[k].to_numpy(float) for k in ("high", "low", "close"))
        a = atr(h, lo, c)
        for p in pc.pools(h, lo, c, a):
            above = p["name"] == "tops"
            last = p["touches"][-1][0]
            n = len(p["touches"])
            out.append(
                Pool(
                    p["level"],
                    f"{name} equal {p['name']} x{n}",
                    taken_after(p["level"], above, h, lo, last + 1),
                )
            )
    day = closed(m15, 15, as_of)
    day = day[day.index >= bh.day_start(as_of)]
    if len(day):
        h, lo = day.high.to_numpy(float), day.low.to_numpy(float)
        t = [i.tz_convert(TH).strftime("%H:%M") for i in day.index]
        for i in range(1, len(day) - 1):
            # a swing needs the bar after it, so "taken" counts from two bars on
            if h[i] > h[i - 1] and h[i] > h[i + 1]:
                out.append(Pool(float(h[i]), f"M15 swing high {t[i]}", taken_after(h[i], True, h, lo, i + 2)))
            if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]:
                out.append(
                    Pool(float(lo[i]), f"M15 swing low {t[i]}", taken_after(lo[i], False, h, lo, i + 2))
                )
        out.append(Pool(float(h.max()), "the day's high", False))
        out.append(Pool(float(lo.min()), "the day's low", False))
        th = pd.DatetimeIndex(day.index).tz_convert(TH)
        start = as_of.tz_convert(TH).normalize()
        asia = (th >= start + pd.Timedelta(hours=7)) & (th < start + pd.Timedelta(hours=13))
        if as_of.tz_convert(TH) >= start + pd.Timedelta(hours=13) and asia.any():
            after = (
                int(np.argmax(~asia & (th >= start + pd.Timedelta(hours=13)))) if (~asia).any() else len(day)
            )
            ah, al = float(h[asia].max()), float(lo[asia].min())
            out.append(Pool(ah, "the Asia high", taken_after(ah, True, h, lo, after)))
            out.append(Pool(al, "the Asia low", taken_after(al, False, h, lo, after)))
    y = d1[d1.index + pd.Timedelta(days=1) <= as_of]
    if len(y):
        out.append(Pool(float(y.high.iloc[-1]), "yesterday's high", False))
        out.append(Pool(float(y.low.iloc[-1]), "yesterday's low", False))
    return out


def rounds(price: float, step: float = ROUND_STEP) -> list[Pool]:
    """The round numbers just below and above ``price``."""
    lo = np.floor(price / step) * step
    return [Pool(float(lo), "round number", False), Pool(float(lo + step), "round number", False)]


def volume_nodes(
    m1: pd.DataFrame, as_of: pd.Timestamp, bucket: float = BUCKET, top: int = 3
) -> list[tuple[float, float]]:
    """The busiest price steps of the last 24 hours: each M1 bar's tick volume spread evenly over the steps
    its range covers; (the step's low, its share of the volume), busiest first."""
    x = closed(m1, 1, as_of)
    x = x[x.index >= as_of - pd.Timedelta(hours=24)]
    if not len(x):
        return []
    vol: dict[float, float] = {}
    for lo, hi, v in zip(
        x.low.to_numpy(float), x.high.to_numpy(float), x.tick_volume.to_numpy(float), strict=True
    ):
        steps = np.arange(np.floor(lo / bucket), np.floor(hi / bucket) + 1) * bucket
        for s in steps:
            vol[float(s)] = vol.get(float(s), 0.0) + v / len(steps)
    total = sum(vol.values())
    best = sorted(vol.items(), key=lambda kv: -kv[1])[:top]
    return [(round(s, 2), v / total) for s, v in best]


@dataclass(frozen=True)
class Structure:
    top: float
    bottom: float
    atr_m5: float
    sell_stop: float  # past the top (and a pool just beyond it)
    buy_stop: float
    sell_zone: float = 0.0  # the far end of the liquidate zone the sell's stop passes (before the buffer)
    buy_zone: float = 0.0


def beyond_zone(
    edge: float,
    price: float,
    pools: list[Pool],
    a: float,
    up: bool,
    bands: Sequence[tuple[float, float]] = (),
) -> tuple[float, float]:
    """(the stop, the far end of the liquidate zone it passes). The zone starts at ``edge`` (up: above it):
    when price stands at the edge, the next untaken pool beyond counts if it lies within EDGE_JUMP_ATR (07-08
    18:44: 0.53 ATR away, the stop was run there); then, step by step, every untaken pool within reach of the
    zone so
    far and every volume band (low, high) that starts within reach or holds it; the zone ends at most
    ZONE_MAX_ATR past the edge (07-08 07:25: an unbounded chain put a 4,105.84 sell's stop at 4,154.41, 9 ATR
    out); then the buffer. A taken pool has had its stops run: it does not count."""
    sign, reach = (1.0 if up else -1.0), POOL_REACH_ATR * a
    live = sorted((p.price for p in pools if not p.taken), key=lambda x: (x - edge) * sign)
    far = edge
    if abs(edge - price) <= reach:
        nxt = next((x for x in live if (x - edge) * sign > 0), None)
        if nxt is not None and (nxt - edge) * sign <= EDGE_JUMP_ATR * a:
            far = nxt
    moved = True
    while moved:
        moved = False
        for x in live:
            if 0 < (x - far) * sign <= reach:
                far, moved = x, True
        for lo, hi in bands:
            near, end = (lo, hi) if up else (hi, lo)
            if (near - far) * sign <= reach and (end - far) * sign > 0:
                far, moved = end, True
    limit = edge + sign * ZONE_MAX_ATR * a
    if (far - limit) * sign > 0:
        far = limit
    return round(far + sign * BUFFER_ATR * a, 2), round(far, 2)


def beyond(
    edge: float,
    price: float,
    pools: list[Pool],
    a: float,
    up: bool,
    bands: Sequence[tuple[float, float]] = (),
) -> float:
    """The stop past ``edge`` and past the liquidate zone beyond it (:func:`beyond_zone`)."""
    return beyond_zone(edge, price, pools, a, up, bands)[0]


def structure(
    m5: pd.DataFrame,
    as_of: pd.Timestamp,
    price: float,
    near: list[Pool],
    bands: Sequence[tuple[float, float]] = (),
    forming: tuple[float, float] | None = None,
) -> Structure | None:
    """The structure of the last two hours of M5 bars and the stops beyond it; ``forming`` (high, low): the
    closed M1 bars of the M5 bar not closed yet, part of the structure (07-07 19:09: price had broken over the
    2-hour top inside the forming bar and a sell's 'stop past the top' sat under its entry)."""
    x = closed(m5, 5, as_of)
    if len(x) < STRUCTURE_MIN_M5:  # Monday 07:00 Thai: 23 bars since the open - one hour is enough to read
        return None
    h, lo, c = (x[k].to_numpy(float) for k in ("high", "low", "close"))
    a = atr(h, lo, c)
    top, bottom = float(h[-STRUCTURE_M5:].max()), float(lo[-STRUCTURE_M5:].min())
    if forming is not None:
        top, bottom = max(top, forming[0]), min(bottom, forming[1])
    (sell, sell_zone), (buy, buy_zone) = (
        beyond_zone(top, price, near, a, True, bands),
        beyond_zone(bottom, price, near, a, False, bands),
    )
    return Structure(top, bottom, a, sell, buy, sell_zone, buy_zone)


def forming(m1: pd.DataFrame, m5: pd.DataFrame, as_of: pd.Timestamp) -> tuple[float, float] | None:
    """(high, low) of the closed M1 bars after the last closed M5 bar (the M5 bar still forming), or None."""
    x5 = closed(m5, 5, as_of)
    if not len(x5):
        return None
    x1 = closed(m1, 1, as_of)
    tail = x1[x1.index >= x5.index[-1] + pd.Timedelta(minutes=5)]
    return (float(tail.high.max()), float(tail.low.min())) if len(tail) else None


def structure_now(
    m1: pd.DataFrame,
    m5: pd.DataFrame,
    m15: pd.DataFrame,
    d1: pd.DataFrame,
    h1: pd.DataFrame,
    as_of: pd.Timestamp,
) -> Structure | None:
    """The structure and the stops beyond the liquidation zone at ``as_of`` (the map's last line)."""
    x1, xh = closed(m1, 1, as_of), closed(h1, 60, as_of)
    if not len(x1) or len(xh) < 15:
        return None
    price = float(x1.close.iloc[-1])
    reach = NEAR_ATR * atr(xh.high.to_numpy(float), xh.low.to_numpy(float), xh.close.to_numpy(float))
    near = [p for p in pools(m5, m15, d1, as_of) + rounds(price) if abs(p.price - price) <= reach]
    bands = [(s, s + BUCKET) for s, _ in volume_nodes(m1, as_of)]
    return structure(m5, as_of, price, near, bands, forming(m1, m5, as_of))


def liquidity_lines(
    m1: pd.DataFrame,
    m5: pd.DataFrame,
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    d1: pd.DataFrame,
    as_of: pd.Timestamp,
) -> list[str]:
    """The map as the AI reads it: the pools above and below price (nearest first), the volume nodes and the
    stops beyond the structure."""
    x1 = closed(m1, 1, as_of)
    xh = closed(h1, 60, as_of)
    if not len(x1) or len(xh) < 15:
        return ["(not enough bars for the liquidity map)"]
    price = float(x1.close.iloc[-1])
    reach = NEAR_ATR * atr(xh.high.to_numpy(float), xh.low.to_numpy(float), xh.close.to_numpy(float))
    every = pools(m5, m15, d1, as_of) + rounds(price)
    near = sorted(
        {(round(p.price, 2), p.kind): p for p in every if abs(p.price - price) <= reach}.values(),
        key=lambda p: abs(p.price - price),
    )

    def row(p: Pool) -> str:
        return f"{p.price:.2f} {p.kind}{' (taken)' if p.taken else ''} {p.price - price:+.2f}"

    above = [row(p) for p in near if p.price > price][:6]
    below = [row(p) for p in near if p.price <= price][:6]
    # the liquidate zones by the side whose STOP they concern - never take-profit points (owner 2026-10-25)
    none = "none within 3 H1 ATR"
    out = [
        f"price {price:.2f}",
        "above (a SELL's stop side, not targets): " + (" | ".join(above) or none),
        "below (a BUY's stop side, not targets): " + (" | ".join(below) or none),
    ]
    nodes = volume_nodes(m1, as_of)
    if nodes:
        out.append(
            "volume nodes (24 h, tick volume by price): "
            + ", ".join(f"{s:.0f}-{s + BUCKET:.0f} {share:.0%}" for s, share in nodes)
        )
    st = structure(m5, as_of, price, near, [(s, s + BUCKET) for s, _ in nodes], forming(m1, m5, as_of))
    if st is not None:
        out.append(
            f"the structure (2 h of M5): top {st.top:.2f}, bottom {st.bottom:.2f}; a SELL's stop beyond it "
            f"{st.sell_stop:.2f}, a BUY's stop beyond it {st.buy_stop:.2f} (M5 ATR {st.atr_m5:.2f})"
        )
        out.append(  # 07-08 14:08: the zone the stop passes was not among the 6 nearest levels listed
            f"the liquidate zones those stops pass: above {st.top:.2f} up to {st.sell_zone:.2f}, below "
            f"{st.bottom:.2f} down to {st.buy_zone:.2f}, then {BUFFER_ATR:g} M5 ATR"
        )
    return out
