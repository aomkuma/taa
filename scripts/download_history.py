"""Download closed MT5 history to Parquet (and optionally the SQL store).

python scripts/download_history.py --symbols EURUSD,XAUUSD --timeframes M15,H1 --days 365
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.broker.factory import build_read_only
from app.config import load_settings
from app.core.enums import Timeframe
from app.logging_config import configure_logging
from app.market_data.history_download import download_history
from app.market_data.history_store import ParquetHistoryStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--symbols", default=None, help="comma list (default: ALLOWED_SYMBOLS)")
    parser.add_argument("--timeframes", default="M15,H1,H4,D1")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--out", default="data/history")
    parser.add_argument("--fake", action="store_true", help="use FakeMT5 (development)")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    settings = load_settings(env_file=args.env_file)
    configure_logging("download", settings.env.LOG_LEVEL, settings.path(settings.env.LOG_DIR))
    bundle = build_read_only(settings, fake=args.fake)
    report = bundle.client.connect()
    store = ParquetHistoryStore(settings.path(args.out))
    symbols = args.symbols.split(",") if args.symbols else settings.config.symbols.allowed
    end = bundle.client.clock.now_utc()
    start = end - timedelta(days=args.days)
    for symbol in symbols:
        spec = bundle.gateway.symbol_spec(symbol)
        for tf_name in args.timeframes.split(","):
            tf = Timeframe(tf_name.strip())
            df = download_history(bundle.gateway, symbol, tf, start, end)
            total = store.save(report.account.server, symbol, tf, df, spec)
            print(f"{symbol} {tf}: {len(df)} bars downloaded, {total} stored")
    bundle.client.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
