"""Crash-safe mutation check for the research session's three newly covered behaviors.

Run from the repo with ``.venv\\Scripts\\python research\\2026-10-26-three-bots\\review_plant_bugs.py``.
Each mutation is restored byte-for-byte, including after an interrupted run on the next invocation.
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BACKUP = HERE / ".review_bugs_backup"
TREND = "app/strategy/trend_box.py"
RANGE = "app/strategy/range_break.py"
TREND_TEST = "tests/unit/test_strategy_trend_box.py"
RANGE_TEST = "tests/unit/test_strategy_range_break.py"

BUGS: list[tuple[str, str, bytes, bytes, str, str]] = [
    (
        "invert the trend box height cap comparison",
        TREND,
        b"top - floor <= self.params.box * leg",
        b"top - floor >= self.params.box * leg",
        TREND_TEST,
        "test_a_box_taller_than_the_cap_is_not_a_box",
    ),
    (
        "add box share to leg instead of multiplying the cap",
        TREND,
        b"self.params.box * leg",
        b"self.params.box + leg",
        TREND_TEST,
        "test_a_box_taller_than_the_cap_is_not_a_box",
    ),
    (
        "label H4 bins by their close instead of their open",
        RANGE,
        b'opens.resample("4h").agg',
        b'opens.resample("4h", label="right", closed="right").agg',
        RANGE_TEST,
        "test_h4_is_built_from_h1_open_times_and_only_from_closed_bars",
    ),
    (
        "use first H1 high instead of the H4 maximum",
        RANGE,
        b'"high": "max"',
        b'"high": "first"',
        RANGE_TEST,
        "test_h4_is_built_from_h1_open_times_and_only_from_closed_bars",
    ),
    (
        "discard the latest H4 bar that has already closed",
        RANGE,
        b"(h4.index + pd.Timedelta(hours=4)) <= at",
        b"(h4.index + pd.Timedelta(hours=5)) <= at",
        RANGE_TEST,
        "test_an_unclosed_h4_bar_never_reaches_the_zigzag",
    ),
    (
        "divide by leg instead of multiplying the trend box cap",
        TREND,
        b"self.params.box * leg",
        b"self.params.box / leg",
        TREND_TEST,
        "test_a_box_taller_than_the_cap_is_not_a_box",
    ),
    (
        "divide reward by the disabled take-profit floor",
        RANGE,
        b"reward < self.params.min_take_profit",
        b"reward / self.params.min_take_profit < 1.0",
        RANGE_TEST,
        "test_sell_break_plan_is_the_mirror_and_reward_floor_is_enforced",
    ),
]


def pytest(test: str, case: str | None = None) -> subprocess.CompletedProcess[str]:
    target = test if case is None else f"{test}::{case}"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
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
        print(f"restored {relpath} from an interrupted run")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    restore_any()
    baseline = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TREND_TEST, RANGE_TEST],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if baseline.returncode:
        raise RuntimeError(f"baseline strategy tests failed:\n{baseline.stdout}\n{baseline.stderr}")

    BACKUP.mkdir(exist_ok=True)
    results: list[str] = []
    missed = False
    for name, relpath, old, new, test, case in BUGS:
        target = ROOT / relpath
        clean = target.read_bytes()
        if clean.count(old) != 1 or old == new:
            raise RuntimeError(f"mutation anchor is not unique for: {name}")
        parked = BACKUP / (relpath.replace("/", "__") + ".bak")
        if not parked.exists():
            parked.write_bytes(clean)
        try:
            target.write_bytes(clean.replace(old, new, 1))
            caught = pytest(test, case).returncode != 0
            result = f"{'CAUGHT' if caught else 'MISSED'} | {name}"
            results.append(result)
            missed |= not caught
        finally:
            target.write_bytes(clean)
            parked.unlink(missing_ok=True)
        print(results[-1])

    summary = f"\n{len(BUGS) - sum(r.startswith('MISSED') for r in results)}/{len(BUGS)} caught"
    output = "\n".join([*results, summary]) + "\n"
    (HERE / "review_plant_bugs_output.txt").write_text(output, encoding="utf-8")
    print(summary)
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
