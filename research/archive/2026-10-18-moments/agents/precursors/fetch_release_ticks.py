"""Old gold ticks around the 08:30-NY minute for NS-1 (owner's go-ahead 2026-10-20 18:33 Thai), read-only from MT5.

For each weekday in [start, end] (release days first, then a sample of other days if asked), the ticks of 08:20 ..
09:05 New York are saved to data/ticks_old/XAUUSD/<NY date>.parquet (time_utc, bid, ask), the same columns as
data/ticks. MT5 downloads whole months into the terminal's Bases (on D:): the run stops when D: has less than 20 GB
free. Days already saved are skipped.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/fetch_release_ticks.py 2021-09-01 2025-10-17 [--all]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "ticks_old" / "XAUUSD"
DRIVE = "D:/"
MIN_FREE_GB = 20.0


def ticks(bundle, a: pd.Timestamp, z: pd.Timestamp) -> pd.DataFrame:
    """The ticks in [a, z) UTC. gateway.ticks_range fails on this terminal (2026-10-20: 'Call failed' with epoch ints
    and a +-1 day margin), so the window is asked with datetimes widened by 6 h, and the server epochs are converted
    with the gateway's own ServerClock, as ticks_range does."""
    import numpy as np  # noqa: PLC0415

    mt5 = bundle.client.mt5
    raw = bundle.client.call("copy_ticks_range", "XAUUSD", (a - pd.Timedelta(hours=6)).to_pydatetime(),
                             (z + pd.Timedelta(hours=6)).to_pydatetime(), mt5.COPY_TICKS_ALL)
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=["time_utc", "bid", "ask"])
    arr = np.asarray(raw)
    msc = arr["time_msc"].astype("int64")
    t = bundle.gateway.server_clock.server_epochs_to_utc(msc // 1000) + pd.to_timedelta(msc % 1000, unit="ms")
    df = pd.DataFrame({"time_utc": t, "bid": arr["bid"].astype(float), "ask": arr["ask"].astype(float)})
    return df[(df.time_utc >= a) & (df.time_utc < z)].reset_index(drop=True)


def main() -> None:
    from app.broker.factory import build_read_only  # noqa: PLC0415
    from app.config import load_settings  # noqa: PLC0415

    a, z = sys.argv[1], sys.argv[2]
    every = "--all" in sys.argv
    cal = pd.read_csv(ROOT / "app/news/us_releases.csv")
    rel = set(cal[(cal.time_et == "08:30") & (cal.date >= a) & (cal.date <= z)].date)
    days = [d for d in pd.bdate_range(a, z) if every or f"{d:%Y-%m-%d}" in rel]
    OUT.mkdir(parents=True, exist_ok=True)
    settings = load_settings(env_file=str(ROOT / ".env"))
    bundle = build_read_only(settings, fake=False)
    bundle.client.connect()
    got = empty = 0
    try:
        for d in days:
            f = OUT / f"{d:%Y-%m-%d}.parquet"
            if f.exists():
                continue
            if shutil.disk_usage(DRIVE).free / 2**30 < MIN_FREE_GB:
                print(f"stopped: D: below {MIN_FREE_GB} GB free")
                break
            t0 = pd.Timestamp(f"{d:%Y-%m-%d} 08:20").tz_localize("America/New_York").tz_convert("UTC")
            x = ticks(bundle, t0, t0 + pd.Timedelta(minutes=45))
            if len(x) == 0:
                empty += 1
                print(f"{d:%Y-%m-%d}: no ticks")
                continue
            x.to_parquet(f)
            got += 1
            print(f"{d:%Y-%m-%d}: {len(x)} ticks {x.time_utc.iloc[0]} .. {x.time_utc.iloc[-1]}", flush=True)
    finally:
        bundle.client.shutdown()
    print(f"saved {got}, empty {empty}, of {len(days)} days; D: free {shutil.disk_usage(DRIVE).free / 2**30:.1f} GB")


if __name__ == "__main__":
    main()
