"""Plant future-data and outcome-label bugs; every mutant must fail the TR1 tests."""

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
        "timestamp the impulse using a future bar",
        "decision=pd.Timestamp(m1.index[index]) + pd.Timedelta(minutes=1)",
        "decision=pd.Timestamp(m1.index[end - 1]) + pd.Timedelta(minutes=1)",
    ),
    Mutation(
        "make a pullback pivot available before its confirming bar closes",
        "pivot_available=pd.Timestamp(pivot.avail)",
        "pivot_available=pd.Timestamp(bars.index[index])",
    ),
    Mutation(
        "trigger continuation from an intrabar extreme rather than its close",
        "continued = closes[current] > continuation if impulse.side > 0 else closes[current] < continuation",
        "continued = highs[current] > continuation if impulse.side > 0 else lows[current] < continuation",
    ),
    Mutation(
        "omit the entry spread from the protective-stop buffer",
        "buffer = max(spread, 0.10 * candidate.entry_atr)",
        "buffer = 0.10 * candidate.entry_atr",
    ),
    Mutation(
        "mark a long opportunity on ask instead of executable bid",
        "mark = bid if side > 0 else ask",
        "mark = ask",
    ),
    Mutation(
        "ignore a quote exactly at the stop",
        "stop_mask = mark <= stop if side > 0 else mark >= stop",
        "stop_mask = mark < stop if side > 0 else mark > stop",
    ),
    Mutation(
        "let quotes after the declared horizon affect the label",
        "horizon_index = int(horizon_matches[0]) if len(horizon_matches) else len(times)",
        "horizon_index = len(times)",
    ),
    Mutation(
        "hide the stop-gap quote from adverse excursion",
        "observed_end = stop_index + 1",
        "observed_end = stop_index",
    ),
]


def run_one(mutation: Mutation) -> bool:
    with tempfile.TemporaryDirectory(prefix="tr1-opportunity-mutant-") as temp_name:
        temp = Path(temp_name)
        shutil.copytree(HERE / "tr1", temp / "tr1")
        shutil.copytree(HERE / "tests", temp / "tests")
        path = temp / "tr1" / "opportunity.py"
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
    print(f"{caught} of {len(MUTATIONS)} opportunity bugs caught")  # noqa: T201
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
