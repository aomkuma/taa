"""Plant material TR1 foundation bugs in temporary copies; every mutation must fail a test."""

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
    file: str
    old: str
    new: str


MUTATIONS = [
    Mutation("unlock P2", "boundaries.py", "if not allow_validation:", "if False:"),
    Mutation("unlock exam", "boundaries.py", "if not allow_exam:", "if False:"),
    Mutation(
        "include the period end",
        "data.py",
        '("open_time", "<", period.end.to_pydatetime())',
        '("open_time", "<=", period.end.to_pydatetime())',
    ),
    Mutation("open a forbidden tick day", "data.py", "if not self.period.contains(day):", "if False:"),
    Mutation(
        "let a span cross the boundary",
        "data.py",
        "if not self.period.contains(start) or end > self.period.end:",
        "if False:",
    ),
    Mutation(
        "drop same-millisecond quotes",
        "data.py",
        'return frame.sort_values("time_utc", kind="stable").reset_index(drop=True)',
        'return frame.drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)',
    ),
    Mutation(
        "expose a bar early", "bars.py", 'bars["avail"] = bars["close_time"]', 'bars["avail"] = bars["last"]'
    ),
    Mutation("ATR uses one fewer bar", "bars.py", ".rolling(length).mean()", ".rolling(length - 1).mean()"),
    Mutation("confirm a pivot early", "bars.py", "confirm = pivot + radius", "confirm = pivot + radius - 1"),
    Mutation(
        "buy at the bid",
        "simulation.py",
        "price = ask[index] + slippage if side > 0 else bid[index] - slippage",
        "price = bid[index] + slippage if side > 0 else bid[index] - slippage",
    ),
    Mutation(
        "ignore an entry gap",
        "simulation.py",
        "price = max(trigger, ask[index]) + slippage if side > 0 else min(trigger, bid[index]) - slippage",
        "price = trigger + slippage if side > 0 else trigger - slippage",
    ),
    Mutation(
        "book a gap stop at the stop",
        "simulation.py",
        "exit_price = min(stop, price) if side > 0 else max(stop, price)",
        "exit_price = stop",
    ),
    Mutation(
        "book a target at the market",
        "simulation.py",
        "times[index], target, ExitReason.TARGET, risk",
        "times[index], price, ExitReason.TARGET, risk",
    ),
    Mutation(
        "delay the time exit", "simulation.py", "if times[index] >= exit_at:", "if times[index] > exit_at:"
    ),
]


def run_one(mutation: Mutation) -> bool:
    with tempfile.TemporaryDirectory(prefix="tr1-mutant-") as temp_name:
        temp = Path(temp_name)
        shutil.copytree(HERE / "tr1", temp / "tr1")
        shutil.copytree(HERE / "tests", temp / "tests")
        path = temp / "tr1" / mutation.file
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
    print(f"{caught} of {len(MUTATIONS)} foundation bugs caught")  # noqa: T201
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
