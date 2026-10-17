"""Why does TS trade so little? Runs one backtest of setup_triple_screen through the real CLI with the setup's
evaluate wrapped, and counts, over every bar where its trigger fired (structure.bos_choch), which conditions
failed, alone and in combination, plus the stop distance (entry ATR) and the R:R of the plans. Read-only apart
from the backtest output folder.

usage: CONFIG_FILE=data/research/config_ts_r_m15.yaml ... python ts_funnel.py app.cli backtest --server ... \
       --out <folder>   (the "app.cli backtest" words make the run visible to the run-count checks)
"""

import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.cli.__main__ import main  # noqa: E402
from app.strategy import setups  # noqa: E402

failed_alone: collections.Counter[str] = collections.Counter()
failed_any: collections.Counter[str] = collections.Counter()
combos: collections.Counter[tuple[str, ...]] = collections.Counter()
sl_atr: list[float] = []
rr: list[float] = []
h4_states: collections.Counter[str] = collections.Counter()
pivot_dist: list[float] = []  # the pullback extreme to the nearest H1/H4 level, in that read's ATR
fired = 0
orig = setups.TripleScreen.evaluate


def nearest_level_atr(ctx: setups.StrategyContext) -> float | None:
    snap = ctx.evidence.get(ctx.market.entry_timeframe)
    trig = [
        a
        for a in (snap.items if snap else ())
        if a.evidence.detector_id == "structure.bos_choch" and a.age_bars == 0
    ]
    if not trig or trig[0].evidence.invalidation is None:
        return None
    pivot = trig[0].evidence.invalidation
    dists = [
        abs(lv.price - pivot) / r.atr
        for f in ("H1", "H4")
        if (r := setups._read(ctx.market, f)) is not None and r.atr > 0
        for lv in r.levels
    ]
    return min(dists) if dists else None


def wrapped(self: setups.TripleScreen, ctx: setups.StrategyContext) -> setups.Signal:
    global fired
    sig = orig(self, ctx)
    if not any(c.name == "trigger" and c.passed for c in sig.conditions):
        return sig
    fired += 1
    failed = tuple(c.name for c in sig.conditions if not c.passed)
    combos[failed] += 1
    for name in failed:
        failed_any[name] += 1
    if len(failed) == 1:
        failed_alone[failed[0]] += 1
    if (d := nearest_level_atr(ctx)) is not None:
        pivot_dist.append(d)
    for c in sig.conditions:
        if c.name == "screen_h4":
            h4_states[c.detail.split(" (")[0]] += 1
        if c.name == "sl_within_limit" and (m := re.match(r"SL ([\d.]+) ATR", c.detail)):
            sl_atr.append(float(m.group(1)))
        if c.name == "rr_ok" and (m := re.match(r"RR (-?[\d.]+)", c.detail)):
            rr.append(float(m.group(1)))
    return sig


setups.TripleScreen.evaluate = wrapped  # type: ignore[method-assign]
args = sys.argv[1:]
if args[:2] == ["app.cli", "backtest"]:
    args = args[1:]
code = main(args)


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))] if s else float("nan")


print(f"\ntriggers evaluated: {fired}")
print("condition | failed (any) | the only failure")
for name, n in failed_any.most_common():
    print(f"  {name:22} {n:6d} {failed_alone.get(name, 0):6d}")
print("most common failure sets:")
for combo, n in combos.most_common(12):
    print(f"  {n:6d}  {', '.join(combo) or '(passed)'}")
print(
    f"stop distance (entry ATR): median {pct(sl_atr, 0.5):.2f}  p25 {pct(sl_atr, 0.25):.2f}  "
    f"p75 {pct(sl_atr, 0.75):.2f}  p90 {pct(sl_atr, 0.9):.2f}  (n {len(sl_atr)})"
)
print(f"R:R of the plans: median {pct(rr, 0.5):.2f}  p25 {pct(rr, 0.25):.2f}  p75 {pct(rr, 0.75):.2f}")
print("H4 map relative to the trigger:", dict(h4_states.most_common()))
n = len(pivot_dist)
print(
    "pullback extreme to the nearest H1/H4 level: "
    + "  ".join(
        f"<= {t:g} ATR {sum(d <= t for d in pivot_dist) / n:.0%}" for t in (0.25, 0.5, 0.75, 1.0, 1.5)
    )
    + f"  (n {n})"
    if n
    else "no pivot distances"
)
sys.exit(code)
