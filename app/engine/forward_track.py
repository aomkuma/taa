"""DEMO forward tracking against the backtests (owner, 2026-10-14): is the bot on the demo account doing what
its backtests said, day by day and per setup?

From the engine database only (``broker_trades``: closed bot trades with their R multiple). For each setup
with a backtest baseline the report gives the forward mean R/trade next to the backtest's, and the band the
backtest expects for the mean of that many trades (mean ± 1.645 × sd / √n, a normal approximation of the
90 % range). A forward mean below the band says the live behaviour differs from the backtest; inside it says
only that the two do not disagree yet. Nothing here forecasts anything.

The baselines are the backtests that made the setups pass (docs/archive/SETUP_REVIEW.md §15.3,
§16), with the trades' standard deviation measured from their trade lists (2026-10-14). A baseline
holds from the day the owner put those parameters on the bot (``since``); a setup's earlier trades
ran other parameters and are listed apart as "<setup> (before <label>)".
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.clock import ensure_utc
from app.storage.database import Database
from app.storage.models import BrokerTradeRow

THAI = timezone(timedelta(hours=7))  # the owner reads dates in Thai time
Z90 = 1.645


@dataclass(frozen=True, slots=True)
class Baseline:
    label: str
    mean_r: float
    sd_r: float
    win_rate: float
    trades_per_year: int
    source: str
    since: datetime  # the owner's decision that put these parameters on the bot


BASELINES: dict[str, Baseline] = {
    "setup_harmonic_prz": Baseline(
        "harmonic V1", 0.211, 1.446, 0.409, 181, "SETUP_REVIEW §15.3", datetime(2026, 10, 12, tzinfo=UTC)
    ),
    "setup_breakout": Baseline(
        "breakout F1", 0.159, 0.572, 0.798, 99, "SETUP_REVIEW §16", datetime(2026, 10, 14, tzinfo=UTC)
    ),
}


@dataclass(frozen=True, slots=True)
class Trade:
    strategy: str
    symbol: str
    entry_time: datetime
    exit_time: datetime
    net: float
    r: float | None


@dataclass(frozen=True, slots=True)
class SetupLine:
    strategy: str
    trades: int
    wins: int
    net: float
    mean_r: float | None
    baseline: Baseline | None

    @property
    def band(self) -> tuple[float, float] | None:
        """The 90 % range the backtest expects for the mean of this many trades."""
        if self.baseline is None or self.trades == 0:
            return None
        half = Z90 * self.baseline.sd_r / math.sqrt(self.trades)
        return self.baseline.mean_r - half, self.baseline.mean_r + half

    @property
    def verdict(self) -> str:
        band = self.band
        if band is None or self.mean_r is None:
            return "no baseline" if self.baseline is None else "no trades"
        if self.mean_r < band[0]:
            return "below the backtest range"
        if self.mean_r > band[1]:
            return "above the backtest range"
        return "inside the backtest range"


def load_trades(db: Database, since: datetime | None = None) -> list[Trade]:
    with db.session() as sess:
        q = select(BrokerTradeRow).order_by(BrokerTradeRow.exit_time)
        if since is not None:
            q = q.where(BrokerTradeRow.exit_time >= ensure_utc(since))
        return [
            Trade(
                r.strategy,
                r.symbol,
                ensure_utc(r.entry_time),
                ensure_utc(r.exit_time),
                float(r.net),
                r.r_multiple,
            )
            for r in sess.scalars(q)
        ]


def by_setup(trades: list[Trade]) -> list[SetupLine]:
    groups: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        b = BASELINES.get(t.strategy)
        old = b is not None and t.entry_time < b.since
        groups[f"{t.strategy} (before {b.label})" if old and b else t.strategy].append(t)
    out = []
    for name, ts in groups.items():
        rs = [t.r for t in ts if t.r is not None]
        out.append(
            SetupLine(
                strategy=name,
                trades=len(ts),
                wins=sum(t.net > 0 for t in ts),
                net=round(sum(t.net for t in ts), 2),
                mean_r=round(sum(rs) / len(rs), 3) if rs else None,
                baseline=BASELINES.get(name),  # None for the "(before ...)" groups
            )
        )
    out.sort(key=lambda s: (s.baseline is None, -s.trades))
    return out


def by_day(trades: list[Trade]) -> list[tuple[date, int, float, float, float]]:
    """(Thai date, trades, net, R that day, cumulative R)."""
    days: dict[date, list[Trade]] = defaultdict(list)
    for t in trades:
        days[t.exit_time.astimezone(THAI).date()].append(t)
    out, cum = [], 0.0
    for d in sorted(days):
        r = sum(t.r or 0.0 for t in days[d])
        cum += r
        out.append((d, len(days[d]), round(sum(t.net for t in days[d]), 2), round(r, 2), round(cum, 2)))
    return out


def report(db: Database, since: datetime | None = None, *, proven_only: bool = False) -> str:
    """The tracking table in Markdown (Thai dates)."""
    trades = load_trades(db, since)
    if proven_only:
        trades = [
            t for t in trades if (b := BASELINES.get(t.strategy)) is not None and t.entry_time >= b.since
        ]
    when = "" if since is None else " since " + since.astimezone(THAI).strftime("%Y-%m-%d %H:%M")
    lines = [
        "# DEMO vs backtest",
        "",
        f"Closed bot trades{when} (Thai time): {len(trades)}{', proven setups only' if proven_only else ''}.",
        "The range is the 90 % band the backtest expects for the mean R of that many trades; with few",
        'trades it is wide, and "inside" only means the two do not disagree yet.',
        "",
        "## Per setup",
        "",
        "| Setup | Trades | Win % | Net | R/trade | Backtest R/trade (win %) | Expected for n | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in by_setup(trades):
        b, band = s.baseline, s.band
        bt = "-" if b is None else f"{b.mean_r:+.3f} ({b.win_rate:.0%}; {b.label}, {b.source})"
        rng = "-" if band is None else f"{band[0]:+.2f} .. {band[1]:+.2f}"
        mean = "-" if s.mean_r is None else f"{s.mean_r:+.3f}"
        win = f"{s.wins / s.trades:.0%}" if s.trades else "-"
        lines.append(
            f"| {s.strategy} | {s.trades} | {win} | {s.net:+.2f} | {mean} | {bt} | {rng} | {s.verdict} |"
        )
    lines += [
        "",
        "## Per day (Thai date)",
        "",
        "| Date | Trades | Net | R | Cumulative R |",
        "|---|---|---|---|---|",
    ]
    for d, n, net, r, cum in by_day(trades):
        lines.append(f"| {d.isoformat()} | {n} | {net:+.2f} | {r:+.2f} | {cum:+.2f} |")
    return "\n".join(lines) + "\n"
