"""The rejection-at-a-level trigger for TS (the owner's way: sell at the zone once the entry timeframe turns, not
after the structure break). On every entry bar: the extreme of the last ``WINDOW`` bars (the high for a SELL) is
followed by the first close beyond the previous bar's extreme (Elder's third screen) on this bar; the row records
the extreme, its distance to the nearest H1/H4 chart-read level and the same context as ts_dataset.py, so
ts_study.py reads both files the same way (``pivot`` = the extreme). Writes <out>/triggers.csv.

usage: CONFIG_FILE=data/research/config_ts_all_m15.yaml ... python ts_reject_dataset.py app.cli backtest ... --out <dir>
"""

import csv
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.cli.__main__ import main  # noqa: E402
from app.strategy import setups  # noqa: E402

WINDOW = int(os.environ.get("TS_WINDOW", "8"))  # M15: 2 hours
MAX_DIST = 1.5  # read ATR: rows farther from every level are not kept
rows: list[dict[str, object]] = []
orig = setups.TripleScreen.evaluate


def _rel(market: setups.MarketContext, tf: str, buy: bool) -> tuple[str, str]:
    m = None if market.htf is None else market.htf.frames.get(tf)
    if m is None:
        return "NONE", "NONE"
    return setups._relative(m.state, buy), setups._swing_relative(m.read, buy)


def _levels(market: setups.MarketContext, tf: str, pivot: float, close: float, buy: bool) -> dict[str, object]:
    read = setups._read(market, tf)
    if read is None or not read.atr > 0:
        return {f"{tf}_atr": None, f"{tf}_pivot_dist": None, f"{tf}_pivot_role": None, f"{tf}_ahead": None}
    near = min(read.levels, key=lambda lv: abs(lv.price - pivot), default=None)
    sign = 1 if buy else -1
    ahead = sorted((lv.price for lv in read.levels if (lv.price - close) * sign > 0), key=lambda p: abs(p - close))
    return {
        f"{tf}_atr": read.atr,
        f"{tf}_pivot_dist": None if near is None else abs(near.price - pivot) / read.atr,
        f"{tf}_pivot_role": None if near is None else near.role.value,
        f"{tf}_ahead": ahead[0] if ahead else None,
    }


def _scan(ctx: setups.StrategyContext) -> None:
    frame = ctx.frame(ctx.market.entry_timeframe)
    if len(frame) < WINDOW + 2 or not {"high", "low", "close", "atr"} <= set(frame.columns):
        return
    tail = frame.iloc[-(WINDOW + 1) :]
    hi, lo, cl = (tail[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    atr = float(tail["atr"].iloc[-1])
    if not math.isfinite(atr) or atr <= 0:
        return
    n = len(cl)
    for buy in (False, True):
        # the pullback's extreme among the bars before this one (a high for a SELL, a low for a BUY)
        j = int(np.argmin(lo[:-1])) if buy else int(np.argmax(hi[:-1]))
        extreme = lo[j] if buy else hi[j]

        def beyond(k: int, buy: bool = buy) -> bool:
            return bool(cl[k] > hi[k - 1]) if buy else bool(cl[k] < lo[k - 1])

        if j < 1 or not beyond(n - 1) or any(beyond(k) for k in range(j + 1, n - 1)):
            continue
        market = ctx.market
        lv = {}
        for tf in ("H1", "H4"):
            lv.update(_levels(market, tf, extreme, cl[-1], buy))
        dists = [d for d in (lv["H1_pivot_dist"], lv["H4_pivot_dist"]) if d is not None]
        if not dists or min(dists) > MAX_DIST:
            continue
        h4_map, h4_sw = _rel(market, "H4", buy)
        h1_map, h1_sw = _rel(market, "H1", buy)
        rows.append(
            {
                "time": market.decision_time_utc.isoformat(),
                "side": "BUY" if buy else "SELL",
                "kind": f"reject{n - 1 - j}",
                "close": cl[-1],
                "atr": atr,
                "spread_points": float(frame["spread"].iloc[-1]) if "spread" in frame else None,
                "pivot": extreme,
                "pivot_atr": abs(cl[-1] - extreme) / atr,
                "h4_map": h4_map,
                "h4_swings": h4_sw,
                "h1_map": h1_map,
                "h1_swings": h1_sw,
                **lv,
            }
        )


def wrapped(self: setups.TripleScreen, ctx: setups.StrategyContext) -> setups.Signal:
    _scan(ctx)
    return orig(self, ctx)


setups.TripleScreen.evaluate = wrapped  # type: ignore[method-assign]
args = sys.argv[1:]
if args[:2] == ["app.cli", "backtest"]:
    args = args[1:]
code = main(args)
out = Path(args[args.index("--out") + 1])
out.mkdir(parents=True, exist_ok=True)
with open(out / "triggers.csv", "w", newline="", encoding="utf-8") as f:
    if rows:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
print(f"triggers: {len(rows)} -> {out / 'triggers.csv'}")
sys.exit(code)
