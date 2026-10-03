"""Historical candle storage for backtests and charts.

* :class:`ParquetHistoryStore`: local files ``<root>/<server>/<symbol>/<TF>.parquet`` plus a JSON sidecar with
  the symbol specification snapshot (engine host / local backtests).
* :class:`SqlHistoryStore`: ``history_candles`` table (cloud worker backtests, PWA charts).

Both store the normalized candle frame (UTC ``open_time``) and merge new data idempotently by open time.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
from sqlalchemy import delete, select

from app.core.clock import Clock, SystemClock, ensure_utc
from app.core.enums import Timeframe
from app.market_data.data_models import CANDLE_COLUMNS, SymbolSpec
from app.storage.database import Database
from app.storage.models import HistoryCandle

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe(name: str) -> str:
    return _SAFE.sub("_", name)


class HistoryStore(Protocol):
    def save(
        self, server: str, symbol: str, tf: Timeframe, df: pd.DataFrame, spec: SymbolSpec | None = None
    ) -> int: ...

    def load(
        self,
        server: str,
        symbol: str,
        tf: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame: ...


def _merge(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    frames = [f for f in (existing, new) if not f.empty]
    if not frames:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset="open_time", keep="last").sort_values("open_time")
    return merged.reset_index(drop=True)[CANDLE_COLUMNS]


def _slice(df: pd.DataFrame, start: datetime | None, end: datetime | None) -> pd.DataFrame:
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df["open_time"] >= pd.Timestamp(ensure_utc(start))
    if end is not None:
        mask &= df["open_time"] < pd.Timestamp(ensure_utc(end))
    return df.loc[mask].reset_index(drop=True)


class ParquetHistoryStore:
    def __init__(self, root: Path, clock: Clock | None = None) -> None:
        self.root = root
        self.clock = clock or SystemClock()

    def path(self, server: str, symbol: str, tf: Timeframe) -> Path:
        return self.root / _safe(server) / _safe(symbol) / f"{tf.value}.parquet"

    def save(
        self, server: str, symbol: str, tf: Timeframe, df: pd.DataFrame, spec: SymbolSpec | None = None
    ) -> int:
        path = self.path(server, symbol, tf)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=CANDLE_COLUMNS)
        merged = _merge(existing, df[CANDLE_COLUMNS] if not df.empty else df)
        tmp = path.with_suffix(".tmp")
        merged.to_parquet(tmp, index=False)
        tmp.replace(path)
        if spec is not None:
            meta: dict[str, Any] = {
                "server": server,
                "symbol": symbol,
                "spec": asdict(spec),
                "saved_at_utc": self.clock.now_utc().isoformat(),
            }
            path.with_name("spec.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return len(merged)

    def load(
        self,
        server: str,
        symbol: str,
        tf: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        path = self.path(server, symbol, tf)
        if not path.exists():
            return pd.DataFrame(columns=CANDLE_COLUMNS)
        df = pd.read_parquet(path)
        for col in ("open_time", "close_time"):
            df[col] = pd.to_datetime(df[col], utc=True)
        return _slice(df, start, end)

    def spec(self, server: str, symbol: str) -> dict[str, Any] | None:
        path = self.root / _safe(server) / _safe(symbol) / "spec.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def available(self) -> list[tuple[str, str, Timeframe]]:
        out = []
        for file in sorted(self.root.glob("*/*/*.parquet")):
            try:
                out.append((file.parent.parent.name, file.parent.name, Timeframe(file.stem)))
            except ValueError:
                continue
        return out


class SqlHistoryStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(
        self, server: str, symbol: str, tf: Timeframe, df: pd.DataFrame, spec: SymbolSpec | None = None
    ) -> int:
        if df.empty:
            return 0
        times = [pd.Timestamp(t).to_pydatetime() for t in df["open_time"]]
        with self.db.session() as sess:
            sess.execute(
                delete(HistoryCandle).where(
                    HistoryCandle.server == server,
                    HistoryCandle.symbol == symbol,
                    HistoryCandle.timeframe == tf.value,
                    HistoryCandle.open_time.in_(times),
                )
            )
            sess.add_all(
                [
                    HistoryCandle(
                        server=server,
                        symbol=symbol,
                        timeframe=tf.value,
                        open_time=t,
                        time_server=int(ts),
                        open=float(o),
                        high=float(h),
                        low=float(lo),
                        close=float(c),
                        tick_volume=int(v),
                        spread=int(sp),
                    )
                    for t, ts, o, h, lo, c, v, sp in zip(
                        times,
                        df["time_server"].to_numpy(dtype="int64"),
                        df["open"].to_numpy(dtype=float),
                        df["high"].to_numpy(dtype=float),
                        df["low"].to_numpy(dtype=float),
                        df["close"].to_numpy(dtype=float),
                        df["tick_volume"].to_numpy(dtype="int64"),
                        df["spread"].to_numpy(dtype="int64"),
                        strict=True,
                    )
                ]
            )
        return len(df)

    def load(
        self,
        server: str,
        symbol: str,
        tf: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        stmt = select(HistoryCandle).where(
            HistoryCandle.server == server,
            HistoryCandle.symbol == symbol,
            HistoryCandle.timeframe == tf.value,
        )
        if start is not None:
            stmt = stmt.where(HistoryCandle.open_time >= ensure_utc(start))
        if end is not None:
            stmt = stmt.where(HistoryCandle.open_time < ensure_utc(end))
        with self.db.session() as sess:
            rows = list(sess.execute(stmt.order_by(HistoryCandle.open_time)).scalars())
        if not rows:
            return pd.DataFrame(columns=CANDLE_COLUMNS)
        open_time = pd.DatetimeIndex([r.open_time for r in rows])
        return pd.DataFrame(
            {
                "open_time": open_time,
                "close_time": open_time + pd.Timedelta(seconds=tf.seconds),
                "time_server": [r.time_server for r in rows],
                "open": [r.open for r in rows],
                "high": [r.high for r in rows],
                "low": [r.low for r in rows],
                "close": [r.close for r in rows],
                "tick_volume": [r.tick_volume for r in rows],
                "spread": [r.spread for r in rows],
                "real_volume": [0] * len(rows),
            }
        )
