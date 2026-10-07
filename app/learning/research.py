"""Research harness: hypotheses about a setup, tested the same way every time (TAA-L707; SETUP_REVIEW).

Pure functions over closed ``PLAN`` shadow trades (:class:`Signal`, REPLAY or LIVE) and the stored bid bars of
their horizon (M1 or M5). Nothing here changes what the bot trades: every result is a hypothetical, bar-based
re-simulation, and a finding is a proposal for a shadow variant (TAA-L702), never a config change.

**Price path.** Each signal becomes a :class:`PricePath` in units of its own risk (entry to initial stop),
measured on exit-side prices from the recorded entry fill, like the shadow resolver
(:mod:`app.advisory.shadow`): a BUY exits at the bid (the bar), a SELL at the ask (the bar plus its spread).
The path starts with the first bar that opens at or after the entry and ends before the time stop; the open
of the first bar at or after the time stop closes what is still open (``end``).

**Exit rules** (:class:`Rules`) are applied bar by bar in the resolver's order: an open beyond the stop fills
at the open, an open beyond the target fills at the target (never better), a bar reaching the stop counts
before anything else in it (pessimistic), then a partial, the target, and only then are break-even, trailing
and the time stop updated for the next bar. A stop multiplier keeps the risk percent: the lot shrinks, so the
result and the known costs are divided by it.

**Retest entries** wait ``wait_bars`` entry-timeframe bars for a limit ``depth`` risks against the signal;
the limit fills only when the entry-side price reaches it (the exit-side path plus the signal's spread), never
at a better price. The stop sits ``stop`` risks from the signal's entry; an unfilled retest is no trade
(``None`` alone, 0 R in paired comparisons).

**Costs.** The spread is in the prices. Commission and swap are the stored trade's ``r_multiple − r_net``
(swap depends on the holding time, so this is an approximation for variants that hold longer or shorter).

**Honesty rules.** Every statistic is a mean R with a seeded bootstrap CI for all signals and for each half
(split at the midpoint of the signals' time range unless given). A rule chosen on one half is reported only
on the other (:func:`walk_forward`), with the number of rules it was chosen from.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.core.clock import ensure_utc
from app.core.enums import Side, Timeframe
from app.core.errors import TaaError

HORIZON = timedelta(hours=72)  # the shadow resolver's default time stop
CONFIDENCE = 0.90
RESAMPLES = 1000
MIN_N = 20  # below this a statistic has no interval
MIN_RULE_N = 100  # a walk-forward candidate needs this many signals on the half it is chosen on
EMA_SPAN = 20
ATR_BARS = 14
ATR_PCT_BARS = 100
RANGE_BARS = 20


class ResearchError(TaaError):
    pass


# --- inputs -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Signal:
    """One closed ``PLAN`` shadow trade: the signal as it was entered and its stored result."""

    shadow_id: str
    strategy: str
    symbol: str
    timeframe: Timeframe  # the entry timeframe
    side: Side
    signal_at: datetime  # the signal bar's close
    entry_at: datetime
    entry: float  # the fill (ask for a BUY, bid for a SELL, slippage included)
    initial_sl: float
    tp: float | None
    atr: float | None
    spread: float  # price units at the signal
    cost_r: float  # commission and swap in R (r_multiple - r_net)
    r_net: float
    features: Mapping[str, float] = field(default_factory=dict)

    @property
    def risk(self) -> float:
        return (self.entry - self.initial_sl) * self.side.sign

    def mirrored(self) -> Signal:
        """The same instant taken the other way: the other side of the spread, same distances and costs."""
        sign = self.side.sign
        entry = self.entry - sign * self.spread
        tp = None if self.tp is None else entry - sign * abs(self.tp - self.entry)
        return Signal(
            f"{self.shadow_id}:mirror",
            self.strategy,
            self.symbol,
            self.timeframe,
            self.side.opposite,
            self.signal_at,
            self.entry_at,
            entry,
            entry + sign * self.risk,
            tp,
            self.atr,
            self.spread,
            self.cost_r,
            float("nan"),
            self.features,
        )


@dataclass(frozen=True, slots=True)
class PricePath:
    """Exit-side prices after the entry, in risks from the entry fill (positive = in the trade's favour)."""

    open: np.ndarray
    fav: np.ndarray  # the bar's best price for the position
    adv: np.ndarray  # the bar's worst price for the position
    close: np.ndarray
    end: float | None  # the open at the time stop; None when the data ends first (censored)
    target: float | None  # the signal's target in risks
    spread_r: float  # the signal's spread in risks (entry-side price = exit-side + spread)
    cost_r: float
    per_bar: int  # path bars per entry-timeframe bar

    def __len__(self) -> int:
        return len(self.open)

    @property
    def final(self) -> float:
        """Where a trade still open at the end of the path closes."""
        if self.end is not None:
            return self.end
        return float(self.close[-1]) if len(self.close) else 0.0


def build_path(
    signal: Signal, bars: pd.DataFrame, *, point: float, horizon: timedelta = HORIZON
) -> PricePath:
    """The signal's path over *bars*: bid OHLC sorted by ``open_time`` (UTC), ``spread`` in points."""
    risk = signal.risk
    if not risk > 0:
        raise ResearchError(f"{signal.shadow_id}: the stop is not on the losing side of the entry")
    start = pd.Timestamp(ensure_utc(signal.entry_at))
    deadline = start + pd.Timedelta(horizon)
    times = pd.DatetimeIndex(bars["open_time"])
    i0, i1 = times.searchsorted(start), times.searchsorted(deadline)
    window = bars.iloc[i0:i1]
    after = bars.iloc[i1 : i1 + 1]
    sign = signal.side.sign

    def rel(price: np.ndarray) -> np.ndarray:
        return (price - signal.entry) * sign / risk

    offset = 0.0 if signal.side is Side.BUY else 1.0  # a SELL exits at the ask
    spread = window["spread"].to_numpy(dtype=float) * point * offset
    high = window["high"].to_numpy(dtype=float) + spread
    low = window["low"].to_numpy(dtype=float) + spread
    end = None
    if not after.empty:
        first = after.iloc[0]
        end = float(rel(np.array([float(first["open"]) + float(first["spread"]) * point * offset]))[0])
    bar_seconds = _bar_seconds(bars)
    return PricePath(
        open=rel(window["open"].to_numpy(dtype=float) + spread),
        fav=rel(high if sign > 0 else low),
        adv=rel(low if sign > 0 else high),
        close=rel(window["close"].to_numpy(dtype=float) + spread),
        end=end,
        target=None if signal.tp is None else abs(signal.tp - signal.entry) / risk,
        spread_r=signal.spread / risk,
        cost_r=signal.cost_r,
        per_bar=max(1, signal.timeframe.seconds // bar_seconds),
    )


def _bar_seconds(bars: pd.DataFrame) -> int:
    if len(bars) == 0:
        return 60
    span = (bars["close_time"].iloc[0] - bars["open_time"].iloc[0]) / pd.Timedelta(seconds=1)
    return max(60, round(span / 60) * 60)


# --- re-simulation ------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rules:
    """Exit rules in risks of the ORIGINAL stop; the result is in R of the variant's own risk."""

    target: float | None = None  # None: the signal's own target
    target_scale: float = 1.0
    stop_mult: float = 1.0
    break_even: tuple[float, float] | None = None  # (after +x, stop to y)
    partial: tuple[float, float] | None = None  # (fraction, at +x)
    trail: tuple[float, float] | None = None  # (once +x, distance d)
    time_bars: int | None = None  # entry bars without reaching +time_min
    time_min: float = 0.5


AS_TRADED = Rules()


def simulate(path: PricePath, rules: Rules = AS_TRADED) -> float | None:
    """A market entry at the signal under *rules*; None when the path holds no bar."""
    if len(path) == 0:
        return None
    own = path.target if rules.target is None else rules.target
    target = None if own is None else own * rules.target_scale
    stop = -rules.stop_mult
    taken, rest, best = 0.0, 1.0, 0.0

    def result(price: float) -> float:
        return (taken + rest * price - path.cost_r) / rules.stop_mult

    for i in range(len(path)):
        if path.open[i] <= stop:
            return result(float(path.open[i]))
        if target is not None and path.open[i] >= target:
            return result(target)
        if path.adv[i] <= stop:
            return result(stop)
        if rules.partial is not None and rest == 1.0 and path.fav[i] >= rules.partial[1]:
            taken, rest = rules.partial[0] * rules.partial[1], 1.0 - rules.partial[0]
        if target is not None and path.fav[i] >= target:
            return result(target)
        best = max(best, float(path.fav[i]))
        if rules.break_even is not None and best >= rules.break_even[0]:
            stop = max(stop, rules.break_even[1])
        if rules.trail is not None and best >= rules.trail[0]:
            stop = max(stop, best - rules.trail[1])
        if rules.time_bars is not None and i + 1 >= rules.time_bars * path.per_bar and best < rules.time_min:
            return result(float(path.close[i]))
    return result(path.final)


@dataclass(frozen=True, slots=True)
class Retest:
    """A limit ``depth`` risks against the signal, ``wait_bars`` entry bars long; stop ``stop`` from entry."""

    depth: float
    stop: float
    wait_bars: int
    target_scale: float = 1.0


def simulate_retest(path: PricePath, retest: Retest) -> float | None:
    """The retest entry; None when the limit never fills (or the path is empty)."""
    if not retest.stop > retest.depth:
        raise ResearchError("a retest stop must lie beyond its limit")
    if path.target is None:
        return None
    window = min(len(path), retest.wait_bars * path.per_bar)
    touched = np.nonzero(path.adv[:window] + path.spread_r <= -retest.depth)[0]
    if len(touched) == 0:
        return None
    i0 = int(touched[0])
    risk = retest.stop - retest.depth
    target = path.target * retest.target_scale

    def result(price: float) -> float:
        return (price + retest.depth - path.cost_r) / risk

    for i in range(i0, len(path)):
        if i > i0 and path.open[i] <= -retest.stop:
            return result(float(path.open[i]))
        if path.adv[i] <= -retest.stop:
            return result(-retest.stop)
        if i > i0 and path.fav[i] >= target:  # the fill bar's high may have come before the fill
            return result(target)
    return result(path.final)


def simulate_reentry(path: PricePath, within_bars: int) -> float | None:
    """As traded; after a stop-out, one more entry at the original entry price within *within_bars* bars."""
    first = simulate(path)
    if first is None:
        return None
    hit = np.nonzero(path.adv <= -1.0)[0]
    if not len(hit) or first > -0.99:
        return first
    j0 = int(hit[0]) + 1
    back = np.nonzero(path.fav[j0 : j0 + within_bars * path.per_bar] >= 0.0)[0]
    if not len(back):
        return first
    k = j0 + int(back[0]) + 1  # the touch bar's open and range came before the new entry: count from the next
    second = PricePath(
        path.open[k:],
        path.fav[k:],
        path.adv[k:],
        path.close[k:],
        path.end,
        path.target,
        path.spread_r,
        path.cost_r,
        path.per_bar,
    )
    again = simulate(second)
    return first if again is None else first + again


# --- statistics ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Stat:
    n: int
    mean: float | None
    low: float | None  # bootstrap CI; None below MIN_N
    high: float | None
    win_rate: float | None


def summarize(
    values: Sequence[float], *, seed: int = 0, resamples: int = RESAMPLES, confidence: float = CONFIDENCE
) -> Stat:
    """Mean with a seeded percentile-bootstrap CI (the same values always give the same interval)."""
    n = len(values)
    if n == 0:
        return Stat(0, None, None, None, None)
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    win = float((arr > 0).mean())
    if n < MIN_N:
        return Stat(n, round(mean, 4), None, None, round(win, 4))
    rng = np.random.default_rng(seed)
    means = np.sort(arr[rng.integers(0, n, size=(resamples, n))].mean(axis=1))
    tail = (1 - confidence) / 2
    low = float(means[max(0, math.floor(tail * resamples))])
    high = float(means[min(resamples - 1, math.ceil((1 - tail) * resamples) - 1)])
    return Stat(n, round(mean, 4), round(low, 4), round(high, 4), round(win, 4))


@dataclass(frozen=True, slots=True)
class Halves:
    all: Stat
    first: Stat
    second: Stat


@dataclass(frozen=True, slots=True)
class Row:
    """One hypothesis: the variant's own results and its paired effect against the signals as traded."""

    group: str
    label: str
    signals: int
    filled: int
    result: Halves
    paired: Halves | None  # variant minus as traded on the same signals (unfilled = 0 R)


@dataclass(frozen=True, slots=True)
class Hypothesis:
    group: str
    label: str
    run: Callable[[Signal, PricePath, PricePath | None], float | None]  # (signal, path, mirrored path)
    paired: bool = True


def default_hypotheses(seed: int = 0) -> list[Hypothesis]:
    """The setup review's set (SETUP_REVIEW §6, §8): exits, stop size, retests, re-entry and the baselines."""
    del seed  # the baselines are exact expectations (no draws); kept for a stable signature

    def market(rules: Rules) -> Callable[[Signal, PricePath, PricePath | None], float | None]:
        return lambda _s, p, _m: simulate(p, rules)

    def random_direction(_s: Signal, p: PricePath, m: PricePath | None) -> float | None:
        """The expected R of a fair coin per signal: the mean of both directions (one draw would add noise of
        about ±0.1 R on a few hundred signals with far targets)."""
        a, b = simulate(p), None if m is None else simulate(m)
        return None if a is None or b is None else (a + b) / 2

    out = [
        Hypothesis("baseline", "as traded", market(Rules()), paired=False),
        Hypothesis("baseline", "the other direction", lambda _s, _p, m: None if m is None else simulate(m)),
        Hypothesis("baseline", "random direction", random_direction),
    ]
    out += [Hypothesis("exit", f"target {x:g} R", market(Rules(target=x))) for x in (0.5, 1.0, 1.5)]
    out += [
        Hypothesis("exit", f"break-even after +{x:g} R", market(Rules(break_even=(x, 0.05))))
        for x in (0.5, 1.0)
    ]
    out += [
        Hypothesis("exit", "half off at +1 R", market(Rules(partial=(0.5, 1.0)))),
        Hypothesis("exit", "trail 0.5 R once +0.5 R", market(Rules(trail=(0.5, 0.5)))),
        Hypothesis("exit", "trail 1 R once +1 R", market(Rules(trail=(1.0, 1.0)))),
    ]
    out += [
        Hypothesis("exit", f"time stop {n} bars below +0.5 R", market(Rules(time_bars=n))) for n in (4, 8)
    ]
    for m in (1.5, 2.0):
        out.append(Hypothesis("stop", f"stop x{m:g}, same target price", market(Rules(stop_mult=m))))
        out.append(
            Hypothesis("stop", f"stop x{m:g}, same R multiple", market(Rules(stop_mult=m, target_scale=m)))
        )
    for wait in (4, 16):
        for depth, stop in ((0.5, 1.0), (0.5, 2.0), (1.0, 2.0), (1.0, 3.0)):
            label = f"retest -{depth:g} R, stop -{stop:g} R, {wait} bars"
            out.append(Hypothesis("retest", label, _retest_run(Retest(depth, stop, wait))))
    out += [Hypothesis("reentry", f"re-enter within {n} bars of the stop", _reentry_run(n)) for n in (4, 16)]
    return out


Run = Callable[[Signal, PricePath, PricePath | None], float | None]


def _retest_run(retest: Retest) -> Run:
    def run(_signal: Signal, path: PricePath, _mirror: PricePath | None) -> float | None:
        return simulate_retest(path, retest)

    return run


def _reentry_run(within_bars: int) -> Run:
    def run(_signal: Signal, path: PricePath, _mirror: PricePath | None) -> float | None:
        return simulate_reentry(path, within_bars)

    return run


def split_time(signals: Sequence[Signal]) -> datetime:
    """The midpoint of the signals' time range (the default walk-forward split)."""
    if not signals:
        raise ResearchError("no signals")
    first = min(s.signal_at for s in signals)
    last = max(s.signal_at for s in signals)
    return first + (last - first) / 2


def _halves(
    keyed: Sequence[tuple[bool, float]], seed: int, resamples: int
) -> Halves:  # (in the first half, value)
    return Halves(
        summarize([v for _, v in keyed], seed=seed, resamples=resamples),
        summarize([v for first, v in keyed if first], seed=seed, resamples=resamples),
        summarize([v for first, v in keyed if not first], seed=seed, resamples=resamples),
    )


def evaluate(
    items: Sequence[tuple[Signal, PricePath, PricePath | None]],
    hypotheses: Sequence[Hypothesis],
    *,
    split_at: datetime,
    seed: int = 0,
    resamples: int = RESAMPLES,
) -> list[Row]:
    """Every hypothesis on every signal with a path, against the signals as traded."""
    usable = [(s, p, m) for s, p, m in items if len(p)]
    base = {s.shadow_id: simulate(p) for s, p, _ in usable}
    rows = []
    for hyp in hypotheses:
        own: list[tuple[bool, float]] = []
        diff: list[tuple[bool, float]] = []
        for s, p, m in usable:
            first = s.signal_at < split_at
            value = hyp.run(s, p, m)
            if value is not None:
                own.append((first, value))
            b = base[s.shadow_id]
            if b is not None:
                diff.append((first, (0.0 if value is None else value) - b))
        rows.append(
            Row(
                hyp.group,
                hyp.label,
                len(usable),
                len(own),
                _halves(own, seed, resamples),
                _halves(diff, seed, resamples) if hyp.paired else None,
            )
        )
    return rows


@dataclass(frozen=True, slots=True)
class WalkForward:
    """The best rule by one half's mean, reported on the other half only."""

    chosen_on: str  # "first" | "second"
    label: str
    candidates: int  # how many rules it was chosen from (multiple testing)
    chosen_mean: float
    judged: Stat


def walk_forward(
    rows: Sequence[Row], *, measure: str = "result", min_n: int = MIN_RULE_N
) -> list[WalkForward]:
    """For each half: pick the row with the best mean on it, report that row on the other half."""
    out = []
    for chosen_on, judged_on in (("first", "second"), ("second", "first")):
        best: tuple[float, Row] | None = None
        candidates = 0
        for row in rows:
            halves = row.result if measure == "result" else row.paired
            if halves is None:
                continue
            stat: Stat = getattr(halves, chosen_on)
            if stat.n < min_n or stat.mean is None:
                continue
            candidates += 1
            if best is None or stat.mean > best[0]:
                best = (stat.mean, row)
        if best is None:
            continue
        chosen = best[1].result if measure == "result" else best[1].paired
        if chosen is None:
            continue
        out.append(WalkForward(chosen_on, best[1].label, candidates, best[0], getattr(chosen, judged_on)))
    return out


# --- context at the signal bar ------------------------------------------------------------------------------


def context_frame(bars: pd.DataFrame) -> pd.DataFrame:
    """Causal context per entry-timeframe bar, indexed by ``close_time`` (bars ≤ t only: no look-ahead)."""
    df = bars.set_index(pd.DatetimeIndex(bars["close_time"])).sort_index()
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(
        axis=1
    )
    atr = tr.rolling(ATR_BARS).mean()
    out = pd.DataFrame(index=df.index)
    out["atr"] = atr
    out["ema"] = df["close"].ewm(span=EMA_SPAN, adjust=False).mean()
    out["close"] = df["close"]
    out["bar_atr"] = (df["high"] - df["low"]) / atr
    out["atr_pct"] = atr.rolling(ATR_PCT_BARS).rank(pct=True)
    prior = df["high"].rolling(RANGE_BARS).max().shift(1) - df["low"].rolling(RANGE_BARS).min().shift(1)
    out["range_atr"] = prior / atr
    return out


def context_of(signals: Sequence[Signal], frames: Mapping[str, pd.DataFrame]) -> dict[str, dict[str, float]]:
    """Context features per signal id; a signal whose bar is missing gets no entry."""
    out: dict[str, dict[str, float]] = {}
    seen: set[tuple[str, object]] = set()
    for s in sorted(signals, key=lambda x: x.signal_at):
        day = (s.symbol, s.signal_at.date())
        first_of_day = day not in seen
        seen.add(day)
        frame = frames.get(s.symbol)
        t = pd.Timestamp(ensure_utc(s.signal_at))
        if frame is None or t not in frame.index:
            continue
        row = frame.loc[t].to_numpy(dtype=float)
        bar = {str(k): float(v) for k, v in zip(frame.columns, row, strict=True)}
        atr = bar["atr"]
        if not atr > 0:
            continue
        out[s.shadow_id] = {
            "hour_utc": float(t.hour),
            "stretch_ema_atr": (bar["close"] - bar["ema"]) * s.side.sign / atr,
            "bar_atr": bar["bar_atr"],
            "atr_pct": bar["atr_pct"],
            "range_atr": bar["range_atr"],
            "cost_share": s.spread / s.risk,
            "first_of_day": 1.0 if first_of_day else 0.0,
            "htf_aligned": float(s.features.get("ctx:htf_aligned", 0.0)),
        }
    return out


@dataclass(frozen=True, slots=True)
class ContextRule:
    """A single condition chosen on one half (best mean of the half it was chosen on), judged on the other."""

    chosen_on: str
    feature: str
    op: str  # "<=" | ">"
    edge: float
    chosen_mean: float
    chosen_n: int
    judged: Stat


def context_rules(
    values: Mapping[str, tuple[bool, float]],  # signal id -> (in the first half, R)
    context: Mapping[str, Mapping[str, float]],
    *,
    top: int = 5,
    min_n: int = MIN_RULE_N,
    seed: int = 0,
    resamples: int = RESAMPLES,
) -> tuple[list[ContextRule], int]:
    """Quartile-edge rules per feature, chosen per half and judged on the other; also the candidate count."""
    rows = [(values[k][0], values[k][1], context[k]) for k in values if k in context]
    out: list[ContextRule] = []
    candidates = 0
    for chosen_on, first_flag in (("first", True), ("second", False)):
        pool = [(r, c) for first, r, c in rows if first is first_flag]
        other = [(r, c) for first, r, c in rows if first is not first_flag]
        scored: list[tuple[float, int, str, str, float]] = []
        for feature in sorted({f for _, c in pool for f in c}):
            col = np.array([c.get(feature, np.nan) for _, c in pool], dtype=float)
            res = np.array([r for r, _ in pool], dtype=float)
            ok = ~np.isnan(col)
            if ok.sum() < min_n:
                continue
            for edge in np.unique(np.quantile(col[ok], [0.25, 0.5, 0.75])):
                for op in ("<=", ">"):
                    mask = ok & ((col <= edge) if op == "<=" else (col > edge))
                    if mask.sum() >= min_n:
                        scored.append((float(res[mask].mean()), int(mask.sum()), feature, op, float(edge)))
        candidates += len(scored)
        for mean, n, feature, op, edge in sorted(scored, reverse=True)[:top]:
            judged = [
                r
                for r, c in other
                if feature in c and not math.isnan(c[feature]) and ((c[feature] <= edge) == (op == "<="))
            ]
            stat = summarize(judged, seed=seed, resamples=resamples)
            out.append(ContextRule(chosen_on, feature, op, round(edge, 4), round(mean, 4), n, stat))
    return out, candidates


# --- losers -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoserProfile:
    """How the losers of the as-traded re-simulation lost (SETUP_REVIEW §6)."""

    trades: int
    losers: int
    reached_before_stop: dict[str, float]  # "+0.5" -> share of losers that were this far in favour first
    target_after_stop: float | None  # share of stopped trades whose original target was reached later
    mfe_quantiles: dict[str, float]


def loser_profile(paths: Iterable[PricePath]) -> LoserProfile:
    results = [(p, simulate(p)) for p in paths if len(p)]
    losers = [p for p, r in results if r is not None and r < 0]
    best: list[float] = []
    stopped = later = 0
    for p in losers:
        hit = np.nonzero(p.adv <= -1.0)[0]
        end = int(hit[0]) if len(hit) else len(p)
        best.append(float(np.max(p.fav[:end])) if end > 0 else 0.0)
        if len(hit) and p.target is not None:
            stopped += 1
            later += bool(np.any(p.fav[int(hit[0]) + 1 :] >= p.target))
    share = {
        f"+{x:g}": round(sum(b >= x for b in best) / len(best), 4) if best else 0.0
        for x in (0.25, 0.5, 1.0, 1.5)
    }
    mfe = [float(np.max(p.fav)) for p, _ in results]
    quant = {f"p{q}": round(float(np.percentile(mfe, q)), 3) for q in (25, 50, 75, 90)} if mfe else {}
    return LoserProfile(
        len(results), len(losers), share, round(later / stopped, 4) if stopped else None, quant
    )


# --- the report ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResearchReport:
    strategy: str
    timeframes: list[str]
    signals: int  # closed PLAN shadow trades found
    with_path: int  # of which had bars after the entry
    split_at: datetime
    rows: list[Row]
    walk_forward: list[WalkForward]
    walk_forward_paired: list[WalkForward]
    context: list[ContextRule]
    context_candidates: int
    losers: LoserProfile
    by_symbol: dict[str, Stat]  # as traded, per symbol
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["split_at"] = self.split_at.isoformat()
        return data


def research(
    signals: Sequence[Signal],
    paths: Mapping[str, PricePath],
    mirrors: Mapping[str, PricePath],
    frames: Mapping[str, pd.DataFrame],
    *,
    hypotheses: Sequence[Hypothesis] | None = None,
    split_at: datetime | None = None,
    seed: int = 0,
    resamples: int = RESAMPLES,
) -> ResearchReport:
    """The hypothesis set for one strategy: *paths*/*mirrors* by signal id, *frames* (entry TF) by symbol."""
    if not signals:
        raise ResearchError("no closed PLAN shadow trades for this selection")
    split = ensure_utc(split_at) if split_at is not None else split_time(signals)
    items = [(s, paths[s.shadow_id], mirrors.get(s.shadow_id)) for s in signals if s.shadow_id in paths]
    rows = evaluate(
        items, hypotheses or default_hypotheses(seed), split_at=split, seed=seed, resamples=resamples
    )
    market = [r for r in rows if r.group in {"exit", "stop", "retest", "reentry", "baseline"}]
    as_traded = {s.shadow_id: (s.signal_at < split, simulate(p)) for s, p, _ in items if len(p)}
    values = {k: (first, v) for k, (first, v) in as_traded.items() if v is not None}
    ctx = context_of(signals, {sym: context_frame(df) for sym, df in frames.items()})
    rules, candidates = context_rules(values, ctx, seed=seed, resamples=resamples)
    by_symbol: dict[str, list[float]] = defaultdict(list)
    for s, p, _ in items:
        v = simulate(p)
        if v is not None:
            by_symbol[s.symbol].append(v)
    return ResearchReport(
        strategy=signals[0].strategy,
        timeframes=sorted({s.timeframe.value for s in signals}),
        signals=len(signals),
        with_path=sum(1 for _, p, _ in items if len(p)),
        split_at=split,
        rows=rows,
        walk_forward=walk_forward(market),
        walk_forward_paired=walk_forward(market, measure="paired"),
        context=rules,
        context_candidates=candidates,
        losers=loser_profile(p for _, p, _ in items),
        by_symbol={k: summarize(v, seed=seed, resamples=resamples) for k, v in sorted(by_symbol.items())},
        notes=[
            "hypothetical bar-based re-simulation of past signals; past results do not predict future ones",
            "a rule is a finding only when it holds on the half it was not chosen on",
        ],
    )
