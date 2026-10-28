"""Every TS trigger with its context, for the rule study (ts_study.py). Runs one backtest through the real CLI
with setup_triple_screen's evaluate wrapped; the run's config switches the setup's gates off (every
structure.bos_choch close on the entry timeframe is a row). Writes <out>/triggers.csv.

usage: CONFIG_FILE=data/research/config_ts_all_m15.yaml ... python ts_dataset.py app.cli backtest ... --out <dir>
"""

import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.cli.__main__ import main  # noqa: E402
from app.evidence.framework import Direction  # noqa: E402
from app.strategy import setups  # noqa: E402

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


def wrapped(self: setups.TripleScreen, ctx: setups.StrategyContext) -> setups.Signal:
    sig = orig(self, ctx)
    snap = ctx.evidence.get(ctx.market.entry_timeframe)
    trig = [
        a
        for a in (snap.items if snap else ())
        if a.evidence.detector_id == "structure.bos_choch" and a.age_bars == 0
    ]
    if len({a.evidence.direction for a in trig}) != 1 or trig[0].evidence.invalidation is None:
        return sig
    ev = trig[0].evidence
    buy = ev.direction is Direction.BULL
    frame = ctx.frame(ctx.market.entry_timeframe)
    last = frame.iloc[-1]
    close, atr = float(last["close"]), float(last["atr"])
    if not (math.isfinite(close) and math.isfinite(atr)) or atr <= 0:
        return sig
    market = ctx.market
    h4_map, h4_sw = _rel(market, "H4", buy)
    h1_map, h1_sw = _rel(market, "H1", buy)
    row: dict[str, object] = {
        "time": market.decision_time_utc.isoformat(),
        "side": "BUY" if buy else "SELL",
        "kind": setups.variant(ev),
        "close": close,
        "atr": atr,
        "spread_points": float(last["spread"]) if "spread" in last else None,
        "pivot": ev.invalidation,
        "pivot_atr": abs(close - ev.invalidation) / atr,
        "h4_map": h4_map,
        "h4_swings": h4_sw,
        "h1_map": h1_map,
        "h1_swings": h1_sw,
    }
    for tf in ("H1", "H4"):
        row.update(_levels(market, tf, ev.invalidation, close, buy))
    rows.append(row)
    return sig


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
