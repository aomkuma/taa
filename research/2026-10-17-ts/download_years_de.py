"""Read-only: gold bars for 2021-10 .. 2023-09 (years E and D, plus warm-up) into a SEPARATE store,
data/history_old (owner, 2026-10-17: more independent years for the TS rules). The main store data/history is not
touched, so the gold M1 file the backtests load keeps its size (the S1 session's request)."""

import sys
from datetime import UTC, datetime

sys.path.insert(0, ".")
from app.broker.factory import build_read_only
from app.config import load_settings
from app.core.enums import Timeframe
from app.market_data.history_download import download_history
from app.market_data.history_store import ParquetHistoryStore


def day(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


END = day(2023, 10, 3)
JOBS = [
    ("XAUUSD", "D1", day(2020, 9, 1), END),
    ("XAUUSD", "H4", day(2020, 12, 1), END),
    ("XAUUSD", "H1", day(2021, 6, 1), END),
    ("XAUUSD", "M15", day(2021, 7, 1), END),
    ("XAUUSD", "M1", day(2021, 9, 1), END),
]
settings = load_settings()
b = build_read_only(settings)
report = b.client.connect()
store = ParquetHistoryStore(settings.path("data/history_old"))
try:
    for sym, tf_name, start, end in JOBS:
        df = download_history(b.gateway, sym, Timeframe(tf_name), start, end)
        total = store.save(report.account.server, sym, Timeframe(tf_name), df, b.gateway.symbol_spec(sym))
        first = df.close_time.min() if len(df) else None
        last = df.close_time.max() if len(df) else None
        print(f"{sym} {tf_name}: {len(df)} bars {first} .. {last}, {total} stored", flush=True)
finally:
    b.client.shutdown()
