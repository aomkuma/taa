"""Bot 2e: the owner's setup (eye/METHOD.md section 2e) as a bot, written to eye/BOT_SPEC.md.

It walks real trading days bar by bar on the stored gold data, as ``eye/walk.py`` does by hand. At every
closed M5 bar inside the owner's windows it applies the seven steps of 2e; when steps 1-4 hold it writes a
stop-limit (or limit) order with its stop and target into ``eye/bot_ledger.csv``, which ``eye/score.py``
scores and ``eye/money.py --ledger bot_ledger.csv`` reads in money.

    python eye/bot2e.py --from 2026-04-06 --to 2026-04-07
    python eye/bot2e.py --from 2026-04-06 --to 2026-04-07 --h1-mode lows --min-r 1

**No look-ahead is structural.** ``decide`` takes frames that are already cut to the bars closed at ``now``
(``cut`` does the cutting, and ``decide`` refuses a frame that holds a later bar); the ZigZag is run on that
cut, and only its fixed pivots are used - never the point MT5 still moves.

Every definition the owner did not give is a field of ``Params``, marked ``[Claude]`` there, with the
spec's default, and its value is written into every decision's ``structure`` text.

A BUY and a SELL share one code path: a SELL is the BUY seen in a mirror (prices negated, highs and lows
swapped), so the two cannot drift apart. Names ending ``_v`` are in the view (a SELL's are negated).
"""

from __future__ import annotations

import argparse
import csv
import importlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from app.indicators.chart_read import zigzag_pivots  # noqa: E402
from app.indicators.momentum import rsi  # noqa: E402
from app.indicators.price_action import Swing, SwingKind  # noqa: E402
from eye.score import SPREAD, score, start_of  # noqa: E402

walk: Any = importlib.import_module("eye.walk")  # the by-hand walker; reused so both read the same bars
POINT: float = walk.POINT
SHOWN: dict[str, int] = walk.SHOWN
STEP: dict[str, pd.Timedelta] = walk.STEP
WARMUP: int = walk.WARMUP
ZIGZAG: dict[str, int] = walk.ZIGZAG
frame = walk.frame
macd_mt5 = walk.macd_mt5

TH = "Asia/Bangkok"
READER = "bot2e"
LEDGER_PATH = HERE / "bot_ledger.csv"
LOG_PATH = HERE / "bot_log.csv"
LEDGER_COLUMNS = [
    "id", "cutoff_thai", "decided_at", "reader", "side", "entry", "stop", "target", "fill", "exit", "why",
    "r_net", "structure", "rules", "conflict", "at_decision_r", "missed_by", "trigger", "setup",
]  # fmt: skip
LOG_COLUMNS = [
    "date", "time_thai", "window", "price", "h1_mode", "side", "band", "tf", "count", "pivots", "div_macd",
    "div_rsi", "kind", "step3", "step4", "step5", "reason",
]  # fmt: skip

# The owner's windows (METHOD 2c), Thai time, in minutes after midnight. A decision is written at an M5
# close ``now`` with start < now <= end (the bar that closes at the start belongs to the time before).
WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("Asia", 7 * 60, 9 * 60),
    ("London", 13 * 60, 15 * 60),
    ("New York", 19 * 60 + 30, 23 * 60),
)
TIMEFRAMES = ("M5", "M15")  # the owner: "M5-M15"; M5 first
FRAME_BARS = {tf: SHOWN[tf] + WARMUP for tf in ("H1", "M15", "M5")}  # what walk.py computes on, per frame


@dataclass(frozen=True)
class Params:
    """Every parameter the owner did not give. ``[Claude]`` marks a definition made by Claude."""

    h1_mode: str = "strict"  # [Claude] how the H1 trend is read: "strict" or "lows" (spec step 1)
    level_min_age_h: float = 24.0  # [Claude] a level's pivot is at least this many hours old ("earlier days")
    level_bars: int = 500  # [Claude] levels come from the last this-many H1 bars
    band_frac: float = 0.10  # [Claude] half-width of a level band = this x median height of 20 H1 legs
    band_legs: int = 20  # [Claude] how many H1 ZigZag legs the median height is taken over
    counter_pivots: int = 20  # [Claude] the zone's lows are looked for among the last this-many fixed pivots
    count_min: int = 3  # the owner: "3 to 5 peaks"
    count_max: int = 5
    trigger_offset: float = 0.50  # [Claude] "a little over" the broken level, USD
    stop_buffer: float = 0.50  # [Claude] stop beyond the extreme / band edge, USD
    target_buffer: float = 0.50  # [Claude] target before the opposite band's edge, USD
    min_r: float = 2.0  # the owner's floor (R9): "the profit has to be 1:2"; no decision under it
    spread: float = (
        SPREAD  # the owner's real spread on gold, USD (the R written into a decision is net of it)
    )

    def text(self) -> str:
        """The [Claude] parameters as they are written into a decision."""
        return (
            f"h1_mode={self.h1_mode} level_min_age_h={self.level_min_age_h:g} level_bars={self.level_bars} "
            f"band_frac={self.band_frac:g} band_legs={self.band_legs} counter_pivots={self.counter_pivots} "
            f"trigger_offset={self.trigger_offset:g} stop_buffer={self.stop_buffer:g} "
            f"target_buffer={self.target_buffer:g} min_r={self.min_r:g}"
        )


# The reasons a bar can end without an order, in the order the steps run; a later one means the bar got
# further. ``reason`` in the log is always one of these, or "order written".
REASONS = [
    "market closed", "outside window", "warm-up", "order pending", "step1: no side", "step2: no levels",
    "step2: no counter-move", "step2: L* not in a support band", "step2: count outside 3-5 and no M",
    "step2: no divergence on both", "step3: structure not broken", "step3: no higher low yet",
    "step4: no H_d", "step5: price below the higher low", "step7: no target level",
    "reward under 2R", "setup already played out", "setup already used", "order written",
]  # fmt: skip
RANK = {r: i for i, r in enumerate(REASONS)}


@dataclass(frozen=True)
class VPivot:
    """A fixed pivot in the view: ``low`` is true for a low of the view (a SELL's highs are its lows)."""

    low: bool
    price: float
    pos: int


@dataclass
class Setup:
    """What steps 2-7 found, in the view."""

    tf: str
    lstar: VPivot
    lhl: VPivot
    hd: VPivot
    band: tuple[float, float]
    counted: list[VPivot]
    kind: str  # "count" or "M"
    div_macd: bool
    div_rsi: bool
    entry_v: float
    trigger_v: float | None
    stop_v: float
    target_v: float
    r: float


@dataclass
class Outcome:
    """One timeframe's pass through the steps: where it stopped, what it saw, and any setup it found."""

    tf: str
    reason: str
    info: dict[str, str] = field(default_factory=dict)
    setup: Setup | None = None


@dataclass
class Result:
    """What ``decide`` returns: the log row for this ``now`` and the decision row, if one was written."""

    log: dict[str, str]
    decision: dict[str, str] | None = None
    key: str = ""  # the written setup's identity, so the same setup is not written twice


# --- cutting and windows ------------------------------------------------------------------------------


def cut(full: dict[str, pd.DataFrame], now: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """The closed bars at ``now``: a bar exists if ``open_time + tf <= now`` (the closed-bar cut of walk.py).
    Only the tail each computation needs is kept."""
    out: dict[str, pd.DataFrame] = {}
    for tf, df in full.items():
        ends = df.index + STEP[tf]
        k = int(ends.searchsorted(now, side="right"))
        out[tf] = df.iloc[max(0, k - FRAME_BARS[tf]) : k]
    return out


def window_of(now: pd.Timestamp) -> str:
    """The owner's window ``now`` falls in (an M5 close, Thai time), or an empty string."""
    # R7: a window opens at its start, start <= now <= end (the close at 07:00 is the first look).
    t = now.tz_convert(TH)
    minute = t.hour * 60 + t.minute
    return next((name for name, a, b in WINDOWS if a <= minute <= b), "")


# --- step 1: the side -----------------------------------------------------------------------------------


def h1_side(pivots: Sequence[Swing], price: float, mode: str) -> str | None:
    """ "BUY" / "SELL" from the H1 fixed pivots, or None (spec step 1). ``strict``: both the last high and the
    last low above (below) the ones before them. ``lows``: the last low above the one before and price above
    that low (up); the last high under the one before and price under it (down); both or neither = None."""
    highs = [p.price for p in pivots if p.kind is SwingKind.HIGH]
    lows = [p.price for p in pivots if p.kind is SwingKind.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return None
    if mode == "strict":
        up = highs[-1] > highs[-2] and lows[-1] > lows[-2]
        down = highs[-1] < highs[-2] and lows[-1] < lows[-2]
    elif mode == "lows":
        up = lows[-1] > lows[-2] and price > lows[-1]
        down = highs[-1] < highs[-2] and price < highs[-1]
    else:
        raise ValueError(f"h1_mode must be 'strict' or 'lows', got {mode!r}")
    if up == down:  # both or neither
        return None
    return "BUY" if up else "SELL"


# --- step 2a: the levels from the left --------------------------------------------------------------------


def level_bands(prices: Sequence[float], half_width: float) -> list[tuple[float, float]]:
    """Each price becomes its own band of +- ``half_width``, centre the price. Bands are not merged
    (Revision 1, R1: merging chained overlapping bands into one 165 USD support)."""
    return [(q - half_width, q + half_width) for q in sorted(prices)]


def h1_bands(
    h1_pivots: Sequence[Swing], n_bars: int, now: pd.Timestamp, p: Params
) -> list[tuple[float, float]]:  # fmt: skip
    """The level bands, in real prices: H1 fixed pivots of the last ``level_bars`` bars whose bar is at least
    ``level_min_age_h`` old, as bands of ``band_frac`` x the median height of the last ``band_legs`` legs."""
    if len(h1_pivots) < 2:
        return []
    legs = [abs(b.price - a.price) for a, b in pairwise(h1_pivots)]
    legs = legs[-p.band_legs :]
    half = p.band_frac * float(np.median(legs))
    limit = now - pd.Timedelta(hours=p.level_min_age_h)
    prices = [
        s.price
        for s in h1_pivots
        if s.pivot_pos >= n_bars - p.level_bars and pd.Timestamp(s.pivot_at) <= limit  # type: ignore[arg-type]
    ]
    return level_bands(prices, half)


# --- the view -------------------------------------------------------------------------------------------


def to_view(pivots: Sequence[Swing], sign: int) -> list[VPivot]:
    """Fixed pivots in the view: unchanged for a BUY; for a SELL kinds swap and prices are negated."""
    if sign > 0:
        return [VPivot(s.kind is SwingKind.LOW, s.price, s.pivot_pos) for s in pivots]
    return [VPivot(s.kind is SwingKind.HIGH, -s.price, s.pivot_pos) for s in pivots]


def _div(price_new: float, price_old: float, osc_new: float, osc_old: float) -> bool:
    if not all(np.isfinite([price_new, price_old, osc_new, osc_old])):
        return False
    return price_new <= price_old and osc_new > osc_old


# --- steps 2b-7 on one timeframe, in the view -----------------------------------------------------------


def analyse_view(
    pv: Sequence[VPivot],
    hi_v: np.ndarray,
    lo_v: np.ndarray,
    close_v: np.ndarray,
    macd_v: np.ndarray,
    rsi_v: np.ndarray,
    bands_v: Sequence[tuple[float, float]],
    tf: str,
    p: Params,
) -> Outcome:
    """Steps 2b-7 for a BUY in the view, on one timeframe. Takes only data already cut at ``now``."""
    out = Outcome(tf=tf, reason="step2: no levels")
    if not bands_v:
        return out

    # 2b (R10): count by zone. The zone is the support band holding a fixed LOW of the entry timeframe.
    # SPEC-QUESTION: R10 says "the latest fixed LOW", but once the higher low of step 3 has formed the latest
    # low sits above the band and the zone would vanish just when steps 3-7 need it. So the latest fixed
    # low of the last `counter_pivots` pivots that lies inside ANY band is taken; of the bands holding it,
    # the one whose centre is nearest (R1). Bands are the view's bands; no test that they lie "below price".
    full = list(pv)
    last = full[-p.counter_pivots :]
    out.reason = "step2: no counter-move"
    band: tuple[float, float] | None = None
    for q in reversed([q for q in last if q.low]):
        holding = [b for b in bands_v if b[0] <= q.price <= b[1]]
        if holding:
            band = min(holding, key=lambda b: abs((b[0] + b[1]) / 2 - q.price))
            break
    out.reason = "step2: L* not in a support band"
    if band is None:
        return out
    out.info["band"] = f"{band[0]:.2f}-{band[1]:.2f}"
    below = np.flatnonzero(close_v < band[0])  # a close through the zone ends it as a support
    reset = int(below[-1]) if below.size else -1
    zone = [q for q in last if q.low and band[0] <= q.price <= band[1] and q.pos > reset]
    out.reason = "step2: no counter-move"
    if not zone:
        return out
    lstar = zone[0]
    for q in zone:
        if q.price < lstar.price:  # the first of equal lows
            lstar = q
    # SPEC-QUESTION: R10 says the count = how many zone lows there are. Counted here: the zone lows up to
    # and including L*; a zone low after L* (a higher low of step 3 still inside a wide band) is not part of
    # the exhaustion into the level, and counting it would inflate every setup past 5 (tried: 04-06's
    # decision vanished). Divergence is read at L* against the zone low immediately before it.
    counted = [q for q in zone if q.pos <= lstar.pos]
    n = len(counted)
    out.info["count"] = str(n)
    out.info["pivots"] = " ".join(f"{q.price:.2f}" for q in counted)

    il = full.index(lstar)
    # Divergence at L* against the zone low before it (R10).
    iz = zone.index(lstar)
    prev_low = zone[iz - 1] if iz >= 1 else None
    d_macd = d_rsi = False
    if prev_low is not None:
        d_macd = _div(lstar.price, prev_low.price, float(macd_v[lstar.pos]), float(macd_v[prev_low.pos]))
        d_rsi = _div(lstar.price, prev_low.price, float(rsi_v[lstar.pos]), float(rsi_v[prev_low.pos]))
    out.info["div_macd"], out.info["div_rsi"] = str(d_macd), str(d_rsi)

    # The M is exactly two counted lows, both zone lows (R3, R10); a count of 3-5
    # always needs divergence on both.
    m_ok = n == 2
    count_ok = p.count_min <= n <= p.count_max and d_macd and d_rsi
    if not (count_ok or m_ok):
        out.reason = (
            "step2: no divergence on both"
            if p.count_min <= n <= p.count_max
            else "step2: count outside 3-5 and no M"
        )
        return out
    kind = "count" if count_ok else "M"
    out.info["kind"] = kind

    # 3: the structure breaks: a bar's high above the last fixed high before L*, then a fixed higher low.
    out.reason = "step3: structure not broken"
    if il < 1 or full[il - 1].low:
        return out
    h_prev = full[il - 1]
    after = hi_v[lstar.pos + 1 :]
    above = np.flatnonzero(after > h_prev.price)
    if above.size == 0:
        return out
    break_pos = lstar.pos + 1 + int(above[0])
    out.info["step3"] = f"broke {h_prev.price:.2f}"
    out.reason = "step3: no higher low yet"
    # SPEC-QUESTION: no limit on a setup's age - a higher low fixed hours before the window can still
    # produce an order at the next window (the spec says "written once L_hl is fixed").
    lhl = next((q for q in full[il + 1 :] if q.low and q.pos > break_pos and q.price > lstar.price), None)
    if lhl is None:
        return out
    out.info["step3"] += f"; higher low {lhl.price:.2f}"

    # 4: the high the dip to the higher low started from.
    out.reason = "step4: no H_d"
    ih = full.index(lhl)
    if ih < 1 or full[ih - 1].low:
        return out
    hd = full[ih - 1]
    out.info["step4"] = f"H_d {hd.price:.2f}"

    # 5: if price is already below the higher low the setup is void.
    out.reason = "step5: price below the higher low"
    if close_v[-1] < lhl.price:
        return out
    # A plain limit at H_d only while the last close is above H_d; at or under it the order is a stop limit
    # again, a fresh break being needed (Revision 1, R5).
    plain = bool(close_v[-1] > hd.price)
    trigger_v = None if plain else hd.price + p.trigger_offset
    out.info["step5"] = "limit" if plain else "stop limit"

    # 6 and 7: the stop beyond the band, the target before the next resistance band.
    entry_v = hd.price
    stop_v = min(lstar.price, band[0]) - p.stop_buffer
    out.reason = "step7: no target level"
    resist = [b for b in bands_v if b[0] > entry_v]
    if not resist:
        return out
    target_v = min(b[0] for b in resist) - p.target_buffer
    if target_v <= entry_v:
        return out
    r = (target_v - entry_v - p.spread) / (entry_v - stop_v)
    out.info["step5"] += f"; R {r:.2f}"
    out.reason = "reward under 2R"  # the owner's floor, R9 (min_r)
    if r < p.min_r:
        return out

    # R8 [Claude]: a setup whose stop or target has traded since the higher low formed is over; the order
    # would be withdrawn the moment it was written, so none is written.
    out.reason = "setup already played out"
    if hi_v[lhl.pos + 1 :].size and (
        float(hi_v[lhl.pos + 1 :].max()) >= target_v or float(lo_v[lhl.pos + 1 :].min()) <= stop_v
    ):
        return out
    out.setup = Setup(
        tf, lstar, lhl, hd, band, counted, kind, d_macd, d_rsi, entry_v, trigger_v, stop_v, target_v, r
    )
    out.reason = "order written"
    return out


# --- decide ---------------------------------------------------------------------------------------------


def _zigzag(df: pd.DataFrame) -> list[Swing]:
    return zigzag_pivots(
        df.high.to_numpy(dtype=np.float64),
        df.low.to_numpy(dtype=np.float64),
        POINT,
        index=list(df.index),
        **ZIGZAG,
    )


def _check_cut(frames: dict[str, pd.DataFrame], now: pd.Timestamp) -> None:
    """Refuse a frame that is unsorted or holds any bar with ``open_time + tf > now`` (Revision 1, R4)."""
    for tf, df in frames.items():
        if not df.index.is_monotonic_increasing:
            raise ValueError(f"{tf} frame is not sorted by time")
        if bool(np.any(np.asarray(df.index + STEP[tf] > now))):
            raise ValueError(f"{tf} frame holds a bar that had not closed at {now}")


def decide(
    frames: dict[str, pd.DataFrame],
    now: pd.Timestamp,
    p: Params,
    used: frozenset[str] = frozenset(),
    pending: bool = False,
) -> Result:
    """Apply the seven steps at ``now`` to frames already cut to the bars closed then (``cut``).
    ``used`` holds setups already written; ``pending`` is true while an earlier order is live."""
    _check_cut(frames, now)
    t = now.tz_convert(TH)
    m5 = frames["M5"]
    log = dict.fromkeys(LOG_COLUMNS, "")
    log.update(date=f"{t:%Y-%m-%d}", time_thai=f"{t:%H:%M}", h1_mode=p.h1_mode)

    def done(reason: str, info: dict[str, str] | None = None, tf: str = "") -> Result:
        log["reason"] = reason
        log["tf"] = tf
        for k, v in (info or {}).items():
            log[k] = v
        return Result(log)

    window = window_of(now)
    log["window"] = window
    if len(m5) == 0 or m5.index[-1] + STEP["M5"] != now:
        return done("market closed")  # the bar that closes at `now` is not in the data
    log["price"] = f"{float(m5.close.iloc[-1]):.2f}"
    if not window:
        return done("outside window")
    if any(len(frames[tf]) < WARMUP for tf in ("H1", "M15", "M5")):
        return done("warm-up")
    if pending:
        return done("order pending")

    h1 = frames["H1"]
    h1_piv = _zigzag(h1)
    side = h1_side(h1_piv, float(m5.close.iloc[-1]), p.h1_mode)
    if side is None:
        return done("step1: no side")
    log["side"] = side
    sign = 1 if side == "BUY" else -1
    bands = h1_bands(h1_piv, len(h1), now, p)
    bands_v = sorted((min(sign * lo, sign * hi), max(sign * lo, sign * hi)) for lo, hi in bands)

    outcomes: list[Outcome] = []
    for tf in TIMEFRAMES:
        df = frames[tf]
        piv = to_view(_zigzag(df), sign)
        hi_v = df.high.to_numpy(dtype=np.float64) if sign > 0 else -df.low.to_numpy(dtype=np.float64)
        lo_v = df.low.to_numpy(dtype=np.float64) if sign > 0 else -df.high.to_numpy(dtype=np.float64)
        close_v = sign * df.close.to_numpy(dtype=np.float64)
        macd_v = sign * macd_mt5(df.close)["main"].to_numpy(dtype=np.float64)
        rsi_v = sign * rsi(df.close, 14).to_numpy(dtype=np.float64) + (0.0 if sign > 0 else 100.0)
        out = analyse_view(piv, hi_v, lo_v, close_v, macd_v, rsi_v, bands_v, tf, p)
        if out.setup is not None:
            s = out.setup
            times = df.index
            key = f"{side}|{tf}|{times[s.lstar.pos]}|{times[s.lhl.pos]}"
            # SPEC-QUESTION: the spec does not say how a setup that stays valid for many bars is kept from
            # being written twice; its identity is side, timeframe, L* time and higher-low time.
            if key in used:
                out.reason, out.setup = "setup already used", None
            else:
                out.info["key"] = key
        outcomes.append(out)
        if out.setup is not None:
            break

    # SPEC-QUESTION: the log has one row per bar but two timeframes are evaluated; its reason is the one of
    # the timeframe that got furthest through the steps (M5 on a tie), the decision the first timeframe
    # that wrote one.
    best = outcomes[-1] if outcomes[-1].setup else max(outcomes, key=lambda o: RANK[o.reason])
    info = dict(best.info)
    info.pop("key", None)
    result = done(best.reason, info, best.tf)
    if best.setup is None:
        return result
    result.key = best.info["key"]
    result.decision = _row(best.setup, side, sign, now, frames[best.tf], p)
    return result


def _row(s: Setup, side: str, sign: int, now: pd.Timestamp, df: pd.DataFrame, p: Params) -> dict[str, str]:
    """The ledger row (spec section 6) for a setup, prices back in real terms."""
    t = now.tz_convert(TH)
    last_bar = t - pd.Timedelta(minutes=5)
    times = pd.DatetimeIndex(df.index).tz_convert(TH)
    macd = macd_mt5(df.close)["main"].to_numpy(dtype=np.float64)
    rs = rsi(df.close, 14).to_numpy(dtype=np.float64)

    def real(v: float) -> float:
        return round(sign * v, 2)

    pts = "; ".join(
        f"{real(q.price):.2f}@{times[q.pos]:%d/%m %H:%M} macd {macd[q.pos]:.2f} rsi {rs[q.pos]:.1f}"
        for q in s.counted
    )
    high_word = "lowest low" if sign > 0 else "highest high"
    shape = {"count": f"count of {len(s.counted)}", "M": "M" if sign > 0 else "W"}[s.kind]
    structure = (
        f"bot2e {s.tf} {side}, {p.h1_mode} H1 side. Level band {real(s.band[0]):.2f}-{real(s.band[1]):.2f}"
        f" (support in the view); {shape} at L*={real(s.lstar.price):.2f} ({high_word} of the counter-move). "
        f"Counted: {pts}. Divergence on MACD {s.div_macd}, on RSI {s.div_rsi}"
        f"{' (diverged anyway)' if s.kind == 'M' and s.div_macd and s.div_rsi else ''}. "
        f"Structure broken, higher low {real(s.lhl.price):.2f}@{times[s.lhl.pos]:%d/%m %H:%M}; "
        f"H_d={real(s.hd.price):.2f}. R {s.r:.2f} (net of {p.spread:g} spread). Parameters: {p.text()}"
    )
    trig = "" if s.trigger_v is None else f"{real(s.trigger_v):.2f}"
    return {
        "id": "",  # numbered by the walker
        "cutoff_thai": f"{t:%Y-%m-%d} 07:00",
        "decided_at": f"{last_bar:%d/%m %H:%M}",
        "reader": READER,
        "side": side,
        "entry": f"{real(s.entry_v):.2f}",
        "stop": f"{real(s.stop_v):.2f}",
        "target": f"{real(s.target_v):.2f}",
        "fill": "", "exit": "", "why": "", "r_net": "",
        "structure": structure,
        "rules": "?????????",
        "conflict": "",
        "at_decision_r": "",
        "missed_by": "",
        "trigger": trig,
        "setup": "+++++++",
    }  # fmt: skip


# --- the walk ---------------------------------------------------------------------------------------------


def load_frames() -> dict[str, pd.DataFrame]:
    return {tf: frame(tf) for tf in ("H1", "M15", "M5")}


def _read(path: Path, columns: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return [{c: r.get(c, "") for c in columns} for r in csv.DictReader(fh)]


def _write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def walk_days(
    days: Sequence[str],
    p: Params,
    full: dict[str, pd.DataFrame],
    prior: Sequence[dict[str, str]] = (),
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Walk the given Thai dates in order; returns (decisions, log rows). ``prior`` are rows written before
    the first day, which may still be live (one order at a time)."""
    written: list[dict[str, str]] = [r for r in prior if r["side"] in ("BUY", "SELL")]
    mine: list[dict[str, str]] = []
    logs: list[dict[str, str]] = []
    used: set[str] = set()
    finished: set[str] = set()
    for day in days:
        midnight = pd.Timestamp(day, tz=TH)
        for _, a, b in WINDOWS:
            now = midnight + pd.Timedelta(minutes=a)
            end = midnight + pd.Timedelta(minutes=b)
            while now <= end:
                now_utc = now.tz_convert("UTC")
                frames = cut(full, now_utc)
                known = frames["M5"]
                live = False
                for r in written:  # one order at a time: live while score.py still calls it open
                    if r["id"] in finished:
                        continue
                    scored = score(r, known, start_of(r, {}))
                    if scored["why"] == "open":
                        live = True
                    else:
                        finished.add(r["id"])
                res = decide(frames, now_utc, p, frozenset(used), pending=live)
                logs.append(res.log)
                if res.decision is not None:
                    n = sum(1 for r in mine if r["cutoff_thai"][:10] == day) + 1
                    row = res.decision
                    row["id"] = f"B-{day.replace('-', '')}-{n}"
                    mine.append(row)
                    written.append(row)
                    used.add(res.key)
                now += pd.Timedelta(minutes=5)
    return mine, logs


def days_between(first: str, last: str) -> list[str]:
    return [f"{d:%Y-%m-%d}" for d in pd.date_range(first, last, freq="D")]


def run(first: str, last: str, p: Params, ledger: Path = LEDGER_PATH, log: Path = LOG_PATH) -> None:
    days = days_between(first, last)
    full = load_frames()
    old = _read(ledger, LEDGER_COLUMNS)
    prior = [r for r in old if r["cutoff_thai"][:10] < days[0]]
    mine, logs = walk_days(days, p, full, prior)
    keep = [r for r in old if r["cutoff_thai"][:10] not in days]
    _write(ledger, LEDGER_COLUMNS, sorted(keep + mine, key=lambda r: (r["cutoff_thai"][:10], r["id"])))
    old_log = [r for r in _read(log, LOG_COLUMNS) if r["date"] not in days]
    _write(log, LOG_COLUMNS, old_log + logs)

    counts: dict[str, int] = {}
    for r in logs:
        counts[r["reason"]] = counts.get(r["reason"], 0) + 1
    print(f"{first}..{last} h1-mode {p.h1_mode}: {len(logs)} bars evaluated, {len(mine)} decisions")
    for r in mine:
        print(
            f"  {r['id']} {r['decided_at']} {r['side']} entry {r['entry']} trigger {r['trigger'] or '-'} "
            f"stop {r['stop']} target {r['target']}"
        )
    for reason, c in sorted(counts.items(), key=lambda kv: RANK[kv[0]]):
        print(f"  {c:4d}  {reason}")


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    ap.add_argument("--from", dest="first", required=True, help="first Thai date, YYYY-MM-DD")
    ap.add_argument("--to", dest="last", required=True, help="last Thai date, YYYY-MM-DD")
    d = Params()
    ap.add_argument("--h1-mode", choices=("strict", "lows"), default=d.h1_mode)
    ap.add_argument("--min-r", type=float, default=d.min_r)
    ap.add_argument("--trigger-offset", type=float, default=d.trigger_offset)
    ap.add_argument("--stop-buffer", type=float, default=d.stop_buffer)
    ap.add_argument("--target-buffer", type=float, default=d.target_buffer)
    ap.add_argument("--band-frac", type=float, default=d.band_frac)
    a = ap.parse_args(argv)
    params = Params(
        h1_mode=a.h1_mode,
        min_r=a.min_r,
        trigger_offset=a.trigger_offset,
        stop_buffer=a.stop_buffer,
        target_buffer=a.target_buffer,
        band_frac=a.band_frac,
    )
    run(a.first, a.last, params)


if __name__ == "__main__":
    main()
