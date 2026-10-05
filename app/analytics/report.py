"""The analytics report of a set of closed trades (PLAN §A15 "Analytics", §A16; TAA-1005). Pure.

One shape for every scope (paper, shadow, a backtest run):

- **KPIs:** trades, wins/losses/scratches, win rate, expectancy in R, profit factor, net P/L, max drawdown,
  Sharpe and Sortino, average holding time.
- **Curves:** the cumulative result and its drawdown, per closed trade.
- **R distribution**, **performance by style** (the A16 tags), **MAE/MFE** per trade and the **P/L
  attribution** summary.

Conventions:

- R is the basis everywhere (shadow trades without a lot have no money). Money figures appear only when every
  trade has its net P/L (``basis`` says which one the profit factor uses).
- Sharpe and Sortino use daily sums of R (UTC days with a closed trade), annualized with √260, risk-free 0;
  fewer than two days or zero variance → None. Drawdown is measured in R from the running peak of the
  cumulative result.
- Results of hypothetical scopes are labelled by the caller. Nothing here is a forecast.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.analytics.attribution import attribute
from app.analytics.recommendations import SEGMENT_DIMENSIONS
from app.analytics.styles import style_tags
from app.analytics.trade_builder import Outcome, Trade
from app.core.clock import ensure_utc

TRADING_DAYS = 260
R_BIN = 0.5
R_LOW, R_HIGH = -3.0, 5.0  # outer bins collect everything beyond
MAX_POINTS = 500  # MAE/MFE points and curve points kept (the most recent)
STYLE_DIMENSIONS: tuple[str, ...] = (*SEGMENT_DIMENSIONS, "weekday")


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None or not math.isfinite(value) else round(value, digits)


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(daily: Sequence[float], *, downside: bool) -> float | None:
    if len(daily) < 2:
        return None
    mean = sum(daily) / len(daily)
    if downside:
        below = [min(v, 0.0) for v in daily]
        var = sum(v * v for v in below) / (len(daily) - 1)
    else:
        var = sum((v - mean) ** 2 for v in daily) / (len(daily) - 1)
    if var <= 0:
        return None
    return mean / math.sqrt(var) * math.sqrt(TRADING_DAYS)


def _kpis(trades: Sequence[Trade], rs: Sequence[float]) -> dict[str, Any]:
    outcomes = Counter(t.outcome for t in trades)
    money = [t.net_pnl for t in trades]
    has_money = bool(trades) and all(m is not None for m in money)
    if has_money:
        gains = sum(m for m in money if m is not None and m > 0)
        losses = -sum(m for m in money if m is not None and m < 0)
        basis = "MONEY"
    else:
        gains, losses = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
        basis = "R"
    curve, peak, max_dd = 0.0, 0.0, 0.0
    for r in rs:
        curve += r
        peak = max(peak, curve)
        max_dd = max(max_dd, peak - curve)
    daily: dict[str, float] = defaultdict(float)
    for t in trades:
        if t.r_multiple is not None:
            daily[ensure_utc(t.exit_time).date().isoformat()] += t.r_multiple
    decided = outcomes[Outcome.WIN] + outcomes[Outcome.LOSS]
    holds = [t.holding.total_seconds() / 60 for t in trades]
    return {
        "trades": len(trades),
        "rated": len(rs),
        "wins": outcomes[Outcome.WIN],
        "losses": outcomes[Outcome.LOSS],
        "scratches": outcomes[Outcome.SCRATCH],
        "win_rate": _round(outcomes[Outcome.WIN] / decided) if decided else None,
        "expectancy_r": _round(_mean(rs)),
        "net_r": _round(sum(rs)),
        "net_pnl": _round(sum(m for m in money if m is not None), 2) if has_money else None,
        "profit_factor": _round(gains / losses) if losses > 0 else None,
        "basis": basis,
        "max_drawdown_r": _round(max_dd),
        "sharpe": _round(_ratio(list(daily.values()), downside=False)),
        "sortino": _round(_ratio(list(daily.values()), downside=True)),
        "avg_hold_minutes": _round(_mean(holds), 1),
    }


def _curves(trades: Sequence[Trade]) -> list[dict[str, Any]]:
    out, total, money, peak = [], 0.0, 0.0, 0.0
    has_money = all(t.net_pnl is not None for t in trades)
    for t in trades:
        if t.r_multiple is None:
            continue
        total += t.r_multiple
        money += t.net_pnl or 0.0
        peak = max(peak, total)
        out.append(
            {
                "time": ensure_utc(t.exit_time).isoformat(),
                "r": round(total, 4),
                "money": round(money, 2) if has_money else None,
                "drawdown_r": round(total - peak, 4),
            }
        )
    return out[-MAX_POINTS:]


def _histogram(rs: Sequence[float]) -> list[dict[str, Any]]:
    edges = [R_LOW + i * R_BIN for i in range(int((R_HIGH - R_LOW) / R_BIN) + 1)]
    counts = [0] * (len(edges) + 1)  # below the first edge, each bin, above the last edge
    for r in rs:
        if r < R_LOW:
            counts[0] += 1
        elif r >= R_HIGH:
            counts[-1] += 1
        else:
            counts[1 + int((r - R_LOW) // R_BIN)] += 1
    bins = [{"low": None, "high": R_LOW, "count": counts[0]}]
    bins += [{"low": lo, "high": lo + R_BIN, "count": counts[1 + i]} for i, lo in enumerate(edges[:-1])]
    bins.append({"low": R_HIGH, "high": None, "count": counts[-1]})
    return bins


def _by_style(trades: Sequence[Trade]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, dict[str, list[Trade]]] = {d: defaultdict(list) for d in STYLE_DIMENSIONS}
    for t in trades:
        tags = style_tags(t)
        for d in STYLE_DIMENSIONS:
            groups[d][str(getattr(tags, d))].append(t)
    out: dict[str, list[dict[str, Any]]] = {}
    for d, values in groups.items():
        rows = []
        for value, ts in values.items():
            rs = [t.r_multiple for t in ts if t.r_multiple is not None]
            wins = sum(t.outcome is Outcome.WIN for t in ts)
            decided = wins + sum(t.outcome is Outcome.LOSS for t in ts)
            rows.append(
                {
                    "value": value,
                    "trades": len(ts),
                    "expectancy_r": _round(_mean(rs)),
                    "net_r": _round(sum(rs)),
                    "win_rate": _round(wins / decided) if decided else None,
                }
            )
        out[d] = sorted(rows, key=lambda r: (-r["trades"], r["value"]))
    return out


def _mae_mfe(trades: Sequence[Trade]) -> list[dict[str, Any]]:
    points = [
        {
            "trade_id": t.trade_id,
            "symbol": t.symbol,
            "mae_r": _round(t.mae_r),
            "mfe_r": _round(t.mfe_r),
            "r": _round(t.r_multiple),
            "outcome": t.outcome.value,
        }
        for t in trades
        if t.mae_r is not None and t.mfe_r is not None
    ]
    return points[-MAX_POINTS:]


def _attribution(trades: Sequence[Trade]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for t in trades:
        counts.update(a.code.value for a in attribute(t))
    total = len(trades)
    return [
        {"code": code, "count": n, "share": _round(n / total) if total else None}
        for code, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def build_report(trades: Sequence[Trade]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda t: (ensure_utc(t.exit_time), t.trade_id))
    rs = [t.r_multiple for t in ordered if t.r_multiple is not None and math.isfinite(t.r_multiple)]
    first: datetime | None = ordered[0].entry_time if ordered else None
    last: datetime | None = ordered[-1].exit_time if ordered else None
    return {
        "period": {
            "start": None if first is None else ensure_utc(first).isoformat(),
            "end": None if last is None else ensure_utc(last).isoformat(),
        },
        "hypothetical": any(t.hypothetical for t in ordered),
        "kpis": _kpis(ordered, rs),
        "curve": _curves(ordered),
        "r_histogram": _histogram(rs),
        "by_style": _by_style(ordered),
        "mae_mfe": _mae_mfe(ordered),
        "attribution": _attribution(ordered),
    }
