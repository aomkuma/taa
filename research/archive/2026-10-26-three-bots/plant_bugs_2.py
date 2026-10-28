"""Crash-safe mutation check for the two opt-in trend box levers.

Run from the repository root with ``.venv\\Scripts\\python research\\2026-10-26-three-bots\\plant_bugs_2.py``.
Each mutation is restored byte-for-byte, including leftovers from an interrupted prior run.
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BACKUP = HERE / ".plant_bugs_2_backup"
TREND = "app/strategy/trend_box.py"
TEST = "tests/unit/test_strategy_trend_box.py"

BUGS: list[tuple[str, bytes, bytes, str]] = [
    (
        "enable the big time frame lever by default",
        b"require_big_tf: bool = False",
        b"require_big_tf: bool = True",
        "test_big_tf_off_keeps_an_opposing_h4_out_of_the_decision",
    ),
    (
        "let an up H4 trend pass a down box",
        b'(down and h4_direction == "UP")',
        b'(down and h4_direction == "FLAT")',
        "test_big_tf_down_blocks_up_h4_but_flat_and_down_keep_the_entry",
    ),
    (
        "let a down H4 trend pass an up box",
        b'(not down and h4_direction == "DOWN")',
        b'(not down and h4_direction == "UP")',
        "test_big_tf_up_blocks_down_h4",
    ),
    (
        "leave the H1 warmup too short to build 300 H4 bars",
        b"return 1200 if self.params.require_big_tf else 400",
        b"return 400",
        "test_big_tf_down_blocks_up_h4_but_flat_and_down_keep_the_entry",
    ),
    (
        "accept only 299 closed H4 bars",
        b"if len(h4) < 300:",
        b"if len(h4) < 299:",
        "test_big_tf_requires_300_closed_h4_bars",
    ),
    (
        "allow a still-forming H4 bar into ZigZag",
        b"(h4.index + pd.Timedelta(hours=4)) <= at",
        b"(h4.index + pd.Timedelta(hours=4)) <= at + pd.Timedelta(hours=4)",
        "test_big_tf_does_not_send_a_forming_h4_bar_to_zigzag",
    ),
    (
        "widen a stop whose distance equals the ATR floor",
        b"if abs(stop - price) < stop_floor:",
        b"if abs(stop - price) <= stop_floor:",
        "test_min_stop_atr_does_not_widen_a_stop_exactly_at_the_floor",
    ),
    (
        "turn on the ATR floor by default",
        b"min_stop_atr: float = Field(default=0.0, ge=0)",
        b"min_stop_atr: float = Field(default=1.0, ge=0)",
        "test_min_stop_atr_off_leaves_a_tiny_box_stop_unchanged",
    ),
    (
        "move a BUY stop away from the entry in the wrong direction",
        b"stop = price + stop_floor if down else price - stop_floor",
        b"stop = price + stop_floor if down else price + stop_floor",
        "test_min_stop_atr_mirrors_the_buy_stop_direction",
    ),
    (
        "halve the configured ATR stop floor",
        b"stop_floor = self.params.min_stop_atr * atr_value",
        b"stop_floor = 0.5 * self.params.min_stop_atr * atr_value",
        "test_min_stop_atr_widens_only_narrow_stops_and_reports_floor",
    ),
    (
        "omit the stop floor condition from widened entries",
        b"if stop_widened:",
        b"if False:",
        "test_min_stop_atr_widens_only_narrow_stops_and_reports_floor",
    ),
    (
        "run the reward-risk check against box width instead of widened risk",
        b"reward < self.params.min_r * risk",
        b"reward < self.params.min_r * abs(top - floor)",
        "test_min_stop_atr_widening_is_included_in_the_min_r_gate",
    ),
]


def pytest(case: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and pytest arguments; case is a constant in this file
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"{TEST}::{case}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def restore_any() -> None:
    if not BACKUP.exists():
        return
    for parked in sorted(BACKUP.glob("*.bak")):
        relpath = parked.with_suffix("").name.replace("__", "/")
        (ROOT / relpath).write_bytes(parked.read_bytes())
        parked.unlink()
        sys.stdout.write(f"restored {relpath} from an interrupted run\n")
    if BACKUP.exists() and not any(BACKUP.iterdir()):
        BACKUP.rmdir()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    restore_any()
    baseline = subprocess.run(  # noqa: S603 - fixed interpreter, pytest module and repository-owned test path
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TEST],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if baseline.returncode:
        raise RuntimeError(
            f"trend box tests failed before mutation checks:\n{baseline.stdout}\n{baseline.stderr}"
        )

    BACKUP.mkdir(exist_ok=True)
    target = ROOT / TREND
    results: list[str] = []
    try:
        clean = target.read_bytes()
        parked = BACKUP / (TREND.replace("/", "__") + ".bak")
        parked.write_bytes(clean)
        for name, old, new, case in BUGS:
            current = target.read_bytes()
            if current.count(old) != 1 or old == new:
                raise RuntimeError(f"mutation anchor is not unique for: {name}")
            try:
                target.write_bytes(current.replace(old, new, 1))
                outcome = pytest(case)
                caught = outcome.returncode != 0
                results.append(f"{'CAUGHT' if caught else 'MISSED'} | {case} | {name}")
            finally:
                target.write_bytes(clean)
        count = sum(result.startswith("CAUGHT") for result in results)
        output = "\n".join([*results, f"{count}/{len(BUGS)} caught"]) + "\n"
        (HERE / "plant_bugs_2_output.txt").write_text(output, encoding="utf-8")
        sys.stdout.write(output)
        return 0 if count == len(BUGS) else 1
    finally:
        target.write_bytes((BACKUP / (TREND.replace("/", "__") + ".bak")).read_bytes())
        (BACKUP / (TREND.replace("/", "__") + ".bak")).unlink(missing_ok=True)
        if BACKUP.exists() and not any(BACKUP.iterdir()):
            BACKUP.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
