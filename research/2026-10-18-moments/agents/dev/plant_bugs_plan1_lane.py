"""Planted bugs for the plan1 lane in the app (app/strategy/plan1.py, the backtest's quote path in
app/backtest/engine.py, the lane spread cap in app/config.py / app/engine/decision_engine.py): each a small edit
made in place, the lane's tests run (TESTS below), the file restored in a `finally`; every bug must make a test
fail (CAUGHT). Bugs 9-16 are the measurer's (2026-10-21, 16:40 Thai), missed at first, now with their own tests.

Run it with nothing else importing app/ at the same time (it edits the source for a few seconds per bug).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_plan1_lane.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN1, ENGINE = ROOT / "app/strategy/plan1.py", ROOT / "app/backtest/engine.py"
CONFIG, DECISION = ROOT / "app/config.py", ROOT / "app/engine/decision_engine.py"
TESTS = ["tests/unit/test_plan1.py", "tests/backtest/test_engine_ticks.py", "tests/unit/test_lanes_config.py",
         "tests/unit/test_decision_engine.py"]

BUGS: list[tuple[str, Path, str, str]] = [
    ("ORB: a close AT the range high counts as a break", PLAN1, "side = 1 if c[k] > rh else", "side = 1 if c[k] >= rh else"),
    ("ORB: the stop on the break side", PLAN1, "stop = d.rl if buy else d.rh", "stop = d.rh if buy else d.rl"),
    ("ORB: the target fixed at 2 R", PLAN1, "take_profit=price + d.side * p.target_r * risk", "take_profit=price + d.side * 2.0 * risk"),
    ("ORB: a 5-minute late first bar refused", PLAN1, "ns[i0] - t0n > p.late_open_minutes * NS_MIN", "ns[i0] - t0n >= p.late_open_minutes * NS_MIN"),
    ("ORB: a range exactly 1.5 H refused", PLAN1, "rh - rl > p.wide_atr * atr", "rh - rl >= p.wide_atr * atr"),
    ("ORB: the entry window one minute longer", PLAN1, "(p.range_minutes + p.entry_minutes) * NS_MIN", "(p.range_minutes + p.entry_minutes + 1) * NS_MIN"),
    ("H1 ATR: the forming hour included", PLAN1, "hours + pd.Timedelta(hours=1) <= t", "hours <= t"),
    ("H1 ATR: high - low, no previous close", PLAN1, "tr = np.maximum(hh[-ATR_BARS:], pc) - np.minimum(ll[-ATR_BARS:], pc)",
     "tr = hh[-ATR_BARS:] - ll[-ATR_BARS:]"),
    ("pools: 'yesterday' includes today", PLAN1, "before = np.asarray((srv_day < today) &", "before = np.asarray((srv_day <= today) &"),
    ("pools: yesterday only one day back (Monday misses Friday)", PLAN1, "(srv_day >= today - pd.Timedelta(days=3))",
     "(srv_day >= today - pd.Timedelta(days=1))"),
    ("pools: the Asia range to 08:00 Thai", PLAN1, "(thai < d0 + pd.Timedelta(hours=7))", "(thai < d0 + pd.Timedelta(hours=8))"),
    ("pools: a swing high needs only its left bin", PLAN1, "qh[k] > qh[k - 1] and qh[k] > qh[k + 1]", "qh[k] > qh[k - 1]"),
    ("pools: a swing low needs only its left bin", PLAN1, "ql[k] < ql[k - 1] and ql[k] < ql[k + 1]", "ql[k] < ql[k - 1]"),
    ("pool break: the bar 15 minutes back left out", PLAN1, "(opens >= t - pd.Timedelta(minutes=minutes))",
     "(opens > t - pd.Timedelta(minutes=minutes))"),
    ("pool break: a buy pool at the first open counts", PLAN1, "if first < v < top]", "if first <= v < top]"),
    ("pool break: a sell pool at the first open counts", PLAN1, "if first > v > bottom]", "if first >= v > bottom]"),
    ("ORB: Saturday allowed", PLAN1, "or at.weekday() > 4:", "or at.weekday() > 5:"),
    ("pools: the Asia range on the UTC day", PLAN1, "thai = idx.tz_convert(BANGKOK)", "thai = idx.tz_convert(\"UTC\")"),
    ("pools: the M15 fractal read from the forming bin", PLAN1, "for k in range(len(q) - 2, 0, -1):", "for k in range(len(q) - 1, 0, -1):"),
    ("pool break: a 16-minute window", PLAN1, "keep = np.asarray((opens >= t - pd.Timedelta(minutes=minutes))",
     "keep = np.asarray((opens >= t - pd.Timedelta(minutes=minutes + 1))"),
    ("pool break: a sell measured on the high", PLAN1, "return [k for k, v in found.items() if first > v > bottom]",
     "return [k for k, v in found.items() if first > v > top]"),
    ("H4 change: 5 bars back, not 6", PLAN1, "then = float(atr[-1]), float(atr[-1 - bars])", "then = float(atr[-1]), float(atr[-bars])"),
    ("H4 change: the forming H4 bar read", PLAN1, "done = h4[h4.index <= t]", "done = h4"),
    ("H4: the journal's +0.5 % margin dropped", PLAN1, "or 100.0 * change <= max_pct", "or 100.0 * change <= 0.0"),
    ("H4: at the margin counts as expanding", PLAN1, "or 100.0 * change <= max_pct", "or 100.0 * change < max_pct"),
    ("H4: an unknown ATR counts as expanding (fail open)", PLAN1, "return not math.isfinite(change) or 100.0 * change <= max_pct",
     "return math.isfinite(change) and 100.0 * change <= max_pct"),
    ("straddle: S2's unit (price / 4000) instead of USD", PLAN1, "    def unit(self, bid: float) -> float:\n        return 1.0\n\n    def upcoming",
     "    def unit(self, bid: float) -> float:\n        return bid / 4000.0\n\n    def upcoming"),
    ("straddle: New York without summer time", PLAN1, "local_instant(day, p.ny_open, p.ny_zone)",
     "local_instant(day, p.ny_open, \"Etc/GMT+5\")"),
    ("straddle: out 30 min after the fill minute, not 08:30", PLAN1, "start = pd.Timestamp(r.at) if r is not None else",
     "start = entry.floor(\"min\") if r is not None else"),
    ("straddle: only on calendar days (S2's planner)", PLAN1, "return DailyStraddle(self.params, ())", "return ReleaseStraddle(self.params, self._calendar)"),
    ("engine: positions not stepped on ticks", ENGINE, "held = any(p.symbol == symbol for p in self.broker.positions.values()) or",
     "held = False and any(p.symbol == symbol for p in self.broker.positions.values()) or"),
    ("engine: the clock left at the bar close for tick entries", ENGINE, "            self.clock.set(at)\n", "            pass\n"),
    ("journal: no spread record", PLAN1,
     '            Condition("spread", True, 1.0, spread_detail(market.bid, market.ask, ctx)),\n', ""),
    ("lane spread cap ignored by the decision engine", DECISION, "limit = self.config.spread_limit_for(symbol, req.signal.strategy)",
     "limit = self.config.spread_limit(symbol)"),
    ("lane spread cap lost in the lane's own view", CONFIG,
     "            risk = risk.model_copy(update={\"max_spread_points\": lane.max_spread_points})\n", ""),
    ("engine: no journal record", ENGINE, "        result.journal[selected.signal_id] = {", "        _unused = {"),
    ("engine: a decision reads the bar's first tick", ENGINE, "bid, ask = float(bids[-1]), float(asks[-1])",
     "bid, ask = float(bids[0]), float(asks[0])"),
    ("engine: decisions keep the bar quote despite ticks", ENGINE,
     "        if self.quotes is not None:\n            t_ns, bids, asks = self.quotes.between(symbol, bar.open_time, t)",
     "        if False:\n            t_ns, bids, asks = self.quotes.between(symbol, bar.open_time, t)"),
]


def run_tests() -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS], cwd=ROOT,  # noqa: S603
                       capture_output=True, text=True, check=False)
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-1:] or ["?"]
    return r.returncode == 0, tail[0]


def main() -> None:
    ok, line = run_tests()
    print(f"control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, path, old, new) in enumerate(BUGS, 1):
        src = path.read_text(encoding="utf-8")
        if src.count(old) != 1:
            raise SystemExit(f"bug #{k} {name}: the text to edit is not found exactly once")
        try:
            path.write_text(src.replace(old, new), encoding="utf-8", newline="\n")
            ok, line = run_tests()
        finally:
            path.write_text(src, encoding="utf-8", newline="\n")
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
