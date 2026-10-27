"""Crash-safe mutation checks for DEV_SPEC_3.

Run at the repository root with ``.venv\\Scripts\\python research\\2026-10-26-three-bots\\plant_bugs_3.py``.
Each planted edit is restored byte-for-byte; backups from an interrupted run are restored on startup.
"""

from __future__ import annotations

import subprocess  # nosec B404 - invokes this repository's tests with fixed arguments
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BACKUP = HERE / ".plant_bugs_3_backup"


@dataclass(frozen=True)
class Bug:
    name: str
    path: str
    old: bytes
    new: bytes
    test: str


BUGS = (
    Bug(
        "classify a rising close above its mean as mixed",
        "app/strategy/edge_side.py",
        b"current_close > current_mean and current_mean > previous_mean",
        b"current_close > current_mean and current_mean < previous_mean",
        "test_strategy_edge_side.py::test_rising_daily_mean_with_close_above_it_is_buy",
    ),
    Bug(
        "classify a falling close below its mean as mixed",
        "app/strategy/edge_side.py",
        b"current_close < current_mean and current_mean < previous_mean",
        b"current_close < current_mean and current_mean > previous_mean",
        "test_strategy_edge_side.py::test_falling_daily_mean_with_close_below_it_is_sell",
    ),
    Bug(
        "ignore the mean slope when close is above it",
        "app/strategy/edge_side.py",
        b"current_close > current_mean and current_mean > previous_mean",
        b"current_close > current_mean",
        "test_strategy_edge_side.py::test_close_above_a_falling_mean_is_mixed",
    ),
    Bug(
        "ignore the mean slope when close is below it",
        "app/strategy/edge_side.py",
        b"current_close < current_mean and current_mean < previous_mean",
        b"current_close < current_mean",
        "test_strategy_edge_side.py::test_close_below_a_rising_mean_is_mixed",
    ),
    Bug(
        "guess a BUY with exactly one 50-day mean sample",
        "app/strategy/edge_side.py",
        b"if len(closed) < 51:\n        return None",
        b"if len(closed) < 51:\n        return Side.BUY",
        "test_strategy_edge_side.py::test_exactly_fifty_closed_daily_bars_do_not_guess_the_mean_slope",
    ),
    Bug(
        "allow 49 daily bars to pass the history guard",
        "app/strategy/edge_side.py",
        b"if len(closed) < 51:\n        return None",
        b"if len(closed) < 50:\n        return Side.BUY",
        "test_strategy_edge_side.py::test_forty_nine_closed_daily_bars_return_no_side",
    ),
    Bug(
        "include a forming D1 bar in the regime",
        "app/strategy/edge_side.py",
        b"<= pd.Timestamp(at)]",
        b"<= pd.Timestamp(at) + pd.Timedelta(days=1)]",
        "test_strategy_edge_side.py::test_unclosed_daily_bar_does_not_change_the_edge_side",
    ),
    Bug(
        "permit D1 as the entry timeframe",
        "app/strategy/edge_side.py",
        b"if entry.seconds >= Timeframe.D1.seconds:",
        b"if entry.seconds > Timeframe.D1.seconds:",
        "test_strategy_edge_side.py::test_entry_at_or_above_daily_raises_value_error",
    ),
    Bug(
        "accept fewer than 1,200 H1 bars",
        "app/strategy/edge_side.py",
        b"len(h1) < 1200",
        b"len(h1) < 1199",
        "test_strategy_edge_side.py::test_short_h1_history_returns_no_side",
    ),
    Bug(
        "invert agreement for boolean true readings",
        "app/strategy/weighing.py",
        b'agrees = value is (item.wants == "true")',
        b'agrees = value is not (item.wants == "true")',
        "test_strategy_weighing.py::test_all_readings_agree",
    ),
    Bug(
        "award full weight to disagreeing booleans",
        "app/strategy/weighing.py",
        b"contribution = item.weight if agrees else 0.0",
        b"contribution = 0.0 if agrees else item.weight",
        "test_strategy_weighing.py::test_all_readings_disagree",
    ),
    Bug(
        "use the raw numeric value instead of its contribution",
        "app/strategy/weighing.py",
        b'fraction = numeric if item.wants == "high" else 1.0 - numeric',
        b'fraction = (1.0 - numeric) if item.wants == "high" else 1.0 - numeric',
        "test_strategy_weighing.py::test_mixed_readings_use_weighted_contributions",
    ),
    Bug(
        "count a missing weight in the denominator",
        "app/strategy/weighing.py",
        b"if value is None:\n            missing.append(item.name)\n            continue",
        (
            b"if value is None:\n            missing.append(item.name)\n"
            b"            denominator += item.weight\n            continue"
        ),
        "test_strategy_weighing.py::test_missing_reading_is_removed_from_the_denominator",
    ),
    Bug(
        "score wants-low as wants-high",
        "app/strategy/weighing.py",
        b'fraction = numeric if item.wants == "high" else 1.0 - numeric',
        b'fraction = numeric if item.wants == "high" else numeric',
        "test_strategy_weighing.py::test_low_numeric_reading_scores_the_complement",
    ),
    Bug(
        "give an empty scale a positive score",
        "app/strategy/weighing.py",
        b"total = numerator / denominator if denominator > 0 else 0.0",
        b"total = numerator / denominator if denominator > 0 else 1.0",
        "test_strategy_weighing.py::test_empty_scale_scores_zero_and_has_no_readings",
    ),
    Bug(
        "let zero total weight pass a zero threshold",
        "app/strategy/weighing.py",
        b"meets = denominator > 0 and total >= scale.threshold",
        b"meets = denominator >= 0 and total >= scale.threshold",
        "test_strategy_weighing.py::test_zero_weight_is_readable_but_cannot_create_a_score",
    ),
    Bug(
        "make the threshold comparison strict",
        "app/strategy/weighing.py",
        b"total >= scale.threshold",
        b"total > scale.threshold",
        "test_strategy_weighing.py::test_threshold_is_met_at_equality",
    ),
    Bug(
        "treat None as a numeric reading",
        "app/strategy/weighing.py",
        b"if value is None:",
        b"if False and value is None:",
        "test_strategy_weighing.py::test_none_is_reported_as_missing",
    ),
    Bug(
        "enable trend edge filtering by default",
        "app/strategy/trend_box.py",
        b"require_edge_side: bool = False",
        b"require_edge_side: bool = True",
        "test_strategy_trend_box.py::test_edge_side_parameters_default_off",
    ),
    Bug(
        "skip the trend bot's direction check",
        "app/strategy/trend_box.py",
        b"if side is not expected:",
        b"if side is expected:",
        "test_strategy_trend_box.py::test_edge_side_blocks_down_bot_unless_daily_edge_is_sell",
    ),
    Bug(
        "allow an unknown edge side through the trend bot",
        "app/strategy/trend_box.py",
        b"if side is not expected:",
        b"if side is not expected and side is not None:",
        "test_strategy_trend_box.py::test_edge_side_none_blocks_before_trend_data_is_read",
    ),
    Bug(
        "leave trend warmup short when edge filtering is enabled",
        "app/strategy/trend_box.py",
        b"self.params.require_big_tf or self.params.require_edge_side",
        b"self.params.require_big_tf",
        "test_strategy_trend_box.py::test_edge_side_warmup_is_1200_only_when_enabled",
    ),
    Bug(
        "enable range edge filtering by default",
        "app/strategy/range_break.py",
        b"require_edge_side: bool = False",
        b"require_edge_side: bool = True",
        "test_strategy_trend_box.py::test_edge_side_parameters_default_off",
    ),
    Bug(
        "block a range break that matches the edge",
        "app/strategy/range_break.py",
        b"if edge is not side:",
        b"if edge is side:",
        "test_strategy_range_break.py::test_edge_side_allows_a_range_break_that_matches_the_daily_edge",
    ),
    Bug(
        "allow a range break against the edge",
        "app/strategy/range_break.py",
        b"if edge is not side:",
        b"if edge is not Side.SELL:",
        "test_strategy_range_break.py::test_edge_side_blocks_a_range_break_against_the_daily_edge",
    ),
    Bug(
        "make the up trend bot expect the wrong edge side",
        "app/strategy/trend_box.py",
        b'expected = Side.SELL if self.direction == "DOWN" else Side.BUY',
        b"expected = Side.SELL",
        "test_strategy_trend_box.py::test_edge_side_blocks_up_bot_unless_daily_edge_is_buy",
    ),
    Bug(
        "let a range break through when the edge side is missing",
        "app/strategy/range_break.py",
        b"if edge is not side:",
        b"if edge is Side.BUY:",
        "test_strategy_range_break.py::test_no_daily_edge_blocks_a_range_break",
    ),
)


def restore_any() -> None:
    """Recover any source files parked before an interrupted mutation run."""
    if not BACKUP.exists():
        return
    for parked in sorted(BACKUP.glob("*.bak")):
        relative = parked.stem.replace("__", "/")
        (ROOT / relative).write_bytes(parked.read_bytes())
        parked.unlink()
        sys.stdout.write(f"restored {relative} from an interrupted run\n")
    if not any(BACKUP.iterdir()):
        BACKUP.rmdir()


def run_test(test: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned test selectors
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"tests/unit/{test}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    restore_any()
    test_paths = sorted({bug.test.split("::", 1)[0] for bug in BUGS})
    baseline = subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned test paths
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *[f"tests/unit/{p}" for p in test_paths],
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if baseline.returncode:
        raise RuntimeError(f"focused baseline tests failed:\n{baseline.stdout}\n{baseline.stderr}")

    BACKUP.mkdir(exist_ok=True)
    clean_files: dict[str, bytes] = {}
    results: list[str] = []
    try:
        for bug in BUGS:
            target = ROOT / bug.path
            clean = clean_files.setdefault(bug.path, target.read_bytes())
            parked = BACKUP / (bug.path.replace("/", "__") + ".bak")
            if not parked.exists():
                parked.write_bytes(clean)
            current = target.read_bytes()
            if current.count(bug.old) != 1 or bug.old == bug.new:
                raise RuntimeError(f"mutation anchor is not unique for: {bug.name}")
            try:
                target.write_bytes(current.replace(bug.old, bug.new, 1))
                outcome = run_test(bug.test)
                caught = outcome.returncode != 0
                results.append(f"{'CAUGHT' if caught else 'MISSED'} | {bug.test} | {bug.name}")
                if not caught:
                    results.append(outcome.stdout.strip() or "mutation test exited successfully")
            finally:
                target.write_bytes(clean)

        caught_count = sum(row.startswith("CAUGHT") for row in results)
        output = "\n".join([*results, f"{caught_count}/{len(BUGS)} caught"]) + "\n"
        (HERE / "plant_bugs_3_output.txt").write_text(output, encoding="utf-8")
        sys.stdout.write(output)
        return 0 if caught_count == len(BUGS) else 1
    finally:
        for relative, original in clean_files.items():
            target = ROOT / relative
            target.write_bytes(original)
            parked = BACKUP / (relative.replace("/", "__") + ".bak")
            if parked.exists() and parked.read_bytes() != original:
                raise RuntimeError(f"backup mismatch while restoring {relative}")
            parked.unlink(missing_ok=True)
        if BACKUP.exists() and not any(BACKUP.iterdir()):
            BACKUP.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
