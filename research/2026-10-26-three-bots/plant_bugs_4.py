"""Crash-recoverable, one-at-a-time mutation check for DEV_SPEC_4.

Run from the repository root with ``.venv/Scripts/python research/.../plant_bugs_4.py``.
If the process is interrupted, rerunning this script restores any source files it had changed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RECOVERY = HERE / ".plant_bugs_4_recovery"
MANIFEST = RECOVERY / "manifest.json"
OUTPUT = HERE / "plant_bugs_4_output.txt"


def restore() -> None:
    if MANIFEST.is_file():
        for item in json.loads(MANIFEST.read_text(encoding="utf-8")):
            shutil.copyfile(RECOVERY / item["backup"], ROOT / item["path"])
    shutil.rmtree(RECOVERY, ignore_errors=True)


def mutation(path: str, before: str, after: str, test: str, label: str) -> tuple[str, str, str, str, str]:
    return path, before, after, test, label


BUGS = [
    mutation(
        "app/risk/day_plan.py",
        '("condition", (r"\\bcondition\\b",)),',
        '("condition", (r"\\babsent_condition\\b",)),',
        "tests/unit/test_risk_day_plan.py::test_plan_markers_are_case_insensitive_and_order_independent",
        "condition marker omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        '("levels", (r"\\blevels\\b",)),',
        '("levels", (r"\\babsent_levels\\b",)),',
        "tests/unit/test_risk_day_plan.py::test_plan_markers_are_case_insensitive_and_order_independent",
        "levels marker omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        '("side with the edge", (r"\\bside with the edge\\b", r"\\bedge_side\\b")),',
        '("side with the edge", (r"\\babsent_edge\\b",)),',
        "tests/unit/test_risk_day_plan.py::test_plan_markers_are_case_insensitive_and_order_independent",
        "edge-side marker omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        '("scenarios", (r"\\bscenarios\\b",)),',
        '("scenarios", (r"\\babsent_scenarios\\b",)),',
        "tests/unit/test_risk_day_plan.py::test_plan_markers_are_case_insensitive_and_order_independent",
        "scenarios marker omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        '("condition", (r"\\bcondition\\b",)),',
        '("wrong", (r"\\bcondition\\b",)),',
        "tests/unit/test_risk_day_plan.py::test_a_partial_plan_names_the_missing_part",
        "condition refusal detail omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        '("levels", (r"\\blevels\\b",)),',
        '("wrong", (r"\\blevels\\b",)),',
        "tests/unit/test_risk_day_plan.py::test_a_partial_plan_names_the_missing_part",
        "levels refusal detail omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        '("side with the edge", (r"\\bside with the edge\\b", r"\\bedge_side\\b")),',
        '("wrong", (r"\\bside with the edge\\b", r"\\bedge_side\\b")),',
        "tests/unit/test_risk_day_plan.py::test_a_partial_plan_names_the_missing_part",
        "edge-side refusal detail omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        '("scenarios", (r"\\bscenarios\\b",)),',
        '("wrong", (r"\\bscenarios\\b",)),',
        "tests/unit/test_risk_day_plan.py::test_a_partial_plan_names_the_missing_part",
        "scenarios refusal detail omitted",
    ),
    mutation(
        "app/risk/day_plan.py",
        "lowered = text.casefold()",
        "lowered = text",
        "tests/unit/test_risk_day_plan.py::test_plan_markers_are_case_insensitive_and_order_independent",
        "case-insensitive match disabled",
    ),
    mutation(
        "app/risk/day_plan.py",
        "if missing:",
        "if missing and len(text.strip()) != 1:",
        "tests/unit/test_risk_day_plan.py::test_a_one_character_plan_is_incomplete",
        "one-character plan allowed",
    ),
    mutation(
        "app/risk/day_plan.py",
        "fh.read(READ_LIMIT)",
        "fh.read()",
        "tests/unit/test_risk_day_plan.py::test_plan_check_reads_no_more_than_the_bound",
        "bounded read removed",
    ),
    mutation(
        "app/strategy/plan1.py",
        "class Plan1OrbParams(StrategyParams):\n    require_edge_side: bool = False",
        "class Plan1OrbParams(StrategyParams):\n    require_edge_side: bool = True",
        "tests/unit/test_plan1.py::TestPlan1Orb::test_edge_defaults_stay_off_and_warmup_grows_only_when_enabled",
        "ORB default switched on",
    ),
    mutation(
        "app/strategy/plan1.py",
        "lean = behind(edge_lean(ctx.frames, at, market.entry_timeframe), own_side)\n            except ValueError:\n                lean = None\n            edge_ok = lean is not None and lean >= 0",
        "lean = behind(edge_lean(ctx.frames, at, market.entry_timeframe), own_side)\n            except ValueError:\n                lean = None\n            edge_ok = True",
        "tests/unit/test_plan1.py::TestPlan1Orb::test_the_optional_edge_gate_refuses_an_opposing_or_unreadable_h4",
        "ORB edge refusal bypassed",
    ),
    mutation(
        "app/strategy/plan1.py",
        "lean = behind(edge_lean(ctx.frames, at, market.entry_timeframe), own_side)\n            except ValueError:\n                lean = None\n            edge_ok = lean is not None and lean >= 0",
        "lean = behind(edge_lean(ctx.frames, at, market.entry_timeframe), own_side)\n            except ValueError:\n                lean = None\n            edge_ok = lean is not None and lean > 0",
        "tests/unit/test_plan1.py::TestPlan1Orb::test_the_optional_edge_gate_refuses_an_opposing_or_unreadable_h4",
        "zero edge incorrectly refused",
    ),
    mutation(
        "app/strategy/plan1.py",
        "return max(base, 64 * 4 * 60) if self.params.require_edge_side else base",
        "return base",
        "tests/unit/test_plan1.py::TestPlan1Orb::test_edge_defaults_stay_off_and_warmup_grows_only_when_enabled",
        "ORB warmup too short",
    ),
    mutation(
        "app/strategy/plan1.py",
        "lean = behind(edge_lean(ctx.frames, at, ctx.market.entry_timeframe), own_side)\n            except ValueError:\n                lean = None\n            edge_ok = lean is not None and lean >= 0",
        "lean = behind(edge_lean(ctx.frames, at, ctx.market.entry_timeframe), own_side)\n            except ValueError:\n                lean = None\n            edge_ok = True",
        "tests/unit/test_plan1.py::TestPlan1Straddle::test_the_optional_edge_gate_refuses_a_buy_against_h4_and_reads_context_timeframe",
        "NY edge refusal bypassed",
    ),
    mutation(
        "app/strategy/plan1_b2.py",
        "edge_ok = lean is not None and lean >= 0",
        "edge_ok = True",
        "tests/unit/test_plan1_b2.py::test_optional_edge_gate_uses_the_context_entry_frame_and_fails_closed",
        "B2 / B2M5 edge refusal bypassed",
    ),
    mutation(
        "app/ai/plan.py",
        '"- scenarios:",',
        '"- scenario list:",',
        "tests/unit/test_ai_plan.py::test_the_plan_goes_to_the_journal_and_the_store",
        "AI scenario marker omitted",
    ),
]


def main() -> int:
    restore()
    originals: dict[str, bytes] = {}
    for path, *_ in BUGS:
        target = ROOT / path
        originals[path] = target.read_bytes()
    RECOVERY.mkdir(parents=True)
    items = []
    for index, (path, *_rest) in enumerate(BUGS):
        backup = f"source_{index}.bin"
        (RECOVERY / backup).write_bytes(originals[path])
        items.append({"path": path, "backup": backup})
    MANIFEST.write_text(json.dumps(items), encoding="utf-8")

    lines = ["DEV_SPEC_4 planted-bug report", "Each mutant was restored before the next was planted.", ""]
    try:
        for path, before, after, test, label in BUGS:
            target = ROOT / path
            current = target.read_text(encoding="utf-8")
            if current.count(before) != 1:
                raise RuntimeError(f"expected exactly one mutation site for {label} in {path}")
            target.write_text(current.replace(before, after, 1), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            restore()
            # Recreate the recovery journal for the next mutant, with clean source bytes.
            RECOVERY.mkdir(parents=True)
            items = []
            for index, (source, *_rest) in enumerate(BUGS):
                backup = f"source_{index}.bin"
                (RECOVERY / backup).write_bytes(originals[source])
                items.append({"path": source, "backup": backup})
            MANIFEST.write_text(json.dumps(items), encoding="utf-8")
            status = "CAUGHT" if result.returncode else "MISSED"
            summary = next(
                (line.strip() for line in result.stdout.splitlines() if "failed" in line or "passed" in line),
                "no pytest summary",
            )
            lines.append(f"{status}: {label} | {test} | {summary}")
            OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        restore()
    finally:
        restore()
    missed = sum(line.startswith("MISSED:") for line in lines)
    lines.extend(["", f"Caught: {len(BUGS) - missed}; missed: {missed}."])
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return int(missed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
