"""Read-only: bars for the out-of-sample year 2024-10 .. 2025-09 (plus warm-up) into data/history (merged)."""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from app.broker.factory import build_read_only
from app.config import load_settings
from app.core.enums import Timeframe
from app.market_data.history_download import download_history
from app.market_data.history_store import ParquetHistoryStore

TRADED = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD"]
ALL = sorted(os.listdir("data/history/FBS-Demo"))
END = datetime(2025, 10, 6, tzinfo=timezone.utc)  # the stored year starts 2025-10-05
D = lambda y, m, d: datetime(y, m, d, tzinfo=timezone.utc)
JOBS = (
    [(s, "H1", D(2024, 8, 1), END) for s in ALL]
    + [(s, "M15", D(2024, 8, 1), END) for s in TRADED]
    + [(s, "D1", D(2022, 9, 1), D(2024, 4, 25)) for s in TRADED]
    + [("XAUUSD", "M30", D(2024, 8, 1), END), ("XAUUSD", "M1", D(2024, 9, 1), END)]
)
settings = load_settings()
b = build_read_only(settings)
report = b.client.connect()
store = ParquetHistoryStore(settings.path("data/history"))
try:
    for sym, tf_name, start, end in JOBS:
        tf = Timeframe(tf_name)
        df = download_history(b.gateway, sym, tf, start, end)
        total = store.save(report.account.server, sym, tf, df, b.gateway.symbol_spec(sym))
        first = df.close_time.min() if len(df) else None
        print(f"{sym} {tf_name}: {len(df)} bars from {first}, {total} stored", flush=True)
finally:
    b.client.shutdown()
