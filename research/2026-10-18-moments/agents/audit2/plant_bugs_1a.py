"""Planted bugs in app/market_data/history_download.py; each must fail tests/unit/test_history_download.py.

First the module as committed (git HEAD, before the audit's fix) runs against the tests: the symptom tests
must fail there. Then each mutant is loaded in a fresh interpreter as ``app.market_data.history_download``
(the file on disk is never changed) and the test file runs against it. CAUGHT = at least one test failed.

Run from the repo root: .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant_bugs_1a.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "app" / "market_data" / "history_download.py"
TEST = "tests/unit/test_history_download.py"

MUTANTS = [
    ("no tail check at all", "        if expected is None or (last", "        if True or (last"),
    ("no tick source", "    tick = gateway.tick(symbol)\n", "    tick = None\n"),
    ("no newest-bars source", "    if not newest.empty:\n", "    if False:\n"),
    ("window end not enforced", "if lo <= t < hi]", "if lo <= t]"),
    ("window start not enforced", "if lo <= t < hi]", "if t < hi]"),
    ("strict comparison (false alarm)", "last >= expected)", "last > expected)"),
    (
        "tail not re-read",
        "        df = _combine([df, _download_range(",
        "        _ = _combine([df, _download_range(",
    ),
    ("no wait before the re-read", "        pause(wait)\n", ""),
    ("wait not doubled", "        wait *= 2\n", ""),
    ("one retry only", "TAIL_RETRIES = 4", "TAIL_RETRIES = 1"),
    (
        "returns the stale frame instead of raising",
        "    raise HistoryIncompleteError(",
        "    return df\n    raise HistoryIncompleteError(",
    ),
    (
        "tick floored in UTC, not server time",
        "clock.server_epoch_to_utc(server_s // tf.seconds * tf.seconds)",
        "pd.Timestamp(tick.time_utc).floor(f'{tf.seconds}s')",
    ),
    (
        "re-read keeps the first copy of a bar",
        'subset="open_time", keep="last"',
        'subset="open_time", keep="first"',
    ),
    ("tail re-read starts at the window start", "max(start, last.to_pydatetime())", "start"),
]

RUNNER = """
import sys, types
sys.path.insert(0, {root!r})
import app.market_data
mod = types.ModuleType("app.market_data.history_download")
mod.__file__ = {path!r}
sys.modules["app.market_data.history_download"] = mod
exec(compile(open({path!r}, encoding="utf-8").read(), {path!r}, "exec"), mod.__dict__)
import pytest
sys.exit(pytest.main([{test!r}, "-q", "-p", "no:cacheprovider", "--no-header"]))
"""


def run_module(path: Path) -> tuple[int, str, list[str]]:
    code = RUNNER.format(root=str(ROOT), path=str(path), test=TEST)
    res = subprocess.run(  # noqa: S603 - our own interpreter and code
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=False
    )
    summary = [ln for ln in res.stdout.splitlines() if " passed" in ln or " failed" in ln]
    failed = [ln.split("::")[-1] for ln in res.stdout.splitlines() if ln.startswith("FAILED")]
    return res.returncode, (summary[-1] if summary else str(res.returncode)), failed


def main() -> int:
    original = SRC.read_text(encoding="utf-8")
    caught = 0
    with tempfile.TemporaryDirectory() as tmp:
        head = subprocess.run(  # noqa: S603, S607 - git, read only
            ["git", "show", "HEAD:app/market_data/history_download.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        before = Path(tmp) / "history_download_head.py"
        before.write_text(head, encoding="utf-8")
        rc, summary, failed = run_module(before)
        print(f"BEFORE (git HEAD module): {summary}")
        for f in failed:
            print(f"          {f}")
        for name, old, new in MUTANTS:
            if original.count(old) != 1:
                print(f"BAD MUTANT (pattern found {original.count(old)} times): {name}")
                return 2
            path = Path(tmp) / "history_download_mutant.py"
            path.write_text(original.replace(old, new), encoding="utf-8")
            rc, summary, failed = run_module(path)
            ok = rc != 0
            caught += ok
            print(f"{'CAUGHT' if ok else 'MISSED'}  {name}: {summary}")
            for f in failed:
                print(f"          {f}")
    print(f"{caught} of {len(MUTANTS)} caught")
    # the unmutated module must pass
    res = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", TEST, "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print("AFTER (the fixed module):", res.stdout.strip().splitlines()[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
