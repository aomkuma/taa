"""Bot 2e: the owner's setup (eye/METHOD.md section 2e) as a bot, written to eye/BOT_SPEC.md.

It walks real trading days bar by bar on the stored gold data, as ``eye/walk.py`` does by hand. At every
closed M5 bar inside the owner's windows it applies the seven steps of 2e; when steps 1-4 hold it writes a
stop-limit (or limit) order with its stop and target into ``eye/bot_ledger.csv``, which ``eye/score.py``
scores and ``eye/money.py --ledger bot_ledger.csv`` reads in money.

    python eye/bot2e.py --from 2026-04-06 --to 2026-04-07              # mode fib (eye/BOT_RULES.md)
    python eye/bot2e.py --from 2026-04-06 --to 2026-04-07 --mode 2e    # the record
    python eye/bot2e.py --from 2026-04-06 --to 2026-04-07 --mode 2e --h1-mode lows --min-r 1

**No look-ahead is structural.** ``decide`` takes frames that are already cut to the bars closed at ``now``
(``cut`` does the cutting, and ``decide`` refuses a frame that holds a later bar); the ZigZag is run on that
cut, and only its fixed pivots are used - never the point MT5 still moves.

Every definition the owner did not give is a field of ``Params``, marked ``[Claude]`` there, with the
spec's default, and its value is written into every decision's ``structure`` text.

Mode "fib" implements eye/BOT_RULES.md (the specification in force); mode "2e" is the earlier setup, kept as a
record and untouched.

A BUY and a SELL share one code path: a SELL is the BUY seen in a mirror (prices negated, highs and lows
swapped), so the two cannot drift apart. Names ending ``_v`` are in the view (a SELL's are negated).
"""

from __future__ import annotations

import argparse
import csv
import importlib
import re
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
    # the fib path (BOT_RULES rule 14): the lean, the leg, each rule's state and numbers, the order
    "lean", "leg", "r10", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r11", "trend_legs", "order", "stop",
    "target", "ladder", "r",
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
# What mode "2e" has always been given (``decide`` trims to it); ``cut`` keeps more for the fib path, which
# reads the last 1,500 closed bars of each timeframe and the M5 bars after a leg (an M15 leg can be 4,500
# M5 bars old).
FRAME_BARS_2E = {tf: SHOWN[tf] + WARMUP for tf in ("H1", "M15", "M5")} | {"H4": 600}
FRAME_BARS = {"H4": 1500, "H1": SHOWN["H1"] + WARMUP, "M15": SHOWN["M15"] + WARMUP, "M5": 4700}


@dataclass(frozen=True)
class Params:
    """Every parameter the owner did not give. ``[Claude]`` marks a definition made by Claude. The fields up
    to ``spread`` are mode "2e"'s (a record); from ``mode`` on are the fib path's, with the defaults of
    eye/BOT_RULES.md's parameter table."""

    h1_mode: str = "strict"  # [Claude] how the H1 trend is read: "strict" or "lows" (spec step 1)
    level_min_age_h: float = 24.0  # [Claude] a level's pivot is at least this many hours old ("earlier days")
    level_bars: int = 500  # [Claude] levels come from the last this-many bars of the major timeframe
    band_frac: float = 0.10  # [Claude] half-width of a level band = this x median height of 20 legs
    band_legs: int = 20  # [Claude] how many ZigZag legs the median height is taken over
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
    mode: str = "fib"  # "fib" (eye/BOT_RULES.md, the default) | "2e" (a record only - not run)
    # --- the fib path ---
    fib_tf: str = "M5"  # [Claude] the setup timeframe: the leg (rule 2) and the range (rule 11)
    fib_entry: float = 0.618  # the owner's levels 0.618 / 0.382 / 0.236; default [Claude] until the real run
    fib_early: float = 0.0  # [Claude] x the leg above the level (the owner's idea of getting in early)
    fib_stop: str = "line"  # line (owner) | swing, line_tight ([Claude] variants); rule 7
    fib_count: str = "off"  # owner: "try both"; the default [Claude]; rule 4
    max_trend_legs: int = 5  # [Claude] rule 5: a trend of this many legs or more is not chased
    major_tf: str = "H4"  # [Claude] the timeframe the bands (rule 8) are read on
    max_entry_frac: float = 0.25  # [Claude] rule 9: |price - order price| at most this x the leg
    fib_range: str = "on"  # [Claude] rule 11: trade the range when there is no lean and no M5 trend
    max_orders: int = 1  # [Claude] orders live (pending or open) at once; a new one needs fewer than this
    order_life_bars: int = 24  # [Claude] rule 12: M5 bars an order may wait for its fill (last included)

    def __post_init__(self) -> None:
        if self.max_orders < 1:
            raise ValueError(f"max_orders must be at least 1, got {self.max_orders!r}")
        if self.order_life_bars < 1:
            raise ValueError(f"order_life_bars must be at least 1, got {self.order_life_bars!r}")
        for name, allowed in (
            ("mode", ("2e", "fib")),
            ("fib_tf", ("M5", "M15")),
            ("fib_entry", (0.618, 0.382, 0.236)),
            ("fib_early", (0, 0.10)),
            ("fib_stop", ("line", "swing", "line_tight")),
            ("fib_count", ("off", "on")),
            ("max_trend_legs", (5, 3)),
            ("max_entry_frac", (0.15, 0.25, 0.35)),
            ("major_tf", ("H4", "H1")),
            ("fib_range", ("on", "off")),
        ):
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, got {getattr(self, name)!r}")
        # Combinations without meaning (BOT_RULES, Parameters): refused at start.
        if self.fib_early > 0 and (self.fib_entry != 0.382 or self.fib_stop != "line_tight"):
            raise ValueError("fib_early above 0 needs fib_entry 0.382 and fib_stop line_tight")
        if self.fib_stop == "swing" and self.fib_entry != 0.618:
            raise ValueError("fib_stop swing needs fib_entry 0.618")
        if self.fib_stop == "line_tight" and not self.fib_early > 0:
            raise ValueError("fib_stop line_tight needs fib_early above 0")

    def text(self) -> str:
        """The [Claude] parameters as they are written into a decision (the mode's own)."""
        if self.mode == "fib":
            return (
                f"mode={self.mode} fib_tf={self.fib_tf} fib_entry={self.fib_entry:g} "
                f"fib_early={self.fib_early:g} fib_stop={self.fib_stop} fib_count={self.fib_count} "
                f"max_trend_legs={self.max_trend_legs} major_tf={self.major_tf} level_bars={self.level_bars} "
                f"level_min_age_h={self.level_min_age_h:g} band_frac={self.band_frac:g} "
                f"band_legs={self.band_legs} max_entry_frac={self.max_entry_frac:g} "
                f"fib_range={self.fib_range} stop_buffer={self.stop_buffer:g} "
                f"target_buffer={self.target_buffer:g} spread={self.spread:g} max_orders={self.max_orders} "
                f"order_life_bars={self.order_life_bars} min_r={self.min_r:g}"
            )
        return (
            f"h1_mode={self.h1_mode} level_min_age_h={self.level_min_age_h:g} level_bars={self.level_bars} "
            f"band_frac={self.band_frac:g} band_legs={self.band_legs} counter_pivots={self.counter_pivots} "
            f"trigger_offset={self.trigger_offset:g} stop_buffer={self.stop_buffer:g} "
            f"target_buffer={self.target_buffer:g} min_r={self.min_r:g} h1_tf={self.h1_tf} "
            f"h1_swings={self.h1_swings} entry_tfs={self.entry_tfs} div_mode={self.div_mode} "
            f"mode={self.mode} max_orders={self.max_orders}"
        )


# The reasons a bar can end without an order, in the order the steps run; a later one means the bar got
# further. ``reason`` in the log is always one of these, or "order written". The fib path's come first
# (BOT_RULES' order of evaluation); the 2e path's keep their relative order.
REASONS = [
    "market closed", "outside window", "warm-up", "order pending",
    "fib: no range", "fib: no live leg", "fib: leg or range already used",
    "fib: leg has run (100 % traded)", "fib: M5 trend (H100 not above the M5 high)",
    "fib: against the H1 lean", "fib: count outside 3-5 and no M", "fib: no divergence",
    "fib: trend run at the limit", "fib: no bounce above the order price",
    "fib: price not above the order price", "fib: no target above the order price",
    "fib: range broken", "fib: price outside the range zone",
    "step1: no side",
    "step2: no levels",
    "step2: no counter-move", "step2: L* not in a support band", "step2: count outside 3-5 and no M",
    "step2: no divergence", "step3: structure not broken",
    "step3: no higher low yet",
    "step4: no H_d", "step5: price below the higher low", "step7: no target level",
    "reward under 2R", "setup already played out", "fib: order price too far from price",
    "setup already used", "order written",
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


# --- the fib path (eye/BOT_RULES.md): rules 1-13 ---------------------------------------------------------
#
# Prices here are in the view of the side being tried (a SELL's are negated, highs and lows swapped) except
# rule 11, which is written for both sides and is not mirrored. ``real`` turns a view price back.

FIB_BARS = 1500  # BOT_RULES "Words used": fixed pivots are read on the last 1,500 closed bars of a timeframe
FIB_LEVELS = (0.236, 0.382, 0.618)
EXT_127, EXT_161 = 1.272, 1.618
RANGE_SELL, RANGE_BUY = 0.88, 0.12  # rule 11: the limit levels (a share of the range above its low)
RANGE_PAST_LOW, RANGE_PAST_HIGH = -0.27, 1.27  # rule 11: the stops, and (no buffer) the break levels
M_COUNT, COUNT_MIN, COUNT_MAX = 2, 3, 5  # rule 4: the owner's M, and "3 to 5 peaks"
EPS = 1e-9  # float noise at an exact boundary is not a refusal


def _real(sign: int, v: float) -> float:
    return round(sign * v, 2)


def _tt(ts: pd.Timestamp) -> str:
    """A time as the owner reads it: Thai, day/month hour:minute."""
    return f"{ts.tz_convert(TH):%d/%m %H:%M}"


@dataclass
class FibSetup:
    """An order the fib path found. Prices are real (a SELL's too); ``marker`` is the withdrawal marker that
    ``eye/score.py`` reads from the row, ``detail`` the text that names the leg or the range."""

    kind: str  # "leg" or "range"
    side: str
    tf: str
    key: str
    order: float
    stop: float
    target: float
    r: float
    step: str  # the ladder step ("1.618", "1.272", "band") or "range edge"
    gap: float  # |the price - the order price|, for rule 13
    marker: str
    detail: str


@dataclass
class FibOut:
    reason: str
    info: dict[str, str] = field(default_factory=dict)
    setup: FibSetup | None = None


@dataclass
class LegData:
    """Everything rules 2-10 read for one side, in that side's view. The arrays are positional: a pivot's
    ``pos`` indexes ``times`` / ``close_v`` (setup timeframe) or, for ``m5_pv``, ``m5_ptimes``."""

    side: str
    sign: int
    tf: str
    pv: list[VPivot]
    times: pd.DatetimeIndex
    close_v: np.ndarray
    macd_v: np.ndarray
    rsi_v: np.ndarray
    m5_times: pd.DatetimeIndex
    m5_hi_v: np.ndarray
    m5_lo_v: np.ndarray
    price_v: float
    m5_pv: list[VPivot]
    m5_ptimes: pd.DatetimeIndex
    bands_v: list[tuple[float, float]]
    lean: str | None
    lean_text: str


# --- rule 1: the H1 lean ------------------------------------------------------------------------------------


def lean_view(pv: Sequence[VPivot], hi_v: np.ndarray, close_v: np.ndarray) -> VPivot | None:
    """Rule 1 for a BUY lean, in the view: ``Lf`` = the latest fixed LOW, ``Hp`` = the latest fixed HIGH with
    a time before it (none - no lean); the last close strictly above ``Lf``, and some bar after ``Lf``'s
    pivot bar with a high strictly above ``Hp``. Returns ``Lf`` when the lean holds. A SELL lean is this on
    the mirror."""
    lows = [q for q in pv if q.low]
    if not lows:
        return None
    lf = lows[-1]
    hp = next((q for q in reversed(pv) if not q.low and q.pos < lf.pos), None)
    if hp is None or not float(close_v[-1]) > lf.price:
        return None
    if not bool(np.any(hi_v[lf.pos + 1 :] > hp.price)):
        return None
    return lf


def h1_lean(h1: pd.DataFrame, piv: Sequence[Swing]) -> tuple[str | None, str]:
    """Rule 1: "BUY" / "SELL" / None from the closed H1 bars and their fixed pivots, and a text for the
    record. Both holding: the one whose pivot (``Hf`` / ``Lf``) is later."""
    held: dict[str, VPivot] = {}
    for side, sign in (("BUY", 1), ("SELL", -1)):
        hi_v = h1.high.to_numpy(dtype=np.float64) if sign > 0 else -h1.low.to_numpy(dtype=np.float64)
        close_v = sign * h1.close.to_numpy(dtype=np.float64)
        got = lean_view(to_view(piv, sign), hi_v, close_v)
        if got is not None:
            held[side] = got
    if not held:
        return None, "none"
    side = max(held, key=lambda s: held[s].pos)
    f = held[side]
    sign = 1 if side == "BUY" else -1
    kind = "Lf" if side == "BUY" else "Hf"
    return side, f"{side} ({kind} {_real(sign, f.price):.2f}@{_tt(pd.Timestamp(h1.index[f.pos]))})"


# --- rule 2: the counter-leg --------------------------------------------------------------------------


def fib_leg(pv: Sequence[VPivot], close_v: np.ndarray) -> tuple[VPivot, VPivot, list[VPivot]] | None:
    """Rule 2 for a BUY in the view. ``L0`` = the latest fixed LOW that is strictly lower than every fixed low
    after it, has at least one fixed low after it, and has no setup-timeframe close below it after its pivot
    bar. ``H100`` = the highest fixed HIGH from the high pivot immediately before the run's first low
    (inclusive) up to ``L0``. Returns (L0, H100, the run's lows, L0 last), or None."""
    lows = [i for i, q in enumerate(pv) if q.low]
    k = None
    # SPEC-QUESTION: "the latest fixed LOW that meets all three" - a later low that fails the close test is
    # skipped and an earlier low that meets all three is taken (the rule does not say the leg then ends).
    for a in range(len(lows) - 2, -1, -1):
        q = pv[lows[a]]
        if not all(q.price < pv[j].price for j in lows[a + 1 :]):
            continue
        after = close_v[q.pos + 1 :]
        if after.size and float(after.min()) < q.price:
            continue
        k = a
        break
    if k is None:
        return None
    first = k
    while first > 0 and pv[lows[first - 1]].price > pv[lows[first]].price:
        first -= 1
    run = [pv[j] for j in lows[first : k + 1]]
    start = lows[first] - 1 if lows[first] >= 1 and not pv[lows[first] - 1].low else lows[first]
    highs = [q for q in pv[start : lows[k]] if not q.low]
    if not highs:
        return None
    top = highs[0]
    for q in highs:
        if q.price > top.price:
            top = q
    return pv[lows[k]], top, run


# --- rules 3 and 5: the trend on M5 -------------------------------------------------------------------


def m5_trend(
    m5_pv: Sequence[VPivot], m5_ptimes: pd.DatetimeIndex, t100: pd.Timestamp, h100: float
) -> tuple[VPivot | None, int]:  # fmt: skip
    """Rules 3 and 5 for a BUY in the view, on the M5 fixed pivots. Returns (the latest fixed M5 HIGH whose
    time is strictly before ``H100``'s, or None; the trend's legs). Legs = 1 + the number of fixed M5 highs
    before ``H100``, latest first, each strictly lower than the one counted before it (``H100`` first)."""
    highs = [q for q in m5_pv if not q.low and m5_ptimes[q.pos] < t100]
    ref = highs[-1] if highs else None
    legs, prev = 1, h100
    for q in reversed(highs):
        if q.price < prev:
            legs += 1
            prev = q.price
        else:
            break
    return ref, legs


# --- rule 4: the count --------------------------------------------------------------------------------


def run_divergence(run: Sequence[VPivot], macd_v: np.ndarray, rsi_v: np.ndarray) -> tuple[bool, bool]:
    """Divergence at L0 against the previous low of the run: MACD main / RSI at L0's pivot bar higher than at
    the previous low's, setup timeframe, in the view. A run of one low has no previous low."""
    if len(run) < 2:
        return False, False
    a, b = run[-2], run[-1]
    return (
        _div(b.price, a.price, float(macd_v[b.pos]), float(macd_v[a.pos])),
        _div(b.price, a.price, float(rsi_v[b.pos]), float(rsi_v[a.pos])),
    )


def count_reason(n: int, d_macd: bool, d_rsi: bool) -> str:
    """Rule 4 with ``fib_count`` on: "" when the run passes, else the reason. 3 to 5 lows need divergence on
    at least one oscillator; exactly 2 lows are the owner's M and pass without it; 1 and 6 or more fail."""
    if n == M_COUNT:
        return ""
    if COUNT_MIN <= n <= COUNT_MAX:
        return "" if (d_macd or d_rsi) else "fib: no divergence"
    return "fib: count outside 3-5 and no M"


# --- rules 7 and 8: the stop and the target -----------------------------------------------------------


def fib_stop_v(p: Params, pv: Sequence[VPivot], l0: VPivot, leg: float) -> float:
    """Rule 7 for a BUY in the view. 0.382 / 0.236: ``L0 - stop_buffer``. 0.618: the 23.6 % level - buffer
    (line); swing: one buffer below the lower of that level and the lowest fixed setup-timeframe low after
    ``L0`` (none: the line stop). ``line_tight``: the 0.382 level - buffer."""
    if p.fib_stop == "line_tight":
        return l0.price + 0.382 * leg - p.stop_buffer
    if p.fib_entry != 0.618:
        return l0.price - p.stop_buffer
    line = l0.price + 0.236 * leg
    if p.fib_stop == "swing":
        later = [q.price for q in pv if q.low and q.pos > l0.pos]
        if later:
            return min(line, min(later)) - p.stop_buffer
    return line - p.stop_buffer


def fib_ladder(
    p: Params, l0: float, leg: float, order: float, bands_v: Sequence[tuple[float, float]]
) -> tuple[float, str]:  # fmt: skip
    """Rule 8 for a BUY in the view: ONE step by the bands, no fall-through. A band is "in the way" when its
    near (lower) edge lies strictly above the order price and strictly below the raw extension tested."""
    raw127, raw161 = l0 + EXT_127 * leg, l0 + EXT_161 * leg
    way = [b[0] for b in bands_v if order < b[0] < raw161]
    if not way:
        return raw161 - p.target_buffer, "1.618"
    if not any(e < raw127 for e in way):
        return raw127 - p.target_buffer, "1.272"
    return min(way) - p.target_buffer, "band"


def planned_r(order: float, stop: float, target: float, spread: float) -> float:
    """R of a BUY in the view: (target - order - spread) / (order - stop); minus infinity with no risk."""
    risk = order - stop
    return (target - order - spread) / risk if risk > 0 else float("-inf")


# --- one side's leg: rules 2-10 in the order of evaluation --------------------------------------------


def analyse_leg(d: LegData, p: Params, used: frozenset[str] = frozenset()) -> FibOut:
    """One side's latest leg through the order of evaluation (BOT_RULES): 2 -> 10 -> 3 (and the lean) -> 4
    -> 5 -> 6 -> 7 -> 8 -> 6 (played out) -> 9. Returns the order, or the reason for none."""
    out = FibOut("fib: no live leg")
    got = fib_leg(d.pv, d.close_v)
    if got is None:
        return out
    l0, h100, run = got
    leg = h100.price - l0.price
    t0, t100 = pd.Timestamp(d.times[l0.pos]), pd.Timestamp(d.times[h100.pos])
    s = d.sign
    key = f"{d.side}|{d.tf}|{t0}|{t100}"
    out.info["leg"] = (
        f"L0 {_real(s, l0.price):.2f}@{_tt(t0)} H100 {_real(s, h100.price):.2f}@{_tt(t100)} leg {leg:.2f}"
    )
    out.info["count"] = str(len(run))
    out.info["pivots"] = " ".join(f"{_real(s, q.price):.2f}" for q in run)
    if key in used:
        out.reason = "fib: leg or range already used"
        return out

    # 10: a leg that has run is over (M5 bars whose open is at or after L0's pivot bar's close).
    k = int(d.m5_times.searchsorted(t0 + STEP[d.tf], side="left"))
    peak = float(d.m5_hi_v[k:].max()) if d.m5_hi_v[k:].size else float("-inf")
    extreme = "high" if s > 0 else "low"
    out.info["r10"] = f"M5 {extreme} after L0 {_real(s, peak):.2f} vs H100 {_real(s, h100.price):.2f}"
    out.reason = "fib: leg has run (100 % traded)"
    if peak > h100.price:
        return out

    # 3: the M5 trend, then the lean.
    ref, legs = m5_trend(d.m5_pv, d.m5_ptimes, t100, h100.price)
    out.reason = "fib: M5 trend (H100 not above the M5 high)"
    if ref is None:
        out.info["r3"] = "no fixed M5 high before H100"
        return out
    t_ref = _tt(pd.Timestamp(d.m5_ptimes[ref.pos]))
    word = "high" if s > 0 else "low"
    out.info["r3"] = f"H100 {_real(s, h100.price):.2f} vs M5 {word} {_real(s, ref.price):.2f}@{t_ref}"
    if not h100.price > ref.price:
        return out
    out.reason = "fib: against the H1 lean"
    if d.lean is not None and d.lean != d.side:
        return out

    # 4: the count (a filter, off by default); the divergence is recorded either way.
    d_macd, d_rsi = run_divergence(run, d.macd_v, d.rsi_v)
    out.info["div_macd"], out.info["div_rsi"] = str(d_macd), str(d_rsi)
    out.info["r4"] = f"{len(run)} lows, MACD {d_macd}, RSI {d_rsi}, fib_count {p.fib_count}"
    if p.fib_count == "on":
        why = count_reason(len(run), d_macd, d_rsi)
        if why:
            out.reason = why
            return out

    # 5: the trend run, no chasing.
    out.info["r5"] = f"{legs} legs (limit {p.max_trend_legs})"
    out.info["trend_legs"] = str(legs)
    out.reason = "fib: trend run at the limit"
    if legs >= p.max_trend_legs:
        return out

    # 6: the level, the order price, the bounce.
    x = p.fib_entry
    order = l0.price + (x + p.fib_early) * leg
    first = np.flatnonzero(d.m5_hi_v[k:] > order)
    out.info["r6"] = (
        f"order price {_real(s, order):.2f} (level {x:g} + early {p.fib_early:g}), "
        f"price {_real(s, d.price_v):.2f}"
    )
    out.reason = "fib: no bounce above the order price"
    if first.size == 0:
        return out
    j = k + int(first[0])  # the first M5 bar above the order price
    out.reason = "fib: price not above the order price"
    if not d.price_v > order:
        return out

    # 7 and 8: the stop and the target.
    stop = fib_stop_v(p, d.pv, l0, leg)
    target, step = fib_ladder(p, l0.price, leg, order, d.bands_v)
    out.info["r7"] = f"stop {_real(s, stop):.2f} ({p.fib_stop})"
    out.info["r8"] = f"target {_real(s, target):.2f} (step {step})"
    out.reason = "fib: no target above the order price"
    if not target > order:
        return out
    r = planned_r(order, stop, target, p.spread)
    out.info["r"] = f"{r:.2f}"
    out.reason = "reward under 2R"
    if r < p.min_r:
        return out

    # 6 again: played out - the target from the first bar above the order price on, the stop from the next.
    out.reason = "setup already played out"
    if float(d.m5_hi_v[j:].max()) >= target or (
        d.m5_lo_v[j + 1 :].size and float(d.m5_lo_v[j + 1 :].min()) <= stop
    ):
        return out

    # 9: the order price must be reachable.
    gap = abs(d.price_v - order)
    out.info["r9"] = (
        f"{gap:.2f} from the price, limit {p.max_entry_frac:g} x {leg:.2f} = {p.max_entry_frac * leg:.2f}"
    )
    out.reason = "fib: order price too far from price"
    if gap > p.max_entry_frac * leg + EPS:
        return out

    levels = ", ".join(f"{q * 100:.1f} % {_real(s, l0.price + q * leg):.2f}" for q in FIB_LEVELS)
    pts = ", ".join(f"{_real(s, q.price):.2f}@{_tt(pd.Timestamp(d.times[q.pos]))}" for q in run)
    h100_real = _real(s, h100.price)
    detail = (
        f"Lean {d.lean_text}. Leg: L0 {_real(s, l0.price):.2f}@{_tt(t0)} (0 %), "
        f"H100 {h100_real:.2f}@{_tt(t100)} (100 %), leg {leg:.2f}; levels {levels}; "
        f"run of {len(run)} lows ({pts}), divergence on MACD {d_macd}, "
        f"on RSI {d_rsi}, fib_count {p.fib_count}. M5 trend: H100 {h100_real:.2f} beyond the M5 {word} "
        f"{_real(s, ref.price):.2f}@{_tt(pd.Timestamp(d.m5_ptimes[ref.pos]))}; {legs} trend legs (limit "
        f"{p.max_trend_legs}). Entry level {x * 100:.1f} % = {_real(s, l0.price + x * leg):.2f}, order price "
        f"{_real(s, order):.2f} (fib_early {p.fib_early:g}); stop {_real(s, stop):.2f} ({p.fib_stop}); "
        f"target {_real(s, target):.2f} (ladder step {step}); planned R {r:.2f} "
        f"(net of {p.spread:g} spread). "
        f"Order price {gap:.2f} from the price, limit {p.max_entry_frac * leg:.2f}"
    )
    out.setup = FibSetup(
        "leg", d.side, d.tf, key, _real(s, order), _real(s, stop), _real(s, target), r, step, gap,
        f"withdraw beyond {h100_real:.2f}", detail,
    )  # fmt: skip
    out.reason = "order written"
    return out


# --- rule 11: the range -------------------------------------------------------------------------------


def m5_has_trend(m5_pv_real: Sequence[VPivot]) -> bool | None:
    """Rule 11's M5 test on the real fixed M5 pivots: the latest two highs and the latest two lows. True when
    they are "higher high and higher low" or "lower high and lower low"; None when either kind has fewer
    than two."""
    highs = [q.price for q in m5_pv_real if not q.low]
    lows = [q.price for q in m5_pv_real if q.low]
    if len(highs) < 2 or len(lows) < 2:
        return None
    up = highs[-1] > highs[-2] and lows[-1] > lows[-2]
    down = highs[-1] < highs[-2] and lows[-1] < lows[-2]
    return up or down


def analyse_range(
    lo: float, hi: float, price: float, closes_after: np.ndarray, p: Params, tf: str
) -> FibOut:  # fmt: skip
    """Rule 11, real prices (not mirrored): the range ``lo``..``hi``, the last M5 close ``price``, the setup-
    timeframe closes after the later pivot. SELL limit at 0.88 while 0 < level < 0.88, BUY limit at 0.12 while
    0.12 < level < 1; at least ``min_r``; rule 9 with the range's height; of the two the nearer, then the
    BUY."""
    out = FibOut("fib: range broken")
    h = hi - lo
    # SPEC-QUESTION: the floor (min_r) and the reach (rule 9) are tested on each of the two orders before the
    # nearer is chosen (rule 11 says "if both qualify, the nearer"; whether a refused one still counts is
    # open).
    if h <= 0:
        out.reason = "fib: no range"
        return out
    brk_lo, brk_hi = lo + RANGE_PAST_LOW * h, lo + RANGE_PAST_HIGH * h
    if closes_after.size and (float(closes_after.min()) < brk_lo or float(closes_after.max()) > brk_hi):
        return out
    level = (price - lo) / h
    out.info["r11"] = f"range {lo:.2f}-{hi:.2f}, price level {level:.2f}"
    # SPEC-QUESTION: the break levels are written to 4 decimals, not 2, so the scorer's strict test is the
    #  bot's.
    marker = f"range break {tf} close beyond {brk_lo:.4f} / {brk_hi:.4f}"
    out.reason = "fib: price outside the range zone"
    cands: list[FibSetup] = []
    worst = out.reason
    for side in ("BUY", "SELL"):
        if side == "BUY":
            ok = RANGE_BUY < level < 1
            order, stop, target = lo + RANGE_BUY * h, brk_lo - p.stop_buffer, hi - p.target_buffer
            r = (target - order - p.spread) / (order - stop)
        else:
            ok = 0 < level < RANGE_SELL
            order, stop, target = lo + RANGE_SELL * h, brk_hi + p.stop_buffer, lo + p.target_buffer
            r = (order - target - p.spread) / (stop - order)
        if not ok:
            continue
        why = ""
        if r < p.min_r:
            why = "reward under 2R"
        elif abs(price - order) > p.max_entry_frac * h + EPS:
            why = "fib: order price too far from price"
        if why:
            if RANK[why] > RANK[worst]:
                worst = why
            continue
        detail = (
            f"Range: low {lo:.2f}, high {hi:.2f} (0 % at the low), height {h:.2f}; no H1 lean, no M5 trend. "
            f"{side} limit {order:.2f} at {(order - lo) / h * 100:.0f} %, stop {stop:.2f}, "
            f"target {target:.2f} "
            f"(the far edge); planned R {r:.2f} (net of {p.spread:g} spread); price level {level:.2f}, order "
            f"price {abs(price - order):.2f} from the price, limit {p.max_entry_frac * h:.2f}"
        )
        cands.append(
            FibSetup(
                "range",
                side,
                tf,
                "",
                order,
                stop,
                target,
                r,
                "range edge",
                abs(price - order),
                marker,
                detail,
            )
        )
    if not cands:
        out.reason = worst
        return out
    out.setup = choose(cands)
    out.reason = "order written"
    return out


def choose(cands: Sequence[FibSetup]) -> FibSetup:
    """Rule 13: of several orders the smaller |the price - the order price|; then a BUY before a SELL."""
    return min(cands, key=lambda c: (c.gap, 0 if c.side == "BUY" else 1))


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
    windowed: bool = True,
) -> Result:
    """Apply the rules at ``now`` to frames already cut to the bars closed then (``cut``): mode "2e" the seven
    steps, mode "fib" eye/BOT_RULES.md. ``used`` holds setups already written; ``pending`` is true while
    ``max_orders`` orders are live; ``windowed`` False switches the window test off (the acceptance cases)."""
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
    if windowed and not window:
        return done("outside window")
    if p.mode == "fib":
        return _decide_fib(frames, now, p, used, pending, log, done)
    # mode "2e" reads exactly the frames it always has (``cut`` keeps more, for the fib path)
    frames = {tf: df.tail(FRAME_BARS_2E[tf]) for tf, df in frames.items()}
    if any(len(frames[tf]) < WARMUP for tf in ("H1", "M15", "M5")):
        return done("warm-up")
    if pending:
        return done("order pending")

    h1 = frames["H1"]
    h1_piv = _zigzag(h1)
    side_piv = h1_piv if p.h1_tf == "H1" else _zigzag(frames[p.h1_tf])
    side = h1_side(side_piv, float(m5.close.iloc[-1]), p.h1_mode, p.h1_swings)
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


def _hl_view(df: pd.DataFrame, sign: int) -> tuple[np.ndarray, np.ndarray]:
    """high and low of a frame in the view (a SELL's: negated, swapped), without the oscillators."""
    hi = df.high.to_numpy(dtype=np.float64)
    lo = df.low.to_numpy(dtype=np.float64)
    return (hi, lo) if sign > 0 else (-lo, -hi)


@dataclass
class FibInputs:
    """What the fib path reads at one ``now``: the lean, one ``LegData`` per side, and the setup timeframe's
    own frame, pivots and times (for the range)."""

    lean: str | None
    lean_text: str
    datas: list[LegData]
    df: pd.DataFrame
    times: pd.DatetimeIndex
    zz: list[Swing]
    m5_zz: list[Swing]
    price: float


def fib_inputs(frames: dict[str, pd.DataFrame], now: pd.Timestamp, p: Params) -> FibInputs:
    """Cut every timeframe to its last 1,500 closed bars, read the fixed pivots, the lean (rule 1) and the
    bands (rule 8), and put each side in its view. ``frames`` are already cut to the bars closed at
    ``now``."""
    # SPEC-QUESTION: MACD / RSI are computed over the same last 1,500 closed bars as the pivots (the rules
    #  do not
    # give the series length); ``cut`` keeps 4,700 M5 bars so an M15 leg's L0 (up to 1,500 M15 bars back) has
    # its
    # M5 bars for rules 6 and 10.
    h1 = frames["H1"].tail(FIB_BARS)
    lean, lean_text = h1_lean(h1, _zigzag(h1))
    tf = p.fib_tf
    df = frames[tf].tail(FIB_BARS)
    times = pd.DatetimeIndex(df.index)
    zz = _zigzag(df)
    m5_full = frames["M5"]
    m5_tail = m5_full.tail(FIB_BARS)
    m5_zz = _zigzag(m5_tail)
    m5_ptimes = pd.DatetimeIndex(m5_tail.index)
    major = frames[p.major_tf].tail(FIB_BARS)
    bands = h1_bands(_zigzag(major), len(major), now, p)
    macd = macd_mt5(df.close)["main"].to_numpy(dtype=np.float64)
    rs = rsi(df.close, 14).to_numpy(dtype=np.float64)
    price = float(m5_full.close.iloc[-1])
    m5_times = pd.DatetimeIndex(m5_full.index)
    datas: list[LegData] = []
    for side, sign in (("BUY", 1), ("SELL", -1)):
        bands_v = sorted((min(sign * lo, sign * hi), max(sign * lo, sign * hi)) for lo, hi in bands)
        m5_hi_v, m5_lo_v = _hl_view(m5_full, sign)
        datas.append(
            LegData(
                side=side,
                sign=sign,
                tf=tf,
                pv=to_view(zz, sign),
                times=times,
                close_v=sign * df.close.to_numpy(dtype=np.float64),
                macd_v=sign * macd,
                rsi_v=sign * rs + (0.0 if sign > 0 else 100.0),
                m5_times=m5_times,
                m5_hi_v=m5_hi_v,
                m5_lo_v=m5_lo_v,
                price_v=sign * price,
                m5_pv=to_view(m5_zz, sign),
                m5_ptimes=m5_ptimes,
                bands_v=bands_v,
                lean=lean,
                lean_text=lean_text,
            )
        )
    return FibInputs(lean, lean_text, datas, df, times, zz, m5_zz, price)


def _decide_fib(
    frames: dict[str, pd.DataFrame],
    now: pd.Timestamp,
    p: Params,
    used: frozenset[str],
    pending: bool,
    log: dict[str, str],
    done: Callable[..., Result],
) -> Result:
    """Mode "fib" (eye/BOT_RULES.md) at an M5 close ``now``: warm-up and ``max_orders`` (rule 0), the H1
    lean (1), each side's latest leg (2-10), the choice between a BUY and a SELL (13), and - only if no leg
    order was written - the range (11). Closed bars only: ``decide`` has checked the cut."""
    if any(len(frames[tf]) < FIB_BARS for tf in ("H4", "H1", "M15", "M5")):
        return done("warm-up")
    if pending:
        return done("order pending")
    return fib_decision(fib_inputs(frames, now, p), now, p, used, log, done)


def fib_decision(
    fi: FibInputs,
    now: pd.Timestamp,
    p: Params,
    used: frozenset[str],
    log: dict[str, str],
    done: Callable[..., Result],
) -> Result:
    """Rules 2-13 on the inputs of one ``now``: each side's leg, the choice between a BUY and a SELL (rule
    13), and - only if no leg order was written - the range (rule 11)."""
    tf = p.fib_tf
    log["lean"] = fi.lean_text
    outs = [analyse_leg(d, p, used) for d in fi.datas]
    written = [o for o in outs if o.setup is not None]
    if written:
        pick = choose([o.setup for o in written if o.setup is not None])
        best = next(o for o in written if o.setup is pick)
        return _emit(best, now, tf, p, log, done)
    best = max(outs, key=lambda o: RANK[o.reason])  # the one that got furthest; a tie goes to the BUY
    if p.fib_range == "on" and fi.lean is None and m5_has_trend(to_view(fi.m5_zz, 1)) is False:
        ro = _range_out(fi.zz, fi.times, fi.df, fi.price, tf, p, used)
        if ro.setup is not None:
            return _emit(ro, now, tf, p, log, done)
        if RANK[ro.reason] > RANK[best.reason]:
            best = ro
    return done(best.reason, best.info, tf)


def _range_out(
    zz: Sequence[Swing], times: pd.DatetimeIndex, df: pd.DataFrame, price: float, tf: str, p: Params,
    used: frozenset[str],
) -> FibOut:  # fmt: skip
    """Rule 11 on the setup timeframe: the latest fixed HIGH and LOW, in whichever order; one order per
    range."""
    highs = [s for s in zz if s.kind is SwingKind.HIGH]
    lows = [s for s in zz if s.kind is SwingKind.LOW]
    if not highs or not lows:
        return FibOut("fib: no range")
    hi, lo = highs[-1], lows[-1]
    later = max(hi.pivot_pos, lo.pivot_pos)
    closes_after = df.close.to_numpy(dtype=np.float64)[later + 1 :]
    out = analyse_range(lo.price, hi.price, price, closes_after, p, tf)
    if out.setup is None:
        return out
    # SPEC-QUESTION: one order per range (its two pivot times) - the key has no side, so a BUY and a SELL on
    #  the
    # same range share it.
    key = f"range|{tf}|{times[lo.pivot_pos]}|{times[hi.pivot_pos]}"
    if key in used:
        return FibOut("fib: leg or range already used", out.info)
    out.setup.key = key
    t_lo, t_hi = _tt(times[lo.pivot_pos]), _tt(times[hi.pivot_pos])
    out.setup.detail = (
        f"Range pivots: low {lo.price:.2f}@{t_lo}, high {hi.price:.2f}@{t_hi}. " + out.setup.detail
    )
    return out


def _emit(
    o: FibOut, now: pd.Timestamp, tf: str, p: Params, log: dict[str, str], done: Callable[..., Result]
) -> Result:  # fmt: skip
    """The decision row and the log row of an order the fib path wrote (rule 14)."""
    s = o.setup
    if s is None:  # not reachable: callers pass outcomes that hold an order
        return done(o.reason, o.info, tf)
    info = dict(o.info)
    info.update(
        order=f"{s.order:.2f}", stop=f"{s.stop:.2f}", target=f"{s.target:.2f}", ladder=s.step, r=f"{s.r:.2f}"
    )
    result = done(o.reason, info, tf)
    log["side"] = s.side
    result.key = s.key
    structure = (
        f"bot2e fib {tf} {s.side}, mode fib. {s.detail}. {s.marker}. Key [{s.key}]. Parameters: {p.text()}"
    )
    result.decision = _ledger_dict(
        now, s.side, f"{s.order:.2f}", f"{s.stop:.2f}", f"{s.target:.2f}", "", structure, blank_marks=True
    )
    return result


def _ledger_dict(
    now: pd.Timestamp,
    side: str,
    entry: str,
    stop: str,
    target: str,
    trigger: str,
    structure: str,
    blank_marks: bool = False,
) -> dict[str, str]:
    """The ledger row's fixed fields (spec section 6). The fib path leaves ``rules`` and ``setup`` empty
    (BOT_RULES rule 14); mode 2e keeps its placeholders."""
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
        "rules": "" if blank_marks else "?????????",
        "conflict": "",
        "at_decision_r": "",
        "missed_by": "",
        "trigger": trigger,
        "setup": "" if blank_marks else "+++++++",
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


KEY_MARK = re.compile(r"Key \[([^\]]+)\]")


def row_key(row: dict[str, str]) -> str:
    """The leg or range key a fib row was written on (its ``structure`` carries it); "" for any other row."""
    m = KEY_MARK.search(row.get("structure", ""))
    return m.group(1) if m else ""


def walk_days(
    days: Sequence[str],
    p: Params,
    full: dict[str, pd.DataFrame],
    prior: Sequence[dict[str, str]] = (),
    kept: Sequence[dict[str, str]] = (),
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Walk the given Thai dates in order; returns (decisions, log rows). ``prior`` are rows written before
    the first day, which may still be live (one order at a time); ``kept`` are the other rows the ledger keeps
    (later days), whose keys are used too but which are not live."""
    written: list[dict[str, str]] = [r for r in prior if r["side"] in ("BUY", "SELL")]
    mine: list[dict[str, str]] = []
    logs: list[dict[str, str]] = []
    # Rule 2: a leg (or range) is used once an order is written on it, in this run or an earlier one:
    # the keys of the rows already in the ledger are used from the start.
    used: set[str] = {k for r in [*written, *kept] if (k := row_key(r))}
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
    keep = [r for r in old if r["cutoff_thai"][:10] not in days]  # every row the run keeps
    mine, logs = walk_days(days, p, full, prior, [r for r in keep if r not in prior])
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
    ap.add_argument("--mode", choices=("2e", "fib"), default=d.mode, help="'fib' = eye/BOT_RULES.md")
    ap.add_argument("--fib-tf", choices=("M5", "M15"), default=d.fib_tf)
    ap.add_argument("--fib-entry", type=float, choices=(0.618, 0.382, 0.236), default=d.fib_entry)
    ap.add_argument("--fib-early", type=float, choices=(0.0, 0.10), default=d.fib_early)
    ap.add_argument("--fib-stop", choices=("line", "swing", "line_tight"), default=d.fib_stop)
    ap.add_argument("--fib-count", choices=("off", "on"), default=d.fib_count)
    ap.add_argument("--max-trend-legs", type=int, choices=(5, 3), default=d.max_trend_legs)
    ap.add_argument("--major-tf", choices=("H4", "H1"), default=d.major_tf)
    ap.add_argument("--max-entry-frac", type=float, default=d.max_entry_frac)
    ap.add_argument("--fib-range", choices=("on", "off"), default=d.fib_range)
    ap.add_argument("--max-orders", type=int, default=d.max_orders, help="orders live at once")
    ap.add_argument("--order-life-bars", type=int, default=d.order_life_bars, help="M5 bars to fill")
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
        fib_early=a.fib_early,
        fib_stop=a.fib_stop,
        fib_count=a.fib_count,
        max_trend_legs=a.max_trend_legs,
        major_tf=a.major_tf,
        max_entry_frac=a.max_entry_frac,
        fib_range=a.fib_range,
        max_orders=a.max_orders,
        order_life_bars=a.order_life_bars,
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
