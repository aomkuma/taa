"""The aggressive preset's cage and opt-in (PLAN §A36): config section, env opt-in, LIVE refused."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import (
    AppConfig,
    HighRiskCage,
    HighRiskConfig,
    RiskConfig,
    high_risk_phrase,
    load_settings,
)
from app.core.enums import TradingMode
from app.core.errors import ConfigError

SECTION = """
strategies:
  items:
    - {name: setup_harmonic_prz, enabled: true}
    - {name: setup_breakout, enabled: true}
high_risk:
  setups: [setup_harmonic_prz, setup_breakout]
"""


def _env(mode: str = "PAPER", **extra: str) -> dict[str, str]:
    env = {
        "TRADING_MODE": mode,
        "MT5_LOGIN": "12345678",
        "MT5_PASSWORD": "pw-not-real",
        "MT5_SERVER": "FBS-Demo",
        "MT5_TERMINAL_PATH": "C:/MT5/terminal64.exe",
    }
    env.update(extra)
    return env


def _write(tmp_path: Path, text: str = SECTION) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def _opt_in(mode: str = "PAPER", phrase: str | None = None) -> dict[str, str]:
    return _env(
        mode,
        ENABLE_HIGH_RISK_PROFILE="true",
        HIGH_RISK_CONFIRMATION=phrase if phrase is not None else high_risk_phrase(12345678),
    )


class TestCage:
    def test_risk_block_keeps_the_standard_ceilings(self) -> None:
        with pytest.raises(ValidationError):
            RiskConfig(
                max_risk_per_trade_percent=7.5, max_daily_loss_percent=10, max_total_open_risk_percent=10
            )

    def test_cage_raises_the_bounds(self) -> None:
        cage = HighRiskConfig(setups=["a"]).cage(RiskConfig())
        assert isinstance(cage, HighRiskCage)
        assert cage.max_risk_per_trade_percent == 10.0
        assert cage.max_account_drawdown_percent == 60.0
        assert cage.max_weekly_loss_percent == 35.0
        assert cage.max_open_positions == 3
        assert cage.max_same_direction_per_currency == 1
        assert cage.max_effective_leverage == 200.0  # 0.01 lot of gold on 50 USD is ~90x (owner, 2026-10-14)
        assert cage.min_lot_fallback is True and cage.min_lot_max_risk_percent == 15.0
        assert cage.setups == ("a",)
        assert cage.fade_risk_factor == 0.5

    def test_cage_caps_the_fallback_whatever_the_base(self) -> None:
        cage = HighRiskConfig(setups=["a"], min_lot_max_risk_percent=10).cage(
            RiskConfig(min_lot_fallback=False)
        )
        assert cage.min_lot_fallback is True and cage.min_lot_max_risk_percent == 10.0

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("max_risk_per_trade_percent", 10.5),
            ("max_total_open_risk_percent", 21),
            ("max_daily_loss_percent", 21),
            ("max_weekly_loss_percent", 36),
            ("max_account_drawdown_percent", 61),
            ("max_open_positions", 4),
            ("max_effective_leverage", 201),
            ("min_lot_max_risk_percent", 21),
        ],
    )
    def test_section_above_the_cage_ceilings_is_refused(self, field: str, value: float) -> None:
        with pytest.raises(ValidationError):
            HighRiskConfig.model_validate({"setups": ["a"], field: value})

    def test_cage_refuses_an_uncapped_fallback(self) -> None:
        with pytest.raises(ValidationError, match="minimum lot"):
            HighRiskCage(setups=("a",), min_lot_fallback=True, min_lot_max_risk_percent=None)

    @pytest.mark.parametrize("mode", ["LIVE", "BACKTEST"])
    def test_modes_paper_and_demo_only(self, mode: str) -> None:
        with pytest.raises(ValidationError, match="PAPER and DEMO only"):
            HighRiskConfig(setups=["a"], modes=[TradingMode(mode)])

    def test_setups_must_be_configured_strategies(self) -> None:
        with pytest.raises(ValidationError, match=r"not in strategies\.items"):
            AppConfig.model_validate({"high_risk": {"setups": ["no_such_setup"]}})

    def test_setups_required(self) -> None:
        with pytest.raises(ValidationError):
            HighRiskConfig.model_validate({})


class TestOptIn:
    def test_no_section_no_cage(self, tmp_path: Path) -> None:
        s = load_settings(env_file=None, config_file=tmp_path / "missing.yaml", environ=_env())
        assert s.high_risk_cage() is None
        assert s.high_risk_refusal() == "NOT_ENABLED"

    def test_section_without_opt_in_is_not_enabled(self, tmp_path: Path) -> None:
        s = load_settings(env_file=None, config_file=_write(tmp_path), environ=_env())
        assert s.high_risk_cage() is None
        assert s.high_risk_refusal() == "NOT_ENABLED"

    @pytest.mark.parametrize("mode", ["PAPER", "DEMO"])
    def test_opt_in_gives_the_cage(self, tmp_path: Path, mode: str) -> None:
        env = _opt_in(mode)
        if mode == "DEMO":
            env["ENABLE_DEMO_TRADING"] = "true"
        s = load_settings(env_file=None, config_file=_write(tmp_path), environ=env)
        cage = s.high_risk_cage()
        assert cage is not None and cage.setups == ("setup_harmonic_prz", "setup_breakout")
        assert s.high_risk_refusal() is None

    def test_mode_outside_the_section_is_refused(self, tmp_path: Path) -> None:
        text = SECTION + "  modes: [DEMO]\n"
        s = load_settings(env_file=None, config_file=_write(tmp_path, text), environ=_opt_in("PAPER"))
        assert s.high_risk_cage() is None
        assert s.high_risk_refusal() == "MODE_NOT_ALLOWED"

    def test_wrong_phrase_stops_startup(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="HIGH_RISK_CONFIRMATION"):
            load_settings(
                env_file=None,
                config_file=_write(tmp_path),
                environ=_opt_in(phrase="I-ACCEPT-HIGH-RISK-99999999"),
            )

    def test_opt_in_without_section_stops_startup(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="no high_risk"):
            load_settings(env_file=None, config_file=tmp_path / "missing.yaml", environ=_opt_in())

    def test_live_is_refused(self, tmp_path: Path) -> None:
        env = _opt_in("LIVE")
        env["ENABLE_LIVE_TRADING"] = "true"
        with pytest.raises(ConfigError, match="LIVE"):
            load_settings(env_file=None, config_file=_write(tmp_path), environ=env)

    def test_summary_masks_the_phrase(self, tmp_path: Path) -> None:
        s = load_settings(env_file=None, config_file=_write(tmp_path), environ=_opt_in())
        assert high_risk_phrase(12345678) not in str(s.summary())
