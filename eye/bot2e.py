"""Bot 2e: the owner's Fibonacci setup (eye/BOT_RULES.md) as a bot.

It walks real trading days bar by bar on the stored gold data, as ``eye/walk.py`` does by hand. At every
closed M5 bar inside the owner's windows it applies the rules of eye/BOT_RULES.md; when they hold it writes a
limit order with its stop and target into ``eye/bot_ledger.csv``, which ``eye/score.py`` scores and
``eye/money.py --ledger bot_ledger.csv`` reads in money.

    python eye/bot2e.py --from 2026-04-06 --to 2026-04-07

**H4, M15 and M5 are read** (BOT_RULES rule 0): H4 only for rule 16 (a clear trend, else a fade), M15 and M5
for the legs; no H1 or M30 (the owner, 2026-10-30: "remove 1H"). The earlier mode 2e (H1 side, level bands,
break-and-retest), the H1 lean and range and the M15 strip side are removed; they live in git history.

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
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from app.indicators.chart_read import zigzag_pivots  # noqa: E402
from app.indicators.price_action import Swing, SwingKind  # noqa: E402
from eye.score import SPREAD, score, start_of  # noqa: E402

state11: Any = importlib.import_module("eye.state11")  # BARS_PER_DAY / look_bars: the trading-day looks
walk: Any = importlib.import_module("eye.walk")  # the by-hand walker; reused so both read the same bars
POINT: float = walk.POINT
SHOWN: dict[str, int] = walk.SHOWN
STEP: dict[str, pd.Timedelta] = {**walk.STEP, "H4": pd.Timedelta(hours=4)}
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
    "date", "time_thai", "window", "price", "side", "tf", "reason",
    # the fib path (BOT_RULES rule 14): rule 16's side, the leg, each rule's state and numbers, the order
    "rule16", "trade", "leg", "r10", "r3", "r6", "r7", "r8", "r9", "order", "stop", "target", "extension",
    "r",
]  # fmt: skip

# The timeframes the bot reads (BOT_RULES rule 0): H4 (rule 16 only), M15 and M5; no H1 or M30.
TIMEFRAMES = ("H4", "M15", "M5")

# The owner's windows (METHOD 2c), Thai time, in minutes after midnight. A decision is written at an M5
# close ``now`` with start < now <= end (the bar that closes at the start belongs to the time before).
WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("Asia", 7 * 60, 9 * 60),
    ("London", 13 * 60, 15 * 60),
    ("New York", 19 * 60 + 30, 23 * 60),
)
# ``cut`` keeps more than the fib path's 1,500 bars of M15 and M5: an M15 leg can be 4,500 M5 bars old, and
# rules 6 and 10 read the M5 bars after the leg.
FRAME_BARS = {"H4": 1500, "M15": SHOWN["M15"] + WARMUP, "M5": 4700}


@dataclass(frozen=True)
class Params:
    """Every parameter the owner did not give. ``[Claude]`` marks a definition made by Claude; the defaults
    are those of eye/BOT_RULES.md's parameter table."""

    stop_buffer: float = 0.50  # [Claude] stop beyond the extreme, USD
    target_buffer: float = 0.50  # [Claude] target before the extension, USD
    min_r: float = 2.0  # the owner's floor (R9): "the profit has to be 1:2"; no decision under it
    spread: float = (
        SPREAD  # the owner's real spread on gold, USD (the R written into a decision is net of it)
    )
    mode: str = "fib"  # the only mode (the 2e record is removed: git history)
    fib_tf: str = "M5"  # [Claude] the setup timeframe: the leg (rule 2)
    fib_entry: float = (
        0.382  # the owner's levels 0.382 / 0.618 / 0.236; default 0.382 (his main zone), rule 6
    )
    fib_early: float = 0.0  # [Claude] x the leg above the level (the owner's idea of getting in early)
    fib_stop: str = "line"  # line (owner) | line_tight ([Claude] variant); rule 7 (swing withdrawn)
    fib_count: str = "off"  # fixed off: rule 4 is not used with this leg (BOT_RULES rule 2)
    fib_target: float = 1.618  # the owner's extensions 1.618 / 1.272; default [Claude] (rule 8)
    max_entry_frac: float = 0.25  # [Claude] rule 9: |price - order price| at most this x the leg
    setup_days: int = 2  # the owner (2026-10-30): the setup look, in trading days (BOT_RULES "Words used")
    early_leg: float | str = 0.382  # the owner (2026-10-30: "about 38, 61 %"): rule 2 early leg; "off" = none
    m5_trend: str = (
        "now"  # [Claude] rule 3: "now" = at the decision; "h100" = the old test; "off" = not applied
    )
    fade_min: float | str = (
        1.0  # [Claude] rule 16: a run is faded only if >= fade_min x the leg before it; off
    )
    fade_entry: float = 0.5  # the owner's zone "61 - 38 %", default [Claude] (rule 2, a fade leg)
    fib_lean: str = "on"  # [Claude] research switch: "off" = H4 is not read (rule 16), always a fade leg
    max_orders: int = 1  # [Claude] orders live (pending or open) at once; a new one needs fewer than this
    order_life_bars: int = 24  # [Claude] rule 12: M5 bars an order may wait for its fill (last included)

    def __post_init__(self) -> None:
        if self.max_orders < 1:
            raise ValueError(f"max_orders must be at least 1, got {self.max_orders!r}")
        if self.order_life_bars < 1:
            raise ValueError(f"order_life_bars must be at least 1, got {self.order_life_bars!r}")
        for name, allowed in (
            ("mode", ("fib",)),
            ("fib_tf", ("M5", "M15")),
            ("fib_entry", (0.382, 0.618, 0.236)),
            ("fib_early", (0, 0.10)),
            ("fib_stop", ("line", "line_tight")),
            ("fib_count", ("off",)),
            ("max_entry_frac", (0.15, 0.25, 0.35)),
            ("fib_target", (1.618, 1.272)),
            ("fib_lean", ("on", "off")),
            ("setup_days", (2,)),
            ("m5_trend", ("now", "h100", "off")),
            ("early_leg", (0.382, 0.618, "off")),
            ("fade_min", (1.0, "off")),
            ("fade_entry", (0.5, 0.382, 0.618)),
        ):
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, got {getattr(self, name)!r}")
        # Combinations without meaning (BOT_RULES, Parameters): refused at start.
        if self.fib_early > 0 and (self.fib_entry != 0.382 or self.fib_stop != "line_tight"):
            raise ValueError("fib_early above 0 needs fib_entry 0.382 and fib_stop line_tight")
        if self.fib_stop == "line_tight" and not self.fib_early > 0:
            raise ValueError("fib_stop line_tight needs fib_early above 0")

    def text(self) -> str:
        """The [Claude] parameters as they are written into a decision."""
        return (
            f"mode={self.mode} fib_tf={self.fib_tf} fib_entry={self.fib_entry:g} "
            f"fib_early={self.fib_early:g} fib_stop={self.fib_stop} fib_count={self.fib_count} "
            f"fib_target={self.fib_target:g} "
            f"max_entry_frac={self.max_entry_frac:g} setup_days={self.setup_days} "
            f"m5_trend={self.m5_trend} early_leg={self.early_leg} fade_min={self.fade_min} "
            f"fade_entry={self.fade_entry:g} fib_lean={self.fib_lean} "
            f"stop_buffer={self.stop_buffer:g} target_buffer={self.target_buffer:g} spread={self.spread:g} "
            f"max_orders={self.max_orders} order_life_bars={self.order_life_bars} min_r={self.min_r:g}"
        )


# The reasons a bar can end without an order, in the order the rules run; a later one means the bar got
# further. ``reason`` in the log is always one of these, or "order written" (BOT_RULES' order of evaluation).
REASONS = [
    "market closed", "outside window", "warm-up", "order pending",
    "fib: against the H4 trend", "fib: no live leg", "fib: leg already used",
    "fib: leg has run (100 % traded)", "fib: M5 trend (H100 not above the M5 high)",
    "fib: no M5 trend of its side",
    "fib: no bounce above the order price",
    "fib: price not above the order price", "fib: no target above the order price",
    "reward under 2R", "setup already played out", "fib: order price too far from price",
    "order written",
]  # fmt: skip
RANK = {r: i for i, r in enumerate(REASONS)}


@dataclass(frozen=True)
class VPivot:
    """A fixed pivot in the view: ``low`` is true for a low of the view (a SELL's highs are its lows)."""

    low: bool
    price: float
    pos: int
    confirm: int = (
        -1
    )  # the position of the bar on which the pivot became fixed (-1: not known, e.g. provisional)


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
    for tf in TIMEFRAMES:  # H4, M15 and M5 only; any other frame in ``full`` is never read
        df = full[tf]
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


# --- the view -------------------------------------------------------------------------------------------


def to_view(pivots: Sequence[Swing], sign: int) -> list[VPivot]:
    """Fixed pivots in the view: unchanged for a BUY; for a SELL kinds swap and prices are negated."""
    if sign > 0:
        return [VPivot(s.kind is SwingKind.LOW, s.price, s.pivot_pos, s.confirm_pos) for s in pivots]
    return [VPivot(s.kind is SwingKind.HIGH, -s.price, s.pivot_pos, s.confirm_pos) for s in pivots]


# --- the fib path (eye/BOT_RULES.md): rules 1-13 ---------------------------------------------------------
#
# Prices here are in the view of the side being tried (a SELL's are negated, highs and lows swapped).
# ``_real`` turns a view price back.

FIB_BARS = 1500  # BOT_RULES "Words used": fixed pivots are read on the last 1,500 closed bars of a timeframe
FIB_LEVELS = (0.236, 0.382, 0.618)
EPS = 1e-9  # float noise at an exact boundary is not a refusal
H4_NOT_READ = "H4 not read"  # rule 16's written form when H4 is not read


def _real(sign: int, v: float) -> float:
    return round(sign * v, 2)


def _tt(ts: pd.Timestamp) -> str:
    """A time as the owner reads it: Thai, day/month hour:minute."""
    return f"{ts.tz_convert(TH):%d/%m %H:%M}"


@dataclass
class FibSetup:
    """An order the fib path found. Prices are real (a SELL's too); ``marker`` is the withdrawal marker that
    ``eye/score.py`` reads from the row, ``detail`` the text that names the leg."""

    side: str
    tf: str
    key: str
    order: float
    stop: float
    target: float
    r: float
    step: str  # the target's extension ("1.618" / "1.272")
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
    hi_v: np.ndarray  # the setup frame's highs and lows in the view (a SELL's: negated, swapped)
    lo_v: np.ndarray
    close_v: np.ndarray  # the setup frame's closes in the view (rule 17's break)
    m5_times: pd.DatetimeIndex
    m5_hi_v: np.ndarray
    m5_lo_v: np.ndarray
    price_v: float
    m5_pv: list[VPivot]
    m5_ptimes: pd.DatetimeIndex
    look_lo: int = (
        0  # the setup look's first position in ``times`` / ``close_v``: pivots before it are not read
    )
    h4: str = "none"  # rule 16: H4 "up" / "down" / "none" (not clear) / "off" (fib_lean off: not read)
    h4_text: str = H4_NOT_READ  # rule 16's H4 reading in its written form


# --- rule 16: H4's clear trend, else a fade -----------------------------------------------------------------


def h4_reading(piv: Sequence[Swing]) -> tuple[str, str]:
    """Rule 16: H4 from its fixed pivots - (``up`` / ``down`` / ``none``, the written form
    ``H4 up / down / not clear (highs a->b, lows c->d)``). The latest two fixed HIGHs and the latest two fixed
    LOWs: up when the later high is strictly above the earlier and the later low strictly above the earlier;
    down when both are strictly below; otherwise not clear (also with fewer than two of either)."""
    highs = [q.price for q in piv if q.kind is SwingKind.HIGH][-2:]
    lows = [q.price for q in piv if q.kind is SwingKind.LOW][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return "none", f"H4 not clear ({len(highs)} highs, {len(lows)} lows fixed)"
    text = f"(highs {highs[0]:.2f}->{highs[1]:.2f}, lows {lows[0]:.2f}->{lows[1]:.2f})"
    if highs[1] > highs[0] and lows[1] > lows[0]:
        return "up", f"H4 up {text}"
    if highs[1] < highs[0] and lows[1] < lows[0]:
        return "down", f"H4 down {text}"
    return "none", f"H4 not clear {text}"


def read_h4(frames: dict[str, pd.DataFrame], p: Params) -> tuple[str, str]:
    """Rule 16's H4 reading at the last closed bar; with ``fib_lean`` off H4 is not read (always a fade)."""
    if p.fib_lean == "off":
        return "off", "H4 not read (fib_lean off)"
    return h4_reading(_zigzag(frames["H4"].tail(FIB_BARS)))


# --- rule 2: the counter-leg --------------------------------------------------------------------------


@dataclass
class Leg:
    """A leg found by rule 2 in the view, traded with it: 0 % at ``l0`` (the start, a LOW), 100 % at ``h100``
    (the end, a HIGH). ``early`` = ``h100`` is provisional (not a pivot; it moves with new highs)."""

    l0: VPivot
    h100: VPivot
    early: bool = False
    fade: bool = False  # a fade leg: ``l0`` is E (0 %, the run's end), ``h100`` is S (100 %, the run's start)


def fib_leg(pv: Sequence[VPivot], lo_v: np.ndarray) -> Leg | None:
    """Rule 2's fixed leg for a BUY in the view: ``H100`` = the latest fixed HIGH (the end), ``L0`` = the
    fixed LOW immediately before it (the start); the leg ``H100 - L0`` must be above zero, and no
    setup-timeframe low below ``L0`` after ``H100``'s bar (the start is broken: no leg)."""
    highs = [i for i, q in enumerate(pv) if not q.low]
    if not highs or highs[-1] == 0 or not pv[highs[-1] - 1].low:
        return None
    h100, l0 = pv[highs[-1]], pv[highs[-1] - 1]
    if not h100.price > l0.price:
        return None
    since = lo_v[h100.pos + 1 :]
    if since.size and float(since.min()) < l0.price:
        return None
    return Leg(l0, h100)


def early_leg(pv: Sequence[VPivot], hi_v: np.ndarray, lo_v: np.ndarray, frac: float) -> Leg | None:
    """Rule 2's early leg for a BUY in the view. ``Lf`` = the latest fixed pivot when it is a LOW, ``Hp`` =
    the fixed HIGH before it. Over the setup-timeframe bars after ``Lf``'s pivot bar to the last closed bar:
    a low below ``Lf`` - no early leg; otherwise when the highest high is at or above
    ``Lf + frac x (Hp - Lf)`` the leg is ``L0`` = ``Lf`` and the provisional ``H100`` = that highest high
    (the earliest bar holding it)."""
    if len(pv) < 2 or not pv[-1].low or pv[-2].low:
        return None
    lf, hp = pv[-1], pv[-2]
    if not hp.price > lf.price:
        return None
    since_hi, since_lo = hi_v[lf.pos + 1 :], lo_v[lf.pos + 1 :]
    if since_hi.size == 0 or float(since_lo.min()) < lf.price:
        return None
    top = float(since_hi.max())
    if top < lf.price + frac * (hp.price - lf.price) - EPS:
        return None
    return Leg(lf, VPivot(False, top, lf.pos + 1 + int(since_hi.argmax())), early=True)


def fade_leg(pv: Sequence[VPivot], fade_min: float | str) -> Leg | None:
    """Rule 2's fade leg for a BUY after a run down, in the view: ``E`` = the latest fixed pivot when it is a
    LOW, ``S`` = the fixed HIGH before it (the run = ``S - E`` above zero); the Fibo is drawn 0 % at ``E``,
    100 % at ``S`` (``l0`` = E, ``h100`` = S, so a level x is ``E + x (S - E)``). The run is faded only when
    long: at least ``fade_min`` x the leg before it (from the fixed pivot before ``S`` to ``S``); a missing
    pivot before ``S`` leaves nothing to compare - no fade leg - unless ``fade_min`` is off."""
    if len(pv) < 2 or not pv[-1].low or pv[-2].low:
        return None
    e, s_ = pv[-1], pv[-2]
    run = s_.price - e.price
    if not run > 0:
        return None
    if fade_min != "off":
        if len(pv) < 3:
            return None
        before = abs(s_.price - pv[-3].price)
        if run < float(fade_min) * before - EPS:
            return None
    return Leg(e, s_, fade=True)


def find_leg(d: LegData, p: Params) -> Leg | None:
    """The side's latest leg (rule 2) as rule 16 allows: H4 up / down (``fib_lean`` on) - only the trend
    leg of that direction (an early leg when ``early_leg`` is on and one stands, else the fixed leg); H4 not
    clear or not read - the fade leg. ``L0`` and ``H100`` (for a fade: ``E`` and ``S``) both inside the setup
    look (a provisional end's bar too), otherwise no leg."""
    if d.h4 in ("up", "down"):
        if (d.h4 == "up") != (d.side == "BUY"):
            return None  # against the H4 trend: no leg on this side
        leg = early_leg(d.pv, d.hi_v, d.lo_v, float(p.early_leg)) if p.early_leg != "off" else None
        if leg is None:
            leg = fib_leg(d.pv, d.lo_v)
    else:
        leg = fade_leg(d.pv, p.fade_min)
    if leg is None or leg.l0.pos < d.look_lo or leg.h100.pos < d.look_lo:
        return None
    return leg


# --- rules 3 and 5: the trend on M5 -------------------------------------------------------------------


def m5_trend(m5_pv: Sequence[VPivot], m5_ptimes: pd.DatetimeIndex, t100: pd.Timestamp) -> VPivot | None:
    """Rule 3, ``m5_trend`` h100 (the record), for a BUY in the view: the latest fixed M5 HIGH whose time is
    strictly before ``H100``'s, or None."""
    highs = [q for q in m5_pv if not q.low and m5_ptimes[q.pos] < t100]
    return highs[-1] if highs else None


def m5_state(m5_pv: Sequence[VPivot]) -> tuple[str, str]:
    """Rule 3, ``m5_trend`` now, in the view: ("UP" / "DOWN" / "none", a text of the four pivots). The
    latest two fixed HIGHs and the latest two fixed LOWs of the view by time: UP when the later high is
    strictly above the earlier and the later low strictly above the earlier, DOWN when both are strictly
    below, else none (also with fewer than two of either). In a SELL's view "UP" is the real DOWN; the caller
    reads it as its side's trend."""
    hs = [q for q in m5_pv if not q.low][-2:]
    ls = [q for q in m5_pv if q.low][-2:]
    if len(hs) < 2 or len(ls) < 2:
        return "none", f"{len(hs)} highs, {len(ls)} lows in the view"
    text = f"highs {hs[0].price:.2f}->{hs[1].price:.2f}, lows {ls[0].price:.2f}->{ls[1].price:.2f} (view)"
    if hs[1].price > hs[0].price and ls[1].price > ls[0].price:
        return "UP", text
    if hs[1].price < hs[0].price and ls[1].price < ls[0].price:
        return "DOWN", text
    return "none", text


# --- rules 7 and 8: the stop and the target -----------------------------------------------------------


def fib_stop_v(p: Params, l0: VPivot, leg: float) -> float:
    """Rule 7 for a BUY in the view. 0.382 / 0.236: ``L0 - stop_buffer`` (beyond 0 %). 0.618: the 23.6 %
    level - buffer (line, beyond 23 %). ``line_tight``: the 0.382 level - buffer."""
    if p.fib_stop == "line_tight":
        return l0.price + 0.382 * leg - p.stop_buffer
    if p.fib_entry != 0.618:
        return l0.price - p.stop_buffer
    return l0.price + 0.236 * leg - p.stop_buffer


def fib_target_v(p: Params, l0: float, leg: float) -> float:
    """Rule 8 for a BUY in the view: the Fibo extension ``L0 + fib_target x leg - target_buffer``. No band and
    no step: no level is major on this path (a SELL is the mirror)."""
    return l0 + p.fib_target * leg - p.target_buffer


def planned_r(order: float, stop: float, target: float, spread: float) -> float:
    """R of a BUY in the view: (target - order - spread) / (order - stop); minus infinity with no risk."""
    risk = order - stop
    return (target - order - spread) / risk if risk > 0 else float("-inf")


# --- one side's leg: rules 2-10 in the order of evaluation --------------------------------------------


def _m5_gate(d: LegData, p: Params, out: FibOut, h100: VPivot, t100: pd.Timestamp) -> str | None:
    """Rule 3 for a trend leg: the M5 trend at the decision must be this side's (or, ``m5_trend`` h100,
    H100 above the latest fixed M5 high before it). Returns its text for the record, or None with ``out`` set
    to the refusal."""
    s = d.sign
    word = "high" if s > 0 else "low"
    if p.m5_trend == "off":  # a research variant: rule 3 is not applied at all
        out.info["r3"] = "rule 3 off (m5_trend off)"
        return "rule 3 off"
    if p.m5_trend == "h100":  # the record: H100 above the latest fixed M5 high before it
        ref = m5_trend(d.m5_pv, d.m5_ptimes, t100)
        out.reason = "fib: M5 trend (H100 not above the M5 high)"
        if ref is None:
            out.info["r3"] = "no fixed M5 high before H100"
            return None
        t_ref = _tt(pd.Timestamp(d.m5_ptimes[ref.pos]))
        out.info["r3"] = f"H100 {_real(s, h100.price):.2f} vs M5 {word} {_real(s, ref.price):.2f}@{t_ref}"
        if not h100.price > ref.price:
            return None
        return (
            f"M5 trend: H100 {_real(s, h100.price):.2f} beyond the M5 {word} "
            f"{_real(s, ref.price):.2f}@{_tt(pd.Timestamp(d.m5_ptimes[ref.pos]))}"
        )
    state, pivots_text = m5_state(d.m5_pv)
    want = "UP" if s > 0 else "DOWN"
    seen = "no trend" if state == "none" else (want if state == "UP" else ("DOWN" if s > 0 else "UP"))
    out.info["r3"] = f"M5 {seen} ({pivots_text}), a {d.side} needs {want}"
    out.reason = "fib: no M5 trend of its side"
    if state != "UP":
        return None
    return f"M5 trend {want} ({pivots_text})"


def retest_break(d: LegData, leg: Leg) -> int | None:
    """Rule 17 for a BUY in the view, on a fixed trend leg: the position (in the setup frame) of the first
    setup-timeframe close strictly above ``H100`` among the bars whose open is at or after the close of the
    bar on which ``H100`` became fixed - but only when that bar closes exactly now (the order is written at
    the break close). None otherwise (no break yet, an old break, or a provisional / fade leg)."""
    if leg.fade or leg.early or leg.h100.confirm < 0:
        return None
    start = leg.h100.confirm + 1
    beyond = np.flatnonzero(d.close_v[start:] > leg.h100.price)
    if beyond.size == 0:
        return None
    i = start + int(beyond[0])
    now = pd.Timestamp(d.m5_times[-1]) + STEP["M5"]
    return i if pd.Timestamp(d.times[i]) + STEP[d.tf] == now else None


def analyse_leg(d: LegData, p: Params, used: frozenset[str] = frozenset()) -> FibOut:
    """One side's latest leg through the order of evaluation (BOT_RULES): 2 -> 10 -> 3 -> 4
    -> 5 -> 6 -> 7 -> 8 -> 6 (played out) -> 9. Returns the order, or the reason for none."""
    out = FibOut("fib: no live leg")
    if p.fib_lean == "on" and d.h4 in ("up", "down") and (d.h4 == "up") != (d.side == "BUY"):
        out.reason = "fib: against the H4 trend"  # rule 16: only the trend leg of H4's direction
        return out
    found = find_leg(d, p)  # rule 2, inside the setup look
    if found is None:
        return out
    l0, h100 = found.l0, found.h100
    leg = h100.price - l0.price
    t0, t100 = pd.Timestamp(d.times[l0.pos]), pd.Timestamp(d.times[h100.pos])
    s = d.sign
    # One order per leg: the key is the start's time, shared by an early leg and the fixed leg after it
    key = f"{d.side}|{d.tf}|{t0}"  # a fade leg: side, timeframe, E's time (E = l0)
    mark = "?" if found.early else ""  # the provisional end of an early leg
    if found.fade:
        word = "run up" if d.side == "SELL" else "run down"
        trade = f"fade {d.side} after the {word} {_real(s, h100.price):.2f} -> {_real(s, l0.price):.2f}"
        out.info["leg"] = (
            f"fade S {_real(s, h100.price):.2f}@{_tt(t100)} E {_real(s, l0.price):.2f}@{_tt(t0)} "
            f"run {leg:.2f}"
        )
    else:
        trade = f"trend leg {d.side}"
        out.info["leg"] = (
            f"L0 {_real(s, l0.price):.2f}@{_tt(t0)} "
            f"H100{mark} {_real(s, h100.price):.2f}@{_tt(t100)} leg {leg:.2f}"
        )
    out.info["trade"] = trade
    if key in used:
        out.reason = "fib: leg already used"
        return out

    # 10: a leg whose end has been passed is over (M5 bars whose open is at or after the end bar's close). A
    # trend leg: a high above H100 after H100's bar; a fade leg: a new extreme beyond E after E's bar.
    start_bar = t0 if found.fade else t100
    k = int(d.m5_times.searchsorted(start_bar + STEP[d.tf], side="left"))
    if found.fade:
        trough = float(d.m5_lo_v[k:].min()) if d.m5_lo_v[k:].size else float("inf")
        word = "low" if s > 0 else "high"
        out.info["r10"] = f"M5 {word} after E {_real(s, trough):.2f} vs E {_real(s, l0.price):.2f}"
        run_over = trough < l0.price
    else:
        peak = float(d.m5_hi_v[k:].max()) if d.m5_hi_v[k:].size else float("-inf")
        word = "high" if s > 0 else "low"
        out.info["r10"] = f"M5 {word} after H100 {_real(s, peak):.2f} vs H100 {_real(s, h100.price):.2f}"
        run_over = peak > h100.price
    out.reason = "fib: leg has run (100 % traded)"
    if run_over:
        return out

    # 3: the M5 trend (a trend leg only: a fade is against the short trend that made the run, rule 16).
    trend_text = "rule 3 not applied to a fade" if found.fade else _m5_gate(d, p, out, h100, t100)
    if trend_text is None:
        return out
    trend_text = f"{trend_text}; trade: {trade}"

    # 6: the level, the order price, the bounce.
    x = p.fade_entry if found.fade else p.fib_entry
    early = 0.0 if found.fade else p.fib_early
    order = l0.price + (x + early) * leg
    first = np.flatnonzero(d.m5_hi_v[k:] > order)
    out.info["r6"] = (
        f"order price {_real(s, order):.2f} (level {x:g} + early {early:g}), price {_real(s, d.price_v):.2f}"
    )
    out.reason = "fib: no bounce above the order price"
    if first.size == 0:
        return out
    j = k + int(first[0])  # the first M5 bar above the order price
    out.reason = "fib: price not above the order price"
    if not d.price_v > order:
        return out

    # 7 and 8: the stop and the target.
    stop = l0.price - p.stop_buffer if found.fade else fib_stop_v(p, l0, leg)  # a fade: beyond E
    target, step = fib_target_v(p, l0.price, leg), f"{p.fib_target:g}"
    out.info["r7"] = f"stop {_real(s, stop):.2f} ({'beyond E' if found.fade else p.fib_stop})"
    out.info["r8"] = f"target {_real(s, target):.2f} ({_target_word(step)})"
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
    h100_real = _real(s, h100.price)
    early_note = ", provisional early leg" if found.early else ""
    if found.fade:
        leg_text = (
            f"Fade leg: S {h100_real:.2f}@{_tt(t100)} (100 %), E {_real(s, l0.price):.2f}@{_tt(t0)} (0 %), "
            f"run {leg:.2f}"
        )
        marker = f"withdraw {'under' if s > 0 else 'over'} {_real(s, l0.price):.2f}"
    else:
        leg_text = (
            f"Leg: L0 {_real(s, l0.price):.2f}@{_tt(t0)} (0 %), "
            f"H100{mark} {h100_real:.2f}@{_tt(t100)} (100 %{early_note}), leg {leg:.2f}"
        )
        marker = f"withdraw beyond {h100_real:.2f}"
    detail = (
        f"{d.h4_text}. {leg_text}; levels {levels}; "
        f"{trend_text}. Entry level {x * 100:.1f} % = {_real(s, l0.price + x * leg):.2f}, order price "
        f"{_real(s, order):.2f} (fib_early {early:g}); stop {_real(s, stop):.2f}; "
        f"target {_real(s, target):.2f} ({_target_word(step)}); planned R {r:.2f} "
        f"(net of {p.spread:g} spread). "
        f"Order price {gap:.2f} from the price, limit {p.max_entry_frac * leg:.2f}"
    )
    out.setup = FibSetup(
        d.side, d.tf, key, _real(s, order), _real(s, stop), _real(s, target), r, step, gap,
        marker, detail,
    )  # fmt: skip
    out.reason = "order written"
    return out


def analyse_retest(d: LegData, p: Params, used: frozenset[str] = frozenset()) -> FibOut | None:
    """Rule 17 for one side: when the side's latest FIXED trend leg (an early leg is another leg) has just
    had its end broken - the first setup-timeframe close beyond ``H100`` closes now - the retest order of that
    leg, after rules 3 and 16; None when there is no break now (or H4 allows no trend leg of this side, the
    leg is used, or it is a fade leg: a fade never gets this order)."""
    if d.h4 not in ("up", "down") or p.fib_lean == "off":
        return None  # a trend leg exists only when H4 trends clearly (rule 16); fade legs have no retest
    if (d.h4 == "up") != (d.side == "BUY"):
        return None
    leg = fib_leg(d.pv, d.lo_v)  # the fixed leg, wherever an early leg stands
    if leg is None or leg.l0.pos < d.look_lo or leg.h100.pos < d.look_lo:
        return None
    break_at = retest_break(d, leg)
    if break_at is None:
        return None
    s = d.sign
    t0, t100 = pd.Timestamp(d.times[leg.l0.pos]), pd.Timestamp(d.times[leg.h100.pos])
    key = f"{d.side}|{d.tf}|{t0}"
    if key in used:
        return None  # the pullback order (or this one) already filled: the leg is used
    out = FibOut("fib: no live leg")
    out.info["leg"] = (
        f"L0 {_real(s, leg.l0.price):.2f}@{_tt(t0)} "
        f"H100 {_real(s, leg.h100.price):.2f}@{_tt(t100)} leg {leg.h100.price - leg.l0.price:.2f}"
    )
    out.info["trade"] = f"trend leg {d.side}, break and retest"
    out.info["r10"] = f"broken by the {d.tf} close at {_tt(pd.Timestamp(d.times[break_at]) + STEP[d.tf])}"
    trend_text = _m5_gate(d, p, out, leg.h100, t100)
    if trend_text is None:
        return out
    return _retest_order(d, p, out, leg, break_at, trend_text)


def _retest_order(
    d: LegData, p: Params, out: FibOut, found: Leg, break_at: int, trend_text: str
) -> FibOut:  # fmt: skip
    """Rule 17: the order at the break close, in the view - a limit at ``H100`` (the retest from above), stop
    beyond the bounce low ``Lb`` (the lowest low of the bars after H100's bar up to the bar before the break
    bar), target ``L0 + fib_target x leg - target_buffer`` or, when that gives R under ``min_r``,
    ``L0 + 2.0 x leg - target_buffer``; still under - no order. Rule 6's bounce and played-out, 9 and 10 do
    not apply; the order is withdrawn only by its target touched before the fill (no ``H100`` marker)."""
    l0, h100, s = found.l0, found.h100, d.sign
    leg = h100.price - l0.price
    t0, t100 = pd.Timestamp(d.times[l0.pos]), pd.Timestamp(d.times[h100.pos])
    lb = float(d.lo_v[h100.pos + 1 : break_at].min())  # Hb for a SELL, in the view
    bar = pd.Timestamp(d.times[break_at]) + STEP[d.tf]
    order = h100.price
    stop = lb - p.stop_buffer
    extremum = "Lb" if s > 0 else "Hb"
    out.info["r6"] = f"retest order price {_real(s, order):.2f} (H100), price {_real(s, d.price_v):.2f}"
    out.info["r7"] = f"stop {_real(s, stop):.2f} (beyond {extremum} {_real(s, lb):.2f})"
    out.reason = "fib: no target above the order price"
    target, step = fib_target_v(p, l0.price, leg), f"{p.fib_target:g}"
    r = planned_r(order, stop, target, p.spread)
    if target > order and r >= p.min_r:
        pass
    else:  # the owner: "161 - 200 % may be the minimum" - the 2.0 extension, none beyond
        target, step = l0.price + 2.0 * leg - p.target_buffer, "2"
        r = planned_r(order, stop, target, p.spread) if target > order else float("-inf")
    out.info["r8"] = f"target {_real(s, target):.2f} (extension {step})"
    out.info["r"] = f"{r:.2f}"
    if not target > order:
        return out
    out.reason = "reward under 2R"
    if r < p.min_r:
        return out
    gap = abs(d.price_v - order)
    out.info["trade"] = f"trend leg {d.side}, break and retest"
    detail = (
        f"{d.h4_text}. Leg: L0 {_real(s, l0.price):.2f}@{_tt(t0)} (0 %), "
        f"H100 {_real(s, h100.price):.2f}@{_tt(t100)} (100 %), leg {leg:.2f}; break and retest: the {d.tf} "
        f"close at {_tt(bar)} went beyond H100 ({_real(s, float(d.close_v[break_at])):.2f}), "
        f"{extremum} {_real(s, lb):.2f}; {trend_text}; trade: {out.info['trade']}. "
        f"Limit at H100 {_real(s, order):.2f}; stop {_real(s, stop):.2f} (beyond {extremum}); "
        f"target {_real(s, target):.2f} (extension {step}); planned R {r:.2f} (net of {p.spread:g} spread)"
    )
    key = f"{d.side}|{d.tf}|{t0}"
    out.setup = FibSetup(
        d.side, d.tf, key, _real(s, order), _real(s, stop), _real(s, target), r, step, gap,
        "no H100 withdrawal (break and retest)", detail,
    )  # fmt: skip
    out.reason = "order written"
    return out


def _target_word(step: str) -> str:
    return f"extension {step}"


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


def _check_cut(frames: dict[str, pd.DataFrame], now: pd.Timestamp) -> None:
    """Refuse a frame that is unsorted or holds any bar with ``open_time + tf > now`` (Revision 1, R4).
    Only H4, M15 and M5 are read, so only they are checked."""
    for tf in TIMEFRAMES:
        df = frames[tf]
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
    """Apply eye/BOT_RULES.md at ``now`` to frames already cut to the bars closed then (``cut``); only the M15
    and M5 frames are read. ``used`` holds setups already written; ``pending`` is true while ``max_orders``
    orders are live; ``windowed`` False switches the window test off (the acceptance cases)."""
    _check_cut(frames, now)
    t = now.tz_convert(TH)
    m5 = frames["M5"]
    log = dict.fromkeys(LOG_COLUMNS, "")
    log.update(date=f"{t:%Y-%m-%d}", time_thai=f"{t:%H:%M}")

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
    return _decide_fib(frames, now, p, used, pending, log, done)


def _hl_view(df: pd.DataFrame, sign: int) -> tuple[np.ndarray, np.ndarray]:
    """high and low of a frame in the view (a SELL's: negated, swapped), without the oscillators."""
    hi = df.high.to_numpy(dtype=np.float64)
    lo = df.low.to_numpy(dtype=np.float64)
    return (hi, lo) if sign > 0 else (-lo, -hi)


@dataclass
class FibInputs:
    """What the fib path reads at one ``now``: rule 16's H4 reading and its written form, one ``LegData`` per
    side, and the setup timeframe's own frame, pivots and times."""

    h4: str
    h4_text: str
    datas: list[LegData]
    df: pd.DataFrame
    times: pd.DatetimeIndex
    zz: list[Swing]
    m5_zz: list[Swing]
    price: float


def fib_inputs(frames: dict[str, pd.DataFrame], now: pd.Timestamp, p: Params) -> FibInputs:
    """Cut the setup timeframe and M5 to their last 1,500 closed bars, read the fixed pivots and rule 16's
    H4 reading, and put each side in its view. ``frames`` are already cut to the bars closed at ``now``."""
    # SPEC-QUESTION: MACD / RSI are computed over the same last 1,500 closed bars as the pivots (the rules
    # do not give the series length); ``cut`` keeps 4,700 M5 bars so an M15 leg's L0 (up to 1,500 M15 bars
    # back) has its M5 bars for rules 6 and 10.
    h4, h4_text = read_h4(frames, p)
    tf = p.fib_tf
    df = frames[tf].tail(FIB_BARS)
    times = pd.DatetimeIndex(df.index)
    zz = _zigzag(df)
    look_lo = max(0, len(df) - state11.look_bars(tf, p.setup_days))  # the setup look, in the setup frame
    m5_full = frames["M5"]
    m5_tail = m5_full.tail(FIB_BARS)
    m5_zz = _zigzag(m5_tail)
    m5_lo = max(0, len(m5_tail) - state11.look_bars("M5", p.setup_days))  # rules 3 and 5 read M5 in the look
    m5_read = [q for q in m5_zz if q.pivot_pos >= m5_lo]
    m5_ptimes = pd.DatetimeIndex(m5_tail.index)
    price = float(m5_full.close.iloc[-1])
    m5_times = pd.DatetimeIndex(m5_full.index)
    datas: list[LegData] = []
    for leg_side, sign in (("BUY", 1), ("SELL", -1)):
        m5_hi_v, m5_lo_v = _hl_view(m5_full, sign)
        hi_v, lo_v = _hl_view(df, sign)
        datas.append(
            LegData(
                side=leg_side,
                sign=sign,
                tf=tf,
                pv=to_view(zz, sign),
                times=times,
                hi_v=hi_v,
                lo_v=lo_v,
                close_v=sign * df.close.to_numpy(dtype=np.float64),
                m5_times=m5_times,
                m5_hi_v=m5_hi_v,
                m5_lo_v=m5_lo_v,
                price_v=sign * price,
                m5_pv=to_view(m5_read, sign),
                look_lo=look_lo,
                m5_ptimes=m5_ptimes,
                h4=h4,
                h4_text=h4_text,
            )
        )
    return FibInputs(h4, h4_text, datas, df, times, zz, m5_zz, price)


def _decide_fib(
    frames: dict[str, pd.DataFrame],
    now: pd.Timestamp,
    p: Params,
    used: frozenset[str],
    pending: bool,
    log: dict[str, str],
    done: Callable[..., Result],
) -> Result:
    """eye/BOT_RULES.md at an M5 close ``now``: warm-up and ``max_orders`` (rule 0), rule 16's side, each
    side's latest leg (2-10), and the choice between a BUY and a SELL (13). Closed bars only: ``decide`` has
    checked the cut."""
    needed = ("H4", "M5") if p.fib_tf == "M5" else ("H4", "M15", "M5")
    if any(len(frames[tf]) < FIB_BARS for tf in needed):
        return done("warm-up")  # 1,500 closed bars of H4 and M5 (and M15 as the setup timeframe), rule 0
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
    13). Rule 16's H4 reading is written; it decides which kind of leg each side may have."""
    tf = p.fib_tf
    log["rule16"] = fi.h4_text
    outs = [analyse_leg(d, p, used) for d in fi.datas]
    outs += [o for d in fi.datas if (o := analyse_retest(d, p, used)) is not None]  # rule 17
    written = [o for o in outs if o.setup is not None]
    if written:
        pick = choose([o.setup for o in written if o.setup is not None])
        best = next(o for o in written if o.setup is pick)
        return _emit(best, now, tf, p, log, done)
    best = max(outs, key=lambda o: RANK[o.reason])  # the one that got furthest; a tie goes to the BUY
    return done(best.reason, best.info, tf)


def _emit(
    o: FibOut, now: pd.Timestamp, tf: str, p: Params, log: dict[str, str], done: Callable[..., Result]
) -> Result:  # fmt: skip
    """The decision row and the log row of an order the fib path wrote (rule 14)."""
    s = o.setup
    if s is None:  # not reachable: callers pass outcomes that hold an order
        return done(o.reason, o.info, tf)
    info = dict(o.info)
    info.update(
        order=f"{s.order:.2f}",
        stop=f"{s.stop:.2f}",
        target=f"{s.target:.2f}",
        extension=s.step,
        r=f"{s.r:.2f}",
    )
    result = done(o.reason, info, tf)
    log["side"] = s.side
    log["trade"] = o.info.get("trade", "")
    result.key = s.key
    structure = (
        f"bot2e fib {tf} {s.side}, mode fib. {s.detail}. {s.marker}. Key [{s.key}]. Parameters: {p.text()}"
    )
    result.decision = _ledger_dict(
        now, s.side, f"{s.order:.2f}", f"{s.stop:.2f}", f"{s.target:.2f}", structure
    )
    return result


def _ledger_dict(
    now: pd.Timestamp,
    side: str,
    entry: str,
    stop: str,
    target: str,
    structure: str,
) -> dict[str, str]:
    """The ledger row's fixed fields. ``rules``, ``setup`` and ``trigger`` stay empty (BOT_RULES rule 14)."""
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
        "rules": "",
        "conflict": "",
        "at_decision_r": "",
        "missed_by": "",
        "trigger": "",
        "setup": "",
    }  # fmt: skip


# --- the walk ---------------------------------------------------------------------------------------------


def load_frames() -> dict[str, pd.DataFrame]:
    return {tf: frame(tf) for tf in TIMEFRAMES}  # H4, M15 and M5: no H1 is loaded


def _read(path: Path, columns: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        rows = [{c: r.get(c, "") for c in columns} for r in csv.DictReader(fh)]
        fh.seek(0)
        # A log written before rule 8 has a ``ladder`` column where ``extension`` is now: carry it over.
        if "extension" in columns:
            for new, old in zip(rows, csv.DictReader(fh), strict=True):
                if not new["extension"] and old.get("ladder"):
                    new["extension"] = old["ladder"]
        return rows


def _write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


# The most orders live (pending or open) and the most filled-and-open at one bar in the last ``walk_days``.
PEAK: dict[str, int] = {"live": 0, "filled": 0}


KEY_MARK = re.compile(r"Key \[([^\]]+)\]")


def row_key(row: dict[str, str]) -> str:
    """The leg key a fib row was written on (its ``structure`` carries it); "" for any other row."""
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
    # Rule 2: a leg is used once an order on it FILLS, in this run or an earlier one (the rows already in the
    # ledger that filled are used from the start); while an order is still waiting its leg is not offered
    # again, and an order that expires or is withdrawn unfilled frees its leg (rule 12).
    m5_all = full["M5"]
    filled_keys: set[str] = {
        k for r in kept if (k := row_key(r)) and score(r, m5_all, start_of(r, {}), p.spread)["fill"]
    }
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
                waiting: set[str] = set()
                for r in written:  # live while score.py still calls it open (pending or filled)
                    if r["id"] in finished:
                        continue
                    scored = score(r, known, start_of(r, {}), p.spread)
                    if scored["fill"] and (k := row_key(r)):
                        filled_keys.add(k)
                    if scored["why"] == "open":
                        live += 1
                        filled += 1 if scored.get("fill") else 0
                        if not scored["fill"] and (k := row_key(r)):
                            waiting.add(k)
                    else:
                        finished.add(r["id"])
                PEAK["live"], PEAK["filled"] = max(PEAK["live"], live), max(PEAK["filled"], filled)
                res = decide(
                    frames, now_utc, p, frozenset(filled_keys | waiting), pending=live >= p.max_orders
                )
                logs.append(res.log)
                if res.decision is not None:
                    n = sum(1 for r in mine if r["cutoff_thai"][:10] == day) + 1
                    row = res.decision
                    row["id"] = f"B-{day.replace('-', '')}-{n}"
                    mine.append(row)
                    written.append(row)
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
    print(f"{first}..{last} {len(logs)} bars evaluated, {len(mine)} decisions")
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
    ap.add_argument("--mode", choices=("fib",), default=d.mode)
    ap.add_argument("--fib-tf", choices=("M5", "M15"), default=d.fib_tf)
    ap.add_argument("--fib-entry", type=float, choices=(0.618, 0.382, 0.236), default=d.fib_entry)
    ap.add_argument("--fib-early", type=float, choices=(0.0, 0.10), default=d.fib_early)
    ap.add_argument("--fib-stop", choices=("line", "line_tight"), default=d.fib_stop)
    ap.add_argument("--fib-count", choices=("off",), default=d.fib_count)
    ap.add_argument("--fib-target", type=float, choices=(1.618, 1.272), default=d.fib_target)
    ap.add_argument("--max-entry-frac", type=float, default=d.max_entry_frac)
    ap.add_argument("--fib-lean", choices=("on", "off"), default=d.fib_lean)
    ap.add_argument("--setup-days", type=int, choices=(2,), default=d.setup_days)
    ap.add_argument("--m5-trend", choices=("now", "h100", "off"), default=d.m5_trend)
    ap.add_argument("--early-leg", choices=("0.382", "0.618", "off"), default=str(d.early_leg))
    ap.add_argument("--fade-min", choices=("1.0", "off"), default=str(d.fade_min))
    ap.add_argument("--fade-entry", type=float, choices=(0.5, 0.382, 0.618), default=d.fade_entry)
    ap.add_argument("--max-orders", type=int, default=d.max_orders, help="orders live at once")
    ap.add_argument("--order-life-bars", type=int, default=d.order_life_bars, help="M5 bars to fill")
    ap.add_argument("--min-r", type=float, default=d.min_r)
    ap.add_argument("--stop-buffer", type=float, default=d.stop_buffer)
    ap.add_argument("--target-buffer", type=float, default=d.target_buffer)
    a = ap.parse_args(argv)
    params = Params(
        mode=a.mode,
        fib_tf=a.fib_tf,
        fib_entry=a.fib_entry,
        fib_early=a.fib_early,
        fib_stop=a.fib_stop,
        fib_count=a.fib_count,
        fib_target=a.fib_target,
        max_entry_frac=a.max_entry_frac,
        setup_days=a.setup_days,
        m5_trend=a.m5_trend,
        early_leg=a.early_leg if a.early_leg == "off" else float(a.early_leg),
        fade_min=a.fade_min if a.fade_min == "off" else float(a.fade_min),
        fade_entry=a.fade_entry,
        fib_lean=a.fib_lean,
        max_orders=a.max_orders,
        order_life_bars=a.order_life_bars,
        min_r=a.min_r,
        stop_buffer=a.stop_buffer,
        target_buffer=a.target_buffer,
    )
    run(a.first, a.last, params)


if __name__ == "__main__":
    main()
