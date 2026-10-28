"""Planted bugs for R10 as a check on every path (ISSUES 41).

Each bug is written into the source, the targeted tests run, and the source is restored; every bug must make
a test fail. Restores with ``write_bytes``.

    .venv/Scripts/python research/2026-10-24-replay/plant_bugs_r10.py
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = Path(__file__).resolve().parent / ".plant_backup_r10"
TESTS = ["tests/unit/test_ai_trader.py", "tests/unit/test_strategy_knowledge.py"]
TR, KB = "app/ai/trader.py", "app/strategy/kb.yaml"
BUGS: list[tuple[str, str, str, str]] = [
    ("an unreadable lean passes instead of refusing", TR,
     "    if not isinstance(value, (int, float)) or isinstance(value, bool):\n        return False",
     "    if not isinstance(value, (int, float)) or isinstance(value, bool):\n        return True"),
    # NOT the NaN case, as first labelled: NaN refuses by itself. Removing the guard lets an INFINITE lean
    # through, because inf >= 0 is True - caught only once the test covered infinity (2026-10-28).
    ("an infinite lean passes without the finiteness guard", TR,
     'return math.isfinite(lean) and (lean if side == "BUY" else -lean) >= 0',
     'return (lean if side == "BUY" else -lean) >= 0'),
    ("the sign is not flipped for a SELL", TR,
     'return math.isfinite(lean) and (lean if side == "BUY" else -lean) >= 0',
     "return math.isfinite(lean) and lean >= 0"),
    ("exactly zero is refused, against the measured rule", TR,
     'return math.isfinite(lean) and (lean if side == "BUY" else -lean) >= 0',
     'return math.isfinite(lean) and (lean if side == "BUY" else -lean) > 0'),
    ("a boolean reading counts as a number", TR,
     "or isinstance(value, bool):", "or isinstance(value, str):"),
    ("the rule is never consulted by the brakes", TR,
     'vetoes += [e["id"] for e in live if e.get("action") == LEAN_BEHIND and not lean_behind(e, f, side)]',
     "pass"),
    ("the veto is inverted", TR,
     'vetoes += [e["id"] for e in live if e.get("action") == LEAN_BEHIND and not lean_behind(e, f, side)]',
     'vetoes += [e["id"] for e in live if e.get("action") == LEAN_BEHIND and lean_behind(e, f, side)]'),
    ("the shipped rule loses its action, so it checks nothing", KB,
     "  action: stand_aside_unless_lean_behind   # the brakes refuse the side when the lean is not behind it\n", ""),
    ("the shipped rule names a reading that does not exist", KB,
     "  lean: h4_lean  ", "  lean: h4_momentum  "),
]  # fmt: skip


def restore_any() -> None:
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
