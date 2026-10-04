from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.advisory.asset_classes import AssetClass, classify
from app.advisory.universe import SymbolCatalog, evaluate_entry, monitored_set
from app.broker import mt5_constants as c
from app.broker.fake_mt5 import ALL_SYMBOLS
from app.config import UniverseConfig
from app.storage.database import Database
from app.storage.models import SymbolCatalogRow
from app.storage.models.base import LOCAL_ENGINE
from tests.strategy_data import EURUSD_SPEC
from tests.unit.test_market_data import setup

WED = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
A = AssetClass


def spec(name: str, base: str, quote: str, path: str = "", calc: int = c.SYMBOL_CALC_MODE_FOREX):  # type: ignore[no-untyped-def]
    return dataclasses.replace(
        EURUSD_SPEC, name=name, currency_base=base, currency_profit=quote, path=path, calc_mode=calc
    )


class TestClassification:
    @pytest.mark.parametrize(
        ("s", "expected"),
        [
            (spec("EURUSD", "EUR", "USD"), A.FOREX_MAJOR),
            (spec("USDJPY", "USD", "JPY"), A.FOREX_MAJOR),
            (spec("EURGBP", "EUR", "GBP"), A.FOREX_MINOR),
            (spec("NZDCAD", "NZD", "CAD"), A.FOREX_MINOR),
            (spec("USDZAR", "USD", "ZAR"), A.FOREX_EXOTIC),
            (spec("EURTRY", "EUR", "TRY"), A.FOREX_EXOTIC),
            (spec("XAUUSD", "XAU", "USD", "Forex\\XAUUSD"), A.METAL),  # the base wins over a Forex path
            (spec("BTCUSD", "BTC", "USD", "", c.SYMBOL_CALC_MODE_CFD), A.CRYPTO),
            (spec("US30", "USD", "USD", "Indices\\US30", c.SYMBOL_CALC_MODE_CFDINDEX), A.INDEX),
            (spec("DE40", "EUR", "EUR", "", c.SYMBOL_CALC_MODE_CFDINDEX), A.INDEX),
            (spec("USOIL", "USD", "USD", "Energies\\USOIL", c.SYMBOL_CALC_MODE_CFD), A.ENERGY),
            (spec("AAPL", "USD", "USD", "Stocks\\US\\AAPL", c.SYMBOL_CALC_MODE_CFD), A.STOCK),
            (spec("MSFT", "USD", "USD", "", c.SYMBOL_CALC_MODE_EXCH_STOCKS), A.STOCK),
            (spec("WEIRD", "USD", "USD", "Misc\\WEIRD", c.SYMBOL_CALC_MODE_CFD), A.OTHER),
        ],
    )
    def test_rules(self, s, expected: AssetClass) -> None:  # type: ignore[no-untyped-def]
        assert classify(s) is expected

    def test_every_fake_symbol_gets_a_tradeable_class(self) -> None:
        _, _, gateway = setup(WED, ALL_SYMBOLS)
        classes = {s.name: classify(s) for s in gateway.symbols()}
        assert classes == {
            "EURUSD": A.FOREX_MAJOR,
            "GBPUSD": A.FOREX_MAJOR,
            "USDJPY": A.FOREX_MAJOR,
            "AUDUSD": A.FOREX_MAJOR,
            "EURGBP": A.FOREX_MINOR,
            "USDZAR": A.FOREX_EXOTIC,
            "XAUUSD": A.METAL,
            "XAGUSD": A.METAL,
            "US30": A.INDEX,
            "USOIL": A.ENERGY,
            "BTCUSD": A.CRYPTO,
            "AAPL": A.STOCK,
        }


class TestConfig:
    def test_defaults_exotics_and_other_opt_in(self) -> None:
        cfg = UniverseConfig()
        assert not cfg.classes["FOREX_EXOTIC"] and not cfg.classes["OTHER"]
        assert all(v for k, v in cfg.classes.items() if k not in ("FOREX_EXOTIC", "OTHER"))
        assert not evaluate_entry(spec("USDZAR", "USD", "ZAR"), cfg).enabled
        assert "opt-in" in evaluate_entry(spec("USDZAR", "USD", "ZAR"), cfg).reason

    def test_overrides_and_partial_class_maps(self) -> None:
        cfg = UniverseConfig(classes={"CRYPTO": False}, symbols={"USDZAR": True, "EURUSD": False})
        assert cfg.classes["FOREX_MAJOR"] is True  # unspecified classes keep their defaults
        assert evaluate_entry(spec("USDZAR", "USD", "ZAR"), cfg).enabled
        assert not evaluate_entry(spec("EURUSD", "EUR", "USD"), cfg).enabled
        assert not evaluate_entry(spec("BTCUSD", "BTC", "USD"), cfg).enabled

    def test_group_filter(self) -> None:
        assert UniverseConfig(include=["*"], exclude=["*.m", "AAPL"]).group == "*,!*.m,!AAPL"
        with pytest.raises(ValueError):
            UniverseConfig(exclude=["!AAPL"])
        with pytest.raises(ValueError):
            UniverseConfig(classes={"BONDS": True})


class TestCatalog:
    def catalog(self, db: Database, cfg: UniverseConfig | None = None):  # type: ignore[no-untyped-def]
        clock, fake, gateway = setup(WED, ALL_SYMBOLS)
        return SymbolCatalog(db, gateway, cfg or UniverseConfig(), clock, server="FBS-Demo"), clock, fake

    def test_refresh_stores_classified_symbols(self, db: Database) -> None:
        cat, _, _ = self.catalog(db)
        entries = cat.refresh()
        assert len(entries) == len(ALL_SYMBOLS)
        enabled = {e.symbol for e in cat.entries()}
        assert "USDZAR" not in enabled and "EURUSD" in enabled and len(enabled) == len(ALL_SYMBOLS) - 1
        stored = cat.entries(enabled_only=False)
        assert {e.symbol: e.asset_class for e in stored}["US30"] is A.INDEX
        assert stored[0].spec.volume_step > 0  # the spec round-trips through JSON

    def test_refresh_is_daily_unless_forced(self, db: Database) -> None:
        cat, clock, fake = self.catalog(db)
        cat.refresh()
        calls = fake.calls["symbols_get"]
        cat.refresh()
        assert fake.calls["symbols_get"] == calls  # served from the table
        clock.advance(25 * 3600)
        cat.refresh()
        assert fake.calls["symbols_get"] == calls + 1
        cat.refresh(force=True)
        assert fake.calls["symbols_get"] == calls + 2

    def test_include_exclude_and_disappearing_symbols(self, db: Database) -> None:
        cat, _, fake = self.catalog(db, UniverseConfig(exclude=["AAPL"]))
        cat.refresh()
        assert "AAPL" not in {e.symbol for e in cat.entries(enabled_only=False)}
        del fake.symbols["BTCUSD"]
        cat.refresh(force=True)
        with db.session() as sess:
            row = sess.get(SymbolCatalogRow, (LOCAL_ENGINE, "FBS-Demo", "BTCUSD"))
            assert row is not None and row.present is False
            assert sess.execute(select(SymbolCatalogRow.symbol)).scalars().all()
        assert "BTCUSD" not in {e.symbol for e in cat.entries()}


class TestMonitoredSet:
    def test_priority_dedupe_and_cap(self) -> None:
        out = monitored_set(
            allowlist=["EURUSD", "XAUUSD"],
            favourites=["BTCUSD", "EURUSD"],
            lists={"swing": ["US30", "AAPL"]},
            ranked=["GBPUSD", "USDJPY", "USOIL", "XAGUSD"],
            auto_top_n=2,
            cap=6,
        )
        assert out == ["EURUSD", "XAUUSD", "BTCUSD", "US30", "AAPL", "GBPUSD"]

    def test_unknown_symbols_are_dropped(self) -> None:
        out = monitored_set(allowlist=["EURUSD"], favourites=["NOPE"], available={"EURUSD"})
        assert out == ["EURUSD"]

    def test_default_cap_is_60(self) -> None:
        ranked = [f"S{i}" for i in range(100)]
        assert len(monitored_set(allowlist=[], ranked=ranked, auto_top_n=100)) == 60
