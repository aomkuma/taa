"""Read-only: M1 bars of the 7 FX majors, 2023-09 .. 2026-10, into data/history (merged), for S1 on currencies
with the spread floor (owner, 2026-10-17: every setup about two trades a day; more markets first).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/download_fx_m1.py
"""

import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from app.broker.factory import build_read_only  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_download import download_history  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

FX = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
START, END = datetime(2023, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 6, tzinfo=timezone.utc)

settings = load_settings()
b = build_read_only(settings)
report = b.client.connect()
store = ParquetHistoryStore(settings.path("data/history"))
try:
    for sym in FX:
        df = download_history(b.gateway, sym, Timeframe.M1, START, END)
        total = store.save(report.account.server, sym, Timeframe.M1, df, b.gateway.symbol_spec(sym))
        print(f"{sym} M1: {len(df)} bars from {df.close_time.min()} to {df.close_time.max()}, {total} stored", flush=True)
finally:
    b.client.shutdown()
