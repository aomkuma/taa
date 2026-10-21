"""copy_ticks_range while the terminal is still downloading a tick month (found 2026-10-20 on the FBS demo terminal).

A request reaching a month that is not yet in ``Bases/<server>/ticks`` blocks about 100 s and answers None with
(-1, "Terminal: Call failed"); the terminal keeps downloading, and the very same request succeeds afterwards (measured
on 2021-02-10: failed after 104.8 s, then 159,639 ticks in 13.3 s, then 0.3 s). It is not the argument form: int epochs
and aware datetimes return the same ticks. The gateway therefore asks again after a pause before it gives up.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from app.broker.fake_mt5 import ALL_SYMBOLS, FakeMT5
from app.broker.gateway import TICK_SYNC_ATTEMPTS, ReadOnlyMT5Gateway
from app.broker.mt5_client import MT5Client
from app.config import load_settings
from app.core.clock import ManualClock, ServerClock
from app.core.errors import BrokerError

ENV = {
    "TRADING_MODE": "PAPER",
    "MT5_LOGIN": "12345678",
    "MT5_PASSWORD": "investor-pass",
    "MT5_SERVER": "FBS-Demo",
    "MT5_TERMINAL_PATH": "x",
}
SYNCING = (-1, "Terminal: Call failed")
START, END = datetime(2026, 9, 30, 14, 0, tzinfo=UTC), datetime(2026, 9, 30, 14, 10, tzinfo=UTC)


def setup() -> tuple[FakeMT5, ReadOnlyMT5Gateway, list[float]]:
    clock = ManualClock(datetime(2026, 9, 30, 15, 0, tzinfo=UTC))
    fake = FakeMT5(clock, symbols=ALL_SYMBOLS, history_days=10, future_days=3)
    s = load_settings(env_file=None, config_file="config.yaml", environ=ENV)
    client = MT5Client(s.env, s.mode, mt5_module=fake, clock=clock)
    client.connect()
    waits: list[float] = []
    gw = ReadOnlyMT5Gateway(client, ServerClock("Europe/Athens", clock), sleep=waits.append)
    return fake, gw, waits


@pytest.mark.parametrize("method", ["ticks_range", "raw_ticks"])
def test_a_month_still_downloading_is_asked_again(method: str) -> None:
    fake, gw, waits = setup()
    fake.fail_next("copy_ticks_range", times=TICK_SYNC_ATTEMPTS - 1, error=SYNCING)
    df = getattr(gw, method)("EURUSD", START, END)
    assert len(df) == 40  # 4 ticks a minute in FakeMT5, 10 minutes
    assert fake.calls["copy_ticks_range"] == TICK_SYNC_ATTEMPTS
    assert waits == [5.0] * (TICK_SYNC_ATTEMPTS - 1)


@pytest.mark.parametrize("method", ["ticks_range", "raw_ticks"])
def test_it_gives_up_after_the_last_attempt_and_says_why(method: str) -> None:
    fake, gw, waits = setup()
    fake.fail_next("copy_ticks_range", times=TICK_SYNC_ATTEMPTS, error=SYNCING)
    with pytest.raises(BrokerError, match="still downloading"):
        getattr(gw, method)("EURUSD", START, END)
    assert fake.calls["copy_ticks_range"] == TICK_SYNC_ATTEMPTS
    assert len(waits) == TICK_SYNC_ATTEMPTS - 1


def test_another_error_is_not_retried() -> None:
    fake, gw, waits = setup()
    fake.fail_next("copy_ticks_range", times=1, error=(-2, "Invalid arguments"))
    with pytest.raises(BrokerError, match="Invalid arguments"):
        gw.ticks_range("EURUSD", START, END)
    assert fake.calls["copy_ticks_range"] == 1 and waits == []


def test_a_first_answer_needs_no_wait() -> None:
    fake, gw, waits = setup()
    assert len(gw.ticks_range("EURUSD", START, END)) == 40
    assert fake.calls["copy_ticks_range"] == 1 and waits == []


def test_an_empty_answer_is_an_answer() -> None:
    """No ticks in the window (a closed market) is not a failure: one call, an empty frame, no wait."""
    fake, gw, waits = setup()
    asked: list[object] = []

    def empty(*args: object) -> np.ndarray:
        asked.append(args)
        return np.empty(0, dtype=[("time", "i8"), ("time_msc", "i8"), ("bid", "f8"), ("ask", "f8")])

    fake.copy_ticks_range = empty  # type: ignore[method-assign]
    df = gw.ticks_range("EURUSD", START, END)
    assert df.empty and list(df.columns) == ["time_utc", "bid", "ask"]
    assert len(asked) == 1 and waits == []
