"""A planted-bug runner for research modules: each mutant must make the given tests fail.

A mutant is the module's source with one text substitution. It runs in a fresh interpreter, registered in
``sys.modules`` under the module's import name with ``__file__`` set to the real file (so paths inside it resolve as
usual); the real file on disk is never changed. CAUGHT = the test run failed (pytest exit code != 0).

    python research/2026-10-18-moments/agents/audit2/plant.py SPEC   (SPEC = a module in audit2 with MUTANTS)
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AUDIT2 = Path(__file__).resolve().parent
PATHS = [
    str(ROOT),
    str(ROOT / "research" / "2026-10-18-moments"),
    str(ROOT / "research" / "2026-10-18-moments" / "agents" / "precursors"),
    str(ROOT / "research" / "2026-10-18-moments" / "agents" / "journal"),
    str(AUDIT2),
]

RUNNER = """
import sys, types
for p in reversed({paths!r}):
    sys.path.insert(0, p)
mod = types.ModuleType({name!r})
mod.__file__ = {real!r}
sys.modules[{name!r}] = mod
exec(compile(open({mutant!r}, encoding="utf-8").read(), {real!r}, "exec"), mod.__dict__)
import pytest
sys.exit(pytest.main([*{tests!r}, "-q", "-p", "no:cacheprovider", "--no-header", "-x"]))
"""


def run(name: str, real: Path, tests: list[str], mutants: list[tuple[str, str, str]]) -> tuple[int, int]:
    """Run every mutant of module ``name`` (file ``real``) against ``tests``; print CAUGHT / MISSED lines."""
    original = real.read_text(encoding="utf-8")
    caught = 0
    with tempfile.TemporaryDirectory() as tmp:
        for label, old, new in mutants:
            n = original.count(old)
            if n != 1:
                print(f"BAD MUTANT (pattern found {n} times): {label}")
                continue
            path = Path(tmp) / real.name
            path.write_text(original.replace(old, new), encoding="utf-8")
            code = RUNNER.format(paths=PATHS, name=name, real=str(real), mutant=str(path), tests=tests)
            res = subprocess.run(  # noqa: S603 - our own interpreter and code
                [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=False
            )
            summary = [ln for ln in res.stdout.splitlines() if " passed" in ln or " failed" in ln or "error" in ln]
            failed = [ln.split("::")[-1] for ln in res.stdout.splitlines() if ln.startswith(("FAILED", "ERROR"))]
            ok = res.returncode != 0
            caught += ok
            print(f"{'CAUGHT' if ok else 'MISSED'}  {label}: {summary[-1] if summary else res.returncode}")
            for f in failed:
                print(f"          {f}")
    print(f"{caught} of {len(mutants)} caught ({name})")
    return caught, len(mutants)


def main() -> int:
    spec = importlib.import_module(sys.argv[1])
    total_caught = total = 0
    for name, real, tests, mutants in spec.TARGETS:
        c, n = run(name, real, tests, mutants)
        total_caught += c
        total += n
    res = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", *sorted({t for _, _, ts, _ in spec.TARGETS for t in ts}), "-q",
         "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"ALL: {total_caught} of {total} caught; unmutated: {res.stdout.strip().splitlines()[-1]}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(AUDIT2))
    sys.exit(main())
