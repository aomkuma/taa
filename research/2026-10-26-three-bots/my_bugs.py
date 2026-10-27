"""The research session's own planted bugs against the delivered strategies (DEV_SPEC.md section 4).

Deliberately NOT the ones the developer session wrote: these are chosen from the spec's own wording, to test
whether its tests catch mistakes it did not think of. Each bug is written in, the developer's own tests are
run, and the file is restored - with a crash-safe backup, so a killed run cannot leave a bug behind.

    .venv\\Scripts\\python <this file>
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\korap\taa")
BACKUP = Path(__file__).resolve().parent / ".my_bugs_backup"
TESTS = ["tests/unit/test_strategy_trend_box.py", "tests/unit/test_strategy_range_break.py"]
TB, RB = "app/strategy/trend_box.py", "app/strategy/range_break.py"

BUGS: list[tuple[str, str, str, str]] = [
    # the spec's own sentences, each broken one way
    ("3.1.1 the New York window is fixed to a clock hour instead of New York local time",
     TB, 'ZoneInfo("America/New_York")', 'ZoneInfo("UTC")'),
    ("3.1.3 the run is measured over 30 minutes, not 60", TB, "minutes=60", "minutes=30"),
    ("3.1.3 the run gate is ten times looser than the measured 1.2 R",
     TB, "return run > 1.2 * risk", "return run > 12.0 * risk"),
    ("3.2.3 the box may be as tall as the whole leg", TB, "self.params.box * leg", "leg"),
    ("3.2.4 the retrace is measured from A, not from B", TB, "- b.price) / leg", "- a.price) / leg"),
    ("3.2.6 the take-profit is the leg's start, not the swing it runs to", TB, "target = b.price", "target = a.price"),
    ("3.2.6 the stop sits on the box edge with no buffer", TB,
     "top + self.params.buffer * (top - floor) if down else floor - self.params.buffer * (top - floor)",
     "top if down else floor"),
    ("3.3.1 a trending H4 also qualifies as a range", RB, 'stepped(swings) != "FLAT" or ', ""),
    ("3.3.3 the break is taken without the previous close being inside",
     RB, "price > hh >= prev", "price > hh"),
    ("3.3.4 a BUY's take-profit is the whole box, not tp_range of it",
     RB, "price + self.params.tp_range * rng,", "price + rng,"),
    ("3.4 break-even moves the stop even before +0.5 R", TB, "ahead >= 0.5 * risk", "ahead >= 0.0 * risk"),
    ("H4 is resampled without the close-to-open shift", RB, '- pd.Timedelta(hours=1)', "- pd.Timedelta(hours=0)"),
    ("H4 uses bars that have not closed yet", RB, "(h4.index + pd.Timedelta(hours=4)) <= at", "h4.index <= at"),
    ("the ZigZag's forming point is used as a confirmed swing", RB,
     "swings, _forming = zigzag(h4.high.to_numpy(float), h4.low.to_numpy(float))",
     ("swings, _forming = zigzag(h4.high.to_numpy(float), h4.low.to_numpy(float))\n"
      "        swings = swings + ([_forming] if _forming is not None else [])")),
]  # fmt: skip


def run() -> bool:
    out = subprocess.run(  # nosec B603 - fixed argv
        [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return out.returncode == 0


def restore_any() -> None:
    for f in sorted(BACKUP.glob("*.bak")) if BACKUP.exists() else []:
        head, body = f.read_text(encoding="utf-8").split("\n", 1)
        (ROOT / head).write_text(body, encoding="utf-8")
        print(f"restored {head} from an interrupted run")
        f.unlink()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    restore_any()
    if not run():
        print("the developer's tests do not pass on the clean source - stopping")
        return 1
    missed = []
    for name, path, old, new in BUGS:
        f = ROOT / path
        src = f.read_text(encoding="utf-8")
        if src.count(old) != 1 or old == new:
            print(f"SKIP    {name} (the text is not unique in {path}, or the bug is a no-op)")
            continue
        BACKUP.mkdir(exist_ok=True)
        parked = BACKUP / (path.replace("/", "_") + ".bak")
        parked.write_text(path + "\n" + src, encoding="utf-8")
        try:
            f.write_text(src.replace(old, new), encoding="utf-8")
            caught = not run()
        finally:
            f.write_text(src, encoding="utf-8")
            parked.unlink(missing_ok=True)
        print(f"{'caught' if caught else 'MISSED'}  {name}")
        if not caught:
            missed.append(name)
    print(f"\n{len(BUGS) - len(missed)}/{len(BUGS)} caught by the developer's own tests")
    for m in missed:
        print(f"  MISSED: {m}")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
