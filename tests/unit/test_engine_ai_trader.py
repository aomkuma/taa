"""The AI trader lane (app/engine/ai_trader.py, TAA-1805): the candle rows as the readers take them, one watcher
cycle per new closed M1 bar with the closes since the last cycle, nothing started while a call runs."""

from __future__ import annotations

from concurrent.futures import Future
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import AITraderConfig
from app.core.enums import Timeframe
from app.engine import ai_trader as at
from app.market_data.data_models import CandleFrame, QualityReport


def rows(start: str, closes: list[float], minutes: int = 1) -> pd.DataFrame:
    t = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=len(closes), freq=f"{minutes}min")
    return pd.DataFrame(
        {
            "open_time": t,
            "close_time": t + pd.Timedelta(minutes=minutes),
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "tick_volume": [100] * len(closes),
        }
    )


class FakeCandles:
    """closed_candles returns the M1 rows given (the last ``count``), and one bar for the other frames."""

    def __init__(self, m1: pd.DataFrame) -> None:
        self.m1 = m1
        self.asked: list[tuple[str, Timeframe, int]] = []

    def closed_candles(self, symbol: str, tf: Timeframe, count: int) -> CandleFrame:
        self.asked.append((symbol, tf, count))
        df = self.m1.tail(count) if tf is Timeframe.M1 else rows("2026-10-23T00:00", [4000.0], 15)
        return CandleFrame(
            symbol, tf, df.reset_index(drop=True), QualityReport(), datetime(2026, 10, 23, tzinfo=UTC)
        )


def lane(tmp_path: Path, m1: pd.DataFrame) -> tuple[at.AITraderLane, list[tuple[pd.Timestamp, list[float]]]]:
    calls: list[tuple[pd.Timestamp, list[float]]] = []
    ln = at.AITraderLane(
        AITraderConfig(enabled=True), FakeCandles(m1), provider=None, releases=(),  # type: ignore[arg-type]
        store=tmp_path, journal=tmp_path / "journal.md", background=False,
    )  # fmt: skip

    def on_bar(now: pd.Timestamp, closes: list[float]) -> dict[str, Any] | None:
        calls.append((now, closes))
        return None

    ln.watcher.on_bar = on_bar  # type: ignore[method-assign]
    return ln, calls


def test_to_frame_indexes_by_the_open_and_keeps_the_last_copy():
    df = rows("2026-10-23T15:00", [1.0, 2.0, 3.0])
    # out of order, and bar 15:01 again at the end with a corrected close (the later copy wins, as in the history)
    df = pd.concat([df.iloc[[2, 0, 1]], df.iloc[[1]].assign(close=9.0)])
    got = at.to_frame(df)
    assert list(got.columns) == ["open", "high", "low", "close", "tick_volume"]
    assert list(got.index) == [pd.Timestamp(f"2026-10-23T15:0{i}", tz="UTC") for i in range(3)]
    assert got.close.tolist() == [1.0, 9.0, 3.0]


def test_one_cycle_per_new_closed_bar_with_the_closes_since_the_last(tmp_path: Path):
    m1 = rows("2026-10-23T15:00", [10.0, 11.0, 12.0])  # closed bars 15:00, 15:01, 15:02
    ln, calls = lane(tmp_path, m1)
    assert ln.tick() is True
    # the first cycle: now = the last bar's close 15:03, closes of the bars opened from that bar on
    assert calls == [(pd.Timestamp("2026-10-23T15:03", tz="UTC"), [12.0])]
    assert ln.tick() is False  # no new bar
    ln.candles.m1 = rows("2026-10-23T15:00", [10.0, 11.0, 12.0, 13.0, 14.0])  # two more closed: 15:03, 15:04
    assert ln.tick() is True
    assert calls[1] == (pd.Timestamp("2026-10-23T15:05", tz="UTC"), [13.0, 14.0])  # both since 15:03
    assert len(calls) == 2


def test_the_frames_ask_every_frame_once_with_its_count(tmp_path: Path):
    ln, _ = lane(tmp_path, rows("2026-10-23T15:00", [10.0, 11.0]))
    ln.tick()
    asked = {(tf, n) for _, tf, n in ln.candles.asked if n > 2}
    # what the readers need: M5 built from 1,400 x 5 = 7,000 M1 bars (rhythm_scan), 2,600 bars of M15 / H1 / H4
    # (rhythm_scan's window), the D1 history since 2021 for the zone grid (1,327 bars on 2026-10-23)
    assert asked == {
        (Timeframe.M1, 7200),
        (Timeframe.M15, 2700),
        (Timeframe.H1, 2700),
        (Timeframe.H4, 2700),
        (Timeframe.D1, 2500),
    }


def test_nothing_starts_while_a_call_runs_and_its_closes_wait(tmp_path: Path):
    ln, calls = lane(tmp_path, rows("2026-10-23T15:00", [10.0, 11.0]))
    ln.tick()
    ln._running = Future()  # a call still running (never done here)
    ln.candles.m1 = rows("2026-10-23T15:00", [10.0, 11.0, 12.0])
    assert ln.tick() is False
    assert len(calls) == 1
    ln._running.set_result(None)  # it finished: the next tick hands over the bar that waited
    assert ln.tick() is True
    assert calls[1] == (pd.Timestamp("2026-10-23T15:03", tz="UTC"), [12.0])


def test_no_bars_no_cycle(tmp_path: Path):
    ln, calls = lane(tmp_path, rows("2026-10-23T15:00", []))
    assert ln.tick() is False
    assert calls == []


def test_suspensions_and_the_journal_are_read_from_the_store(tmp_path: Path):
    ln, _ = lane(tmp_path, rows("2026-10-23T15:00", [10.0]))
    assert ln._suspensions() == {}
    assert ln._journal() == ""
    (tmp_path / "suspended.json").write_text('{"R01": "2026-10-23T22:00:00+00:00"}', encoding="utf-8")
    (tmp_path / "journal.md").write_text("## notes", encoding="utf-8")
    assert ln._suspensions() == {"R01": "2026-10-23T22:00:00+00:00"}
    assert ln._journal() == "## notes"
