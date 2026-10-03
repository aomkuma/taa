"""TAA-110: multi-asset FakeMT5, symbol groups, tick history, fixed/tiered leverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.broker import mt5_constants as c
from app.broker.fake_mt5 import ALL_SYMBOLS, FakeAccount, FakeMT5, fbs_forex_leverage_for_equity
from app.broker.gateway import ReadOnlyMT5Gateway
from app.broker.mt5_client import MT5Client
from app.broker.symbol_groups import match_group
from app.config import load_settings
from app.core.clock import ManualClock, ServerClock
from app.core.enums import Side, Timeframe

ENV = {
    "TRADING_MODE": "PAPER",
    "MT5_LOGIN": "12345678",
    "MT5_PASSWORD": "investor-pass",
    "MT5_SERVER": "FBS-Demo",
    "MT5_TERMINAL_PATH": "x",
}


def setup(start: datetime, account: FakeAccount | None = None):  # type: ignore[no-untyped-def]
    clock = ManualClock(start)
    fake = FakeMT5(clock, account=account, symbols=ALL_SYMBOLS, history_days=10, future_days=3)
    s = load_settings(env_file=None, config_file="config.yaml", environ=ENV)
    client = MT5Client(s.env, s.mode, mt5_module=fake, clock=clock)
    client.connect()
    return clock, fake, ReadOnlyMT5Gateway(client, ServerClock("Europe/Athens", clock))


@pytest.mark.parametrize(
    ("name", "group", "expected"),
    [
        ("EURUSD", None, True),
        ("EURUSD", "*", True),
        ("EURUSD", "*, !*EUR*", False),
        ("GBPUSD", "*, !*EUR*", True),
        ("XAUUSD", "XA*", True),
        ("eurusd", "EUR*", True),
        ("US30", "*USD*", False),
        ("EURGBP", "*USD*, !EUR*, EURGBP", True),
    ],
)
def test_match_group(name: str, group: str | None, expected: bool) -> None:
    assert match_group(name, group) is expected


def test_symbols_with_group_filter() -> None:
    _, _, gw = setup(datetime(2026, 9, 30, 15, 0, tzinfo=UTC))
    names = {s.name for s in gw.symbols()}
    assert {"EURUSD", "US30", "BTCUSD", "AAPL", "USOIL", "XAGUSD"} <= names
    no_usd = {s.name for s in gw.symbols("*, !*USD*")}
    assert "EURGBP" in no_usd and "EURUSD" not in no_usd
    specs = {s.name: s for s in gw.symbols()}
    assert specs["US30"].calc_mode == c.SYMBOL_CALC_MODE_CFDINDEX
    assert specs["AAPL"].path.startswith("Stocks")


def test_schedules_per_asset_type() -> None:
    # Saturday: FX closed, crypto open
    clock, _, gw = setup(datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
    btc = gw.rates_from_pos("BTCUSD", Timeframe.M1, 0, 5)
    assert int(btc["time"].iloc[-1]) >= gw.server_clock.utc_to_server_epoch(clock.now_utc()) - 120
    # Wednesday 03:00 UTC: US stock closed (overnight), FX open
    clock2, _, gw2 = setup(datetime(2026, 9, 30, 3, 0, tzinfo=UTC))
    aapl_last = gw2.rates_from_pos("AAPL", Timeframe.M1, 0, 1)
    last_utc = gw2.server_clock.server_epoch_to_utc(int(aapl_last["time"].iloc[-1]))
    assert last_utc < clock2.now_utc() - timedelta(hours=6)  # previous session's close
    eur_last = gw2.rates_from_pos("EURUSD", Timeframe.M1, 0, 1)
    assert gw2.server_clock.server_epoch_to_utc(
        int(eur_last["time"].iloc[-1])
    ) >= clock2.now_utc() - timedelta(minutes=2)


def test_ticks_consistent_with_m1_bars() -> None:
    _, _, gw = setup(datetime(2026, 9, 30, 15, 0, tzinfo=UTC))
    start, end = datetime(2026, 9, 30, 14, 0, tzinfo=UTC), datetime(2026, 9, 30, 14, 10, tzinfo=UTC)
    ticks = gw.ticks_range("EURUSD", start, end)
    bars = gw.rates_range("EURUSD", Timeframe.M1, start, end)
    assert len(ticks) == 4 * len(bars) == 40
    assert ticks["time_utc"].is_monotonic_increasing
    assert ticks["time_utc"].min() >= start and ticks["time_utc"].max() < end
    assert (ticks["ask"] > ticks["bid"]).all()
    assert ticks["bid"].max() == pytest.approx(bars["high"].max())
    assert ticks["bid"].min() == pytest.approx(bars["low"].min())


def test_fixed_instrument_leverage_and_tiers() -> None:
    _, _, gw = setup(
        datetime(2026, 9, 30, 15, 0, tzinfo=UTC), FakeAccount(tiered_leverage=True, balance=100.0)
    )
    assert gw.account().leverage == 3000
    eur = gw.calc_margin(Side.BUY, "EURUSD", 1.0, 1.1)
    gold_price = gw.tick("XAUUSD").bid  # type: ignore[union-attr]
    gold = gw.calc_margin(Side.BUY, "XAUUSD", 1.0, gold_price)
    assert eur is not None and gold is not None
    assert eur == pytest.approx(100_000 * gw.tick("EURUSD").bid / 3000, rel=0.02)  # type: ignore[union-attr]
    assert gold == pytest.approx(100 * gold_price / 500, rel=0.01)  # metals fixed at 1:500


def test_fbs_tiers() -> None:
    assert [fbs_forex_leverage_for_equity(x) for x in (100, 200, 4_999, 5_000, 29_999, 30_000, 200_000)] == [
        3000,
        2000,
        2000,
        1000,
        1000,
        500,
        200,
    ]


def test_cross_and_exotic_profit_conversion() -> None:
    _, _, gw = setup(datetime(2026, 9, 30, 15, 0, tzinfo=UTC))
    gbp = gw.calc_profit(Side.BUY, "EURGBP", 1.0, 0.8600, 0.8590)  # loss in GBP converted to USD
    zar = gw.calc_profit(Side.BUY, "USDZAR", 1.0, 18.20, 18.10)
    assert gbp is not None and gbp < 0 and abs(gbp) > 100  # 100 GBP > 100 USD
    assert zar is not None and zar < 0
    assert np.isfinite(gbp) and np.isfinite(zar)
