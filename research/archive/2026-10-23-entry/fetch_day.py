"""Refresh one UTC day of XAUUSD from MT5, read-only: the bars (scripts/download_history.py, merged) and the day's
ticks into data/ticks/XAUUSD/<date>.parquet (time_utc, bid, ask; replaced only when the new file holds more ticks).
For back-filling the observer after the PC slept (owner 2026-10-23: "load the ticks and bars in full and run it
back").

    .venv/Scripts/python research/2026-10-23-entry/fetch_day.py 2026-10-23
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/2026-10-18-moments/agents/precursors"))
from fetch_release_ticks import ticks  # noqa: E402

OUT = ROOT / "data/ticks/XAUUSD"


def main() -> None:
    day = pd.Timestamp(sys.argv[1], tz="UTC")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/download_history.py"), "--symbols", "XAUUSD",
                        "--timeframes", "M1,M5,M15,H1,H4,D1", "--days", "3"], cwd=ROOT, check=False)  # noqa: S603
    print(f"bars refreshed (exit {r.returncode})")
    from app.broker.factory import build_read_only
    from app.config import load_settings

    bundle = build_read_only(load_settings(env_file=str(ROOT / ".env")), fake=False)
    bundle.client.connect()
    try:
        x = ticks(bundle, day, day + pd.Timedelta(days=1))
    finally:
        bundle.client.shutdown()
    f = OUT / f"{day:%Y-%m-%d}.parquet"
    old = len(pd.read_parquet(f)) if f.exists() else 0
    if len(x) > old:
        x.to_parquet(f)
        print(f"{f.name}: {len(x)} ticks (was {old}), {x.time_utc.iloc[0]} .. {x.time_utc.iloc[-1]}")
    else:
        print(f"{f.name}: kept the stored {old} ticks (MT5 gave {len(x)})")


if __name__ == "__main__":
    main()
