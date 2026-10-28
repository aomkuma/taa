"""Read-only: M1, M15 and H1 bars of the gold-like markets (spread about 0.2-0.36 of the M1 range), 2023-08 ..
2026-10, into data/history (merged), for S1 beyond gold
(owner, 2026-10-17: every setup about two trades a day; more markets first).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/download_more.py
"""

import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from app.broker.factory import build_read_only  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_download import download_history  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

MARKETS = ["US100", "JP225", "US30", "US500", "XAUAUD"]
START, END = datetime(2023, 8, 1, tzinfo=timezone.utc), datetime(2026, 10, 6, tzinfo=timezone.utc)

settings = load_settings()
b = build_read_only(settings)
report = b.client.connect()
store = ParquetHistoryStore(settings.path("data/history"))
try:
    for sym in MARKETS:
        for tf in (Timeframe.M1, Timeframe.M15, Timeframe.H1):
            df = download_history(b.gateway, sym, tf, START, END)
            total = store.save(report.account.server, sym, tf, df, b.gateway.symbol_spec(sym))
            print(f"{sym} {tf}: {len(df)} bars from {df.close_time.min()}, {total} stored", flush=True)
finally:
    b.client.shutdown()
