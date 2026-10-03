"""Backtest metrics (PLAN §A17 "Metrics"; TAA-504). Deterministic functions of trades and the equity curve.

Conventions:

- Returns for Sharpe/Sortino are **daily**: the equity curve's last value per UTC day, then the day-over-day
  change; annualized with √260 (trading days of a 24×5 market). Risk-free rate 0. Fewer than two daily
  returns, or zero variance, means the ratio is undefined (``None``).
- CAGR uses calendar time between the first and last equity points.
- Drawdown is measured on equity from its running peak; the longest drawdown is the longest time spent below
  a previous peak (still open at the end counts until the end).
- R multiples use each trade's planned risk (loss at the stop with costs); MAE/MFE in R use the distance from
  the entry to the initial stop.
- Exposure is the share of equity points with at least one open position.

Nothing here is a forecast. Results are a bar-based approximation with the limitations listed in §A17.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.execution.simulated_broker import ClosedTrade, EquityPoint

TRADING_DAYS = 260


@dataclass(frozen=True)
class Metrics:
    trades: int
    wins: int
    losses: int
    win_rate: float | None
    net_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    expectancy_money: float | None
    expectancy_r: float | None
    avg_win_r: float | None
    avg_loss_r: float | None
    max_drawdown: float
    max_drawdown_percent: float
    longest_drawdown_days: float
    cagr_percent: float | None
    calmar: float | None
    sharpe: float | None
    sortino: float | None
    exposure_percent: float
    commission: float
    swap: float
    avg_mae_r: float | None
    avg_mfe_r: float | None
    initial_equity: float
    final_equity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in asdict(self).items()
        }


def _mean(values: Sequence[float]) -> float | None:
    return float(np.mean(values)) if values else None


def equity_frame(curve: Sequence[EquityPoint]) -> pd.DataFrame:
    """Columns ``balance``, ``equity``, ``peak``, ``drawdown`` (money ≤ 0) and ``drawdown_percent``."""
    if not curve:
        return pd.DataFrame(
            columns=["balance", "equity", "peak", "drawdown", "drawdown_percent", "open_positions"]
        )
    df = pd.DataFrame(
        {
            "balance": [p.balance for p in curve],
            "equity": [p.equity for p in curve],
            "open_positions": [p.open_positions for p in curve],
        },
        index=pd.DatetimeIndex([p.at for p in curve], name="time"),
    )
    df["peak"] = df["equity"].cummax()
    df["drawdown"] = df["equity"] - df["peak"]
    df["drawdown_percent"] = np.where(df["peak"] > 0, 100.0 * df["drawdown"] / df["peak"], 0.0)
    return df


def longest_drawdown(df: pd.DataFrame) -> timedelta:
    longest = timedelta(0)
    start = None
    for at, dd in zip(df.index, df["drawdown"], strict=True):
        if dd < 0 and start is None:
            start = at
        elif dd >= 0 and start is not None:
            longest = max(longest, at - start)
            start = None
    if start is not None:
        longest = max(longest, df.index[-1] - start)
    return longest


def daily_returns(df: pd.DataFrame) -> pd.Series:
    days = pd.DatetimeIndex(df.index).floor("D")
    daily = df["equity"].groupby(days).last()
    return daily.pct_change().dropna()


def _ratio(returns: pd.Series, downside: bool) -> float | None:
    if len(returns) < 2:
        return None
    mean = float(returns.mean())
    if downside:
        neg = returns[returns < 0]
        dev = float(np.sqrt((neg**2).sum() / len(returns)))
    else:
        dev = float(returns.std(ddof=1))
    if dev == 0 or not math.isfinite(dev):
        return None
    return mean / dev * math.sqrt(TRADING_DAYS)


def compute_metrics(
    trades: Sequence[ClosedTrade], curve: Sequence[EquityPoint], initial_equity: float
) -> Metrics:
    df = equity_frame(curve)
    nets = [t.net for t in trades]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n < 0]
    rs = [r for t in trades if (r := t.r_multiple) is not None]
    win_rs = [r for r in rs if r > 0]
    loss_rs = [r for r in rs if r < 0]
    gross_profit, gross_loss = sum(wins), -sum(losses)
    final = float(df["equity"].iloc[-1]) if len(df) else initial_equity
    max_dd = float(-df["drawdown"].min()) if len(df) else 0.0
    max_dd_pct = float(-df["drawdown_percent"].min()) if len(df) else 0.0
    cagr = None
    if len(df) >= 2 and initial_equity > 0 and final > 0:
        years = (df.index[-1] - df.index[0]).total_seconds() / (365.25 * 86_400)
        if years > 0:
            cagr = 100.0 * ((final / initial_equity) ** (1 / years) - 1)
    returns = daily_returns(df) if len(df) else pd.Series(dtype=float)
    mae_r, mfe_r = [], []
    for t in trades:
        if t.sl_initial is not None:
            dist = abs(t.entry_price - t.sl_initial)
            if dist > 0:
                mae_r.append(t.mae / dist)
                mfe_r.append(t.mfe / dist)
    return Metrics(
        trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=None if not trades else 100.0 * len(wins) / len(trades),
        net_profit=sum(nets),
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=None if gross_loss == 0 else gross_profit / gross_loss,
        expectancy_money=_mean(nets),
        expectancy_r=_mean(rs),
        avg_win_r=_mean(win_rs),
        avg_loss_r=_mean(loss_rs),
        max_drawdown=max_dd,
        max_drawdown_percent=max_dd_pct,
        longest_drawdown_days=longest_drawdown(df).total_seconds() / 86_400 if len(df) else 0.0,
        cagr_percent=cagr,
        calmar=None if cagr is None or max_dd_pct == 0 else cagr / max_dd_pct,
        sharpe=_ratio(returns, downside=False),
        sortino=_ratio(returns, downside=True),
        exposure_percent=100.0 * float((df["open_positions"] > 0).mean()) if len(df) else 0.0,
        commission=sum(t.commission for t in trades),
        swap=sum(t.swap for t in trades),
        avg_mae_r=_mean(mae_r),
        avg_mfe_r=_mean(mfe_r),
        initial_equity=initial_equity,
        final_equity=final,
    )
