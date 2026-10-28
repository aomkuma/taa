"""Read-only: bring gold's and the USD majors' bar history up to date from the FBS demo terminal (the forward check of
the frozen Setup OWN rules on data after 2026-10-14; docs/OWN_SETUP_ROUNDS.md). Bars are merged into data/history; gold
ticks are fetched with download_ticks.py.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/update_history.py [START]
"""

import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from app.broker.factory import build_read_only  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_download import download_history  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

SYMBOLS = {
    "XAUUSD": (Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1),
    **{p: (Timeframe.M1,) for p in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD")},
    **{p: (Timeframe.M1,) for p in ("US500", "JP225")},
}


def main() -> None:
    start = datetime.fromisoformat(sys.argv[1]).replace(tzinfo=timezone.utc) if len(sys.argv) > 1 else datetime(2026, 10, 12, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) + timedelta(hours=1)
    settings = load_settings()
    b = build_read_only(settings)
    report = b.client.connect()
    store = ParquetHistoryStore(settings.path("data/history"))
    try:
        for sym, tfs in SYMBOLS.items():
            for tf in tfs:
                df = download_history(b.gateway, sym, tf, start, end)
                total = store.save(report.account.server, sym, tf, df, b.gateway.symbol_spec(sym))
                last = df.close_time.max() if len(df) else None
                print(f"{sym} {tf}: {len(df)} bars to {last}, {total} stored", flush=True)
    finally:
        b.client.shutdown()


if __name__ == "__main__":
    main()
