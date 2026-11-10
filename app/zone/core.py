"""The run-zone setup's pure logic (eye/ZONE_RULES.md; ZONE_LIVE L0): the step, the grids, the visits, the
skips, the setup's life bar by bar, the numbers.

Pure functions over bars - no broker, no clock, no file writes (bars are only read). The simulation
(``eye/zone_bot.py``) and the real-time runner both call it. The reference this reproduces is
``eye/research/zone_reference.py`` (v3, ``ZFIX=1``); where it and the specification differ, the specification
wins.

Closed bars only: every reading at time ``t`` uses bars and pivots whose close time is at or before ``t`` (the
visit test itself reads the H1 bar as it happens, rule 4). Times are UTC internally (``pandas`` timestamps
with ``tz="UTC"``); Thai time (Asia/Bangkok) is used for months only.

Independent of the Fibonacci bot (rule 0) and of ``eye/``: nothing is imported from either.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.indicators.chart_read import zigzag_pivots
from app.zone.params import ZoneParams

ROOT = Path(__file__).resolve().parents[2]

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


ALL_FRAMES = ("D1", "H4", "H1", "M15", "M5")


def load_bars(market: str, data_dir: Path | str | None = None, frames: tuple[str, ...] = ALL_FRAMES) -> Bars:
    """The five frames and ``point`` of a market (``frames``: only those; the others are left empty, never
    read). Any market but XAUUSD stops with "no bars for <market>" before anything is loaded."""
    if market not in MARKET_DIRS:
        raise ZoneError(f"no bars for {market}")
    d = Path(data_dir) if data_dir is not None else MARKET_DIRS[market]
    if not d.exists():
        raise ZoneError(f"no stored bars at {d}")
    point = float(json.loads((d / "spec.json").read_text(encoding="utf-8"))["spec"]["point"])
    fr = {
        tf: check_frame(pd.read_parquet(d / f"{tf}.parquet"), tf) if tf in frames else pd.DataFrame()
        for tf in ALL_FRAMES
    }
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


@dataclass(frozen=True)
class H1Reader:
    """The H1 frame and the ``exec_tf`` frame as arrays, with the H1 EMA / ATR: what the readings of one H1
    bar (``visits_at_bar``) need. Built once per run by ``H1Reader.build``; a real-time runner builds it
    again when a bar has closed."""

    o: np.ndarray
    hi: np.ndarray
    lo: np.ndarray
    c: np.ndarray
    rng: np.ndarray
    h1_open_ns: np.ndarray
    ema: np.ndarray
    atr: np.ndarray
    ex_open_ns: np.ndarray
    ex_low: np.ndarray
    ex_high: np.ndarray
    ex_open_time: pd.Series
    per_h: int
    state: dict[str, PivotSet]

    @classmethod
    def build(cls, bars: Bars, params: ZoneParams, state: dict[str, PivotSet] | None = None) -> H1Reader:
        h1 = bars.h1
        ex = bars.frame(params.exec_tf)
        if state is None:
            state = build_state(bars)
        o, hi, lo, c = (h1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        ema, atr = h1_indicators(h1, params)
        return cls(
            o,
            hi,
            lo,
            c,
            hi - lo,
            _ns(h1["open_time"]),
            ema,
            atr,
            _ns(ex["open_time"]),
            ex["low"].to_numpy(float),
            ex["high"].to_numpy(float),
            ex["open_time"],
            PER_H[params.exec_tf],
            state,
        )

    def __len__(self) -> int:
        return len(self.o)


def visits_at_bar(
    r: H1Reader,
    i: int,
    g: Grid,
    armed: dict[tuple[float, float, float], bool],
    params: ZoneParams,
    *,
    readings: bool = True,
) -> list[Visit]:
    """Rule 4 for the H1 bar ``i`` under the grid ``g``: the re-arming update, then the visits of the bar's
    lines, each with the readings of rule 5 (``armed`` is updated in place; absent = armed). The visits are in
    line order, not yet in the same-hour order. Raises ``ZoneError`` if a visit lacks an hour of ``exec_tf``
    history. With ``readings`` False only the arming is updated (nothing is read from ``exec_tf``; no visit is
    returned): the arming depends on closed H1 bars alone."""
    o, hi, lo, c = r.o, r.hi, r.lo, r.c
    t_ns = int(r.h1_open_ns[i])
    a, s = g.anchor, g.step
    z = params.near_frac * s
    away = params.away_frac * s
    ra, rs = round(a, 2), round(s, 2)
    out: list[Visit] = []
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
        if not readings:
            continue
        sgn = 1 if down else -1
        toward = (c[i - params.mom_bars : i] - o[i - params.mom_bars : i]) * -sgn
        run = float((c[i - 1] - o[i - params.run_bars]) * -sgn)
        trends = frame_trends(r.state, t_ns)
        j0 = int(np.searchsorted(r.ex_open_ns, t_ns, side="left"))
        if j0 < r.per_h:
            raise ZoneError(
                f"{params.exec_tf} has no hour of history before the visit at "
                f"{pd.Timestamp(t_ns, unit='ns', tz='UTC')} - start the run at "
                f"{r.ex_open_time.iloc[min(r.per_h, len(r.ex_open_time) - 1)]} or later"
            )
        jt = j0
        hour_end = t_ns + 3_600_000_000_000  # only exec bars of the visit's own hour
        while jt < min(j0 + r.per_h, len(r.ex_open_ns)) and r.ex_open_ns[jt] < hour_end:
            if (sgn > 0 and r.ex_low[jt] <= line + z) or (sgn < 0 and r.ex_high[jt] >= line - z):
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
                mom_median=float(np.median(r.rng[i - params.mom_med_bars : i])),
                mom_run=run,
                ema_dist=float(abs(c[i - 1] - r.ema[i - 1])),
                atr=float(r.atr[i - 1]),
                trends=trends,
                share=sideways_share(trends, params.gate_w),
                j0=j0,
                touch_j=jt,
                from_open=float(abs(o[i] - line)),
            )
        )
    return out


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
    if not grids:
        return []
    r = H1Reader.build(bars, params, state)
    gstart = grid_index(grids)
    armed: dict[tuple[float, float, float], bool] = {}  # key -> armed; absent = armed
    first = max(int(np.searchsorted(r.h1_open_ns, start.value, side="left")), warmup_index(params))
    out: list[Visit] = []
    for i in range(first, len(r)):
        t_ns = int(r.h1_open_ns[i])
        if t_ns >= end.value:
            break
        gk = int(np.searchsorted(gstart, t_ns, side="right")) - 1
        if gk < 0:
            continue
        out.extend(visits_at_bar(r, i, grids[gk], armed, params))
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


@dataclass(frozen=True)
class SetupPlan:
    """What is fixed when a setup is taken: its prices (rule 6) and the constants its life reads."""

    sgn: int
    line: float
    p1: float
    p2: float
    sl: float
    tp: float
    away: float  # away_frac x S
    cancel: float  # cancel_frac x S
    j0: int  # the exec row opening at or after the visit's time
    end: int  # the exec row from which an unfilled setup is withdrawn: j0 + order_life_h x per_h
    per_h: int
    be_entry: bool  # be_mode == "entry"
    be_frac: float


def plan_setup(v: Visit, params: ZoneParams) -> SetupPlan:
    """The prices and constants of a setup for the visit ``v`` (rule 6)."""
    sgn, s, line = v.sgn, v.step, v.line
    per_h = PER_H[params.exec_tf]
    if v.j0 < per_h:
        raise ZoneError(f"{params.exec_tf} has no hour of history before the visit at {v.time}")
    return SetupPlan(
        sgn=sgn,
        line=line,
        p1=line + sgn * params.p1_frac * s,
        p2=line - sgn * params.p2_frac * s,
        sl=line - sgn * params.sl_frac * s,
        tp=line + sgn * params.tp_steps * s,
        away=params.away_frac * s,
        cancel=params.cancel_frac * s,
        j0=v.j0,
        end=v.j0 + params.order_life_h * per_h,
        per_h=per_h,
        be_entry=params.be_mode == "entry",
        be_frac=params.be_frac,
    )


@dataclass(frozen=True)
class BarValues:
    """What the life of a setup reads of the ``exec_tf`` bar ``j``: its bid high / low, its spread in price
    (``spread x point``), the close of the bar before it, and the open of the bar ``per_h`` bars before it."""

    high: float
    low: float
    spread_px: float
    prev_close: float
    open_hour_ago: float


def bar_values(ex: ExecBars, j: int, per_h: int, point: float) -> BarValues:
    return BarValues(
        ex.high[j], ex.low[j], ex.spread[j] * point, ex.close[j - 1], ex.open[j - per_h]
    )  # numpy scalars on purpose: the comparisons are the simulation's own


@dataclass(frozen=True)
class SetupLife:
    """A setup's state after some bar. ``status``: ``live`` (the next bar is next), ``withdrawn`` (rule 6:
    expired or moved away with nothing filled), ``cancel`` (the closed-hour or fill-moment cancel), ``exit``
    (rule 7: ``how`` SL / BE / TP at ``exit_price`` on the bar ``exit_j``)."""

    status: str
    fills: tuple[Fill, ...]
    cur_sl: float  # the SL in force (the plan's, or the break-even's)
    be_on: bool = False
    be_j: int | None = None
    exit_j: int | None = None
    exit_price: float | None = None
    how: str | None = None


def start_life(plan: SetupPlan) -> SetupLife:
    """The state before the first bar ``j0``: nothing filled, the plan's SL."""
    return SetupLife("live", (), plan.sl)


def step_setup(plan: SetupPlan, life: SetupLife, j: int, b: BarValues) -> SetupLife:
    """The state after the bar ``j`` given the state after the bar ``j - 1`` (``start_life`` before ``j0``):
    rules 6 and 7, in the order and with the comparisons of the simulation - (1) withdrawn / expired, (2) the
    closed-hour cancel (both only while nothing is filled), (3) P1 then P2 with the fill-moment cancel,
    (4) the exit test (SL, then TP only on a later bar than every fill), then the break-even. A state that is
    not ``live`` is returned as it is."""
    if life.status != "live":
        return life
    sgn, line, p1, p2, tp = plan.sgn, plan.line, plan.p1, plan.p2, plan.tp
    sp = b.spread_px
    fills = list(life.fills)
    be_on, cur_sl, be_j = life.be_on, life.cur_sl, life.be_j
    if not fills:
        far = b.high - line if sgn > 0 else line - b.low
        if j >= plan.end or (j > plan.j0 and far >= plan.away):  # (1) withdrawn / expired
            return SetupLife("withdrawn", (), cur_sl, be_on, be_j)
        if (b.prev_close - b.open_hour_ago) * -sgn >= plan.cancel:  # (2) the closed-hour cancel
            return SetupLife("cancel", (), cur_sl, be_on, be_j)
    lo_px = b.low + sp if sgn > 0 else b.low
    for name, px in (("P1", p1), ("P2", p2)):  # (3) P1 then P2
        if any(f.name == name for f in fills) or (be_on and name == "P2"):
            continue  # an unfilled P2 is cancelled once the break-even is on
        hit = lo_px <= px if sgn > 0 else b.high >= px
        if hit and not fills and (px - b.open_hour_ago) * -sgn >= plan.cancel:
            # the fill-moment cancel stops the whole setup; P2 is not tested
            return SetupLife("cancel", (), cur_sl, be_on, be_j)
        if hit and (fills or j < plan.end):
            fills.append(Fill(name, j, px))
    if fills:  # (4) the exit test, on the fill bar too (the SL only there)
        stop = b.low <= cur_sl if sgn > 0 else b.high + sp >= cur_sl
        take = b.high >= tp if sgn > 0 else b.low + sp <= tp
        if stop:
            return SetupLife("exit", tuple(fills), cur_sl, be_on, be_j, j, cur_sl, "BE" if be_on else "SL")
        if take and all(f.j < j for f in fills):
            return SetupLife("exit", tuple(fills), cur_sl, be_on, be_j, j, tp, "TP")
        if plan.be_entry and not be_on:  # the break-even: judged after this bar's exit test
            avg = float(np.mean([f.price for f in fills]))
            mid = avg + plan.be_frac * (tp - avg)
            if (b.high >= mid) if sgn > 0 else (b.low + sp <= mid):
                be_on, cur_sl, be_j = True, avg + sgn * sp, j  # from the next bar, at this bar's spread
    return SetupLife("live", tuple(fills), cur_sl, be_on, be_j)


def simulate_setup(v: Visit, ex: ExecBars, params: ZoneParams, point: float) -> Setup:
    """Rules 6 and 7 for one visit that no skip stopped, bar by bar on ``exec_tf`` (a loop over
    ``step_setup``)."""
    plan = plan_setup(v, params)
    n, j0 = len(ex), v.j0
    life = start_life(plan)
    j = j0
    while j < n:
        life = step_setup(plan, life, j, bar_values(ex, j, plan.per_h, point))
        if life.status != "live":
            break
        j += 1

    def done(
        outcome: str, end_j: int, exit_j: int | None, exit_price: float | None, how: str | None
    ) -> Setup:
        end_time = ex.close_time.iloc[end_j]
        be_sl = life.cur_sl if life.be_on else None
        return Setup(
            v,
            plan.p1,
            plan.p2,
            plan.sl,
            plan.tp,
            outcome,
            life.fills,
            exit_j,
            exit_price,
            how,
            end_j,
            end_time,
            be_sl,
            life.be_j,
        )

    if life.status == "cancel":
        return done("cancel", j, None, None, None)
    if life.status == "exit":
        return done("traded", j, j, life.exit_price, life.how)
    if not life.fills:
        return done("pending", n - 1, None, None, None) if j >= n else done("no fill", j, None, None, None)
    return done("traded", n - 1, n - 1, float(ex.close[n - 1]), "open")


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
