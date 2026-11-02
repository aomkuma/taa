"""The run-zone setup (eye/ZONE_RULES.md): the step, the grids, the visits, the setups, the outputs.

Pure functions over stored bars - a simulation, no orders anywhere. The reference this reproduces is
``eye/research/zone_reference.py`` (v3, ``ZFIX=1``); where it and the specification differ, the specification
wins.

Closed bars only: every reading at time ``t`` uses bars and pivots whose close time is at or before ``t`` (the
visit test itself reads the H1 bar as it happens, rule 4). Times are UTC internally (``pandas`` timestamps
with ``tz="UTC"``); Thai time (Asia/Bangkok) is used for months only.

Independent of the Fibonacci bot (rule 0): nothing is imported from ``bot2e``, ``bot_config`` or
``bot_research``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.indicators.chart_read import zigzag_pivots  # noqa: E402
from eye.zone_config import (  # noqa: E402
    DEFAULT_DB,
    FIELD_NAMES,
    ConfigError,
    ZoneParams,
    load_params,
    param_to_text,
)

TH = "Asia/Bangkok"
MARKET_DIRS = {"XAUUSD": ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD"}
PER_H = {"M5": 12, "M15": 4}
STATE_FRAMES = ("D1", "H4", "H1", "M15")  # the order of gate_w


class ZoneError(ValueError):
    """The data or the run cannot be used as asked; the message says what to do."""


# --- data (rule 10) -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Bars:
    """The five stored frames of one market, times as UTC ``datetime64[ns, UTC]``, and the symbol's point."""

    d1: pd.DataFrame
    h4: pd.DataFrame
    h1: pd.DataFrame
    m15: pd.DataFrame
    m5: pd.DataFrame
    point: float

    def frame(self, tf: str) -> pd.DataFrame:
        return {"D1": self.d1, "H4": self.h4, "H1": self.h1, "M15": self.m15, "M5": self.m5}[tf]


def _ns(s: pd.Series) -> np.ndarray:
    """A datetime column as int64 nanoseconds since the epoch (UTC)."""
    return s.dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")


def check_frame(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Rule 10: no missing times, ``open_time`` strictly increasing, ``close_time > open_time``, and no bar
    overlapping the next (``close_time <= the next open_time``). Returns the frame with UTC ns time columns
    and a fresh index; gaps are taken as they are."""
    out = df.reset_index(drop=True).copy()
    out["open_time"] = pd.to_datetime(out["open_time"], utc=True)
    out["close_time"] = pd.to_datetime(out["close_time"], utc=True)
    if bool(out["open_time"].isna().any() or out["close_time"].isna().any()):
        raise ZoneError(f"{name}: a bar has a missing open_time or close_time")
    out["open_time"] = out["open_time"].astype("datetime64[ns, UTC]")
    out["close_time"] = out["close_time"].astype("datetime64[ns, UTC]")
    ot, ct = _ns(out["open_time"]), _ns(out["close_time"])
    if len(ot) > 1 and not bool(np.all(np.diff(ot) > 0)):
        raise ZoneError(f"{name}: open_time is not strictly increasing (duplicate or unsorted bars)")
    if not bool(np.all(ct > ot)):
        raise ZoneError(f"{name}: a bar has close_time <= open_time")
    if len(ot) > 1 and not bool(np.all(ct[:-1] <= ot[1:])):
        raise ZoneError(f"{name}: a bar overlaps the next one (close_time > the next open_time)")
    return out


def load_bars(market: str, data_dir: Path | str | None = None) -> Bars:
    """The five frames and ``point`` of a market. Any market but XAUUSD stops with "no bars for <market>"
    before anything is loaded."""
    if market not in MARKET_DIRS:
        raise ZoneError(f"no bars for {market}")
    d = Path(data_dir) if data_dir is not None else MARKET_DIRS[market]
    if not d.exists():
        raise ZoneError(f"no stored bars at {d}")
    point = float(json.loads((d / "spec.json").read_text(encoding="utf-8"))["spec"]["point"])
    fr = {tf: check_frame(pd.read_parquet(d / f"{tf}.parquet"), tf) for tf in ("D1", "H4", "H1", "M15", "M5")}
    return Bars(fr["D1"], fr["H4"], fr["H1"], fr["M15"], fr["M5"], point)


def cut_bars(bars: Bars, t: pd.Timestamp) -> Bars:
    """The bars known at ``t``: every frame's bars with ``close_time <= t`` (closed bars only)."""

    def cut(df: pd.DataFrame) -> pd.DataFrame:
        return df[df["close_time"] <= t].reset_index(drop=True)

    return Bars(cut(bars.d1), cut(bars.h4), cut(bars.h1), cut(bars.m15), cut(bars.m5), bars.point)


# --- rule 2: the step ---------------------------------------------------------------------------------------


def weekly_atr(d1: pd.DataFrame) -> pd.DataFrame:
    """Weekly bars from D1 in broker server time (``time_server``, weeks starting Sunday 00:00, W-SUN, label
    left), high = max, low = min, close = the last D1 close; ``atr`` = the simple mean of the last 14 weekly
    true ranges (MT5's ATR). ``done`` = the week's start + 7 days (server time read as UTC): when it counts as
    closed."""
    d = pd.DataFrame(
        {
            "high": d1["high"].to_numpy(float),
            "low": d1["low"].to_numpy(float),
            "close": d1["close"].to_numpy(float),
        },
        index=pd.to_datetime(d1["time_server"].to_numpy(), unit="s"),
    )
    wk = (
        d.resample("W-SUN", label="left", closed="left")
        .agg({"high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    wk["tr"] = pd.concat(
        [
            wk["high"] - wk["low"],
            (wk["high"] - wk["close"].shift()).abs(),
            (wk["low"] - wk["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    wk["atr"] = wk["tr"].rolling(14).mean()
    wk["done"] = (pd.DatetimeIndex(wk.index) + pd.Timedelta(days=7)).tz_localize("UTC")
    return wk


@dataclass(frozen=True)
class Months:
    """Each Thai month start and the step ``S`` of that month."""

    starts: tuple[pd.Timestamp, ...]
    step: dict[str, float]

    def at(self, t: pd.Timestamp) -> float:
        """The step of the Thai month that contains ``t``."""
        return self.step[t.tz_convert(TH).strftime("%Y-%m")]


def month_steps(d1: pd.DataFrame, h4: pd.DataFrame, params: ZoneParams, end: pd.Timestamp) -> Months:
    """The months run from the month before the first stored H4 bar to ``end`` (Thai month starts, 00:00
    Asia/Bangkok). ``S(m)`` = ``step_factor`` x the ATR of the last week closed at or before ``m`` (``watr``),
    or ``step_fixed`` (``fixed``)."""
    first = h4["open_time"].iloc[0].tz_convert(TH).tz_localize(None)
    m0 = first.replace(day=1, hour=0, minute=0, second=0, microsecond=0, nanosecond=0) - pd.DateOffset(
        months=1
    )
    naive = pd.date_range(m0, end.tz_convert(TH).tz_localize(None), freq="MS")
    starts = tuple(pd.Timestamp(m).tz_localize(TH) for m in naive)
    step: dict[str, float] = {}
    wk = weekly_atr(d1) if params.step_mode == "watr" else None
    for m in starts:
        if wk is None:
            s = params.step_fixed
        else:
            w = wk[(wk["done"] <= m) & wk["atr"].notna()]
            if len(w) == 0:
                raise ZoneError(f"no weekly ATR closed by {m}: the D1 history is too short for the step")
            s = params.step_factor * float(w["atr"].iloc[-1])
        step[m.strftime("%Y-%m")] = s
    return Months(starts, step)


# --- rule 3: the grids --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Grid:
    """A grid in force from ``start`` (a pair or month event time): lines ``anchor + k * step``."""

    start: pd.Timestamp
    anchor: float
    step: float
    cause: str  # "pair <a>/<b>" or "month"


def cluster_anchor(a: float, b: float, step: float, params: ZoneParams) -> float | None:
    """A pair is a cluster when ``|a - b|`` is within ``grid_tol x step`` of ``k x step`` for some k in
    ``grid_ks``; then the candidate anchor is the lower price. Otherwise None."""
    d = abs(a - b)
    if any(abs(d - k * step) <= params.grid_tol * step for k in params.grid_ks):
        return min(a, b)
    return None


def off_lines(price: float, anchor: float, step: float) -> float:
    """The distance from ``price`` to the nearest line of the grid (anchor, step)."""
    r = (price - anchor) % step
    return min(r, step - r)


def new_grid_needed(g: Grid | None, lo: float, step: float, params: ZoneParams) -> bool:
    """A pair's candidate anchor ``lo`` at step ``step`` starts a new grid when there is none yet, or ``lo``
    is more than ``shift_tol x S_g`` off the current lines, or the step differs by more than
    ``step_remake x S_g``."""
    if g is None:
        return True
    return (
        off_lines(lo, g.anchor, g.step) > params.shift_tol * g.step
        or abs(step - g.step) > params.step_remake * g.step
    )


def month_remake_needed(g: Grid | None, step: float, params: ZoneParams) -> bool:
    return g is not None and abs(step - g.step) > params.step_remake * g.step


def grids_from_events(
    pairs: list[tuple[pd.Timestamp, float, float]], months: Months, params: ZoneParams, end: pd.Timestamp
) -> list[Grid]:
    """Rule 3 over ``pairs`` (time the pair is known, price a, price b) and the month starts. Events in time
    order, equal times: pairs before months (a stable sort of pairs then months); events at or after ``end``
    are dropped."""
    events: list[tuple[pd.Timestamp, str, tuple[float, float] | None]] = [
        (t, "pair", (a, b)) for t, a, b in pairs
    ]
    events += [(m, "month", None) for m in months.starts]
    events.sort(key=lambda e: e[0].value)
    grids: list[Grid] = []
    for t, kind, pr in events:
        if t >= end:
            break
        st = months.at(t)
        cur = grids[-1] if grids else None
        if kind == "pair":
            if pr is None:
                raise ZoneError("a pair event without its prices")
            lo = cluster_anchor(pr[0], pr[1], st, params)
            if lo is None:
                continue
            if new_grid_needed(cur, lo, st, params):
                grids.append(Grid(t, lo, st, f"pair {pr[0]:.2f}/{pr[1]:.2f}"))
        elif cur is not None and month_remake_needed(cur, st, params):
            grids.append(Grid(t, cur.anchor, st, "month"))
    return grids


def build_grids(
    h4: pd.DataFrame, months: Months, params: ZoneParams, point: float, end: pd.Timestamp
) -> list[Grid]:
    """Rule 3: the H4 pairs (two neighbouring fixed H4 pivots, known at the close of the second one's
    ``confirm_pos`` bar) and the Thai month starts, in time order."""
    piv = zigzag_pivots(h4["high"].to_numpy(float), h4["low"].to_numpy(float), point)
    ct = h4["close_time"]
    pairs = [(ct.iloc[b.confirm_pos].tz_convert(TH), a.price, b.price) for a, b in pairwise(piv)]
    return grids_from_events(pairs, months, params, end)


def grid_index(grids: list[Grid]) -> np.ndarray:
    """The start times of the grids as int64 ns, for ``searchsorted``."""
    return np.array([g.start.value for g in grids], dtype="int64")


# --- rule 5d: the state -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PivotSet:
    """One timeframe's fixed pivots: the close time (ns) of the bar that knows each, is-HIGH, the price."""

    known_ns: np.ndarray
    is_high: np.ndarray
    price: np.ndarray


def fixed_pivots(df: pd.DataFrame, point: float) -> PivotSet:
    """``zigzag_pivots`` on all stored bars of the frame from its first bar (a run start never moves them)."""
    z = zigzag_pivots(df["high"].to_numpy(float), df["low"].to_numpy(float), point)
    ct = _ns(df["close_time"])
    return PivotSet(
        np.array([ct[p.confirm_pos] for p in z], dtype="int64"),
        np.array([p.kind.name == "HIGH" for p in z], dtype=bool),
        np.array([p.price for p in z], dtype=float),
    )


def is_trend(highs: np.ndarray, lows: np.ndarray) -> bool:
    """The frame trends when the last two HIGH and the last two LOW pivots both rise or both fall (strictly);
    otherwise - also with fewer than two of either - it is sideways."""
    if len(highs) < 2 or len(lows) < 2:
        return False
    h, lo = highs[-2:], lows[-2:]
    return bool((h[1] > h[0] and lo[1] > lo[0]) or (h[1] < h[0] and lo[1] < lo[0]))


def frame_trends(state: dict[str, PivotSet], t_ns: int) -> tuple[bool, bool, bool, bool]:
    """Per frame (D1, H4, H1, M15) whether it trends, from the pivots known at ``t_ns``."""
    out = []
    for tf in STATE_FRAMES:
        p = state[tf]
        m = p.known_ns <= t_ns
        out.append(is_trend(p.price[m & p.is_high], p.price[m & ~p.is_high]))
    return (out[0], out[1], out[2], out[3])


def sideways_share(
    trends: tuple[bool, bool, bool, bool], weights: tuple[float, float, float, float]
) -> float:
    """The sum of ``gate_w`` over the sideways frames."""
    return float(sum(0.0 if tr else w for tr, w in zip(trends, weights, strict=True)))


def build_state(bars: Bars) -> dict[str, PivotSet]:
    return {tf: fixed_pivots(bars.frame(tf), bars.point) for tf in STATE_FRAMES}


# --- rules 4 and 5: the visits and what each skip reads -----------------------------------------------------


@dataclass(frozen=True)
class Visit:
    """A visit (rule 4) with the readings of rule 5. The decision of each skip is a separate function."""

    time: pd.Timestamp  # the H1 bar's open, UTC
    i: int  # the H1 row
    side: str  # "BUY" | "SELL"
    sgn: int  # +1 BUY, -1 SELL
    line: float
    step: float  # S
    anchor: float  # the grid's A
    z: float  # near_frac x S
    h1_open: float
    # 5a
    mom_body: float  # the max body toward the line over i-mom_bars .. i-1
    mom_median: float  # the median H1 range over i-mom_med_bars .. i-1
    mom_run: float  # (close_{i-1} - open_{i-run_bars}) x -sgn
    # 5c
    ema_dist: float  # |close - EMA| at i-1
    atr: float  # H1 ATR at i-1
    # 5d
    trends: tuple[bool, bool, bool, bool]  # D1, H4, H1, M15: True = trends
    share: float  # the sideways share
    # the same-hour order
    j0: int  # the exec_tf row opening at or after the visit's time
    touch_j: int  # the first exec_tf row of the hour whose bid is within Z (none: j0 + per_h, or the end)
    from_open: float  # |H1 open - line|


def skip_momentum(v: Visit, params: ZoneParams) -> bool:
    """5a: a body toward the line at least the median range, or the run of ``run_bars`` bars at least S."""
    return v.mom_body >= v.mom_median or v.mom_run >= v.step


def skip_abnormal(v: Visit, params: ZoneParams) -> bool:
    """5c: |close - EMA| >= abn_atr x ATR (a missing ATR never skips)."""
    return bool(v.ema_dist >= params.abn_atr * v.atr)


def skip_busy(visit_time: pd.Timestamp, reservation_end: pd.Timestamp | None) -> bool:
    """5b: a visit at or before the end of the last setup's reservation is skipped (None = free)."""
    return reservation_end is not None and visit_time <= reservation_end


def skip_trend(v: Visit, params: ZoneParams) -> bool:
    """5d: skip when the sideways share is at or under ``gate_min``."""
    return v.share <= params.gate_min


def warmup_index(params: ZoneParams) -> int:
    """The 0-based row of the first H1 bar that can make a visit."""
    return max(params.mom_bars, params.mom_med_bars, params.run_bars, params.atr_len) + 10


def h1_indicators(h1: pd.DataFrame, params: ZoneParams) -> tuple[np.ndarray, np.ndarray]:
    """The H1 EMA(``ema_len``) (``ewm(span, adjust=False)`` over the whole series) and ATR(``atr_len``) (the
    simple mean of the last ``atr_len`` true ranges)."""
    ema = h1["close"].ewm(span=params.ema_len, adjust=False).mean().to_numpy()
    tr = pd.concat(
        [
            h1["high"] - h1["low"],
            (h1["high"] - h1["close"].shift()).abs(),
            (h1["low"] - h1["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return ema, tr.rolling(params.atr_len).mean().to_numpy()


def find_visits(
    bars: Bars,
    grids: list[Grid],
    params: ZoneParams,
    start: pd.Timestamp,
    end: pd.Timestamp,
    state: dict[str, PivotSet] | None = None,
) -> list[Visit]:
    """Rule 4: every visit of H1 bars from ``max(start, warm-up)`` to ``end`` (exclusive), in the order they
    are taken (rule 4's same-hour order: by hour, then the first exec_tf touch, then the distance from the H1
    open, then the line). Raises ``ZoneError`` if a visit lacks an hour of ``exec_tf`` history."""
    h1 = bars.h1
    ex = bars.frame(params.exec_tf)
    per_h = PER_H[params.exec_tf]
    if not grids:
        return []
    if state is None:
        state = build_state(bars)
    o, hi, lo, c = (h1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    rng = hi - lo
    h1_open_ns = _ns(h1["open_time"])
    ema, atr = h1_indicators(h1, params)
    ex_open_ns = _ns(ex["open_time"])
    ex_low, ex_high = ex["low"].to_numpy(float), ex["high"].to_numpy(float)
    gstart = grid_index(grids)
    armed: dict[tuple[float, float, float], bool] = {}  # key -> armed; absent = armed
    first = max(int(np.searchsorted(h1_open_ns, start.value, side="left")), warmup_index(params))
    out: list[Visit] = []
    for i in range(first, len(h1)):
        t_ns = int(h1_open_ns[i])
        if t_ns >= end.value:
            break
        gk = int(np.searchsorted(gstart, t_ns, side="right")) - 1
        if gk < 0:
            continue
        g = grids[gk]
        a, s = g.anchor, g.step
        z = params.near_frac * s
        away = params.away_frac * s
        ra, rs = round(a, 2), round(s, 2)
        # re-arm first: a disarmed line of this grid whose bar stays wholly away
        for key in [k for k, is_armed in armed.items() if not is_armed and k[0] == ra and k[1] == rs]:
            if lo[i] >= key[2] + away or hi[i] <= key[2] - away:
                armed[key] = True
        k_lo = math.ceil((lo[i] - z - a) / s) - 1
        k_hi = math.floor((hi[i] + z - a) / s) + 1
        for k in range(k_lo, k_hi + 1):
            line = round(a + k * s, 2)
            key = (ra, rs, line)
            down = lo[i] <= line + z and o[i] > line
            up = hi[i] >= line - z and o[i] < line
            if not (down or up) or not armed.get(key, True):
                continue
            armed[key] = False
            sgn = 1 if down else -1
            toward = (c[i - params.mom_bars : i] - o[i - params.mom_bars : i]) * -sgn
            run = float((c[i - 1] - o[i - params.run_bars]) * -sgn)
            trends = frame_trends(state, t_ns)
            j0 = int(np.searchsorted(ex_open_ns, t_ns, side="left"))
            if j0 < per_h:
                raise ZoneError(
                    f"{params.exec_tf} has no hour of history before the visit at "
                    f"{pd.Timestamp(t_ns, unit='ns', tz='UTC')} - start the run at "
                    f"{ex['open_time'].iloc[min(per_h, len(ex) - 1)]} or later"
                )
            jt = j0
            hour_end = t_ns + 3_600_000_000_000  # only exec bars of the visit's own hour
            while jt < min(j0 + per_h, len(ex)) and ex_open_ns[jt] < hour_end:
                if (sgn > 0 and ex_low[jt] <= line + z) or (sgn < 0 and ex_high[jt] >= line - z):
                    break
                jt += 1
            out.append(
                Visit(
                    time=pd.Timestamp(t_ns, unit="ns", tz="UTC"),
                    i=i,
                    side="BUY" if sgn > 0 else "SELL",
                    sgn=sgn,
                    line=line,
                    step=s,
                    anchor=a,
                    z=z,
                    h1_open=float(o[i]),
                    mom_body=float(toward.max()),
                    mom_median=float(np.median(rng[i - params.mom_med_bars : i])),
                    mom_run=run,
                    ema_dist=float(abs(c[i - 1] - ema[i - 1])),
                    atr=float(atr[i - 1]),
                    trends=trends,
                    share=sideways_share(trends, params.gate_w),
                    j0=j0,
                    touch_j=jt,
                    from_open=float(abs(o[i] - line)),
                )
            )
    out.sort(key=lambda v: (v.time.value, v.touch_j, v.from_open, v.line))
    return out


# --- rules 6 and 7: the setup, its fills and its exit -----------------------------------------------------


@dataclass(frozen=True)
class ExecBars:
    """The ``exec_tf`` frame as arrays (bid prices, the bar spread in points) and the bar close times."""

    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    spread: np.ndarray
    close_time: pd.Series

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> ExecBars:
        return cls(
            df["open"].to_numpy(float),
            df["high"].to_numpy(float),
            df["low"].to_numpy(float),
            df["close"].to_numpy(float),
            df["spread"].to_numpy(float),
            df["close_time"].reset_index(drop=True),
        )

    def __len__(self) -> int:
        return len(self.open)


@dataclass(frozen=True)
class Fill:
    name: str  # "P1" | "P2"
    j: int  # the exec row of the bar on which it filled
    price: float


@dataclass(frozen=True)
class Setup:
    """A visit that no skip stopped: the orders, what became of them and where its reservation ends."""

    visit: Visit
    p1: float
    p2: float
    sl: float
    tp: float
    outcome: str  # "traded" | "no fill" | "cancel" | "pending"
    fills: tuple[Fill, ...]
    exit_j: int | None  # the exec row of the exit (traded only)
    exit_price: float | None
    how: str | None  # "SL" | "TP" | "BE" | "open" (traded only)
    end_j: int  # the exec row whose close ends the reservation (rule 5b)
    end_time: pd.Timestamp  # that close
    be_sl: float | None = None  # the break-even SL, when it went on
    be_j: int | None = None  # the exec row of the bar that turned it on (it works from the next bar)


@dataclass(frozen=True)
class Position:
    setup: Setup
    fill: Fill
    pnl: float
    risk: float


def positions_of(s: Setup) -> list[Position]:
    """The filled positions of a traded setup: ``pnl = sgn x (exit - fill)``, ``risk = sgn x (fill - SL)``,
    unrounded. An SL exit with a pnl of 0 or more is a fault."""
    if s.exit_price is None:
        return []
    out = []
    for f in s.fills:
        pnl = s.visit.sgn * (s.exit_price - f.price)
        if s.how == "SL" and not pnl < 0:
            raise ZoneError(f"an SL exit with pnl {pnl} for the visit at {s.visit.time}")
        out.append(Position(s, f, pnl, s.visit.sgn * (f.price - s.sl)))
    return out


def setup_r(s: Setup) -> float:
    """A setup's R = the sum of its positions' pnl / the sum of their risks."""
    ps = positions_of(s)
    return sum(p.pnl for p in ps) / sum(p.risk for p in ps)


def simulate_setup(v: Visit, ex: ExecBars, params: ZoneParams, point: float) -> Setup:
    """Rules 6 and 7 for one visit that no skip stopped, bar by bar on ``exec_tf``."""
    sgn, s, line = v.sgn, v.step, v.line
    per_h = PER_H[params.exec_tf]
    p1 = line + sgn * params.p1_frac * s
    p2 = line - sgn * params.p2_frac * s
    sl = line - sgn * params.sl_frac * s
    tp = line + sgn * params.tp_steps * s
    away, cancel = params.away_frac * s, params.cancel_frac * s
    n, j0 = len(ex), v.j0
    if j0 < per_h:
        raise ZoneError(f"{params.exec_tf} has no hour of history before the visit at {v.time}")
    end = min(j0 + params.order_life_h * per_h, n)
    fills: list[Fill] = []
    out: tuple[int, float, str] | None = None
    cancelled = False
    j = j0
    be_on, cur_sl, be_j = False, sl, None  # the break-even (rule 7): on from the bar after its trigger
    while j < n:
        sp = ex.spread[j] * point
        if not fills:
            far = ex.high[j] - line if sgn > 0 else line - ex.low[j]
            if j >= end or (j > j0 and far >= away):  # (1) withdrawn / expired
                break
            if (ex.close[j - 1] - ex.open[j - per_h]) * -sgn >= cancel:  # (2) the closed-hour cancel
                cancelled = True
                break
        lo_px = ex.low[j] + sp if sgn > 0 else ex.low[j]
        for name, px in (("P1", p1), ("P2", p2)):  # (3) P1 then P2
            if any(f.name == name for f in fills) or (be_on and name == "P2"):
                continue  # an unfilled P2 is cancelled once the break-even is on
            hit = lo_px <= px if sgn > 0 else ex.high[j] >= px
            if hit and not fills and (px - ex.open[j - per_h]) * -sgn >= cancel:
                cancelled = True  # the fill-moment cancel stops the whole setup; P2 is not tested
                break
            if hit and (fills or j < end):
                fills.append(Fill(name, j, px))
        if cancelled:
            break
        if fills:  # (4) the exit test, on the fill bar too (the SL only there)
            stop = ex.low[j] <= cur_sl if sgn > 0 else ex.high[j] + sp >= cur_sl
            take = ex.high[j] >= tp if sgn > 0 else ex.low[j] + sp <= tp
            if stop:
                out = (j, cur_sl, "BE" if be_on else "SL")
            elif take and all(f.j < j for f in fills):
                out = (j, tp, "TP")
            if out:
                break
            if params.be_mode == "entry" and not be_on:  # the break-even: judged after this bar's exit test
                avg = float(np.mean([f.price for f in fills]))
                mid = avg + params.be_frac * (tp - avg)
                if (ex.high[j] >= mid) if sgn > 0 else (ex.low[j] + sp <= mid):
                    be_on, cur_sl, be_j = True, avg + sgn * sp, j  # from the next bar, at this bar's spread
        j += 1

    def done(
        outcome: str, end_j: int, exit_j: int | None, exit_price: float | None, how: str | None
    ) -> Setup:
        end_time = ex.close_time.iloc[end_j]
        be_sl = cur_sl if be_on else None
        return Setup(
            v, p1, p2, sl, tp, outcome, tuple(fills), exit_j, exit_price, how, end_j, end_time, be_sl, be_j
        )

    if cancelled:
        return done("cancel", j, None, None, None)
    if not fills:
        return done("pending", n - 1, None, None, None) if j >= n else done("no fill", j, None, None, None)
    if out is None:
        return done("traded", n - 1, n - 1, float(ex.close[n - 1]), "open")
    return done("traded", out[0], out[0], out[1], out[2])


@dataclass(frozen=True)
class Outcome:
    """What became of a visit: a skip reason, or the setup's outcome (``setup`` is set for those)."""

    visit: Visit
    reason: str  # momentum | busy | abnormal | trend | no fill | cancel | pending | traded
    setup: Setup | None


def apply_rules(visits: list[Visit], ex: ExecBars, params: ZoneParams, point: float) -> list[Outcome]:
    """Rule 8, visit by visit in 2a's order: 5a momentum, 5b busy, 5c abnormal, 5d trend, then rules 6 - 7.
    The end of the last setup that was not skipped is the next busy reference."""
    busy: pd.Timestamp | None = None
    out: list[Outcome] = []
    for v in visits:
        if skip_momentum(v, params):
            out.append(Outcome(v, "momentum", None))
        elif skip_busy(v.time, busy):
            out.append(Outcome(v, "busy", None))
        elif skip_abnormal(v, params):
            out.append(Outcome(v, "abnormal", None))
        elif skip_trend(v, params):
            out.append(Outcome(v, "trend", None))
        else:
            s = simulate_setup(v, ex, params, point)
            busy = s.end_time
            out.append(Outcome(v, s.outcome, s))
    return out


@dataclass(frozen=True)
class RunResult:
    grids: list[Grid]
    visits: list[Visit]
    outcomes: list[Outcome]
    ex: ExecBars


def run_zone(bars: Bars, params: ZoneParams, start: pd.Timestamp, end: pd.Timestamp) -> RunResult:
    """The whole simulation on stored bars from ``start`` to ``end`` (exclusive for visits)."""
    months = month_steps(bars.d1, bars.h4, params, end)
    grids = build_grids(bars.h4, months, params, bars.point, end)
    visits = find_visits(bars, grids, params, start, end)
    ex = ExecBars.from_frame(bars.frame(params.exec_tf))
    return RunResult(grids, visits, apply_rules(visits, ex, params, bars.point), ex)


# --- rule 11: the numbers -----------------------------------------------------------------------------------


def thai(t: pd.Timestamp) -> str:
    """ISO text in Thai time: ``2026-10-14 08:30:00+07:00``."""
    return t.tz_convert(TH).isoformat(sep=" ")


def traded(outcomes: list[Outcome]) -> list[Setup]:
    return [o.setup for o in outcomes if o.setup is not None and o.setup.outcome == "traded"]


def summary_stats(outcomes: list[Outcome]) -> dict[str, Any]:
    """Totals over the setups that were traded and closed (open ones are counted apart). Drawdown = the lowest
    (cumulative USD - its running peak) over the setups in visit-time order; a negative month = a Thai
    calendar month (by visit time) with at least one setup and a USD sum below 0."""
    setups = traded(outcomes)
    closed = [s for s in setups if s.how != "open"]
    usd = [sum(p.pnl for p in positions_of(s)) for s in closed]
    rs = [setup_r(s) for s in closed]
    months = [thai(s.visit.time)[:7] for s in closed]
    cum = np.cumsum(usd) if usd else np.array([])
    dd = float((cum - np.maximum.accumulate(cum)).min()) if usd else 0.0
    by_month: dict[str, float] = {}
    by_year: dict[str, list[tuple[float, float]]] = {}
    for m, u, r in zip(months, usd, rs, strict=True):
        by_month[m] = by_month.get(m, 0.0) + u
        by_year.setdefault(m[:4], []).append((u, r))
    reasons: dict[str, int] = {}
    for o in outcomes:
        reasons[o.reason] = reasons.get(o.reason, 0) + 1
    return {
        "setups": len(closed),
        "open": len([s for s in setups if s.how == "open"]),
        "be_exits": len([s for s in closed if s.how == "BE"]),
        "pending": reasons.get("pending", 0),
        "r_per_setup": float(np.mean(rs)) if rs else 0.0,
        "tp_share": float(np.mean([s.how == "TP" for s in closed])) if closed else 0.0,
        "usd": float(sum(usd)),
        "drawdown": dd,
        "months": len(by_month),
        "negative_months": sum(1 for u in by_month.values() if u < 0),
        "by_month": by_month,
        "by_year": {
            y: (len(v), float(np.mean([r for _, r in v])), float(sum(u for u, _ in v)))
            for y, v in by_year.items()
        },
        "reasons": reasons,
    }


def position_rows(outcomes: list[Outcome], ex: ExecBars) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for k, s in enumerate(traded(outcomes)):
        for p in positions_of(s):
            rows.append(
                {
                    "setup": k + 1,
                    "visit": thai(s.visit.time),
                    "pos": p.fill.name,
                    "side": s.visit.side,
                    "line": s.visit.line,
                    "S": s.visit.step,
                    "p1": s.p1,
                    "p2": s.p2,
                    "entry_t": thai(ex.close_time.iloc[p.fill.j]),
                    "entry": p.fill.price,
                    "sl": s.sl,
                    "tp": s.tp,
                    "be_sl": s.be_sl,
                    "be_time": thai(ex.close_time.iloc[s.be_j]) if s.be_j is not None else "",
                    "exit_t": thai(ex.close_time.iloc[s.exit_j if s.exit_j is not None else 0]),
                    "exit": s.exit_price,
                    "how": s.how,
                    "risk": p.risk,
                    "pnl": p.pnl,
                }
            )
    return rows


def visit_rows(outcomes: list[Outcome]) -> list[dict[str, Any]]:
    rows = []
    for o in outcomes:
        v = o.visit
        rows.append(
            {
                "visit": thai(v.time),
                "side": v.side,
                "line": v.line,
                "S": v.step,
                "anchor": v.anchor,
                "outcome": o.reason,
                "mom_body": v.mom_body,
                "mom_median": v.mom_median,
                "mom_run": v.mom_run,
                "ema_dist": v.ema_dist,
                "atr": v.atr,
                "trend_D1": v.trends[0],
                "trend_H4": v.trends[1],
                "trend_H1": v.trends[2],
                "trend_M15": v.trends[3],
                "share": v.share,
            }
        )
    return rows


def summary_rows(
    zone: str, params: ZoneParams, start: pd.Timestamp, end: pd.Timestamp, stats: dict[str, Any]
) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = [("zone", zone)]
    rows += [(f"param.{n}", param_to_text(n, getattr(params, n))) for n in FIELD_NAMES]
    rows += [("start", thai(start)), ("end", thai(end))]
    for k in (
        "setups",
        "open",
        "be_exits",
        "pending",
        "r_per_setup",
        "tp_share",
        "usd",
        "drawdown",
        "months",
        "negative_months",
    ):
        rows.append((k, stats[k]))
    rows += [(f"outcome.{k}", v) for k, v in sorted(stats["reasons"].items())]
    rows += [
        (f"year.{y}", f"setups={n} R={r:.6f} usd={u:.6f}")
        for y, (n, r, u) in sorted(stats["by_year"].items())
    ]
    rows += [(f"month.{m}", f"{u:.6f}") for m, u in sorted(stats["by_month"].items())]
    return rows


POSITION_COLUMNS = [
    "setup", "visit", "pos", "side", "line", "S", "p1", "p2", "entry_t", "entry", "sl", "tp",
    "be_sl", "be_time", "exit_t", "exit", "how", "risk", "pnl",
]  # fmt: skip
VISIT_COLUMNS = [
    "visit", "side", "line", "S", "anchor", "outcome", "mom_body", "mom_median", "mom_run", "ema_dist", "atr",
    "trend_D1", "trend_H4", "trend_H1", "trend_M15", "share",
]  # fmt: skip
GRID_COLUMNS = ["start", "anchor", "step", "cause"]


def summary_text(v: Any) -> str:
    """A summary value as text: floats to 6 decimals, everything else as it is."""
    if isinstance(v, (float, np.floating)):
        return f"{float(v):.6f}"
    return str(v)


def write_outputs(
    out_dir: Path, zone: str, params: ZoneParams, start: pd.Timestamp, end: pd.Timestamp, res: RunResult
) -> dict[str, Any]:
    """Rule 11: positions, visits, grids and summary CSVs (numbers to 6 decimals, times in Thai ISO)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%.6f"
    # explicit columns: an empty run still writes its header
    pos = pd.DataFrame(position_rows(res.outcomes, res.ex), columns=POSITION_COLUMNS)
    pos.to_csv(out_dir / "positions.csv", index=False, float_format=fmt)
    vis = pd.DataFrame(visit_rows(res.outcomes), columns=VISIT_COLUMNS)
    vis.to_csv(out_dir / "visits.csv", index=False, float_format=fmt)
    grid_rows = [
        {"start": thai(g.start), "anchor": g.anchor, "step": g.step, "cause": g.cause} for g in res.grids
    ]
    pd.DataFrame(grid_rows, columns=GRID_COLUMNS).to_csv(out_dir / "grids.csv", index=False, float_format=fmt)
    stats = summary_stats(res.outcomes)
    rows = [(n, summary_text(v)) for n, v in summary_rows(zone, params, start, end, stats)]
    pd.DataFrame(rows, columns=["name", "value"]).to_csv(out_dir / "summary.csv", index=False)
    return stats


# --- rule 11: the charts ------------------------------------------------------------------------------------


def chart_name(n: int, s: Setup, usd: float) -> str:
    """``<nn>_<win|loss|open>_<YYYYMMDD>.png`` (the date is the visit's, Thai)."""
    kind = "open" if s.how == "open" else ("win" if usd > 0 else "loss")
    return f"{n:02d}_{kind}_{s.visit.time.tz_convert(TH):%Y%m%d}.png"


def chart_window(df: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.DataFrame:
    """The bars of a frame that open at or after ``t0`` and close at or before ``t1``."""
    return df[(df["open_time"] >= t0) & (df["close_time"] <= t1)]


def draw_chart(
    path: Path,
    s: Setup,
    grid: Grid,
    bars: Bars,
    params: ZoneParams,
    usd: float,
    candle_xs: list[np.ndarray] | None = None,
    on_figure: Callable[[Any], None] | None = None,
) -> list[float]:
    """One setup, two panels (H1 from 6 days before the first fill to 1 day after the exit; ``exec_tf`` from
    10 hours before to 3 hours after), drawn as MT5 does: on a bar-index axis, candles side by side in order,
    market closures not drawn as empty space, the tick labels the bars' Thai times. Every grid line in view,
    the setup's line thick, fills marked and labelled at their bars, the SL and TP drawn at least a sixth of
    the panel wide with their distances, the exit marked.
    Returns each SL / TP segment's drawn length as a share of its panel's width (read from the artists);
    ``candle_xs``, if given, collects each panel's candle x positions; ``on_figure``, if given, is called with
    the finished figure just before it is saved (a hook for tests to read the drawn artists)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ex = bars.frame(params.exec_tf)
    v = s.visit
    first = ex["close_time"].iloc[s.fills[0].j]
    last = ex["close_time"].iloc[s.exit_j if s.exit_j is not None else s.end_j]
    spans = (
        (bars.h1, first - pd.Timedelta(days=6), last + pd.Timedelta(days=1), "H1"),
        (ex, first - pd.Timedelta(hours=10), last + pd.Timedelta(hours=3), params.exec_tf),
    )
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    fractions: list[float] = []
    for ax, (df, t0, t1, label) in zip(axes, spans, strict=True):
        w = chart_window(df, t0, t1)
        n = len(w)
        xs = np.arange(n)  # the bar index: consecutive, whatever the clock gap between bars
        open_ns = _ns(w["open_time"])

        def pos_of(exec_row: int, open_ns: np.ndarray = open_ns, n: int = n) -> int:
            """The panel position of the bar that contains the exec bar ``exec_row``."""
            t = int(ex["open_time"].iloc[exec_row].value)
            return int(min(max(int(np.searchsorted(open_ns, t, side="right")) - 1, 0), n - 1))

        colors = np.where((w["close"] >= w["open"]).to_numpy(), "#2a7a3b", "#b3302a")
        ax.vlines(xs, w["low"], w["high"], color=colors, linewidth=0.8)
        body = (w["close"] - w["open"]).abs().clip(lower=0.01)
        ax.bar(xs, body, bottom=np.minimum(w["open"], w["close"]), width=0.7, color=colors)
        if candle_xs is not None:
            candle_xs.append(xs)
        prices = [float(w["low"].min()), float(w["high"].max()), s.sl, s.tp, v.line]
        lo, hi = min(prices), max(prices)
        pad = (hi - lo) * 0.04
        ax.set_ylim(lo - pad, hi + pad)
        k0 = math.ceil((lo - pad - grid.anchor) / grid.step)
        k1 = math.floor((hi + pad - grid.anchor) / grid.step)
        for k in range(k0, k1 + 1):
            ln = round(grid.anchor + k * grid.step, 2)
            thick = ln == v.line
            ax.axhline(ln, color="#555555", linewidth=2.6 if thick else 0.6, alpha=0.9 if thick else 0.5)
        left = -0.5
        seg_start = pos_of(s.fills[0].j)
        exit_pos = pos_of(s.exit_j if s.exit_j is not None else s.end_j)
        # the panel's right edge, final: the last bar, the exit, and far enough that the SL / TP segment (from
        # the first fill's bar to that edge) is at least a sixth of the panel as drawn
        right = max(n - 0.5, exit_pos + 0.5, seg_start + max(seg_start - left, 0.0) / 4)
        segments = []
        for name, px, col in (("SL", s.sl, "#b3302a"), ("TP", s.tp, "#2a7a3b")):
            segments.append(ax.hlines(px, seg_start, right, color=col, linewidth=2.2))
            ax.text(
                seg_start,
                px,
                f" {name} {px:.2f} ({abs(px - v.line):.2f} from the line)",
                color=col,
                fontsize=8,
            )
        if s.be_sl is not None and s.be_j is not None and s.be_j + 1 < len(ex):
            bx = pos_of(s.be_j + 1)  # the break-even SL works from the bar after its trigger
            ax.hlines(s.be_sl, bx, right, color="#b3302a", linewidth=1.8, linestyle="--")
            ax.text(
                bx,
                s.be_sl,
                f" BE SL {s.be_sl:.2f} ({abs(s.be_sl - v.line):.2f} from the line)",
                color="#b3302a",
                fontsize=8,
                va="top",
            )
        for f in s.fills:
            fx = pos_of(f.j)
            ax.plot([fx], [f.price], marker="^" if v.sgn > 0 else "v", color="#1f4e9c", markersize=9)
            ax.text(fx, f.price, f" {f.name} {f.price:.2f}", color="#1f4e9c", fontsize=8, va="top")
        if s.exit_j is not None and s.exit_price is not None:
            ax.plot([exit_pos], [s.exit_price], marker="X", color="black", markersize=11)
            ax.text(exit_pos, s.exit_price, f" exit {s.how} {s.exit_price:.2f}", fontsize=8, va="bottom")
        ax.set_xlim(left, right)
        ticks = np.unique(np.linspace(0, n - 1, min(8, n)).round().astype(int))
        ax.set_xticks(ticks)
        ax.set_xticklabels(
            [w["open_time"].iloc[int(i)].tz_convert(TH).strftime("%m-%d %H:%M") for i in ticks],
            rotation=20,
            ha="right",
        )
        lo_x, hi_x = ax.get_xlim()
        for lc in segments:  # read back from the drawn artists
            (x0, _), (x1, _) = lc.get_segments()[0]
            fractions.append((x1 - x0) / (hi_x - lo_x))
        ax.set_ylabel(label)
        ax.tick_params(axis="x", labelsize=7)
    fills = ", ".join(f"{f.name} {f.price:.2f}" for f in s.fills)
    fig.suptitle(
        f"{v.side} line {v.line:.2f} step {v.step:.2f} | fills {fills} | SL {s.sl:.2f} TP {s.tp:.2f} | "
        f"{s.how} {usd:+.2f} USD | visit {thai(v.time)}",
        fontsize=10,
    )
    fig.tight_layout()
    if on_figure is not None:
        on_figure(fig)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=80)
    plt.close(fig)
    return fractions


def write_charts(
    out_dir: Path, res: RunResult, bars: Bars, params: ZoneParams, fractions: list[float] | None = None
) -> list[Path]:
    """One PNG per traded setup (a setup with no fill has nothing to draw). The PNGs of an earlier run in
    ``<out>/charts`` are removed first (nothing else in the folder is touched). ``fractions``, if given,
    collects every SL / TP segment's drawn share of its panel's width."""
    charts = out_dir / "charts"
    if charts.is_dir():
        for old in charts.glob("*.png"):
            old.unlink()
    gstart = grid_index(res.grids)
    paths = []
    for n, s in enumerate(traded(res.outcomes), start=1):
        g = res.grids[int(np.searchsorted(gstart, s.visit.time.value, side="right")) - 1]
        usd = sum(p.pnl for p in positions_of(s))
        path = charts / chart_name(n, s, usd)
        shares = draw_chart(path, s, g, bars, params, usd)
        if fractions is not None:
            fractions.extend(shares)
        paths.append(path)
    return paths


# --- the command line ---------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The run-zone setup on stored bars (eye/ZONE_RULES.md).")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--market", default="XAUUSD")
    ap.add_argument("--set", dest="set_name", default="default")
    ap.add_argument("--start", default="2023-10-01", help="Thai date")
    ap.add_argument("--end", default=None, help="Thai date, exclusive (default: the last stored H1 bar)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-charts", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.market not in MARKET_DIRS:
            raise ZoneError(f"no bars for {a.market}")
        params, version = load_params(a.db, a.market, a.set_name)
        bars = load_bars(a.market)
        start = pd.Timestamp(a.start, tz=TH)
        end = pd.Timestamp(a.end, tz=TH) if a.end else bars.h1["close_time"].iloc[-1]
        zone = f"zone={a.market}/{a.set_name}@v{version}"
        out_dir = Path(a.out) if a.out else ROOT / "eye" / "research" / "zone" / a.market / a.set_name
        res = run_zone(bars, params, start, end)
        stats = write_outputs(out_dir, zone, params, start, end, res)
        n_charts = 0 if a.no_charts else len(write_charts(out_dir, res, bars, params))
    except (ConfigError, ZoneError) as e:
        print(f"zone_bot: {e}", file=sys.stderr)
        return 1
    print(
        f"{zone}: setups {stats['setups']}, {stats['r_per_setup']:+.3f} R a setup, "
        f"TP {stats['tp_share']:.0%}, "
        f"USD {stats['usd']:+.1f}, drawdown {stats['drawdown']:.1f}, open {stats['open']}, "
        f"pending {stats['pending']}, charts {n_charts}; skips {stats['reasons']}; out {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
