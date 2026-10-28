"""Print the reproducible P1-only foundation report for TREND-RUNNER."""

from __future__ import annotations

from pathlib import Path

from tr1.boundaries import PeriodName, period_for
from tr1.data import TickStore, load_m1
from tr1.foundation import (
    available_tick_days,
    compare_broker_bars,
    frame_manifest,
    load_broker_bars,
    tick_manifest,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_ROOT = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD"
TICK_ROOT = REPO / "data" / "ticks" / "XAUUSD"


def main() -> None:
    period = period_for(PeriodName.P1)
    m1 = load_m1(BAR_ROOT / "M1.parquet", period)
    print("TR1 foundation report: P1 only")  # noqa: T201
    print(f"M1: {frame_manifest(m1)}")  # noqa: T201
    print(f"M1 reader: {m1.attrs}")  # noqa: T201
    for name, rule in (("M5", "5min"), ("M15", "15min"), ("H1", "1h")):
        broker = load_broker_bars(BAR_ROOT / f"{name}.parquet", period)
        print(compare_broker_bars(m1, broker, rule))  # noqa: T201
    days = available_tick_days(TICK_ROOT, period)
    store = TickStore(TICK_ROOT, period)
    print(tick_manifest(store, days))  # noqa: T201
    latest = max(store.opened).date() if store.opened else None
    print(f"tick files opened: {len(store.opened)}; latest: {latest}")  # noqa: T201


if __name__ == "__main__":
    main()
