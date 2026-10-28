"""Plant deliberate strategy regressions and require the hand-worked tests to catch them.

Run with ``.venv\\Scripts\\python research\\2026-10-26-three-bots\\plant_bugs.py``. The committed output is
``plant_bugs_output.txt``.
"""

from __future__ import annotations

import subprocess  # nosec B404 - invokes this repository's own test runner
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TEST_TREND = "tests/unit/test_strategy_trend_box.py"
TEST_RANGE = "tests/unit/test_strategy_range_break.py"
TREND = "app/strategy/trend_box.py"
RANGE = "app/strategy/range_break.py"
BUGS: list[tuple[str, str, str, str, str]] = [
    (
        "include the repainting ZigZag endpoint",
        TREND,
        "swings, _forming = zigzag(h1.high.to_numpy(float), h1.low.to_numpy(float))",
        "swings, forming = zigzag(h1.high.to_numpy(float), h1.low.to_numpy(float))\n"
        "        swings = [*swings, *([forming] if forming else [])]",
        "test_down_entry_uses_box_before_decision_bar_and_exact_plan",
    ),
    (
        "include the decision bar in the consolidation box",
        TREND,
        "box = m5.iloc[-n - 1 : -1]",
        "box = m5.iloc[-n:]",
        "test_down_entry_uses_box_before_decision_bar_and_exact_plan",
    ),
    (
        "search boxes shortest first",
        TREND,
        "range(24, 5, -1)",
        "range(6, 25)",
        "test_down_entry_uses_box_before_decision_bar_and_exact_plan",
    ),
    (
        "exclude the inclusive lower retrace boundary",
        TREND,
        "not 0.382 <= retr <= 0.786",
        "not 0.383 <= retr <= 0.786",
        "test_retrace_bounds_are_inclusive",
    ),
    (
        "exclude the inclusive upper retrace boundary",
        TREND,
        "not 0.382 <= retr <= 0.786",
        "not 0.382 <= retr < 0.786",
        "test_retrace_bounds_are_inclusive",
    ),
    (
        "let a wick count as a close break",
        TREND,
        "(down and price >= floor)",
        "(down and float(decision.low) >= floor)",
        "test_wick_only_break_and_running_push_hold",
    ),
    (
        "add extra stop buffer",
        TREND,
        "top + self.params.buffer * (top - floor)",
        "top + (self.params.buffer + 0.1) * (top - floor)",
        "test_down_entry_uses_box_before_decision_bar_and_exact_plan",
    ),
    (
        "demand twenty extra dollars of R reward",
        TREND,
        "reward < self.params.min_r * risk",
        "reward < self.params.min_r * risk + 20",
        "test_down_entry_uses_box_before_decision_bar_and_exact_plan",
    ),
    (
        "aim for the start of the leg instead of its end",
        TREND,
        "target = b.price",
        "target = a.price",
        "test_down_entry_uses_box_before_decision_bar_and_exact_plan",
    ),
    (
        "measure sell run from M1 highs",
        TREND,
        "price - float(run_frame.low.min())",
        "price - float(run_frame.high.max())",
        "test_wick_only_break_and_running_push_hold",
    ),
    (
        "reject an exactly 1.2 R run",
        TREND,
        "return run > 1.2 * risk",
        "return run >= 1.2 * risk",
        "test_run_threshold_is_strict_and_uses_the_preceding_sixty_minutes",
    ),
    (
        "exclude the M1 bar exactly sixty minutes old",
        TREND,
        "m1.index >= at - pd.Timedelta(minutes=60)",
        "m1.index > at - pd.Timedelta(minutes=60)",
        "test_run_threshold_is_strict_and_uses_the_preceding_sixty_minutes",
    ),
    (
        "wait until 0.6 R for break-even",
        TREND,
        "ahead >= 0.5 * risk",
        "ahead >= 0.6 * risk",
        "test_up_break_even_waits_for_touch_then_moves_to_entry",
    ),
    (
        "move the stop before testing the old stop",
        TREND,
        "if (high >= stop) if sell else (low <= stop):",
        "if False:",
        "test_original_stop_is_checked_before_same_bar_break_even_touch",
    ),
    (
        "replace a more favorable stop with break-even",
        TREND,
        "if (pos.side is Side.BUY and pos.sl >= pos.entry) "
        "or (pos.side is Side.SELL and pos.sl <= pos.entry):",
        "if pos.sl == pos.entry:",
        "test_break_even_never_replaces_a_better_stop",
    ),
    (
        "flatten at 08:00 Bangkok",
        TREND,
        "return at.time() == time(7)",
        "return at.time() == time(8)",
        "test_daily_flat_is_at_seven_thai",
    ),
    (
        "retain empty H4 bins",
        RANGE,
        ").dropna()",
        ").fillna(0.0)",
        "test_h4_resampling_uses_the_h1_four_hour_boundaries",
    ),
    (
        "allow an H4 stepping trend",
        RANGE,
        'stepped(swings) != "FLAT"',
        'stepped(swings) != "RANGE"',
        "test_break_plan_matches_the_calculated_h4_box",
    ),
    (
        "ignore the previous M5 close at breakout",
        RANGE,
        "if price > hh >= prev:",
        "if price > hh:",
        "test_trigger_needs_the_close_to_leave_the_box",
    ),
    (
        "double the range breakout stop offset",
        RANGE,
        "self.params.buffer * rng * 0.25",
        "self.params.buffer * rng * 0.5",
        "test_break_plan_matches_the_calculated_h4_box",
    ),
    (
        "remove the five dollar target floor",
        RANGE,
        "reward < self.params.min_take_profit",
        "False",
        "test_sell_break_plan_is_the_mirror_and_reward_floor_is_enforced",
    ),
]


def run(test: str, test_name: str) -> bool:
    result = subprocess.run(  # noqa: S603 - fixed repo-owned test command
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"{test}::{test_name}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )  # nosec B603 - fixed arguments run a repository test
    return result.returncode == 0


def main() -> int:
    baseline = subprocess.run(  # noqa: S603 - fixed repo-owned test command
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TEST_TREND, TEST_RANGE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if baseline.returncode:
        raise RuntimeError(f"clean strategy tests failed:\n{baseline.stdout}\n{baseline.stderr}")
    changed: dict[Path, str] = {}
    results: list[str] = []
    try:
        for name, relpath, original, replacement, test_name in BUGS:
            target = ROOT / relpath
            clean = target.read_text(encoding="utf-8")
            if original not in clean:
                raise RuntimeError(f"mutation anchor missing for: {name}")
            changed[target] = clean
            target.write_text(clean.replace(original, replacement, 1), encoding="utf-8")
            caught = not run(TEST_TREND if relpath == TREND else TEST_RANGE, test_name)
            results.append(f"{'CAUGHT' if caught else 'MISSED'} | {name}")
            target.write_text(clean, encoding="utf-8")
            changed.pop(target)
    finally:
        for target, clean in changed.items():
            target.write_text(clean, encoding="utf-8")
    output = "\n".join([f"Planted bugs: {len(BUGS)}", *results]) + "\n"
    destination = HERE / "plant_bugs_output.txt"
    destination.write_text(output, encoding="utf-8")
    sys.stdout.write(output)
    return 1 if any(line.startswith("MISSED") for line in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
