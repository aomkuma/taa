"""CR-4 eye check (docs/CHART_READ.md §8): the bot picks 20 charts for the owner to read by eye.

Owner, 2026-10-14: the bot samples the charts itself, across the 8 symbols, M15/H1/H4 and every phase, at random
within each group and never by result; the check passes when the bot's trend and its two nearest levels agree
with the owner's reading on at least 16 of 20.

Groups (the phase the bot reads at the bar): UP, DOWN, CONTRACTING, BROADENING, FLIPPED (a flipped level within
1 ATR of the close), SWEEP_RECLAIM and BREAK_HOLD (the event among the read's events). The 20 slots go round the
groups, the timeframes and a shuffled symbol order; each slot draws random bars of the year (2025-10-01 ..
2026-09-30) until the bar's read is in the slot's group. Seed 20261014, so the sample can be redrawn.

    .venv/Scripts/python research/2026-10-14-chart-read/eye_check_sample.py > research/2026-10-14-chart-read/EYE_CHECK.md
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.indicators.chart_read import ChartRead, ChartReadFrame, EventKind, LevelRole, Structure  # noqa: E402

H = "data/history/FBS-Demo"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD"]
TFS = ["M15", "H1", "H4"]
GROUPS = ["UP", "DOWN", "CONTRACTING", "BROADENING", "FLIPPED", "SWEEP_RECLAIM", "BREAK_HOLD"]
START, END = pd.Timestamp("2025-10-01", tz="UTC"), pd.Timestamp("2026-09-30", tz="UTC")
SEED = 20261014
WEB = "http://localhost:8001"
THAI = timedelta(hours=7)


def in_group(r: ChartRead, group: str) -> bool:
    if group in ("UP", "DOWN", "CONTRACTING", "BROADENING"):
        return r.structure is Structure(group)
    if group == "FLIPPED":
        return any(lv.role is LevelRole.FLIPPED and lv.dist_atr <= 1.0 for lv in r.levels)
    return any(e.kind is EventKind(group) for e in r.events)


def load(sym: str, tf: str) -> ChartReadFrame:
    d = pd.read_parquet(f"{H}/{sym}/{tf}.parquet").sort_values("close_time")
    d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    point = json.loads(open(f"{H}/{sym}/spec.json", encoding="utf-8").read())["spec"]["point"]
    return ChartReadFrame(tf, d[["open", "high", "low", "close"]].astype(float), float(point))


def fmt(x: float | None, digits: int) -> str:
    return "-" if x is None else f"{x:,.{digits}f}"


def main() -> None:
    rng = np.random.default_rng(SEED)
    order = list(rng.permutation(SYMBOLS))
    frames: dict[tuple[str, str], ChartReadFrame] = {}
    rows = []
    for slot in range(20):
        group, tf, sym = GROUPS[slot % len(GROUPS)], TFS[slot % len(TFS)], str(order[slot % len(order)])
        key = (sym, tf)
        if key not in frames:
            frames[key] = load(sym, tf)
        f = frames[key]
        lo, hi = int(f.index.searchsorted(START)), int(f.index.searchsorted(END)) - 1
        found = None
        for _ in range(20000):
            pos = int(rng.integers(lo, hi))
            r = f.at(pos)
            if r is not None and in_group(r, group):
                found = r
                break
        if found is None:
            rows.append((slot + 1, sym, tf, group, None))
            continue
        rows.append((slot + 1, sym, tf, group, found))

    print("# Eye check: 20 charts the bot picked (TAA-L813 CR-4)\n")
    print(f"Drawn by `eye_check_sample.py` (seed {SEED}): 8 symbols, M15/H1/H4, 7 groups, random bars of the year")
    print("within each group, never chosen by result. Each link opens the PWA chart as it was at that bar's close")
    print("with the bot's read drawn (`read=1`, `end=`). The check passes when the bot's trend and its two nearest")
    print("levels agree with the owner's reading on at least 16 of the 20 (docs/CHART_READ.md §8).\n")
    print("| # | Symbol | TF | Bar close (Thai time) | Group | Bot's trend | Nearest support | Nearest resistance | Link | Owner: trend | Owner: levels |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for n, sym, tf, group, r in rows:
        if r is None:
            print(f"| {n} | {sym} | {tf} | - | {group} | no bar found | | | | | |")
            continue
        sup, res = r.nearest(above=False), r.nearest(above=True)
        end = pd.Timestamp(r.at).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        local = (pd.Timestamp(r.at) + THAI).strftime("%Y-%m-%d %H:%M")
        link = f"[open]({WEB}/charts?symbol={sym}&tf={tf}&end={end}&read=1)"
        sup_s = "-" if sup is None else f"{fmt(sup.price, r.digits)} ({sup.role.value.lower()})"
        res_s = "-" if res is None else f"{fmt(res.price, r.digits)} ({res.role.value.lower()})"
        print(
            f"| {n} | {sym} | {tf} | {local} | {group} | {r.structure.value} | {sup_s} | {res_s} | {link} | | |"
        )


if __name__ == "__main__":
    main()
