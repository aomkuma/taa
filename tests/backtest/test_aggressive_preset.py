"""The aggressive preset in the backtester and its compounding ruin Monte Carlo (PLAN §A36)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.backtest.engine import BacktestEngine, BacktestResult, RiskPreset
from app.backtest.presets import PROVEN_SETUPS, aggressive_preset
from app.backtest.robustness import RuinRules, RuinTrade, ruin_monte_carlo, trading_day_pool
from app.cli.__main__ import build_parser, main
from app.config import AppConfig, HighRiskCage, HighRiskConfig, StrategiesConfig, StrategyEntry
from app.core.enums import Timeframe
from app.core.errors import ConfigError
from app.execution.simulated_broker import AccountCurrencyOnly
from app.risk.limits import aggressive_limits
from app.strategy.catalog import default_registry
from tests.backtest.test_engine import symbol_data
from tests.strategy_data import EURUSD_SPEC

WED = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
YAML = AppConfig.model_validate(
    {
        "strategies": {
            "items": [
                {"name": "example_trend_pullback", "enabled": True},
                {"name": "setup_harmonic_prz", "enabled": False},
                {"name": "setup_breakout", "enabled": True},
            ]
        }
    }
)


class TestPreset:
    def test_only_the_proven_setups_trade(self) -> None:
        config, preset = aggressive_preset(YAML, 7.5)
        enabled = {i.name for i in config.strategies.items if i.enabled}
        assert enabled == set(PROVEN_SETUPS)
        assert isinstance(preset.cage, HighRiskCage) and preset.cage.setups == PROVEN_SETUPS
        eff = preset.effective
        assert eff.max_risk_per_trade_percent == 7.5 and eff.max_daily_loss_percent == 15.0
        assert eff.max_account_drawdown_percent == 60.0 and eff.max_open_positions == 2
        assert eff.min_lot_fallback is False

    def test_the_section_of_config_yaml_wins(self) -> None:
        section = {"setups": ["setup_breakout"], "max_account_drawdown_percent": 50}
        config = AppConfig.model_validate(YAML.model_dump() | {"high_risk": section})
        out, preset = aggressive_preset(config, 5)
        assert {i.name for i in out.strategies.items if i.enabled} == {"setup_breakout"}
        assert preset.effective.max_account_drawdown_percent == 50

    @pytest.mark.parametrize("risk", [4.9, 10.1])
    def test_risk_outside_five_to_ten_is_refused(self, risk: float) -> None:
        with pytest.raises(ConfigError, match="5-10"):
            aggressive_preset(YAML, risk)

    def test_without_proven_setups_it_is_refused(self) -> None:
        with pytest.raises(ConfigError, match="proven setups"):
            aggressive_preset(AppConfig(), 7.5)


def _run(preset: RiskPreset | None) -> BacktestResult:
    data = {"EURUSD": symbol_data(EURUSD_SPEC, 1)}
    config = AppConfig.model_validate(
        {
            "symbols": {"allowed": ["EURUSD"]},
            "backtest": {"slippage_model": "none"},
            "risk": {"correlation_groups": {}, "max_lot": 50, "min_margin_level_percent": 100},
        }
    )
    strategies = default_registry().from_config(
        StrategiesConfig(items=[StrategyEntry(name="example_trend_pullback")]), config.timeframes
    )
    first = data["EURUSD"].frames[Timeframe.M15]
    engine = BacktestEngine(
        config,
        data,
        strategies,
        AccountCurrencyOnly("USD"),
        start=pd.Timestamp(first["close_time"].iloc[1000]).to_pydatetime(),
        end=pd.Timestamp(first["close_time"].iloc[1450]).to_pydatetime(),
        risk_preset=preset,
    )
    return engine.run()


class TestEngine:
    def test_the_preset_sizes_every_decision(self) -> None:
        cage = HighRiskConfig(setups=["example_trend_pullback"]).cage(
            AppConfig.model_validate({"risk": {"max_lot": 50, "min_margin_level_percent": 100}}).risk
        )
        result = _run(RiskPreset("aggressive-7.5", cage, aggressive_limits(7.5)))
        assert result.trades
        first = result.trades[0]
        assert first.risk_money > 0.03 * 10_000  # far above the standard 0.5 % (margin and leverage cut it)
        assert first.risk_money <= 0.075 * 10_000 + 1e-6

    def test_a_setup_outside_the_preset_never_trades(self) -> None:
        cage = HighRiskConfig(setups=["setup_breakout"]).cage(AppConfig().risk)
        result = _run(RiskPreset("aggressive-7.5", cage, aggressive_limits(7.5)))
        assert not result.trades
        assert result.rejections["STRATEGY_NOT_IN_PRESET"] > 0


def day(n: int, hour: int = 10) -> datetime:
    return WED + timedelta(days=n, hours=hour - 10)


class TestRuin:
    def test_pool_keeps_empty_weekdays_and_moves_weekends_to_friday(self) -> None:
        trades = [RuinTrade(day(0), 1.0), RuinTrade(day(3), -1.0), RuinTrade(day(6), 0.5)]  # Wed, Sat, Tue
        pool = trading_day_pool(trades)
        assert len(pool) == 5  # Wed Thu Fri Mon Tue
        assert [len(d) for d in pool] == [1, 0, 1, 0, 1]
        assert pool[2][0][0] > 86_400  # the Saturday trade: a day after Friday

    def test_compounding_on_wins(self) -> None:
        rep = ruin_monte_carlo([RuinTrade(day(0), 1.0)], RuinRules(risk_percent=10), runs=5, days=3)
        assert rep.finals == pytest.approx([1.1**3] * 5)
        assert rep.max_drawdowns.max() == 0.0 and rep.probability_of_kill == 0.0

    def test_fades_risk_the_fraction(self) -> None:
        rep = ruin_monte_carlo(
            [RuinTrade(day(0), -1.0, fade=True)], RuinRules(risk_percent=10), runs=1, days=1
        )
        assert rep.finals[0] == pytest.approx(0.95)

    def test_daily_budget_stops_the_third_loss(self) -> None:
        losses = [RuinTrade(day(0, h), -1.0) for h in (8, 9, 10)]
        rep = ruin_monte_carlo(losses, RuinRules(risk_percent=7.5), runs=1, days=1)
        assert rep.taken[0] == 2  # 7.5 + 7.5 fits the 15 % budget; 14.4 + 7.5 does not
        assert rep.finals[0] == pytest.approx(0.925**2)

    def test_streak_pause(self) -> None:
        losses = [RuinTrade(day(0, h), -1.0) for h in (8, 9, 10, 11, 12)]
        rules = RuinRules(risk_percent=1.0, daily_loss_percent=20, max_consecutive_losses=4)
        rep = ruin_monte_carlo(losses, rules, runs=1, days=1)
        assert rep.taken[0] == 4

    def test_the_kill_stops_the_run(self) -> None:
        loss = [RuinTrade(day(0), -1.0)]
        rules = RuinRules(risk_percent=10, max_consecutive_losses=50, weekly_loss_percent=100)
        rep = ruin_monte_carlo(loss, rules, runs=3, days=30)
        assert rep.probability_of_kill == 1.0
        assert (rep.max_drawdowns < 60).all()  # refused before it could pass the kill
        assert rep.median_days_to_kill is not None

    def test_deterministic_with_a_seed(self) -> None:
        trades = [RuinTrade(day(i % 5), r) for i, r in enumerate([1.0, -1.0, 0.4, -1.0, 2.0, 0.5])]
        a = ruin_monte_carlo(trades, RuinRules(risk_percent=7.5), runs=50, seed=3)
        b = ruin_monte_carlo(trades, RuinRules(risk_percent=7.5), runs=50, seed=3)
        assert (a.finals == b.finals).all() and (a.max_drawdowns == b.max_drawdowns).all()


class TestCli:
    def test_ruin_reads_trades_and_prints_one_row_per_risk(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        folder = tmp_path / "run"
        folder.mkdir()
        rows = ["entry_time,r_multiple,strategy"]
        rows += [
            f"{(WED + timedelta(days=i)).isoformat()},{r},setup_breakout"
            for i, r in enumerate([0.45, -1.0] * 5)
        ]
        rows += [
            f"{(WED + timedelta(days=i, hours=2)).isoformat()},{r},setup_harmonic_prz"
            for i, r in enumerate([2.0, -1.0])
        ]
        (folder / "trades.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        code = main(
            [
                "backtest",
                "ruin",
                str(folder),
                "--risk",
                "5,10",
                "--runs",
                "20",
                "--fade-strategies",
                "setup_breakout",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "12 trades" in out and "10 fades" in out
        assert sum(line.strip().startswith(("5.00", "10.00")) for line in out.splitlines()) == 2

    def test_plain_backtest_still_parses(self) -> None:
        args = build_parser().parse_args(["backtest", "--preset", "aggressive", "--risk", "7.5"])
        assert args.preset == "aggressive" and args.risk == 7.5 and args.func.__name__ == "cmd_backtest"
