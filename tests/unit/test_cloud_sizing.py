"""Cloud sizing for MANUAL account profiles: the spec-based calculator agrees with MT5 sizing, rates come
from the engine's newest closes, missing data refuses (TAA-8A3)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from app.broker.fake_mt5 import ALL_SYMBOLS
from app.config import RiskConfig
from app.core.enums import Side, Timeframe
from app.market_data.history_store import SqlHistoryStore
from app.risk.position_sizer import AccountFunds, PositionSizer
from app.risk.spec_calculator import SpecCalculator
from app.storage.database import Database
from app.storage.models import AccountProfileRow, SymbolCatalogRow
from app.web.account_profiles import HistoryRates, size_manual
from tests.unit.test_multi_asset import setup

WEDNESDAY = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
RISK = RiskConfig()
FUNDS = AccountFunds(equity=10_000.0, balance=10_000.0, margin=0.0, margin_free=10_000.0)
ENGINE, SERVER = "eng-a", "FBS-Demo"


@pytest.mark.parametrize(
    ("symbol", "sl_distance"), [("EURUSD", 0.0030), ("USDJPY", 0.40), ("XAUUSD", 8.0), ("EURGBP", 0.0030)]
)
def test_spec_sizing_matches_mt5_sizing(symbol: str, sl_distance: float) -> None:
    """The cross-check on owner data: the same trade sized with MT5's calculator and with the cloud's
    calculator over the same spec and the same prices gives the same lot."""
    if symbol not in ALL_SYMBOLS:
        pytest.skip(f"FakeMT5 has no {symbol}")
    _, _, gw = setup(WEDNESDAY)
    spec = gw.symbol_spec(symbol)
    tick = gw.tick(symbol)
    assert tick is not None
    entry, stop = tick.ask, tick.ask - sl_distance

    def rate(ccy: str) -> float | None:  # the same prices MT5 converts with
        for name, s in ALL_SYMBOLS.items():
            q = gw.tick(name)
            if q is None:
                continue
            if s.currency_base == ccy and s.currency_profit == "USD":
                return q.bid
            if s.currency_base == "USD" and s.currency_profit == ccy:
                return 1 / q.bid
        return None

    mt5 = PositionSizer(RISK, gw).size(spec, Side.BUY, entry, stop, FUNDS, lot_limit=spec.volume_max)
    cloud_calc = SpecCalculator({symbol: spec}, "USD", 500.0, rate)
    cloud_spec = cloud_calc.spec_for(symbol)
    assert cloud_spec is not None
    cloud = PositionSizer(RISK, SpecCalculator({symbol: cloud_spec}, "USD", 500.0, rate)).size(
        cloud_spec, Side.BUY, entry, stop, FUNDS, lot_limit=spec.volume_max
    )
    assert mt5.ok and cloud.ok, (mt5.detail, cloud.detail)
    assert abs(mt5.volume - cloud.volume) <= Decimal(str(spec.volume_step)), (mt5.volume, cloud.volume)
    assert abs(mt5.risk_money - cloud.risk_money) / mt5.risk_money < Decimal("0.02")


def test_missing_rates_refuse() -> None:
    _, _, gw = setup(WEDNESDAY)
    spec = gw.symbol_spec("USDJPY")
    calc = SpecCalculator({"USDJPY": spec}, "USD", 100.0, lambda ccy: None)
    assert calc.calc_profit(Side.BUY, "USDJPY", 1.0, 150.0, 149.0) is None
    assert calc.spec_for("USDJPY") is None and calc.calc_margin(Side.BUY, "EURUSD", 1.0, 1.1) is None
    with pytest.raises(ValueError, match="leverage"):
        SpecCalculator({}, "USD", 0, lambda c: 1.0)


def store(db: Database, symbol: str, close: float, at: datetime) -> None:
    _, _, gw = setup(WEDNESDAY)
    spec = gw.symbol_spec(symbol)
    times = pd.DatetimeIndex([at])
    SqlHistoryStore(db, ENGINE).save(
        SERVER,
        symbol,
        Timeframe.M15,
        pd.DataFrame(
            {
                "open_time": times,
                "time_server": [0],
                "open": [close],
                "high": [close],
                "low": [close],
                "close": [close],
                "tick_volume": [1],
                "spread": [1],
            }
        ),
    )
    with db.session() as sess:
        sess.add(
            SymbolCatalogRow(
                engine_id=ENGINE, server=SERVER, symbol=symbol, asset_class="FOREX_MAJOR", enabled=True, reason="",
                path="", description="", spec=dataclasses.asdict(spec), first_seen_at=at, refreshed_at=at, present=True,
            )
        )  # fmt: skip


def profile(currency: str = "USD", **kw: object) -> AccountProfileRow:
    values: dict[str, object] = {
        "user_id": "u1", "source": "MANUAL", "equity": 5_000.0, "balance": 5_000.0, "currency": currency,
        "leverage": 100.0, "risk_percent": None, "updated_at": WEDNESDAY,
    }  # fmt: skip
    return AccountProfileRow(**(values | kw))


class TestManual:
    def test_rates_from_the_newest_closes(self, db: Database) -> None:
        store(db, "EURUSD", 1.10, WEDNESDAY)
        store(db, "USDJPY", 150.0, WEDNESDAY)
        rates = HistoryRates(db, ENGINE, SERVER, "USD", WEDNESDAY)
        assert rates("EUR") == pytest.approx(1.10) and rates("JPY") == pytest.approx(1 / 150)
        assert rates("CHF") is None
        assert HistoryRates(db, ENGINE, SERVER, "EUR", WEDNESDAY)("JPY") == pytest.approx(
            1 / 150 / 1.10
        )  # one hop
        assert HistoryRates(db, ENGINE, SERVER, "EUR", WEDNESDAY)("USD") == pytest.approx(1 / 1.10)
        stale = HistoryRates(db, ENGINE, SERVER, "USD", WEDNESDAY + timedelta(days=8))
        assert stale("EUR") is None  # an old close is no rate
        assert HistoryRates(db, "other-engine", SERVER, "USD", WEDNESDAY)("EUR") is None

    def test_a_manual_profile_is_sized_in_its_own_currency(self, db: Database) -> None:
        store(db, "EURUSD", 1.10, WEDNESDAY)
        store(db, "USDJPY", 150.0, WEDNESDAY)
        args = {"engine_id": ENGINE, "server": SERVER, "side": Side.BUY, "risk": RISK, "now": WEDNESDAY}
        usd = size_manual(db, profile(), symbol="USDJPY", entry=150.0, stop=149.6, risk_percent=None, **args)  # type: ignore[arg-type]
        assert usd.result is not None and usd.result.ok and usd.result.volume > 0
        assert usd.result.budget == Decimal("25.00")  # 0.5% of 5,000
        eur = size_manual(
            db, profile("EUR"), symbol="USDJPY", entry=150.0, stop=149.6, risk_percent=0.25, **args
        )  # type: ignore[arg-type]
        assert eur.result is not None and eur.result.budget == Decimal("12.50")  # the lower percent wins
        assert eur.result.volume < usd.result.volume
        none = size_manual(
            db, profile("CHF"), symbol="USDJPY", entry=150.0, stop=149.6, risk_percent=None, **args
        )  # type: ignore[arg-type]
        assert none.result is None and none.reason == "no_conversion"
        missing = size_manual(
            db, profile(), symbol="XAUUSD", entry=2000.0, stop=1990.0, risk_percent=None, **args
        )  # type: ignore[arg-type]
        assert missing.reason == "no_spec"
        linked = size_manual(
            db,
            profile(source="LINKED_ENGINE"),
            symbol="USDJPY",
            entry=150.0,
            stop=149.6,
            risk_percent=None,
            **args,
        )  # type: ignore[arg-type]
        assert linked.reason == "not_manual"
