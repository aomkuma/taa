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
B2, ORCH = ROOT / "app/strategy/plan1_b2.py", ROOT / "app/engine/orchestrator.py"
TESTS = ["tests/unit/test_plan1.py", "tests/backtest/test_engine_ticks.py", "tests/unit/test_lanes_config.py",
         "tests/unit/test_decision_engine.py", "tests/unit/test_plan1_b2.py",
         "tests/integration/test_engine_release_straddle.py"]

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
    # --- checkpoint B: Asia B2 (app/strategy/plan1_b2.py) and the entries handed over from storage
    ("B2 ZigZag: an equal high does not extend the peak", B2, "            if h[i] >= h[ext]:", "            if h[i] > h[ext]:"),
    ("B2 ZigZag: a swing of 2.5 ATR, not 2", B2, "ZZ_K = 2.0", "ZZ_K = 2.5"),
    ("B2 structure: the provisional trough is the highest low", B2,
     "j = last_b + 1 + int(np.argmin(lo[last_b + 1 : d + 1]))", "j = last_b + 1 + int(np.argmax(lo[last_b + 1 : d + 1]))"),
    ("B2 first close above: a close at the trigger refuses it", B2, "np.all(c[a:d] <= line[:-1])", "np.all(c[a:d] < line[:-1])"),
    ("B2 W: the extreme is the higher low", B2, "extreme=min(t2[1], t3[1]),", "extreme=max(t2[1], t3[1]),"),
    ("B2 sweep-turn: any higher low", B2, "t3[1] > t2[1] + eq:", "t3[1] > t2[1]:"),
    ("B2 H&S: no head depth", B2, "t2[1] < min(t1[1], t3[1]) - HEAD_ATR * atr", "t2[1] < min(t1[1], t3[1]) + 99 * atr"),
    ("B2 W: 60 bars allowed", B2, 'SPAN = {"ihs": 60, "w": 40, "st": 40}', 'SPAN = {"ihs": 60, "w": 60, "st": 40}'),
    ("B2 base: starts a bar late", B2, "            start=d - n,", "            start=d - n + 1,"),
    ("B2 stop: 0.25 ATR past the extreme", B2, "STOP_ATR = 0.2", "STOP_ATR = 0.25"),
    ("B2 no height cap", B2, 'out = [p for p in out if p["height"] <= HEIGHT_ATR * atr[d]]', 'out = [p for p in out if p["height"] >= 0]'),
    ("B2 confirmation: touching the extreme is allowed", B2, "        if lo[k] <= extreme:", "        if lo[k] < extreme:"),
    ("B2 at_level: a sweep without the close back", B2, "elif 0 < past <= sweep and s * (close - (lv - s * z)) > 0:",
     "elif 0 < past <= sweep:"),
    ("B2 at_level: the sweep-turn without its own checks", B2,
     'if p["family"] == "st" and (how != "swept" or s * (p["higher_low"] - (lv - s * z)) < 0):', 'if False:'),
    ("B2 next level: inside the zone counts", B2, "(side * (levels - entry) > z)", "(side * (levels - entry) > 0)"),
    ("B2 levels: a level exactly one tolerance away kept", B2, "if all(abs(cnd[0] - k[0]) > TOL_ATR * a for k in kept):",
     "if all(abs(cnd[0] - k[0]) >= TOL_ATR * a for k in kept):"),
    ("B2 levels: the oldest top, not the latest", B2, 'cand.append((float(sp[tops][int(np.argmax(si[tops]))]), "last top"))',
     'cand.append((float(sp[tops][int(np.argmin(si[tops]))]), "last top"))'),
    ("B2 levels: swings before they are known", B2, "sel = (y.s_known <= t_ns) & (y.s_i > bi - win)", "sel = y.s_i > bi - win"),
    ("B2 level inputs: the running hour counted", B2, "    h1 = h1[end <= tn]", "    h1 = h1[end <= tn + 60 * NS_MIN]"),
    ("B2 TF bars: the running bar counted", B2, "    keep = avail <= pd.Timestamp(t).as_unit(\"ns\").value",
     "    keep = avail <= pd.Timestamp(t).as_unit(\"ns\").value + NS_MIN"),
    ("B2 window: 09:00 Thai included", B2, "return s.hour * 60 + s.minute <= m < e.hour * 60 + e.minute",
     "return s.hour * 60 + s.minute <= m <= e.hour * 60 + e.minute"),
    ("B2 target: any level beyond the entry", B2, "q.side * (q.next_level - price) > risk", "q.side * (q.next_level - price) > 0"),
    ("B2 week 6: a flip allowed, the same side refused", B2, "same = (first.side is Side.BUY) == (side > 0)",
     "same = (first.side is Side.BUY) != (side > 0)"),
    ("B2 exit: a close AT the swing low exits", B2, "(close < swing if buy else close > swing)", "(close <= swing if buy else close >= swing)"),
    ("B2 exit: the time stop one bar late", B2, "if at.value >= t_entry + p.hold_bars * step:", "if at.value > t_entry + p.hold_bars * step:"),
    ("B2 exit: bars before the entry read", B2, "        if f.bars.t_open[bk] < t_entry:\n            return None\n", ""),
    ("B2 M5: its exits counted in M1 bars", B2, "        step = self.minutes * NS_MIN\n", "        step = NS_MIN\n"),
    ("H4 from M1: on the UTC clock, not the server day", PLAN1, "local = opens.tz_convert(ATHENS).tz_localize(None).floor(\"4h\")",
     "local = opens.tz_convert(\"UTC\").tz_localize(None).floor(\"4h\")"),
    ("B2 no target: the cap in USD (150), not in R", B2, "price + q.side * p.target_cap_r * risk", "price + q.side * 150.0"),
    ("regime: 60.00 refused (> instead of >=)", PLAN1, "ok = math.isfinite(atr) and atr >= min_usd", "ok = math.isfinite(atr) and atr > min_usd"),
    ("regime: the forming day read", PLAN1, 'tz_convert("UTC") + pd.Timedelta(days=1)', 'tz_convert("UTC") + pd.Timedelta(days=0)'),
    ("regime: too few days trade (fail open)", PLAN1, "    ok = math.isfinite(atr) and atr >= min_usd", "    ok = not math.isfinite(atr) or atr >= min_usd"),
    ("regime: the ORB ignores the switch", PLAN1, "        if not (floor_ok and pool_ok and conds[2].passed):", "        if not (floor_ok and pool_ok):"),
    ("regime: the straddle ignores the switch", PLAN1, "        return conds, floor_ok and conds[2].passed", "        return conds, floor_ok"),
    ("regime: B2 ignores the switch", B2, "        return conds, floor_ok and side_ok and conds[2].passed", "        return conds, floor_ok and side_ok"),
    ("backtest: a flat-lane skip ignores open positions", ENGINE, "and not self._lane_busy(symbol, lane):", ":"),
    ("ORB: the window's last bar not wanted", PLAN1, "return first <= t <= last and t.weekday() <= 4", "return first <= t < last and t.weekday() <= 4"),
    ("B2: wants every minute (M5 too)", B2, "and not t.value % (self.minutes * NS_MIN)", "and True"),
    # the measurer's four (2026-10-22 02:45 Thai), missed at first
    ("B2 a close AT the trigger line breaks", B2, "return bool(c[d] > line[-1] and", "return bool(c[d] >= line[-1] and"),
    ("B2 levels: two touches on one side a flip zone", B2, "if touches >= 3 or (tops and lows):", "if touches >= 2 or (tops and lows):"),
    ("B2 base: a close AT the high breaks", B2, "side = 1 if c[d] > hi else -1 if c[d] < low else 0", "side = 1 if c[d] >= hi else -1 if c[d] <= low else 0"),
    ("B2 at_level: the farthest level wins", B2, 'if best is None or dist < best["dist"]:', 'if best is None or dist > best["dist"]:'),
    ("store: rejected decisions read as entries", DECISION,
     "                    DecisionRecordRow.decision == Decision.ACCEPT.value,\n                    DecisionRecordRow.profile == Profile.EXECUTION.value,\n                    DecisionRecordRow.created_at >= since,",
     "                    DecisionRecordRow.profile == Profile.EXECUTION.value,\n                    DecisionRecordRow.created_at >= since,"),
    ("backtest: accepted entries not kept", ENGINE, "            self._accepted.append((symbol, PastEntry(t, selected.side, selected.strategy)))", "            pass"),
    ("engine: entries from the last hour only", ORCH, "ENTRY_LOOKBACK = timedelta(days=1)", "ENTRY_LOOKBACK = timedelta(hours=1)"),
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
