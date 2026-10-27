"""Planted bugs for the missing readings (ISSUES 37-38): R10's H4 lean and W03's London ORB range.

Each bug is written into the source, the targeted tests run, and the source is restored; every bug must make
a test fail. Restores with ``write_bytes``: ``write_text`` rewrites a whole file as CRLF on this machine.

    .venv/Scripts/python research/2026-10-24-replay/plant_bugs_readings.py
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = Path(__file__).resolve().parent / ".plant_backup_readings"  # survives a kill: see restore_any()
TESTS = [
    "tests/unit/test_strategy_knowledge.py",
    "tests/unit/test_strategy_behaviors.py",
]
KN, BH = "app/strategy/knowledge.py", "app/strategy/behaviors.py"
BUGS: list[tuple[str, str, str, str]] = [
    # R10's number
    ("the lean is read from open-stamped bars: an hour of lookahead", KN,
     'closes.index = pd.DatetimeIndex(closes.index) + pd.Timedelta(hours=1)',
     'closes.index = pd.DatetimeIndex(closes.index)'),
    ("the lean is shifted the wrong way: two hours out", KN,
     'closes.index = pd.DatetimeIndex(closes.index) + pd.Timedelta(hours=1)',
     'closes.index = pd.DatetimeIndex(closes.index) - pd.Timedelta(hours=1)'),
    ("an unreadable lean becomes 0, which passes a 'lean >= 0' gate", KN,
     'return math.nan if lean is None else lean', 'return 0.0 if lean is None else lean'),
    ("the lean's sign is flipped", KN,
     'return math.nan if lean is None else lean', 'return math.nan if lean is None else -lean'),
    ("the reading is not declared, so no rule may name it", KN,
     '"h4_lean", "orb_high", "orb_low",', '"orb_high", "orb_low",'),
    ("orb_break is not declared as a word reading", KN, '"orb_break": _UPDOWN,', ''),
    # W03's range
    ("the ORB range is read before 13:15, while it is still forming", BH,
     'if th < end:  # the range is still forming: W03\'s first-break window has not opened',
     'if False:  # the range is still forming: W03\'s first-break window has not opened'),
    ("the range window runs to 13:15 inclusive, taking one bar too many", BH,
     '(opens >= start) & (opens < end) & closed_by', '(opens >= start) & (opens <= end) & closed_by'),
    ("the range starts an hour early", BH,
     'start, end = day + pd.Timedelta(hours=13), day + pd.Timedelta(hours=13, minutes=15)',
     'start, end = day + pd.Timedelta(hours=12), day + pd.Timedelta(hours=13, minutes=15)'),
    ("a wick through the range counts as a break", BH,
     'beyond = np.flatnonzero((c > high) | (c < low))',
     'beyond = np.flatnonzero((m1.high.to_numpy(float)[after] > high) | (c < low))'),
    ("the LAST break wins instead of the first", BH,
     'return high, low, "up" if c[beyond[0]] > high else "down"',
     'return high, low, "up" if c[beyond[-1]] > high else "down"'),
    ("bars that have not closed are read", BH,
     'closed_by = opens + pd.Timedelta(minutes=1) <= th',
     'closed_by = opens <= th'),
    # NOT a bug, and dropped after it was planted: `beyond` already holds only indices where the close is
    # above the high or below the low, so `> low` and `> high` pick the same side for every one of them.
    # An equivalent rewrite cannot be caught by a test, and chasing one would have meant writing a test
    # that asserts the implementation rather than the behaviour.
]  # fmt: skip


def restore_any() -> None:
    """Put back any file a killed run left with a bug in it (``finally`` does not run when killed)."""
    for f in sorted(BACKUP.glob("*.bak")) if BACKUP.exists() else []:
        head, _, body = f.read_bytes().partition(b"\n")
        target = ROOT / head.decode()
        target.write_bytes(body)
        print(f"restored {target.relative_to(ROOT)} from an interrupted run")
        f.unlink()


def keep(path: str, src: bytes) -> Path:
    BACKUP.mkdir(exist_ok=True)
    f = BACKUP / (path.replace("/", "_") + ".bak")
    f.write_bytes(path.encode() + b"\n" + src)
    return f


def run() -> bool:
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
