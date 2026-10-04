"""Closed-candle sync: chunked events, the engine's live stream, bulk upload and cloud ingest (TAA-706)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import func, select

from app.broker.fake_mt5 import ALL_SYMBOLS
from app.config import SyncConfig, TimeframesConfig
from app.core.clock import ManualClock
from app.core.enums import Timeframe
from app.core.ids import new_id
from app.market_data.candle_service import CandleService
from app.market_data.history_download import download_history
from app.market_data.history_store import ParquetHistoryStore, SqlHistoryStore
from app.storage.database import Database
from app.storage.models import HistoryCandle, OutboxEventRow
from app.storage.repositories import EngineStateRepository
from app.sync.candles import SEED_BARS, STREAM_KEY, CandleStreamer, queue_frame, queue_history
from app.sync.command_queue import CommandQueue
from app.sync.events import CANDLES, CandlesPayload
from app.sync.ingest import IngestService
from app.sync.outbox import Outbox, OutboxSender, SendResult
from tests.unit.test_market_data import setup

WED = datetime(2026, 9, 30, 10, 7, 30, tzinfo=UTC)
SAT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
SERVER = "FBS-Demo"


def events(db: Database) -> list[OutboxEventRow]:
    with db.session() as sess:
        return list(
            sess.execute(
                select(OutboxEventRow).where(OutboxEventRow.type == CANDLES).order_by(OutboxEventRow.event_id)
            ).scalars()
        )


def frame(
    n: int, start: datetime = datetime(2026, 9, 1, tzinfo=UTC), tf: Timeframe = Timeframe.M15
) -> pd.DataFrame:
    times = pd.date_range(start, periods=n, freq=f"{tf.minutes}min", tz=UTC)
    return pd.DataFrame(
        {
            "open_time": times,
            "close_time": times + pd.Timedelta(minutes=tf.minutes),
            "time_server": [int(t.timestamp()) + 3 * 3600 for t in times],
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.15,
            "tick_volume": 10,
            "spread": 12,
            "real_volume": 0,
        }
    )


class TestChunks:
    def test_frames_become_validated_events_of_at_most_1000_bars(
        self, db: Database, clock: ManualClock
    ) -> None:
        outbox = Outbox(db, clock, SyncConfig(enabled=True))
        assert queue_frame(outbox, SERVER, "EURUSD", Timeframe.M15, frame(2500)) == 3
        rows = events(db)
        payloads = [CandlesPayload.model_validate(r.payload) for r in rows]
        assert [len(p.bars) for p in payloads] == [1000, 1000, 500]
        assert payloads[0].bars[0][0] == datetime(2026, 9, 1, tzinfo=UTC) and payloads[0].bars[0][1] > 0
        assert {r.priority for r in rows} == {1}
        queue_frame(outbox, SERVER, "EURUSD", Timeframe.M15, frame(2500))
        assert len(events(db)) == 3  # re-queued chunks replace their unsent predecessors

    def test_empty_frames_queue_nothing(self, db: Database, clock: ManualClock) -> None:
        assert (
            queue_frame(Outbox(db, clock, SyncConfig(enabled=True)), SERVER, "X", Timeframe.H1, frame(0)) == 0
        )

    @pytest.mark.parametrize(
        "bad",
        [
            {"timeframe": "M2"},
            {"bars": []},
            {"bars": [["2026-09-30T10:00:00", 1, 1.0, 1.0, 1.0, 1.0, 0, 0]]},  # naive time
            {"bars": [["2026-09-30T10:00:00+00:00", 1, float("nan"), 1.0, 1.0, 1.0, 0, 0]]},
            {"bars": [["2026-09-30T10:00:00+00:00", 1, 1.0, 1.0, 1.0, 1.0, -1, 0]]},
            {"bars": [["2026-09-30T10:00:00+00:00", 1, 1.0, 1.0, 1.0, 1.0, 0, 0]] * 1001},
        ],
    )
    def test_payloads_are_strict(self, bad: dict[str, Any]) -> None:
        good = {
            "server": SERVER,
            "symbol": "EURUSD",
            "timeframe": "M15",
            "bars": [["2026-09-30T10:00:00+00:00", 1, 1.0, 1.1, 0.9, 1.0, 5, 3]],
        }
        CandlesPayload.model_validate(good)
        with pytest.raises(ValueError):
            CandlesPayload.model_validate(good | bad)


class TestStreamer:
    def rig(
        self, start: datetime, db: Database, symbols: Any = None
    ) -> tuple[ManualClock, Any, CandleStreamer, Outbox]:
        clock, fake, gw = setup(start, symbols)
        outbox = Outbox(db, clock, SyncConfig(enabled=True))
        streamer = CandleStreamer(
            CandleService(gw, TimeframesConfig(), clock),
            outbox,
            EngineStateRepository(db, clock),
            clock,
            server=SERVER,
            timeframes=[Timeframe.M15, Timeframe.H1, Timeframe.M15],
        )
        return clock, fake, streamer, outbox

    def test_seed_then_only_new_bars(self, db: Database) -> None:
        clock, fake, streamer, _ = self.rig(WED, db)
        assert streamer.timeframes == (Timeframe.M15, Timeframe.H1)
        assert streamer.tick(["EURUSD"]) == 2  # M15 + H1 seeds, one event each
        seeded = [CandlesPayload.model_validate(e.payload) for e in events(db)]
        assert [len(p.bars) for p in seeded] == [SEED_BARS, SEED_BARS]
        assert seeded[0].bars[-1][0] == datetime(
            2026, 9, 30, 9, 45, tzinfo=UTC
        )  # the forming 10:00 bar is not sent
        calls = fake.calls["copy_rates_from_pos"]
        clock.advance(60)
        assert streamer.tick(["EURUSD"]) == 0
        assert fake.calls["copy_rates_from_pos"] == calls  # no new bar could have closed: no broker call
        clock.set(datetime(2026, 9, 30, 10, 15, 5, tzinfo=UTC))
        assert streamer.tick(["EURUSD"]) == 1
        [new] = [CandlesPayload.model_validate(e.payload) for e in events(db)[2:]]
        assert new.timeframe == "M15" and [b[0] for b in new.bars] == [
            datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
        ]

    def test_the_cursor_survives_a_restart(self, db: Database) -> None:
        clock, _, streamer, _ = self.rig(WED, db)
        streamer.tick(["EURUSD"])
        stored = EngineStateRepository(db, clock).load(STREAM_KEY)
        assert stored is not None and stored["EURUSD|M15"] == "2026-09-30T09:45:00+00:00"
        _, _, again, _ = self.rig(datetime(2026, 9, 30, 10, 31, tzinfo=UTC), db)
        assert again.tick(["EURUSD"]) == 1  # M15 10:00 and 10:15 in one event; no new H1 bar yet
        tail = [CandlesPayload.model_validate(e.payload) for e in events(db)[2:]]
        m15 = next(p for p in tail if p.timeframe == "M15")
        assert [b[0].minute for b in m15.bars] == [0, 15]

    def test_a_shut_market_is_not_polled_every_cycle(self, db: Database) -> None:
        clock, fake, streamer, _ = self.rig(SAT, db)
        streamer.tick(["EURUSD"])
        seeded = len(events(db))
        calls = fake.calls["copy_rates_from_pos"]
        clock.advance(60)
        assert streamer.tick(["EURUSD"]) == 0 and fake.calls["copy_rates_from_pos"] == calls
        assert len(events(db)) == seeded

    def test_crypto_keeps_streaming_while_fx_is_shut(self, db: Database) -> None:
        clock, _, streamer, _ = self.rig(SAT, db, ALL_SYMBOLS)  # Saturday: FX closed, crypto trades 24/7
        streamer.tick(["EURUSD", "BTCUSD"])
        before = len(events(db))
        clock.advance(15 * 60)
        assert streamer.tick(["EURUSD", "BTCUSD"]) == 1  # one new BTCUSD M15 bar, nothing for EURUSD
        [new] = [CandlesPayload.model_validate(e.payload) for e in events(db)[before:]]
        assert (new.symbol, new.timeframe, len(new.bars)) == ("BTCUSD", "M15", 1)
        clock.advance(45 * 60)  # an hour later: BTCUSD gets M15 and H1 bars; EURUSD is still shut
        assert streamer.tick(["EURUSD", "BTCUSD"]) == 2
        assert {CandlesPayload.model_validate(e.payload).symbol for e in events(db)[before:]} == {"BTCUSD"}

    def test_a_broker_failure_costs_one_poll(self, db: Database) -> None:
        _clock, fake, streamer, _ = self.rig(WED, db)
        fake.fail_next("copy_rates_from_pos", times=10)
        assert streamer.tick(["EURUSD"]) == 0 and streamer.failures == 2
        fake.fail_next("copy_rates_from_pos", times=0)  # the broker recovers
        assert streamer.tick(["EURUSD"]) == 2  # nothing was skipped: both seeds go out now


class TestUpload:
    def test_queue_history_from_parquet(self, tmp_path: Path, db: Database) -> None:
        clock, _, gw = setup(WED)
        store = ParquetHistoryStore(tmp_path / "history")
        end = clock.now_utc()
        for symbol in ("EURUSD", "XAUUSD"):
            for tf in (Timeframe.M15, Timeframe.H1):
                store.save(
                    SERVER, symbol, tf, download_history(gw, symbol, tf, end - timedelta(days=20), end)
                )
        outbox = Outbox(db, clock, SyncConfig(enabled=True))
        n_events, bars = queue_history(outbox, store, SERVER, symbols=["EURUSD"], timeframes=[Timeframe.M15])
        assert n_events == len(events(db)) and bars > 1000 and n_events == -(-bars // 1000)
        assert queue_history(outbox, store, "Other-Server") == (0, 0)

    def test_drain_sends_until_empty(self, db: Database, clock: ManualClock) -> None:
        outbox = Outbox(db, clock, SyncConfig(enabled=True, batch_size=2))
        queue_frame(outbox, SERVER, "EURUSD", Timeframe.M15, frame(4500))
        sender = OutboxSender(outbox, lambda path, body: SendResult(200), "eng-1", clock)
        assert sender.drain() == 5 and sender.metrics().pending_total == 0
        queue_frame(outbox, SERVER, "EURUSD", Timeframe.H1, frame(10, tf=Timeframe.H1))
        down = OutboxSender(outbox, lambda path, body: SendResult(503, "HTTP 503"), "eng-1", clock)
        assert down.drain() == 0 and down.consecutive_failures == 1


class TestIngest:
    def ingest(self, cloud: Database, engine_id: str, payload: dict[str, Any]) -> Any:
        clock = ManualClock(WED)
        doc = {
            "schema": 1,
            "engine_id": engine_id,
            "sent_at_utc": WED.isoformat(),
            "events": [
                {
                    "event_id": new_id(),
                    "type": CANDLES,
                    "occurred_at_utc": WED.isoformat(),
                    "payload": payload,
                }
            ],
        }
        return IngestService(cloud, clock, CommandQueue(cloud, clock)).ingest(engine_id, doc)

    def payload(self, n: int, close: float = 1.15) -> dict[str, Any]:
        bars = [
            [t.isoformat(), 1, 1.1, 1.2, 1.0, close, 10, 12] for t in frame(n)["open_time"].dt.to_pydatetime()
        ]
        return {"server": SERVER, "symbol": "EURUSD", "timeframe": "M15", "bars": bars}

    def test_bars_are_upserted_per_engine(self, db: Database) -> None:
        assert self.ingest(db, "eng-a", self.payload(5)).accepted == 1
        assert self.ingest(db, "eng-a", self.payload(5, close=1.16)).accepted == 1  # a resend rewrites
        self.ingest(db, "eng-b", self.payload(3))
        with db.session() as sess:
            counts = dict(
                sess.execute(
                    select(HistoryCandle.engine_id, func.count()).group_by(HistoryCandle.engine_id)
                ).all()
            )
        assert counts == {"eng-a": 5, "eng-b": 3}
        df = SqlHistoryStore(db, "eng-a").load(SERVER, "EURUSD", Timeframe.M15)
        assert len(df) == 5 and set(df["close"]) == {1.16}
        assert SqlHistoryStore(db).load(SERVER, "EURUSD", Timeframe.M15).empty  # local rows are separate

    def test_invalid_candles_are_rejected(self, db: Database) -> None:
        bad = self.payload(2) | {"timeframe": "W1"}
        assert [r.code.value for r in self.ingest(db, "eng-a", bad).rejected] == ["INVALID_PAYLOAD"]


def test_cli_upload_history_queues_into_the_engine_outbox(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.cli.__main__ import main

    _clock, _, gw = setup(WED)
    store = ParquetHistoryStore(tmp_path / "history")
    store.save(
        SERVER,
        "EURUSD",
        Timeframe.H1,
        download_history(gw, "EURUSD", Timeframe.H1, WED - timedelta(days=5), WED),
    )
    url = f"sqlite:///{(tmp_path / 'engine.db').as_posix()}"
    env = tmp_path / ".env"
    env.write_text(f"TRADING_MODE=BACKTEST\nENGINE_DB_URL={url}\nMT5_SERVER={SERVER}\n", encoding="utf-8")
    argv = ["--env-file", str(env), "sync", "upload-history", "--history-dir", str(tmp_path / "history")]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "queued" in out and "1 events" in out and "--send" in out
    engine_db = Database(url)
    assert len(events(engine_db)) == 1
    engine_db.dispose()
