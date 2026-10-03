from __future__ import annotations

import csv
import json
import math
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.backtest.engine import BacktestResult
from app.backtest.metrics import compute_metrics, equity_frame, longest_drawdown
from app.backtest.report import TRADE_COLUMNS, Provenance, summary, write_reports
from app.core.enums import ExitReason, Side
from app.execution.simulated_broker import ClosedTrade, EquityPoint

T = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
D = timedelta(days=1)


def trade(net: float, risk: float = 100.0, mae: float = 0.001, mfe: float = 0.002, i: int = 0) -> ClosedTrade:
    return ClosedTrade(
        ticket=i,
        symbol="EURUSD",
        side=Side.BUY,
        volume=0.1,
        entry_time=T + i * D,
        entry_price=1.1,
        exit_time=T + i * D + timedelta(hours=5),
        exit_price=1.1,
        exit_reason=ExitReason.TAKE_PROFIT if net > 0 else ExitReason.STOP_LOSS,
        sl_initial=1.098,
        tp_initial=1.104,
        profit=net + 1.0,
        commission=-1.0,
        swap=0.0,
        mae=mae,
        mfe=mfe,
        risk_money=risk,
        strategy="s",
        signal_id=f"sig{i}",
        magic=7_310_000,
    )


def curve(*equities: float, open_positions: int = 0) -> list[EquityPoint]:
    return [EquityPoint(T + i * D, e, e, 0.0, open_positions if i % 2 else 0) for i, e in enumerate(equities)]


TRADES = [trade(200.0, i=0), trade(-100.0, i=1), trade(150.0, i=2), trade(-100.0, i=3)]
CURVE = curve(10_000, 10_200, 10_100, 10_250, 10_150)


class TestMetrics:
    def test_trade_statistics(self) -> None:
        m = compute_metrics(TRADES, CURVE, 10_000)
        assert (m.trades, m.wins, m.losses) == (4, 2, 2)
        assert m.win_rate == 50.0
        assert m.net_profit == pytest.approx(150.0)
        assert m.profit_factor == pytest.approx(350 / 200)
        assert m.expectancy_money == pytest.approx(37.5)
        assert m.expectancy_r == pytest.approx(0.375)
        assert m.avg_win_r == pytest.approx(1.75)
        assert m.avg_loss_r == pytest.approx(-1.0)
        assert m.commission == pytest.approx(-4.0)
        assert m.avg_mae_r == pytest.approx(0.5)  # 0.001 / 0.002
        assert m.avg_mfe_r == pytest.approx(1.0)

    def test_drawdown(self) -> None:
        m = compute_metrics(TRADES, CURVE, 10_000)
        assert m.max_drawdown == pytest.approx(100.0)
        assert m.max_drawdown_percent == pytest.approx(100 * 100 / 10_200)  # the deeper of two -100 dips
        assert m.longest_drawdown_days == pytest.approx(1.0)  # 10,200 -> 10,100 -> new peak a day later

    def test_open_drawdown_counts_until_the_end(self) -> None:
        df = equity_frame(curve(100, 90, 95, 97))
        assert longest_drawdown(df) == 2 * D

    def test_returns_based_ratios(self) -> None:
        m = compute_metrics(TRADES, CURVE, 10_000)
        assert m.sharpe is not None and m.sortino is not None
        assert m.sortino > m.sharpe  # few, small down days
        assert m.cagr_percent is not None and m.cagr_percent > 0
        assert m.calmar == pytest.approx(m.cagr_percent / m.max_drawdown_percent)

    def test_exposure(self) -> None:
        m = compute_metrics([], curve(1, 1, 1, 1, open_positions=1), 1)
        assert m.exposure_percent == pytest.approx(50.0)

    def test_empty_run_is_well_defined(self) -> None:
        m = compute_metrics([], [], 10_000)
        assert m.trades == 0 and m.win_rate is None and m.profit_factor is None and m.sharpe is None
        assert m.final_equity == 10_000
        assert all(v is None or not isinstance(v, float) or math.isfinite(v) for v in m.to_dict().values())

    def test_no_losses_means_undefined_profit_factor(self) -> None:
        assert compute_metrics([trade(10.0)], CURVE, 10_000).profit_factor is None


RESULT = BacktestResult(
    trades=TRADES,
    equity_curve=CURVE,
    initial_balance=10_000.0,
    start=T,
    end=T + 4 * D,
    symbols=["EURUSD"],
    signals=9,
    decisions=Counter({"ACCEPT": 4, "REJECT": 5}),
    rejections=Counter({"SPREAD_TOO_HIGH": 3, "RR_TOO_LOW": 2}),
)
PROV = Provenance(seed=42, config_hash="cfg123", data_hash="data456", code_version="0.1.0")


class TestReports:
    def test_summary_carries_provenance_and_limitations(self) -> None:
        s = summary(RESULT, PROV)
        assert s["provenance"] == {
            "seed": 42,
            "config_hash": "cfg123",
            "data_hash": "data456",
            "code_version": "0.1.0",
        }
        assert s["metrics"]["trades"] == 4
        assert s["rejections"] == {"SPREAD_TOO_HIGH": 3, "RR_TOO_LOW": 2}
        assert any("past results" in item for item in s["limitations"])

    def test_files(self, tmp_path: Path) -> None:
        paths = write_reports(RESULT, PROV, tmp_path / "run")
        data = json.loads(paths["summary"].read_text(encoding="utf-8"))
        assert data["period"]["start"] == T.isoformat()
        with paths["trades"].open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert tuple(rows[0]) == TRADE_COLUMNS
        assert [float(r["net"]) for r in rows] == [200.0, -100.0, 150.0, -100.0]
        assert rows[0]["r_multiple"] == "2.0"
        equity = paths["equity"].read_text(encoding="utf-8").splitlines()
        assert equity[0].split(",") == [
            "time",
            "balance",
            "equity",
            "open_positions",
            "peak",
            "drawdown",
            "drawdown_percent",
        ]
        assert len(equity) == 1 + len(CURVE)
