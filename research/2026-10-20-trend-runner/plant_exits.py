"""Plant material trail/state/partial-exit bugs; every mutant must fail tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Mutation:
    name: str
    old: str
    new: str


MUTATIONS = [
    Mutation(
        "allow a long structure stop to widen",
        "return max(current, candidate) if side > 0 else min(current, candidate)",
        "return min(current, candidate) if side > 0 else max(current, candidate)",
    ),
    Mutation(
        "ignore a quote exactly at the active stop",
        "return mark <= stop if side > 0 else mark >= stop",
        "return mark < stop if side > 0 else mark > stop",
    ),
    Mutation(
        "book a target gap at the market instead of the declared target",
        "time,\n                    target_2r,\n                    stop,",
        "time,\n                    price,\n                    stop,",
    ),
    Mutation(
        "change the declared one-third split to one-half",
        "(1.0 / 3.0) + (2.0 / 3.0) * raw_r",
        "0.5 + 0.5 * raw_r",
    ),
    Mutation(
        "graduate the trail at two R instead of three R",
        "target_3r = entry + side * 3.0 * risk",
        "target_3r = entry + side * 2.0 * risk",
    ),
    Mutation(
        "continue using M5 after graduation",
        'return event.timeframe == "M15" and graduation_time is not None and event.avail >= graduation_time',
        'return event.timeframe == "M5" and graduation_time is not None and event.avail >= graduation_time',
    ),
    Mutation(
        "remove the STATE fast target before activation",
        "family in (ExitFamily.FAST, ExitFamily.STATE) and not runner",
        "family is ExitFamily.FAST and not runner",
    ),
    Mutation(
        "apply a structure event before its exact availability quote",
        "events[event_index].avail < time",
        "events[event_index].avail <= time",
    ),
    Mutation(
        "delay the runner time exit past its deadline quote",
        "if runner and time >= runner_end:",
        "if runner and time > runner_end:",
    ),
]


def run_one(mutation: Mutation) -> bool:
    with tempfile.TemporaryDirectory(prefix="tr1-exit-mutant-") as temp_name:
        temp = Path(temp_name)
        shutil.copytree(HERE / "tr1", temp / "tr1")
        shutil.copytree(HERE / "tests", temp / "tests")
        path = temp / "tr1" / "exits.py"
        source = path.read_text(encoding="utf-8")
        if source.count(mutation.old) != 1:
            raise RuntimeError(f"mutation anchor is not unique: {mutation.name}")
        path.write_text(source.replace(mutation.old, mutation.new), encoding="utf-8", newline="\n")
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pytest", str(temp / "tests"), "-q"],
            cwd=temp,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode != 0


def main() -> int:
    caught = 0
    for number, mutation in enumerate(MUTATIONS, start=1):
        result = run_one(mutation)
        caught += int(result)
        print(f"{'CAUGHT' if result else 'MISSED'} {number:02d}: {mutation.name}")  # noqa: T201
    print(f"{caught} of {len(MUTATIONS)} exit bugs caught")  # noqa: T201
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
