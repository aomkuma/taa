"""Planted bugs for the ISSUES 29-33 fixes (owner 2026-10-26: "fix the calculation logic, then test it more
thoroughly"). Each bug is written into the source, the targeted tests run, and the source is restored; every bug
must make a test fail.

    .venv/Scripts/python research/2026-10-24-replay/plant_bugs_29_33.py
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = [
    "tests/unit/test_strategy_liquidity.py",
    "tests/unit/test_strategy_ai_lane.py",
    "tests/unit/test_ai_trader.py",
    "tests/unit/test_ai_replay.py",
    "tests/unit/test_engine_ai_trader.py",
    "tests/unit/test_strategy_confirm.py",
    "tests/unit/test_ai_plan.py",
    "tests/unit/test_strategy_zigzag.py",
]
CF = "app/strategy/confirm.py"
ZZ = "app/strategy/zigzag.py"
LQ, LANE, TR, AT, RP = (
    "app/strategy/liquidity.py",
    "app/strategy/ai_lane.py",
    "app/ai/trader.py",
    "app/engine/ai_trader.py",
    "app/engine/ai_replay.py",
)
BUGS: list[tuple[str, str, str, str]] = [
    ("the edge jump has no distance limit", LQ, "(nxt - edge) * sign <= EDGE_JUMP_ATR * a", "True"),
    ("the edge jump excludes exactly 1 ATR", LQ, "(nxt - edge) * sign <= EDGE_JUMP_ATR * a",
     "(nxt - edge) * sign < EDGE_JUMP_ATR * a"),
    ("the zone has no cap", LQ, "if (far - limit) * sign > 0:", "if False:"),
    ("the cap is 3 ATR", LQ, "limit = edge + sign * ZONE_MAX_ATR * a", "limit = edge + sign * 3 * a"),
    ("the zone end includes the buffer", LQ, "return round(far + sign * BUFFER_ATR * a, 2), round(far, 2)",
     "return round(far + sign * BUFFER_ATR * a, 2), round(far + sign * BUFFER_ATR * a, 2)"),
    ("the forming bar is left out", LQ, "top, bottom = max(top, forming[0]), min(bottom, forming[1])", "pass"),
    ("the forming bar starts a bar late", LQ, "x1.index >= x5.index[-1] + pd.Timedelta(minutes=5)",
     "x1.index >= x5.index[-1] + pd.Timedelta(minutes=10)"),
    ("C6 ignores the level", LANE, "mark = pos.entry if level is None else level", "mark = pos.entry"),
    ("the filled order's level is not kept", LANE, "self._levels[symbol] = order.exit_level",
     "self._levels[symbol] = None"),
    ("a plan fill keeps no level", LANE, "self._levels[symbol] = o.exit_level if o.exit_level is not None else o.entry",
     "self._levels[symbol] = None"),
    ("the plan's stop is not moved out", LANE, "keep.append(dataclasses.replace(o, stop=float(m)))", "keep.append(o)"),
    ("the plan's R floor is not checked", LANE, "reward < p.plan_min_rr * risk", "False"),
    ("the plan's 5-USD floor is not checked", LANE, "reward < p.min_take_profit or ", ""),
    ("a stop before the target still blocks", LANE, "if len(hit_sl) and hit_sl[0] < hit_tp[0]:", "if False:"),
    ("the block starts at the bar's open", LANE, "minutes=1 + p.tp_block_minutes", "minutes=p.tp_block_minutes"),
    ("a blocked side still fills", LANE, 'return "keep"  # the side is blocked after a take-profit (C9)', "pass"),
    ("C4 always moves the stop out", TR, 'if c4_keeps_r(braked, check["code"]):', "if True:"),
    ("C4 R floor strict", TR, "return abs(d.target - d.entry) >= MIN_RISK_REWARD * abs(d.entry - code)",
     "return abs(d.target - d.entry) > MIN_RISK_REWARD * abs(d.entry - code)"),
    ("C4 never moves the stop", TR, 'dumped["stop"] = check["code"]', "pass"),
    ("the hand-over skips the plan recheck", AT, 'strategy.recheck_plan_stops(symbol, rec["map_stops_now"])', "pass"),
    ("the order loses its exit level", AT, 'exit_level=None if d.get("exit_level") is None else float(d["exit_level"]),',
     "exit_level=None,"),
    ("the replay does not note positions", RP, "strategy.note_positions(self.symbol, list(positions), self.lane.m1)",
     "pass"),
    # the signal at the level (owner 2026-10-26)
    ("the first touch fills", LANE, 'self._touched.setdefault(order.key, at)  # armed: the first touch is not the entry',
     'return "fill"'),
    ("a confirmed order chases", LANE, "if worse > p.chase_share * abs(order.stop - order.entry):", "if False:"),
    ("a confirmed fill skips the TP check", LANE, 'return "keep" if short else "fill"', 'return "fill"'),
    ("a wait order may be market", LANE, "near = order.direct and abs(order.entry - price) <= tol",
     "near = abs(order.entry - price) <= tol"),
    ("the replay does not read the signal", RP,
     "strategy.confirm_orders(self.symbol, self.lane.m1, at)  # a touched order waits for its signal", "pass"),
    ("a sweep needs no volume", CF, 'and x["v"][ext] > vmean ', ""),
    ("a sweep needs no close back", CF, "and c[-1] < lv:", ":"),
    ("the M's second push may be higher", CF, "<= hi[k] <= hi[p]", "<= hi[k]"),
    ("the M needs no half-way push", CF, "trough + 0.5 * (hi[p] - trough) <= hi[k]", "trough <= hi[k]"),
    ("the M needs no neckline break", CF, "and after[k + 1] < trough", ""),
    ("a break needs no close through", CF, 'return "break" if bool((c < lv).any()) else None', 'return "break"'),
    ("a plan order may go against D1", "app/ai/plan.py", 'if (sell and d1 == "up") or (not sell and d1 == "down"):',
     "if False:"),
    ("a pin needs no wick", CF, "and hi[i] - max(o[i], c[i]) >= 0.5 * rng", ""),
    ("a pin may close up", CF, "and c[i] < lv and c[i] < o[i] and rng > 0", "and c[i] < lv and rng > 0"),
    ("an engulfing need not cover", CF, "covers = o[i] >= c[i - 1] and c[i] <= o[i - 1]", "covers = True"),
    ("a forming bar counts", CF, "return bars[bars.index + pd.Timedelta(minutes=minutes) <= at]", "return bars"),
    ("candles read on M5", CF, "CANDLE_FRAMES = (15, 30, 60)", "CANDLE_FRAMES = (5, 15, 30, 60)"),
    # MetaTrader 5's ZigZag (owner 2026-10-26)
    ("zigzag: a lower low does not move the point", ZZ, "if low_map[shift] != 0 and low_map[shift] < ll and high_map[shift] == 0:",
     "if False:"),
    ("zigzag: a repeated low is a new candidate", ZZ, "        if val == last_low:", "        if False:"),
    ("zigzag: the forming point counts as confirmed", ZZ, "return points[:-1], points[-1]", "return points, points[-1]"),
    ("zigzag: the window is one bar short", ZZ, "val = float(lo[shift - depth + 1 : shift + 1].min())",
     "val = float(lo[shift - depth + 2 : shift + 1].min())"),
    ("the structure read on M1", CF, "STRUCTURE_FRAME = 5", "STRUCTURE_FRAME = 1"),
    ("a buy is not mirrored", CF, '"hi": since.high.to_numpy(float) if sell else -since.low.to_numpy(float),',
     '"hi": since.high.to_numpy(float),'),
]  # fmt: skip


def run() -> bool:
    """True when the targeted tests pass."""
    out = subprocess.run(  # nosec B603 - fixed argv
        [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return out.returncode == 0


def main() -> int:
    assert run(), "the tests must pass on the clean source first"
    missed = 0
    for name, path, old, new in BUGS:
        f = ROOT / path
        src = f.read_text(encoding="utf-8")
        assert src.count(old) == 1, f"{name}: the text to change is not unique in {path}"
        try:
            f.write_text(src.replace(old, new), encoding="utf-8")
            caught = not run()
        finally:
            f.write_text(src, encoding="utf-8")
        missed += not caught
        print(f"{'caught' if caught else 'MISSED'}  {name}")
    print(f"{len(BUGS) - missed}/{len(BUGS)} caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
