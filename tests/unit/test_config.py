from __future__ import annotations

from pathlib import Path

import pytest

from app.config import load_settings, unknown_env_file_keys
from app.core.enums import TradingMode
from app.core.errors import ConfigError


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_defaults_load_in_backtest(tmp_path: Path) -> None:
    s = load_settings(
        env_file=None, config_file=tmp_path / "missing.yaml", environ={"TRADING_MODE": "BACKTEST"}
    )
    assert s.mode is TradingMode.BACKTEST
    assert s.config.risk.max_risk_per_trade_percent == 0.5
    assert len(s.config_hash) == 16


def test_trading_mode_required(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="TRADING_MODE"):
        load_settings(env_file=None, config_file=tmp_path / "x.yaml", environ={})


def test_invalid_mode_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(env_file=None, config_file=tmp_path / "x.yaml", environ={"TRADING_MODE": "YOLO"})


def test_env_overrides_yaml(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "risk:\n  max_risk_per_trade_percent: 0.3\n")
    s = load_settings(
        env_file=None,
        config_file=cfg,
        environ={
            "TRADING_MODE": "BACKTEST",
            "MAX_RISK_PER_TRADE": "0.7",
            "ALLOWED_SYMBOLS": "EURUSD, XAUUSD",
        },
    )
    assert s.config.risk.max_risk_per_trade_percent == 0.7
    assert s.config.symbols.allowed == ["EURUSD", "XAUUSD"]


@pytest.mark.parametrize(
    ("yaml_text", "fragment"),
    [
        ("risk:\n  max_risk_per_trade_percent: 5\n", "max_risk_per_trade_percent"),
        ("risk:\n  max_account_drawdown_percent: 80\n", "max_account_drawdown_percent"),
        ("risk:\n  max_risk_per_trade_percent: 2\n  max_daily_loss_percent: 1\n", "must not exceed"),
        ("risk:\n  max_riskk: 1\n", "max_riskk"),
        ("timeframes:\n  higher: M15\n  entry: H1\n", "higher timeframe"),
        ("engine:\n  health_host: 0.0.0.0\n", "loopback"),
    ],
)
def test_invalid_config_rejected(tmp_path: Path, yaml_text: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_settings(
            env_file=None, config_file=_write(tmp_path, yaml_text), environ={"TRADING_MODE": "BACKTEST"}
        )


def test_paper_requires_mt5_credentials(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="MT5_LOGIN"):
        load_settings(env_file=None, config_file=tmp_path / "x.yaml", environ={"TRADING_MODE": "PAPER"})


def test_ai_provider_requires_key(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="AI_API_KEY"):
        load_settings(
            env_file=None,
            config_file=tmp_path / "x.yaml",
            environ={"TRADING_MODE": "BACKTEST", "AI_PROVIDER": "anthropic"},
        )


def test_cloud_url_must_be_https(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="https"):
        load_settings(
            env_file=None,
            config_file=tmp_path / "x.yaml",
            environ={"TRADING_MODE": "BACKTEST", "CLOUD_BASE_URL": "http://example.com"},
        )


def test_summary_masks_secrets(tmp_path: Path) -> None:
    env = {
        "TRADING_MODE": "PAPER",
        "MT5_LOGIN": "12345678",
        "MT5_PASSWORD": "hunter2-pass",
        "MT5_SERVER": "FBS-Demo",
        "MT5_TERMINAL_PATH": "C:/MT5/terminal64.exe",
    }
    s = load_settings(env_file=None, config_file=tmp_path / "x.yaml", environ=env)
    text = str(s.summary())
    assert "hunter2-pass" not in text
    assert "*****678" in text
    assert "hunter2-pass" not in repr(s.env)


def test_repo_config_yaml_is_valid() -> None:
    s = load_settings(env_file=None, config_file="config.yaml", environ={"TRADING_MODE": "BACKTEST"})
    assert "XAUUSD" in s.config.symbols.overrides
    assert s.config.spread_limit("XAUUSD") == 40
    assert s.config.lot_limit("XAUUSD") == 0.5


def test_unknown_env_keys(tmp_path: Path) -> None:
    f = tmp_path / ".env"
    f.write_text("TRADING_MODE=PAPER\nMAX_RISK_PER_TRAD=1\nDATABASE_URL=x\n", encoding="utf-8")
    assert unknown_env_file_keys(f) == ["MAX_RISK_PER_TRAD"]


def test_env_example_parses() -> None:
    from dotenv import dotenv_values

    values = {k: v for k, v in dotenv_values(".env.example").items() if v}
    assert unknown_env_file_keys(Path(".env.example")) == []
    s = load_settings(env_file=None, config_file="config.yaml", environ=values)  # type: ignore[arg-type]
    assert s.mode is TradingMode.PAPER


def test_env_example_loads_as_env_file() -> None:
    # Blank template lines (CLOUD_BASE_URL=, AI_API_KEY=) must mean "unset", not an invalid empty value.
    s = load_settings(env_file=".env.example", config_file="config.yaml")
    assert s.mode is TradingMode.PAPER
    assert s.env.CLOUD_BASE_URL is None
    assert s.env.AI_API_KEY is None


def test_blank_env_value_is_unset(tmp_path: Path) -> None:
    s = load_settings(
        env_file=None,
        config_file=tmp_path / "x.yaml",
        environ={"TRADING_MODE": "BACKTEST", "CLOUD_BASE_URL": "", "MAX_RISK_PER_TRADE": ""},
    )
    assert s.env.CLOUD_BASE_URL is None
    assert s.config.risk.max_risk_per_trade_percent == 0.5
