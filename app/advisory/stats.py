"""Accuracy statistics and the theory scoreboard (PLAN §A27 "Accuracy statistics", §A29; TAA-6C4).

Pure functions over closed shadow trades (:class:`TradeRecord`), shared with the cloud analytics: no broker,
no clock, no database except the optional loader :func:`load_records`.

Definitions (every result is hypothetical; see ``docs/ADVISORY.md``):

- **hit rate** = TP first ÷ resolved, with a 90% Wilson interval;
- **expectancy** = mean ``r_net`` (R after costs) and mean ``net_pnl`` (account currency, at the lot
  snapshotted at signal time; trades "not tradable at your capital" have no money and count in R only);
- **profit factor** = gross wins ÷ gross losses (R and money); None without a loss;
- **follow-all curve** = cumulative net P/L (and R) in exit order, with its maximum drawdown from the running
  peak (starting at 0);
- **breakdowns** by symbol, strategy, asset class, session, strength bucket, side, timeframe, watchlist (a
  trade counts in every list holding its symbol), alerted and followed;
- **threshold explorer**: the same metrics for "follow every opportunity with metric ≥ x". It is chosen on the
  same data it is measured on, so it is always flagged **in-sample**;
- **theory scoreboard**: per detector and per family × group (asset class × timeframe by default), the trades
  the theory supported: n, hit rate with CI, expectancy, and lift = hit rate ÷ the group's hit rate.

LIVE and REPLAY results are never mixed: :func:`accuracy_report` builds one section per source.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.advisory.confidence import Source, feature_family, is_player, strength_bucket
from app.advisory.shadow import ShadowStatus, Variant
from app.advisory.stats_math import wilson_interval
from app.core.clock import ensure_utc
from app.storage.database import Database
from app.storage.models import ShadowTradeRow

IN_SAMPLE_WARNING = "advisory.accuracy.threshold_in_sample"  # i18n key for the explorer's caveat


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """One CLOSED shadow trade, as the statistics see it."""

    shadow_id: str
    source: Source
    variant: str
    strategy: str
    symbol: str
    asset_class: str
    timeframe: str
    session: str
    side: str
    strength: float
    rr: float | None
    win: bool
    r_net: float
    net_pnl: float | None  # None: not tradable at the owner's capital (R only)
    signal_at: datetime
    exit_at: datetime
    exit_reason: str
    alerted: bool = False
    followed: bool = False
    features: Mapping[str, float] = field(default_factory=dict)


def record_of(row: ShadowTradeRow) -> TradeRecord | None:
    if (
        row.status != ShadowStatus.CLOSED.value
        or row.win is None
        or row.r_net is None
        or row.exit_at is None
        or row.exit_reason is None
    ):
        return None
    return TradeRecord(
        shadow_id=row.shadow_id,
        source=Source(row.source),
        variant=row.variant,
        strategy=row.strategy,
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        session=row.session,
        side=row.side,
        strength=row.setup_strength,
        rr=row.rr,
        win=bool(row.win),
        r_net=row.r_net,
        net_pnl=row.net_pnl,
        signal_at=ensure_utc(row.signal_at),
        exit_at=ensure_utc(row.exit_at),
        exit_reason=row.exit_reason,
        alerted=row.alerted,
        followed=row.followed,
        features=dict(row.features),
    )


def load_records(
    db: Database,
    *,
    server: str,
    variant: Variant = Variant.PLAN,
    source: Source | None = None,
    since: datetime | None = None,
) -> list[TradeRecord]:
    query = select(ShadowTradeRow).where(
        ShadowTradeRow.server == server,
        ShadowTradeRow.variant == variant.value,
        ShadowTradeRow.status == ShadowStatus.CLOSED.value,
    )
    if source is not None:
        query = query.where(ShadowTradeRow.source == source.value)
    if since is not None:
        query = query.where(ShadowTradeRow.signal_at >= since)
    with db.session() as sess:
        rows = list(sess.execute(query.order_by(ShadowTradeRow.exit_at, ShadowTradeRow.shadow_id)).scalars())
    return [r for r in (record_of(row) for row in rows) if r is not None]


# --- core metrics -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CurvePoint:
    at: datetime
    pnl: float  # cumulative net P/L (trades with money only)
    r: float  # cumulative R (every trade)
    drawdown: float  # money below the running peak, >= 0
    drawdown_r: float


def equity_curve(records: Iterable[TradeRecord]) -> list[CurvePoint]:
    """The "follow every one" curve in exit order (ties by id), starting from 0."""
    pnl = r = peak = peak_r = 0.0
    out = []
    for t in sorted(records, key=lambda x: (x.exit_at, x.shadow_id)):
        pnl += t.net_pnl or 0.0
        r += t.r_net
        peak, peak_r = max(peak, pnl), max(peak_r, r)
        out.append(CurvePoint(t.exit_at, pnl, r, peak - pnl, peak_r - r))
    return out


def _profit_factor(values: Iterable[float]) -> float | None:
    wins = losses = 0.0
    for v in values:
        if v > 0:
            wins += v
        elif v < 0:
            losses -= v
    return wins / losses if losses > 0 else None


@dataclass(frozen=True, slots=True)
class Summary:
    n: int
    wins: int
    hit_rate: float | None  # percent
    hit_low: float | None  # 90% Wilson, percent
    hit_high: float | None
    expectancy_r: float | None
    profit_factor_r: float | None
    n_money: int  # trades with a lot (money results)
    expectancy_money: float | None
    profit_factor_money: float | None
    total_pnl: float  # hypothetical, at each moment's lot
    max_drawdown: float  # money, follow-all
    max_drawdown_r: float

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


def summarize(records: Iterable[TradeRecord]) -> Summary:
    trades = list(records)
    n = len(trades)
    wins = sum(t.win for t in trades)
    money = [t.net_pnl for t in trades if t.net_pnl is not None]
    curve = equity_curve(trades)
    low, high = wilson_interval(wins, n) if n else (math.nan, math.nan)
    return Summary(
        n=n,
        wins=wins,
        hit_rate=100 * wins / n if n else None,
        hit_low=100 * low if n else None,
        hit_high=100 * high if n else None,
        expectancy_r=sum(t.r_net for t in trades) / n if n else None,
        profit_factor_r=_profit_factor(t.r_net for t in trades),
        n_money=len(money),
        expectancy_money=sum(money) / len(money) if money else None,
        profit_factor_money=_profit_factor(money),
        total_pnl=round(sum(money), 2),
        max_drawdown=max((p.drawdown for p in curve), default=0.0),
        max_drawdown_r=max((p.drawdown_r for p in curve), default=0.0),
    )


# --- breakdowns ---------------------------------------------------------------------------------------------

Key = Callable[[TradeRecord], Iterable[Hashable]]

DIMENSIONS: dict[str, Key] = {
    "symbol": lambda t: (t.symbol,),
    "strategy": lambda t: (t.strategy,),
    "asset_class": lambda t: (t.asset_class,),
    "session": lambda t: (t.session,),
    "bucket": lambda t: (strength_bucket(t.strength),),
    "side": lambda t: (t.side,),
    "timeframe": lambda t: (t.timeframe,),
    "alerted": lambda t: ("alerted" if t.alerted else "not_alerted",),
    "followed": lambda t: ("followed" if t.followed else "not_followed",),
}


def watchlist_key(watchlists: Mapping[str, Sequence[str]]) -> Key:
    """A trade belongs to every watchlist holding its symbol (none: no row)."""
    members: dict[str, list[str]] = defaultdict(list)
    for name, symbols in watchlists.items():
        for symbol in symbols:
            members[symbol].append(name)
    return lambda t: tuple(members.get(t.symbol, ()))


def breakdown(records: Iterable[TradeRecord], key: Key) -> dict[Hashable, Summary]:
    groups: dict[Hashable, list[TradeRecord]] = defaultdict(list)
    for t in records:
        for k in key(t):
            groups[k].append(t)
    return {k: summarize(v) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


# --- threshold explorer -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ThresholdRow:
    threshold: float
    summary: Summary


@dataclass(frozen=True, slots=True)
class ThresholdExplorer:
    metric: str
    rows: tuple[ThresholdRow, ...]
    in_sample: bool = True  # thresholds picked on the data they are measured on
    warning: str = IN_SAMPLE_WARNING


def threshold_explorer(
    records: Iterable[TradeRecord],
    *,
    metric: str = "SETUP_STRENGTH",
    value: Callable[[TradeRecord], float | None] | None = None,
    thresholds: Sequence[float] = tuple(range(50, 100, 5)),
) -> ThresholdExplorer:
    """ "Follow every opportunity with metric ≥ x" for each x. *value* defaults to the setup strength; pass
    a win-probability scorer (percent) for WIN_PROBABILITY."""
    score = value or (lambda t: t.strength)
    scored = [(score(t), t) for t in records]
    rows = tuple(
        ThresholdRow(x, summarize(t for s, t in scored if s is not None and s >= x)) for x in thresholds
    )
    return ThresholdExplorer(metric, rows)


# --- theory scoreboard --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TheoryScore:
    theory: str  # detector feature (``ev:FAMILY:detector``) or family name
    level: str  # "detector" or "family"
    group: Hashable
    n: int
    hit_rate: float  # percent
    low: float
    high: float
    expectancy_r: float
    base_rate: float  # the group's hit rate, percent
    lift: float | None  # hit rate / base rate


def default_group(t: TradeRecord) -> Hashable:
    return (t.asset_class, t.timeframe)


def scoreboard(
    records: Iterable[TradeRecord], *, group: Callable[[TradeRecord], Hashable] = default_group
) -> list[TheoryScore]:
    """Each theory's record on the trades it supported (``ev:`` feature > 0), per group."""
    trades = list(records)
    base: dict[Hashable, list[TradeRecord]] = defaultdict(list)
    supported: dict[tuple[str, str, Hashable], list[TradeRecord]] = defaultdict(list)
    for t in trades:
        g = group(t)
        base[g].append(t)
        families = set()
        for name, v in t.features.items():
            if is_player(name) and v > 0:
                supported[(name, "detector", g)].append(t)
                families.add(feature_family(name))
        for fam in families:
            supported[(fam, "family", g)].append(t)
    out = []
    for (theory, level, g), rows in supported.items():
        n = len(rows)
        hits = sum(t.win for t in rows)
        low, high = wilson_interval(hits, n)
        b = base[g]
        base_rate = sum(t.win for t in b) / len(b)
        rate = hits / n
        out.append(
            TheoryScore(
                theory=theory,
                level=level,
                group=g,
                n=n,
                hit_rate=100 * rate,
                low=100 * low,
                high=100 * high,
                expectancy_r=sum(t.r_net for t in rows) / n,
                base_rate=100 * base_rate,
                lift=rate / base_rate if base_rate > 0 else None,
            )
        )
    return sorted(out, key=lambda s: (str(s.group), s.level, -s.n, s.theory))


# --- the report ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    source: Source
    summary: Summary
    curve: tuple[CurvePoint, ...]
    breakdowns: dict[str, dict[Hashable, Summary]]
    explorer: ThresholdExplorer
    scoreboard: tuple[TheoryScore, ...]


@dataclass(frozen=True)
class AccuracyReport:
    live: Section
    replay: Section


def section(
    records: Iterable[TradeRecord],
    source: Source,
    *,
    watchlists: Mapping[str, Sequence[str]] | None = None,
    thresholds: Sequence[float] = tuple(range(50, 100, 5)),
) -> Section:
    trades = [t for t in records if t.source is source]
    keys = dict(DIMENSIONS)
    if watchlists:
        keys["watchlist"] = watchlist_key(watchlists)
    return Section(
        source=source,
        summary=summarize(trades),
        curve=tuple(equity_curve(trades)),
        breakdowns={name: breakdown(trades, key) for name, key in keys.items()},
        explorer=threshold_explorer(trades, thresholds=thresholds),
        scoreboard=tuple(scoreboard(trades)),
    )


def accuracy_report(
    records: Iterable[TradeRecord], *, watchlists: Mapping[str, Sequence[str]] | None = None
) -> AccuracyReport:
    """LIVE and REPLAY sections, each computed only from its own trades (never mixed)."""
    trades = list(records)
    return AccuracyReport(
        live=section(trades, Source.LIVE, watchlists=watchlists),
        replay=section(trades, Source.REPLAY, watchlists=watchlists),
    )
