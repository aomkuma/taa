from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest

from app.backtest.report import summary
from app.backtest.runner import data_hash, load_history, run_backtest
from app.cli.__main__ import main
from app.config import AppConfig
from app.core.enums import Timeframe
from app.core.errors import DataQualityError
from app.market_data.data_models import CANDLE_COLUMNS
from app.market_data.history_store import ParquetHistoryStore
from tests.strategy_data import EURUSD_SPEC, resample, sawtooth_m15
from tests.unit.test_exposure_manager import GBPUSD_SPEC

SERVER = "FBS-Demo"
TFS = [Timeframe.H1, Timeframe.M15]
EURGBP_SPEC = dataclasses.replace(EURUSD_SPEC, name="EURGBP", currency_profit="GBP")


def full_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["time_server"] = (out["open_time"].astype("int64") // 10**9 + 3 * 3600).astype("int64")
    out["real_volume"] = 0
    out["tick_volume"] = out["tick_volume"].astype("int64")
    out["spread"] = out["spread"].astype("int64")
    return out[CANDLE_COLUMNS]


def store_symbol(store: ParquetHistoryStore, spec, sign: int = 1) -> None:  # type: ignore[no-untyped-def]
    m15 = sawtooth_m15(1800, sign=sign)
    store.save(SERVER, spec.name, Timeframe.M15, full_columns(m15), spec)
    store.save(SERVER, spec.name, Timeframe.H1, full_columns(resample(m15, Timeframe.H1)), spec)


@pytest.fixture
def store(tmp_path: Path) -> ParquetHistoryStore:
    s = ParquetHistoryStore(tmp_path / "history")
    store_symbol(s, EURUSD_SPEC)
    return s


def window(store: ParquetHistoryStore):  # type: ignore[no-untyped-def]
    m15 = store.load(SERVER, "EURUSD", Timeframe.M15)
    return (
        pd.Timestamp(m15["close_time"].iloc[1000]).to_pydatetime(),
        pd.Timestamp(m15["close_time"].iloc[1450]).to_pydatetime(),
    )


CONFIG = AppConfig.model_validate({"symbols": {"allowed": ["EURUSD", "EURGBP"]}})
# the synthetic uptrend of tests/strategy_data.py, bars 1000-1450 with config.yaml defaults: a regression
# anchor for strategy, decision, sizing and fill code, not a statement about performance
GOLDEN: tuple[int, float, list[str]] = (4, 10387.34, ["TP", "TP", "TP", "TP"])


class TestLoading:
    def test_data_hash_is_stable_and_sensitive(self, store: ParquetHistoryStore) -> None:
        a = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
        b = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
        assert a.digest == b.digest
        changed = dict(a.data)
        frame = changed["EURUSD"].frames[Timeframe.M15].copy()
        frame.loc[500, "close"] += 0.00001
        changed["EURUSD"] = dataclasses.replace(
            changed["EURUSD"], frames={**changed["EURUSD"].frames, Timeframe.M15: frame}
        )
        assert data_hash(changed) != data_hash(a.data)

    def test_fails_closed(self, store: ParquetHistoryStore, tmp_path: Path) -> None:
        with pytest.raises(DataQualityError, match="spec"):
            load_history(store, SERVER, ["GBPUSD"], TFS, account_currency="USD")
        with pytest.raises(DataQualityError, match="history"):
            load_history(store, SERVER, ["EURUSD"], [Timeframe.H4], account_currency="USD")
        store_symbol(store, EURGBP_SPEC)
        with pytest.raises(DataQualityError, match="GBP"):
            load_history(store, SERVER, ["EURGBP"], TFS, account_currency="USD")
        store_symbol(store, GBPUSD_SPEC)  # now GBP has a conversion series
        loaded = load_history(store, SERVER, ["EURGBP"], TFS, account_currency="USD")
        assert "GBPUSD" in loaded.conversion


class TestReproducibility:
    def test_identical_runs_give_identical_outputs(self, store: ParquetHistoryStore) -> None:
        start, end = window(store)
        loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
        first = summary(*run_backtest(CONFIG, loaded, config_hash="h", start=start, end=end))
        second = summary(*run_backtest(CONFIG, loaded, config_hash="h", start=start, end=end))
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert first["provenance"]["data_hash"] == loaded.digest
        assert first["provenance"]["seed"] == CONFIG.backtest.seed

    def test_seed_drives_random_slippage(self, store: ParquetHistoryStore) -> None:
        start, end = window(store)
        loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")

        def entries(seed: int) -> list[float]:
            cfg = CONFIG.model_copy(
                update={
                    "backtest": CONFIG.backtest.model_copy(
                        update={"slippage_model": "random", "slippage_points": 5, "seed": seed}
                    )
                }
            )
            return [
                t.entry_price
                for t in run_backtest(cfg, loaded, config_hash="h", start=start, end=end)[0].trades
            ]

        assert entries(1) == entries(1)
        assert entries(1) != entries(2)

    def test_golden(self, store: ParquetHistoryStore) -> None:
        """A behaviour change in strategy, decision, sizing or fills shows up here first."""
        start, end = window(store)
        loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
        result, _ = run_backtest(CONFIG, loaded, config_hash="h", start=start, end=end)
        got = (
            len(result.trades),
            round(result.final_equity, 2),
            [t.exit_reason.value for t in result.trades],
        )
        assert got == GOLDEN


def test_cli_backtest_writes_reports(
    store: ParquetHistoryStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / ".env"
    env.write_text("TRADING_MODE=BACKTEST\n", encoding="utf-8")
    start, end = window(store)
    out = tmp_path / "report"
    code = main(
        [
            "--env-file",
            str(env),
            "backtest",
            "--server",
            SERVER,
            "--data",
            str(store.root),
            "--symbols",
            "EURUSD",
            "--start",
            start.isoformat(),
            "--end",
            end.isoformat(),
            "--out",
            str(out),
            "--strategies",
            "example_trend_pullback",
        ]
    )
    assert code == 0, capsys.readouterr().err
    data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert data["provenance"]["strategies"] == ["example_trend_pullback"]
    assert (out / "trades.csv").exists() and (out / "equity.csv").exists()
    assert "past results do not predict" in capsys.readouterr().out


class TestEvidence:
    """The pattern setups trigger on evidence: a backtest runs the detectors its strategies need."""

    def test_the_selected_strategies_bring_their_detectors(self, store: ParquetHistoryStore) -> None:
        start, end = window(store)
        loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
        cfg = CONFIG.model_copy(
            update={
                "strategies": CONFIG.strategies.model_copy(
                    update={
                        "items": [*CONFIG.strategies.items, *_setups("setup_breakout", "setup_smc_reversal")]
                    }
                )
            }
        )
        _, plain = run_backtest(
            cfg, loaded, config_hash="h", start=start, end=end, strategy_names=["example_trend_pullback"]
        )
        assert plain.extra["detectors"] == []  # no evidence: as fast as before
        _, setups = run_backtest(
            cfg,
            loaded,
            config_hash="h",
            start=start,
            end=end,
            strategy_names=["setup_breakout", "setup_smc_reversal"],
        )
        ran = set(setups.extra["detectors"])
        assert {"volatility.donchian", "sessions.open_breakout", "smc.fvg"} <= ran
        assert {"smc.liquidity_sweep", "structure.bos_choch"} <= ran  # the SMC confirmations
        assert "chart.triangle" not in ran
        _, none = run_backtest(
            cfg,
            loaded,
            config_hash="h",
            start=start,
            end=end,
            strategy_names=["setup_breakout"],
            detectors=[],
        )
        assert none.extra["detectors"] == []


def _setups(*names: str):  # type: ignore[no-untyped-def]
    from app.config import StrategyEntry

    return [StrategyEntry(name=n, enabled=False) for n in names]
