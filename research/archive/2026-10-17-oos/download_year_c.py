"""Read-only: bars for year C, 2023-10 .. 2024-09 (plus warm-up), into data/history (merged): a third year that
shaped no setup and chose no rule, the final hold-out (2026-10-17)."""
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
END = datetime(2024, 8, 2, tzinfo=timezone.utc)  # the stored history starts 2024-08-01
D = lambda y, m, d: datetime(y, m, d, tzinfo=timezone.utc)
JOBS = (
    [(s, "H1", D(2023, 8, 1), END) for s in ALL]
    + [(s, "M15", D(2023, 8, 1), END) for s in TRADED]
    + [(s, "D1", D(2021, 9, 1), D(2022, 9, 3)) for s in TRADED]
    + [(s, "H4", D(2023, 4, 1), D(2024, 4, 23)) for s in TRADED]
    + [("XAUUSD", "M30", D(2023, 8, 1), END), ("XAUUSD", "M1", D(2023, 9, 1), D(2024, 9, 3))]
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
