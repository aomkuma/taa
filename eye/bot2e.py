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
from collections.abc import Callable, Sequence
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
# H4 is a stored frame too (research option h1_tf=H4); walk.py's tables do not know it.
STEP = {**STEP, "H4": pd.Timedelta(hours=4)}
FRAME_BARS = {tf: SHOWN[tf] + WARMUP for tf in ("H1", "M15", "M5")} | {"H4": 600}


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
    # Research options (eye/BOT_RESEARCH.md). Defaults are the behaviour of revision 3.
    h1_tf: str = "H1"  # [Claude] the timeframe whose fixed ZigZag pivots give the side: "H1" or "H4"
    h1_swings: int = 2  # [Claude] strict side: the last N highs and N lows each rising / falling (2 or 3)
    entry_tfs: str = "M5,M15"  # [Claude] the entry timeframes tried, in order: "M5,M15", "M15" or "M5"
    # [Claude] for the 3-5 count: "both" oscillators diverge (the owner's rule: "if both happen, it is
    # clear") or "one" = at least one. The owner (R11, METHOD 2e): one oscillator is enough; both is the
    # "clear" case. "both" is kept for comparison with the earlier rule.
    div_mode: str = "one"
    spread: float = (
        SPREAD  # the owner's real spread on gold, USD (the R written into a decision is net of it)
    )
    # Revision 5 (R13-R17), the owner's Fibonacci. mode "2e" (default) is every earlier revision untouched.
    mode: str = "2e"  # "2e" | "fib"
    fib_tf: str = "M15"  # [Claude] the timeframe the Fibo leg is read on: "M15" or "M5"
    fib_entry: float = 0.382  # [Claude] the entry level as a fraction of the leg, 0 % at the low (R14)
    # [Claude] "level" = before the next H1 band (step 7), "high" = the leg's 100 %; the owner (10-29: "in a
    # trend it should be 127-161 %"): "ext127" / "ext161" = the 127.2 % / 161.8 % extension - target_buffer
    fib_target: str = "ext161"
    fib_count: str = "off"  # [Claude] "on" = the zone count (R16) must hold, "off" = R15
    # R18 (revision 6): "counter" = the owner's leg, the counter-move just ended (high -> low, then the
    # bounce). The only leg; the field is kept so the ledger text stays the same.
    fib_leg: str = "counter"
    # [Claude] "h1" = only the H1 side may trade (the owner: the larger timeframe's trend is never ignored).
    # The only value; the field is kept so the ledger text stays the same. No H1 side = no fib order
    # (fib_range "on" is the one no-side path).
    fib_side: str = "h1"
    # [Claude] which high is 100 % on the counter leg: "start" = the highest fixed high of the descending run,
    # "latest" = the fixed high immediately before L0 (comparison only; the depth-based "auto" was withdrawn)
    fib_high: str = "start"
    max_orders: int = (
        1  # [Claude] research: orders live (pending or open) at once; a new one needs fewer than this
    )
    fib_range: str = "off"  # [Claude] "on" = trade the sideways edges 88 % / 12 % when H1 gives no side (R17)
    # Revision 7 (R19 / R20 are rules and always on; these are the owner's two open points, run both ways).
    max_entry_distance: float = (
        4.0  # R20, the owner's rule 7: no order whose entry is further than this from price
    )
    fib_stop: str = (
        "line"  # [Claude] "line" = beyond the 0 % / 23.6 % line; "swing" = also beyond the latest lows
    )
    fib_level: str = (
        "off"  # [Claude] "on" = L0 must lie inside an H1 support band (2e step 2a); mirrored for a SELL
    )

    def __post_init__(self) -> None:
        if self.max_orders < 1:
            raise ValueError(f"max_orders must be at least 1, got {self.max_orders!r}")
        if not self.max_entry_distance > 0:
            raise ValueError(f"max_entry_distance must be above 0, got {self.max_entry_distance!r}")
        for name, allowed in (
            ("mode", ("2e", "fib")),
            ("fib_tf", ("M15", "M5")),
            ("fib_target", ("level", "high", "ext127", "ext161")),
            ("fib_count", ("off", "on")),
            ("fib_range", ("off", "on")),
            ("fib_leg", ("counter",)),
            ("fib_high", ("start", "latest")),
            ("fib_side", ("h1",)),
            ("fib_stop", ("line", "swing")),
            ("fib_level", ("off", "on")),
        ):
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, got {getattr(self, name)!r}")

    def text(self) -> str:
        """The [Claude] parameters as they are written into a decision."""
        return (
            f"h1_mode={self.h1_mode} level_min_age_h={self.level_min_age_h:g} level_bars={self.level_bars} "
            f"band_frac={self.band_frac:g} band_legs={self.band_legs} counter_pivots={self.counter_pivots} "
            f"trigger_offset={self.trigger_offset:g} stop_buffer={self.stop_buffer:g} "
            f"target_buffer={self.target_buffer:g} min_r={self.min_r:g} h1_tf={self.h1_tf} "
            f"h1_swings={self.h1_swings} entry_tfs={self.entry_tfs} div_mode={self.div_mode} "
            f"mode={self.mode} fib_tf={self.fib_tf} "
            f"fib_entry={self.fib_entry:g} fib_target={self.fib_target} fib_count={self.fib_count} "
            f"fib_range={self.fib_range} fib_leg={self.fib_leg} fib_side={self.fib_side} "
            f"fib_high={self.fib_high} max_orders={self.max_orders} "
            f"max_entry_distance={self.max_entry_distance:g} fib_stop={self.fib_stop} "
            f"fib_level={self.fib_level}"
        )


# The reasons a bar can end without an order, in the order the steps run; a later one means the bar got
# further. ``reason`` in the log is always one of these, or "order written".
REASONS = [
    "market closed", "outside window", "warm-up", "order pending", "step1: no side",
    "fib: no range", "fib: range broken", "fib: no live leg", "fib: leg has run (100 % traded)",
    "fib: L0 not in a support band", "fib: price below the entry level",
    "fib: entry too far from price",
    "fib: price past the range edge", "fib: price not in the zone yet", "fib: price under the stop",
    "fib: no bounce above the entry level", "fib: count outside 3-5",
    "fib: structure not turned up",
    "fib: no target level", "step2: no levels",
    "step2: no counter-move", "step2: L* not in a support band", "step2: count outside 3-5 and no M",
    "step2: no divergence", "step3: structure not broken",
    "step3: no higher low yet",
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
class FibCount:
    """What step 2 found in the Fibo zone (R16), in the view."""

    lstar: VPivot
    band: tuple[float, float]
    counted: list[VPivot]
    kind: str  # "count" or "M"
    div_macd: bool
    div_rsi: bool


@dataclass
class FibSetup:
    """A Fibo order (R15 / R17), in the view: a plain limit at ``entry_v``."""

    kind: str  # "leg" (R15) or "range" (R17)
    lo_v: float  # 0 % of the leg / range, in the view
    hi_v: float  # 100 %
    lo_pos: int  # bar positions on the frame the leg / range was read on (the range: an H1 frame)
    hi_pos: int
    entry_v: float
    stop_v: float
    target_v: float
    r: float
    count: FibCount | None = None  # fib_count on: the zone count behind it (R16)


@dataclass
class FibOut:
    reason: str
    info: dict[str, str] = field(default_factory=dict)
    setup: FibSetup | None = None


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


def h1_side(pivots: Sequence[Swing], price: float, mode: str, swings: int = 2) -> str | None:
    """ "BUY" / "SELL" from the H1 fixed pivots, or None (spec step 1). ``strict``: both the last high and the
    last low above (below) the ones before them. ``lows``: the last low above the one before and price above
    that low (up); the last high under the one before and price under it (down); both or neither = None."""
    highs = [p.price for p in pivots if p.kind is SwingKind.HIGH]
    lows = [p.price for p in pivots if p.kind is SwingKind.LOW]
    if swings not in (2, 3):
        raise ValueError(f"h1_swings must be 2 or 3, got {swings!r}")
    if len(highs) < swings or len(lows) < swings:
        return None
    if mode == "strict":
        hs, ls = highs[-swings:], lows[-swings:]
        up = all(b > a for a, b in pairwise(hs)) and all(b > a for a, b in pairwise(ls))
        down = all(b < a for a, b in pairwise(hs)) and all(b < a for a, b in pairwise(ls))
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
    full = list(pv)
    found = step2(out, full, close_v, macd_v, rsi_v, bands_v, p)
    if found is None:
        return out
    lstar, band, counted, kind, d_macd, d_rsi = found
    il = full.index(lstar)

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


def step2(
    out: Outcome,
    full: list[VPivot],
    close_v: np.ndarray,
    macd_v: np.ndarray,
    rsi_v: np.ndarray,
    bands_v: Sequence[tuple[float, float]],
    p: Params,
) -> tuple[VPivot, tuple[float, float], list[VPivot], str, bool, bool] | None:
    """Step 2b (R10) for a BUY in the view: the zone count. Returns (L*, band, counted, kind, MACD div,
    RSI div), or None with ``out.reason`` set."""
    # 2b (R10): count by zone. The zone is the support band holding a fixed LOW of the entry timeframe.
    # SPEC-QUESTION: R10 says "the latest fixed LOW", but once the higher low of step 3 has formed the latest
    # low sits above the band and the zone would vanish just when steps 3-7 need it. So the latest fixed
    # low of the last `counter_pivots` pivots that lies inside ANY band is taken; of the bands holding it,
    # the one whose centre is nearest (R1). Bands are the view's bands; no test that they lie "below price".
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
        return None
    out.info["band"] = f"{band[0]:.2f}-{band[1]:.2f}"
    below = np.flatnonzero(close_v < band[0])  # a close through the zone ends it as a support
    reset = int(below[-1]) if below.size else -1
    zone = [q for q in last if q.low and band[0] <= q.price <= band[1] and q.pos > reset]
    out.reason = "step2: no counter-move"
    if not zone:
        return None
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
    # R11: one oscillator is enough (the owner); both is the "clear" case, and the decision text says which.
    diverged = (d_macd or d_rsi) if p.div_mode == "one" else (d_macd and d_rsi)
    count_ok = p.count_min <= n <= p.count_max and diverged
    if not (count_ok or m_ok):
        out.reason = (
            "step2: no divergence" if p.count_min <= n <= p.count_max else "step2: count outside 3-5 and no M"
        )
        return None
    kind = "count" if count_ok else "M"
    out.info["kind"] = kind
    return lstar, band, counted, kind, d_macd, d_rsi


# --- revision 5 (R13-R17): the owner's Fibonacci -----------------------------------------------------------


FIB_EXT = {"ext127": 1.272, "ext161": 1.618}  # the leg's extensions, 0 % at the low, 100 % at the high


def fib_high_choice(p: Params) -> str:
    """``start`` (the highest fixed high of the descending run) or ``latest`` (the fixed high just before L0).
    The depth-based ``auto`` mapping was withdrawn; the default is ``start`` for every entry."""
    return p.fib_high


def fib_leg_counter(
    pv: Sequence[VPivot], close_v: np.ndarray, high_mode: str = "start"
) -> tuple[VPivot, VPivot, list[VPivot]] | None:  # fmt: skip
    """R18 for a BUY in the view: ``L0`` = the latest fixed LOW lower than every fixed low after it (a
    bottom), with no close under it since; ``H100`` = the highest fixed HIGH of the descending run into L0.
    Returns (L0, H100, the run's lows, each lower than the one before, L0 last), or None."""
    # SPEC-QUESTION: [Claude] "lower than every fixed low after it" needs at least one later fixed low - the
    # newest low is not a bottom until a higher low has been fixed after it.
    lows = [i for i, q in enumerate(pv) if q.low]
    k = None
    for a in range(len(lows) - 2, -1, -1):
        if all(pv[lows[a]].price < pv[j].price for j in lows[a + 1 :]):
            k = a
            break
    if k is None:
        return None
    l0 = pv[lows[k]]
    if close_v[l0.pos + 1 :].size and float(close_v[l0.pos + 1 :].min()) < l0.price:
        return None  # a close under the bottom
    first = k
    while first > 0 and pv[lows[first - 1]].price > pv[lows[first]].price:
        first -= 1
    run = [pv[j] for j in lows[first : k + 1]]
    # SPEC-QUESTION: [Claude] the run starts at the high before its first low (if the pivot before it is a
    # high); H100 is the highest fixed high from there to L0.
    start = lows[first] - 1 if lows[first] >= 1 and not pv[lows[first] - 1].low else lows[first]
    highs = [q for q in pv[start : lows[k]] if not q.low]
    if not highs:
        return None
    top = highs[-1]  # "latest": the fixed high just before L0
    if high_mode == "start":
        top = highs[0]
        for q in highs:
            if q.price > top.price:
                top = q
    return l0, top, run


STRONG_BULL_ENTRY = 0.618  # the owner (10-29): an entry this shallow (61.8 %) is the strong-bull case
STRONG_BULL_STOP = 0.236  # ... and its stop is "beyond 23 %", below the 23.6 % level, not below the 0 %


def fib_stop_v(p: Params, low_price: float, high_price: float) -> float:
    """The stop under the leg: below the 0 % - stop_buffer; for an entry at 61.8 % or shallower (the owner's
    strong-bull case) below the 23.6 % level - stop_buffer."""
    # SPEC-QUESTION: "entry 61.8 %" is applied to any fib_entry >= 0.618, not only the value 0.618 itself.
    base = low_price
    if p.fib_entry >= STRONG_BULL_ENTRY:
        base = low_price + STRONG_BULL_STOP * (high_price - low_price)
    return base - p.stop_buffer


def fib_fixed_target_v(p: Params, low_price: float, high_price: float) -> float | None:
    """The target that is a price on the leg itself: ``high`` = the 100 % - target_buffer, ``ext127`` /
    ``ext161`` = the 127.2 % / 161.8 % extension - target_buffer; None for ``level`` (the H1 bands decide)."""
    if p.fib_target == "high":
        return high_price - p.target_buffer
    if p.fib_target in FIB_EXT:
        return low_price + FIB_EXT[p.fib_target] * (high_price - low_price) - p.target_buffer
    return None


def fib_target_v(
    p: Params, low_price: float, high_price: float, entry_v: float, bands_v: Sequence[tuple[float, float]]
) -> float | None:  # fmt: skip
    """R14: see ``fib_fixed_target_v``; ``level`` = just before the nearest H1 band above the entry (step 7).
    None when there is no target above the entry."""
    target = fib_fixed_target_v(p, low_price, high_price)
    if target is None:
        resist = [b for b in bands_v if b[0] > entry_v]
        if not resist:
            return None
        target = min(b[0] for b in resist) - p.target_buffer
    return target if target > entry_v else None


def analyse_fib(
    pv: Sequence[VPivot],
    hi_v: np.ndarray,
    lo_v: np.ndarray,
    close_v: np.ndarray,
    bands_v: Sequence[tuple[float, float]],
    p: Params,
    macd_v: np.ndarray | None = None,
    rsi_v: np.ndarray | None = None,
    price_v: float | None = None,
) -> FibOut:
    """R15 (fib_count off), for a BUY in the view: a plain limit at the entry level while the leg is live and
    the last close is above it; stop per ``fib_stop_v``; target per ``fib_target``; at least ``min_r``.
    R16 (fib_count on, needs ``macd_v`` / ``rsi_v``): the same, but only when step 2 (the zone count or the
    M, R10) holds in the Fibo zone [0 %, entry level] and price has traded into it; the plain limit is then
    written at the last close."""
    out = FibOut(reason="fib: no live leg")
    got = fib_leg_counter(pv, close_v, fib_high_choice(p))
    if got is None:
        return out
    low, high, run = got
    # R19: a leg that has run (any bar after L0 traded beyond the 100 %) is over; no order.
    out.reason = "fib: leg has run (100 % traded)"
    if hi_v[low.pos + 1 :].size and float(hi_v[low.pos + 1 :].max()) > high.price:
        return out
    # fib_level on: L0 must lie inside an H1 support band (the view's bands; resistance for a SELL).
    if p.fib_level == "on":
        out.reason = "fib: L0 not in a support band"
        if not any(b[0] <= low.price <= b[1] for b in bands_v):
            return out
    # R8 reads the bars from here: the target from ``since_t``, the stop from ``since_l`` (they differ by one
    # bar, see below).
    since_t = since_l = low.pos + 1
    rng = high.price - low.price
    entry_v = low.price + p.fib_entry * rng
    out.info["pivots"] = f"{low.price:.2f} {high.price:.2f}"
    stop_v = fib_stop_v(p, low.price, high.price)
    if p.fib_stop == "swing":
        # the most extreme fixed low formed after L0 (L0 itself is already covered by the line stop)
        later = [q.price for q in pv if q.low and q.pos > low.pos]
        if later:
            stop_v = min(stop_v, min(later) - p.stop_buffer)
    count: FibCount | None = None
    if p.fib_count == "on":
        # R18 count on: the run into L0 has 3-5 lower lows, divergence at L0 against the low before it.
        if macd_v is None or rsi_v is None:
            raise ValueError("fib_count on needs the MACD and RSI arrays")
        n = len(run)
        out.info["count"], out.info["pivots"] = str(n), " ".join(f"{q.price:.2f}" for q in run)
        out.reason = "fib: count outside 3-5"
        if not p.count_min <= n <= p.count_max:
            return out
        d_macd = d_rsi = False
        if n >= 2:
            a, b = run[-2], run[-1]
            d_macd = _div(b.price, a.price, float(macd_v[b.pos]), float(macd_v[a.pos]))
            d_rsi = _div(b.price, a.price, float(rsi_v[b.pos]), float(rsi_v[a.pos]))
        out.info["div_macd"], out.info["div_rsi"] = str(d_macd), str(d_rsi)
        out.reason = "step2: no divergence"
        if not ((d_macd or d_rsi) if p.div_mode == "one" else (d_macd and d_rsi)):
            return out
        count = FibCount(low, (low.price, entry_v), run, "count", d_macd, d_rsi)
    out.reason = "fib: no bounce above the entry level"
    if not hi_v[low.pos + 1 :].size or float(hi_v[low.pos + 1 :].max()) <= entry_v:
        return out
    # SPEC-QUESTION: [Claude] R8 for the counter leg is read from the bar that first traded above the
    # entry level: the climb out of L0 itself passes under the 23.6 % stop of a 61.8 % entry. On that
    # crossing bar the TARGET counts (a high at or above it = played out) but its LOW does not (order
    # inside the bar unknown); from the next bar on both count.
    since_t = low.pos + 1 + int(np.flatnonzero(hi_v[low.pos + 1 :] > entry_v)[0])
    since_l = since_t + 1
    out.reason = "fib: price below the entry level"
    if close_v[-1] <= entry_v:
        return out
    # R20: the entry must be reachable - no further than ``max_entry_distance`` from the last close.
    out.reason = "fib: entry too far from price"
    # ``price_v``: the last closed M5 close in the view (R20, M5 and M15 legs alike); None = close_v[-1].
    price = float(close_v[-1]) if price_v is None else price_v
    gap = abs(price - entry_v)
    if gap > p.max_entry_distance + 1e-9:  # float noise at exactly the limit is not a refusal
        out.info["step5"] = f"entry {gap:.2f} USD from the M5 price, limit {p.max_entry_distance:g}"
        return out
    out.reason = "fib: no target level"
    target_v = fib_target_v(p, low.price, high.price, entry_v, bands_v)
    if target_v is None:
        return out
    r = (target_v - entry_v - p.spread) / (entry_v - stop_v)
    out.info["step5"] = f"limit; R {r:.2f}"
    out.reason = "reward under 2R"
    if r < p.min_r:
        return out
    # R8: the stop or the target has traded since the leg's high was fixed - the order would be withdrawn.
    # SPEC-QUESTION: an entry level already touched and bounced from since the high does not stop the order;
    # the limit is written and waits for the next retest.
    out.reason = "setup already played out"
    if (hi_v[since_t:].size and float(hi_v[since_t:].max()) >= target_v) or (
        lo_v[since_l:].size and float(lo_v[since_l:].min()) <= stop_v
    ):
        return out
    out.setup = FibSetup("leg", low.price, high.price, low.pos, high.pos, entry_v, stop_v, target_v, r, count)
    out.reason = "order written"
    return out


# SPEC-QUESTION (R17): the owner's "88 % - 127 %" is read as the sell limit at 88 %, the stop beyond
# 127 %, the target the range's other edge (the owner, 10-29: "sideways, around 100 %"): the range low +
# buffer; the buy limit is at 12 %, the stop beyond -27 %, the target the range high - buffer. 0 % is
# the range's low, 100 % its high.
RANGE_EDGE = 0.12  # the buy limit; the sell limit is the mirror, 88 %
RANGE_PAST = 0.27  # the stop sits beyond this: 27 % under the low, 127 % over the high


def analyse_range(
    lo_price_v: float,
    rng: float,
    hi_v: np.ndarray,
    lo_v: np.ndarray,
    close_v: np.ndarray,
    p: Params,
) -> FibOut:
    """R17 for a BUY in the view on the M5 bars since the range's later pivot (a SELL is the mirror): a plain
    limit at 12 % above the range's low, stop under -27 % - stop_buffer, target 100 % - target_buffer; at
    least ``min_r``. ``close_v``'s last value is the price now."""
    out = FibOut(reason="fib: range broken")
    broken = lo_price_v - RANGE_PAST * rng
    # SPEC-QUESTION: a close beyond the stop level (-27 % / 127 %) since the later pivot voids the range.
    if close_v.size == 0 or float(close_v.min()) < broken:
        return out
    entry_v = lo_price_v + RANGE_EDGE * rng
    # SPEC-QUESTION: the limit is written only while the last close is still on the far side of the edge
    # (above the buy limit, below the sell limit), so it rests as a limit and does not fill at the market.
    out.reason = "fib: price past the range edge"
    if close_v[-1] <= entry_v:
        return out
    stop_v = broken - p.stop_buffer
    target_v = lo_price_v + rng - p.target_buffer
    out.reason = "fib: no target level"
    if target_v <= entry_v:
        return out
    r = (target_v - entry_v - p.spread) / (entry_v - stop_v)
    out.info["step5"] = f"limit; R {r:.2f}"
    out.reason = "reward under 2R"
    if r < p.min_r:
        return out
    out.reason = "setup already played out"
    if float(hi_v.max()) >= target_v or float(lo_v.min()) <= stop_v:
        return out
    out.setup = FibSetup("range", lo_price_v, lo_price_v + rng, -1, -1, entry_v, stop_v, target_v, r)
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


def _view_arrays(df: pd.DataFrame, sign: int) -> tuple[np.ndarray, ...]:
    """high, low, close, MACD and RSI of a frame in the view (a SELL's: negated, highs and lows swapped)."""
    hi_v = df.high.to_numpy(dtype=np.float64) if sign > 0 else -df.low.to_numpy(dtype=np.float64)
    lo_v = df.low.to_numpy(dtype=np.float64) if sign > 0 else -df.high.to_numpy(dtype=np.float64)
    close_v = sign * df.close.to_numpy(dtype=np.float64)
    macd_v = sign * macd_mt5(df.close)["main"].to_numpy(dtype=np.float64)
    rsi_v = sign * rsi(df.close, 14).to_numpy(dtype=np.float64) + (0.0 if sign > 0 else 100.0)
    return hi_v, lo_v, close_v, macd_v, rsi_v


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
    side_piv = h1_piv if p.h1_tf == "H1" else _zigzag(frames[p.h1_tf])
    side = h1_side(side_piv, float(m5.close.iloc[-1]), p.h1_mode, p.h1_swings)
    if p.mode == "fib":
        return _decide_fib(frames, now, p, used, log, done, side, h1_piv)
    if side is None:
        return done("step1: no side")
    log["side"] = side
    sign = 1 if side == "BUY" else -1
    bands = h1_bands(h1_piv, len(h1), now, p)
    bands_v = sorted((min(sign * lo, sign * hi), max(sign * lo, sign * hi)) for lo, hi in bands)

    outcomes: list[Outcome] = []
    for tf in p.entry_tfs.split(","):
        df = frames[tf]
        piv = to_view(_zigzag(df), sign)
        hi_v, lo_v, close_v, macd_v, rsi_v = _view_arrays(df, sign)
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


def _decide_fib(
    frames: dict[str, pd.DataFrame],
    now: pd.Timestamp,
    p: Params,
    used: frozenset[str],
    log: dict[str, str],
    done: Callable[..., Result],
    side: str | None,
    h1_piv: Sequence[Swing],
) -> Result:
    """Mode "fib" (R13-R18): the H1 side (or, with fib_range on and no side, the range edges), then the Fibo
    leg; only the H1 side is tried (a BUY view while H1 says SELL is never evaluated).
    Closed bars only: ``decide`` has checked the cut."""
    h1 = frames["H1"]
    if side is None:
        if p.fib_range != "on":
            return done("step1: no side")
        return _decide_range(frames, now, p, used, log, done, h1_piv)
    views = [(side, 1 if side == "BUY" else -1)]
    tf = p.fib_tf
    df = frames[tf]
    times = pd.DatetimeIndex(df.index)
    zz = _zigzag(df)
    found: list[tuple[str, int, FibOut]] = []
    worst = FibOut(reason="fib: no live leg")
    for vside, sign in views:
        bands = h1_bands(h1_piv, len(h1), now, p)
        bands_v = sorted((min(sign * lo, sign * hi), max(sign * lo, sign * hi)) for lo, hi in bands)
        hi_v, lo_v, close_v, macd_v, rsi_v = _view_arrays(df, sign)
        m5_close_v = sign * float(frames["M5"].close.iloc[-1])
        fo = analyse_fib(to_view(zz, sign), hi_v, lo_v, close_v, bands_v, p, macd_v, rsi_v, m5_close_v)
        if fo.setup is not None:
            found.append((vside, sign, fo))
        elif RANK[fo.reason] >= RANK[worst.reason]:
            worst = fo
    if not found:
        return done(worst.reason, worst.info, tf)
    vside, sign, fo = found[0]  # one view only: the H1 side
    log["side"] = vside
    s = fo.setup
    if s is None:  # not reachable: ``found`` only holds outcomes with a setup
        return done(fo.reason, fo.info, tf)
    key = f"{vside}|{tf}|{times[s.lo_pos]}|{times[s.hi_pos]}"
    if key in used:
        return done("setup already used", fo.info, tf)
    result = done(fo.reason, fo.info, tf)
    result.key = key
    result.decision = _fib_row(s, vside, sign, now, times, tf, p)
    return result


def _decide_range(
    frames: dict[str, pd.DataFrame],
    now: pd.Timestamp,
    p: Params,
    used: frozenset[str],
    log: dict[str, str],
    done: Callable[..., Result],
    h1_piv: Sequence[Swing],
) -> Result:
    """R17: H1 gives no side. The range = the last two fixed H1 pivots (one high, one low); a sell limit at
    88 % and a buy limit at 12 %, each tried; of those that qualify, the one with the nearer entry."""
    h1, m5 = frames["H1"], frames["M5"]
    if len(h1_piv) < 2 or h1_piv[-1].kind is h1_piv[-2].kind:
        return done("fib: no range")
    a, b = h1_piv[-2], h1_piv[-1]
    hi_p, lo_p = (a, b) if a.kind is SwingKind.HIGH else (b, a)
    # SPEC-QUESTION: the range has "seen" the M5 bars from the later pivot's H1 bar on (broken / played out).
    m5s = m5[m5.index >= h1.index[b.pivot_pos]]
    if len(m5s) == 0:
        return done("fib: no range")
    rng = hi_p.price - lo_p.price
    last = float(m5.close.iloc[-1])
    best: tuple[str, int, FibOut] | None = None
    worst = FibOut(reason="fib: no range")
    for side, sign in (("SELL", -1), ("BUY", 1)):
        lo_view = lo_p.price if sign > 0 else -hi_p.price
        hi_v, lo_v, close_v, _, _ = _view_arrays(m5s, sign)
        fo = analyse_range(lo_view, rng, hi_v, lo_v, close_v, p)
        if fo.setup is not None and p.fib_count == "on":
            # R17: step 2 must hold at the edge: zone 12 % .. -27 % (88 % .. 127 % for the sell), on fib_tf.
            # SPEC-QUESTION: here step 2 is a filter only; the entry stays the plain limit at the edge.
            df = frames[p.fib_tf]
            _, _, cv, mv, rv = _view_arrays(df, sign)
            zone = (lo_view - RANGE_PAST * rng, lo_view + RANGE_EDGE * rng)
            c2 = Outcome(tf=p.fib_tf, reason="step2: no levels")
            if step2(c2, to_view(_zigzag(df), sign), cv, mv, rv, [zone], p) is None:
                fo = FibOut(c2.reason, {**fo.info, **c2.info})
        if fo.setup is not None:
            if best is None or abs(sign * fo.setup.entry_v - last) < abs(
                best[1] * best[2].setup.entry_v - last  # type: ignore[union-attr]
            ):
                best = (side, sign, fo)
        elif RANK[fo.reason] >= RANK[worst.reason]:
            worst = fo
    if best is None:
        return done(worst.reason, worst.info, "range")
    side, sign, fo = best
    s = fo.setup
    if s is None:  # not reachable: ``best`` only holds outcomes with a setup
        return done(fo.reason, fo.info, "range")
    log["side"] = side
    key = f"{side}|range|{h1.index[lo_p.pivot_pos]}|{h1.index[hi_p.pivot_pos]}"
    if key in used:
        return done("setup already used", fo.info, "range")
    s.lo_pos, s.hi_pos = lo_p.pivot_pos, hi_p.pivot_pos
    result = done(fo.reason, fo.info, "range")
    result.key = key
    result.decision = _fib_row(s, side, sign, now, pd.DatetimeIndex(h1.index), "H1", p)
    return result


def _fib_row(
    s: FibSetup, side: str, sign: int, now: pd.Timestamp, times: pd.DatetimeIndex, tf: str, p: Params,
) -> dict[str, str]:  # fmt: skip
    """The ledger row of a Fibo order (R13-R17), prices back in real terms."""
    th = times.tz_convert(TH)

    def real(v: float) -> float:
        return round(sign * v, 2)

    rng = s.hi_v - s.lo_v
    hc = fib_high_choice(p)
    lo_t = f"{th[s.lo_pos]:%d/%m %H:%M}" if s.lo_pos >= 0 else "range"
    hi_t = f"{th[s.hi_pos]:%d/%m %H:%M}" if s.hi_pos >= 0 else "range"
    if s.kind == "range":
        shape = "sell edge 88 %-127 %" if sign < 0 else "buy edge 12 %-(-27 %)"
        lo_name = f"range low @{lo_t}, high @{hi_t}"
        text = (
            f"bot2e fib range {shape}, no H1 side, {tf} pivots. {lo_name}; 0 % {real(s.lo_v):.2f}, "
            f"100 % {real(s.hi_v):.2f}; entry (plain limit) {real(s.entry_v):.2f}, "
            f"stop {real(s.stop_v):.2f}, "
            f"target {real(s.target_v):.2f} (the range's other edge, buffer, fib_count={p.fib_count}); "
            f"R {s.r:.2f} (net of {p.spread:g} spread)"
        )
        trig = ""
        entry, stop, target = real(s.entry_v), real(s.stop_v), real(s.target_v)
    else:
        levels = ", ".join(f"{x * 100:.1f} % {real(s.lo_v + x * rng):.2f}" for x in (0.236, 0.382, 0.618))
        which = (
            "highest fixed high of the descending run into L0 (the high the fall began from)"
            if hc == "start"
            else "fixed high immediately before L0"
        )
        h100_text = f"H100 = the {which} (fib_high {p.fib_high} -> {hc}); "
        text = (
            f"bot2e fib {tf} {side}, mode fib (leg {p.fib_leg}, side {p.fib_side}, count {p.fib_count}, "
            f"target {p.fib_target}, stop {p.fib_stop}, level {p.fib_level}), "
            f"{p.h1_mode} H1 side. "
            f"Leg low {real(s.lo_v):.2f}@{lo_t} (0 %), high {real(s.hi_v):.2f}@{hi_t} (100 %); "
            + h100_text
            + f"levels {levels}; "
            f"entry level {p.fib_entry * 100:.1f} % = {real(s.lo_v + p.fib_entry * rng):.2f}"
        )
    if s.count is not None:
        c = s.count
        pts = ", ".join(f"{real(q.price):.2f}@{th[q.pos]:%d/%m %H:%M}" for q in c.counted)
        text += (
            f"; zone count ({c.kind}, {len(c.counted)} lows: {pts}) in the Fibo zone "
            f"{real(c.band[0]):.2f}-{real(c.band[1]):.2f}, divergence on MACD {c.div_macd}, on RSI "
            f"{c.div_rsi}; " + "the entry is the level"
        )
    if s.kind == "leg":
        text += (
            f"; plain limit {real(s.entry_v):.2f}, stop {real(s.stop_v):.2f} (beyond the 0 %, or beyond "
            f"23.6 % for a 61.8 % entry; fib_stop {p.fib_stop}), "
            f"checks passed: R19 leg not run (withdraw beyond {real(s.hi_v):.2f}), R20 entry within "
            f"{p.max_entry_distance:g} USD of price, level band {p.fib_level}; "
            f"target {real(s.target_v):.2f}, R {s.r:.2f} (net of {p.spread:g} spread)"
        )
        trig = ""
        entry, stop, target = real(s.entry_v), real(s.stop_v), real(s.target_v)
    return _ledger_dict(
        now, side, f"{entry:.2f}", f"{stop:.2f}", f"{target:.2f}", trig, f"{text}. Parameters: {p.text()}"
    )


def _ledger_dict(
    now: pd.Timestamp, side: str, entry: str, stop: str, target: str, trigger: str, structure: str
) -> dict[str, str]:
    """The ledger row's fixed fields (spec section 6)."""
    t = now.tz_convert(TH)
    last_bar = t - pd.Timedelta(minutes=5)
    return {
        "id": "",  # numbered by the walker
        "cutoff_thai": f"{t:%Y-%m-%d} 07:00",
        "decided_at": f"{last_bar:%d/%m %H:%M}",
        "reader": READER,
        "side": side,
        "entry": entry,
        "stop": stop,
        "target": target,
        "fill": "", "exit": "", "why": "", "r_net": "",
        "structure": structure,
        "rules": "?????????",
        "conflict": "",
        "at_decision_r": "",
        "missed_by": "",
        "trigger": trigger,
        "setup": "+++++++",
    }  # fmt: skip


def _row(
    s: Setup, side: str, sign: int, now: pd.Timestamp, df: pd.DataFrame, p: Params
) -> dict[str, str]:  # fmt: skip
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
    tail = (
        f"Structure broken, higher low {real(s.lhl.price):.2f}@{times[s.lhl.pos]:%d/%m %H:%M}; "
        f"H_d={real(s.hd.price):.2f}"
    )
    tfs = s.tf
    high_word = "lowest low" if sign > 0 else "highest high"
    shape = {"count": f"count of {len(s.counted)}", "M": "M" if sign > 0 else "W"}[s.kind]
    structure = (
        f"bot2e {tfs} {side}, {p.h1_mode} H1 side. Level band {real(s.band[0]):.2f}-{real(s.band[1]):.2f}"
        f" (support in the view); {shape} at L*={real(s.lstar.price):.2f} ({high_word} of the counter-move). "
        f"Counted: {pts}. Divergence on MACD {s.div_macd}, on RSI {s.div_rsi}"
        f"{' (diverged anyway)' if s.kind == 'M' and s.div_macd and s.div_rsi else ''}. "
        f"{tail}. R {s.r:.2f} (net of {p.spread:g} spread). Parameters: {p.text()}"
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
    return {tf: frame(tf) for tf in ("H1", "H4", "M15", "M5")}


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


# The most orders live (pending or open) and the most filled-and-open at one bar in the last ``walk_days``.
PEAK: dict[str, int] = {"live": 0, "filled": 0}


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
    PEAK.update(live=0, filled=0)
    for day in days:
        midnight = pd.Timestamp(day, tz=TH)
        for _, a, b in WINDOWS:
            now = midnight + pd.Timedelta(minutes=a)
            end = midnight + pd.Timedelta(minutes=b)
            while now <= end:
                now_utc = now.tz_convert("UTC")
                frames = cut(full, now_utc)
                known = frames["M5"]
                live = filled = 0
                for r in written:  # live while score.py still calls it open (pending or filled)
                    if r["id"] in finished:
                        continue
                    scored = score(r, known, start_of(r, {}), p.spread)
                    if scored["why"] == "open":
                        live += 1
                        filled += 1 if scored.get("fill") else 0
                    else:
                        finished.add(r["id"])
                PEAK["live"], PEAK["filled"] = max(PEAK["live"], live), max(PEAK["filled"], filled)
                res = decide(frames, now_utc, p, frozenset(used), pending=live >= p.max_orders)
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
    ap.add_argument("--h1-tf", choices=("H1", "H4"), default=d.h1_tf)
    ap.add_argument("--h1-swings", type=int, choices=(2, 3), default=d.h1_swings)
    ap.add_argument("--entry-tfs", choices=("M5,M15", "M15", "M5"), default=d.entry_tfs)
    ap.add_argument(
        "--div-mode",
        choices=("both", "one"),
        default=d.div_mode,
        help="'one' (the owner's rule, R11) or 'both'",
    )
    ap.add_argument(
        "--mode", choices=("2e", "fib"), default=d.mode, help="'fib' = the owner's Fibonacci (R13-R17)"
    )
    ap.add_argument("--fib-tf", choices=("M15", "M5"), default=d.fib_tf)
    ap.add_argument("--fib-entry", type=float, default=d.fib_entry, help="entry level, 0 %% at the leg's low")
    ap.add_argument("--fib-target", choices=("level", "high", "ext127", "ext161"), default=d.fib_target)
    ap.add_argument("--fib-count", choices=("off", "on"), default=d.fib_count)
    ap.add_argument("--fib-range", choices=("off", "on"), default=d.fib_range)
    ap.add_argument(
        "--fib-leg",
        choices=("counter",),
        default=d.fib_leg,
        help="R18 'counter' (the only leg)",
    )
    ap.add_argument("--fib-high", choices=("start", "latest"), default=d.fib_high)
    ap.add_argument("--max-orders", type=int, default=d.max_orders, help="orders live at once (research)")
    ap.add_argument("--fib-side", choices=("h1",), default=d.fib_side)
    ap.add_argument("--fib-stop", choices=("line", "swing"), default=d.fib_stop)
    ap.add_argument("--fib-level", choices=("off", "on"), default=d.fib_level)
    ap.add_argument("--max-entry-distance", type=float, default=d.max_entry_distance)
    ap.add_argument("--min-r", type=float, default=d.min_r)
    ap.add_argument("--trigger-offset", type=float, default=d.trigger_offset)
    ap.add_argument("--stop-buffer", type=float, default=d.stop_buffer)
    ap.add_argument("--target-buffer", type=float, default=d.target_buffer)
    ap.add_argument("--band-frac", type=float, default=d.band_frac)
    ap.add_argument("--band-legs", type=int, default=d.band_legs)
    ap.add_argument("--level-min-age-h", type=float, default=d.level_min_age_h)
    ap.add_argument("--level-bars", type=int, default=d.level_bars)
    ap.add_argument("--counter-pivots", type=int, default=d.counter_pivots)
    a = ap.parse_args(argv)
    params = Params(
        h1_mode=a.h1_mode,
        h1_tf=a.h1_tf,
        h1_swings=a.h1_swings,
        entry_tfs=a.entry_tfs,
        div_mode=a.div_mode,
        mode=a.mode,
        fib_tf=a.fib_tf,
        fib_entry=a.fib_entry,
        fib_target=a.fib_target,
        fib_count=a.fib_count,
        fib_range=a.fib_range,
        fib_leg=a.fib_leg,
        fib_side=a.fib_side,
        fib_stop=a.fib_stop,
        fib_level=a.fib_level,
        max_entry_distance=a.max_entry_distance,
        max_orders=a.max_orders,
        fib_high=a.fib_high,
        min_r=a.min_r,
        trigger_offset=a.trigger_offset,
        stop_buffer=a.stop_buffer,
        target_buffer=a.target_buffer,
        band_frac=a.band_frac,
        band_legs=a.band_legs,
        level_min_age_h=a.level_min_age_h,
        level_bars=a.level_bars,
        counter_pivots=a.counter_pivots,
    )
    run(a.first, a.last, params)


if __name__ == "__main__":
    main()
