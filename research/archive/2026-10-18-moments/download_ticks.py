"""Read-only: gold's tick history (bid/ask, millisecond times, UTC) from the FBS demo terminal, one Parquet file per
UTC day under data/ticks/XAUUSD (owner, 2026-10-17: "open it" - the demo account, history only, no orders).
Days already on disk are skipped, so the script resumes.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/download_ticks.py 2025-10-01 2026-10-17
    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/download_ticks.py --probe
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, ".")
from app.broker.factory import build_read_only  # noqa: E402
from app.config import load_settings  # noqa: E402

SYMBOL = "XAUUSD"
OUT = Path("data/ticks") / SYMBOL


def main() -> None:
    settings = load_settings()
    b = build_read_only(settings)
    report = b.client.connect()
    print("connected:", report.account.server, "trade mode demo:", "demo" in str(report.account.server).lower(), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        if sys.argv[1:] == ["--probe"]:
            for d in ("2024-10-02", "2025-01-08", "2025-04-02", "2025-07-02", "2025-10-01", "2026-04-01", "2026-10-14"):
                t0 = datetime.fromisoformat(d).replace(tzinfo=timezone.utc)
                try:
                    df = b.gateway.ticks_range(SYMBOL, t0, t0 + timedelta(hours=1))
                    print(d, len(df), "ticks in 00:00-01:00 UTC", flush=True)
                except Exception as exc:  # noqa: BLE001 - a probe reports and goes on
                    print(d, "failed:", exc, flush=True)
            return
        day = datetime.fromisoformat(sys.argv[1]).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(sys.argv[2]).replace(tzinfo=timezone.utc)
        while day < end:
            path = OUT / f"{day:%Y-%m-%d}.parquet"
            if day.weekday() < 5 and not path.exists():
                try:
                    df = b.gateway.ticks_range(SYMBOL, day, day + timedelta(days=1))
                except Exception as exc:  # noqa: BLE001 - one bad day is reported, the rest go on
                    print(f"{day:%Y-%m-%d}: failed {exc}", flush=True)
                else:
                    df.to_parquet(path)
                    print(f"{day:%Y-%m-%d}: {len(df)} ticks", flush=True)
            day += timedelta(days=1)
    finally:
        b.client.shutdown()


if __name__ == "__main__":
    main()
