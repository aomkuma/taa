"""The analytics report of closed trades: KPIs, curves, R distribution, styles, MAE/MFE, attribution (TAA-1005)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.analytics.report import build_report
from app.analytics.trade_builder import Trade
from app.core.enums import ExitReason
from tests.analytics_data import T0, trade


def closed(i: int, r: float, **kw: Any) -> Trade:
    base: dict[str, Any] = {
        "trade_id": f"BACKTEST:{i}",
        "entry_time": T0 + timedelta(days=i),
        "exit_time": T0 + timedelta(days=i, hours=2),
        "r_multiple": r,
        "net_pnl": 50.0 * r,
    }
    if r < 0:
        base |= {"exit_reason": ExitReason.STOP_LOSS, "exit_price": 1.095, "mfe": 0.001, "mae": 0.005}
    return trade(**(base | kw))


def test_kpis_and_curves() -> None:
    trades = [closed(0, 2.0), closed(1, -1.0), closed(2, -1.0), closed(3, 2.0), closed(4, 0.1)]
    report = build_report(trades)
    k = report["kpis"]
    assert (k["trades"], k["wins"], k["losses"], k["scratches"]) == (5, 2, 2, 1)
    assert k["win_rate"] == 0.5 and k["expectancy_r"] == 0.42 and k["net_r"] == 2.1
    assert k["basis"] == "MONEY" and k["net_pnl"] == 105.0 and k["profit_factor"] == 2.05
    assert k["max_drawdown_r"] == 2.0  # +2, then two losses
    assert k["sharpe"] is not None and k["avg_hold_minutes"] == 120.0
    assert [p["r"] for p in report["curve"]] == [2.0, 1.0, 0.0, 2.0, 2.1]
    assert [p["drawdown_r"] for p in report["curve"]] == [0.0, -1.0, -2.0, 0.0, 0.0]
    assert report["hypothetical"] is True and report["period"]["start"] == T0.isoformat()


def test_r_basis_without_money_and_an_empty_report() -> None:
    k = build_report([closed(0, 2.0, net_pnl=None), closed(1, -1.0)])["kpis"]
    assert k["basis"] == "R" and k["net_pnl"] is None and k["profit_factor"] == 2.0
    empty = build_report([])
    assert empty["kpis"]["trades"] == 0 and empty["kpis"]["expectancy_r"] is None and empty["curve"] == []


def test_histogram_styles_mae_mfe_and_attribution() -> None:
    trades = [closed(0, 2.0), closed(1, -1.0), closed(2, 7.0), closed(3, -4.0)]
    report = build_report(trades)
    bins = report["r_histogram"]
    assert bins[0] == {"low": None, "high": -3.0, "count": 1} and bins[-1] == {
        "low": 5.0,
        "high": None,
        "count": 1,
    }
    assert sum(b["count"] for b in bins) == 4
    [strategy] = report["by_style"]["strategy"]
    assert strategy["value"] == "setup_fib_pullback" and strategy["trades"] == 4
    assert {"symbol", "session", "weekday"} <= set(report["by_style"])
    assert len(report["mae_mfe"]) == 4 and report["mae_mfe"][1]["mae_r"] == 1.0
    codes = {a["code"]: a["count"] for a in report["attribution"]}
    assert sum(codes.values()) >= 4  # every trade gets at least one code
