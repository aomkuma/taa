"""Planted bugs for the SWALLOWED.md fix: a lost AI wake must appear in the journals a reader opens.

Each bug is written into the source, the targeted tests run, and the source is restored; every bug must make
a test fail. Unlike the older plant_bugs_*.py here, this one restores with ``write_bytes``: ``write_text``
rewrites a whole file as CRLF on this machine, which is how 66 of app/'s Python files became CRLF.

    .venv/Scripts/python research/2026-10-24-replay/plant_bugs_swallowed.py
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = Path(__file__).resolve().parent / ".plant_backup_swallowed"  # survives a kill: see restore_any()
TESTS = ["tests/unit/test_ai_watcher.py"]
W = "app/ai/watcher.py"
BUGS: list[tuple[str, str, str, str]] = [
    ("the lost wake goes to a file of its own again", W,
     '(self.store / "decisions.jsonl", json.dumps(rec) + "\\n"),',
     '(self.store / "failed.jsonl", json.dumps(rec) + "\\n"),'),
    ("a lost wake is recorded as the provider's ERROR", W, '"status": FAILED,', '"status": "ERROR",'),
    ("a lost wake claims it cost nothing rather than never happening", W, '"cost_usd": None,', '"cost_usd": 0.0,'),
    ("the session notes get no entry", W, "(session, session_entry(now, [FAILED_REASON], rec)),", '(session, ""),'),
    ("the error detail is dropped", W,
     '"detail": f"the watcher cycle failed ({count}): {type(exc).__name__}: {exc}",',
     '"detail": "the watcher cycle failed",'),
    ("reporting the failure may raise over the failure", W, "except OSError:", "except FileNotFoundError:"),
]  # fmt: skip


def restore_any() -> None:
    """Put back any file a killed run left with a bug in it (``finally`` does not run when the process is
    killed)."""
    for f in sorted(BACKUP.glob("*.bak")) if BACKUP.exists() else []:
        head, _, body = f.read_bytes().partition(b"\n")
        target = ROOT / head.decode()
        target.write_bytes(body)
        print(f"restored {target.relative_to(ROOT)} from an interrupted run")
        f.unlink()


def keep(path: str, src: bytes) -> Path:
    """Park ``src`` where an interrupted run can be undone from; the first line names the file."""
    BACKUP.mkdir(exist_ok=True)
    f = BACKUP / (path.replace("/", "_") + ".bak")
    f.write_bytes(path.encode() + b"\n" + src)
    return f


def run() -> bool:
    """True when the targeted tests pass."""
    out = subprocess.run(  # nosec B603 - fixed argv
        [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return out.returncode == 0


def main() -> int:
    restore_any()
    if not run():
        print("the tests must pass on the clean source first")
        return 2
    missed = 0
    for name, path, old, new in BUGS:
        f = ROOT / path
        src = f.read_bytes()
        if src.count(old.encode()) != 1:
            print(f"SKIPPED {name}: the text to change is not unique in {path}")
            missed += 1
            continue
        parked = keep(path, src)
        try:
            f.write_bytes(src.replace(old.encode(), new.encode()))
            caught = not run()
        finally:
            f.write_bytes(src)
            parked.unlink(missing_ok=True)
        missed += not caught
        print(f"{'caught' if caught else 'MISSED'}  {name}")
    print(f"{len(BUGS) - missed}/{len(BUGS)} caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
