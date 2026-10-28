"""Planted bugs against the H4 edge-side gate's own tests (2026-10-27).

The developer session could not do this: its review brief said read-only, so it could not break a line and
watch a test fail - my brief contradicted itself, the second time in a day. This does it instead.

Each bug is written into `app/strategy/edge_side.py` or a strategy, the gate's tests are run, and the file
is restored - with a crash-safe backup, so a killed run cannot leave a bug in a file the live engine
loads.

    .venv\\Scripts\\python research/2026-10-26-three-bots/plant_bugs_edge.py
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this repo's own pytest
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\korap\taa")
BACKUP = Path(__file__).resolve().parent / ".plant_edge_backup"
TESTS = [
    "tests/unit/test_strategy_edge_side.py",
    "tests/unit/test_strategy_trend_box.py",
    "tests/unit/test_strategy_range_break.py",
]
E, TB, RB = "app/strategy/edge_side.py", "app/strategy/trend_box.py", "app/strategy/range_break.py"

BUGS: list[tuple[str, str, str, str]] = [
    ("the close-to-open shift is dropped (an hour of lookahead)",
     E, 'opens.index = pd.DatetimeIndex(opens.index) - pd.Timedelta(hours=1)',
     'opens.index = pd.DatetimeIndex(opens.index)'),
    ("the shift goes the wrong way", E,
     'pd.DatetimeIndex(opens.index) - pd.Timedelta(hours=1)',
     'pd.DatetimeIndex(opens.index) + pd.Timedelta(hours=1)'),
    ("a bar that has not closed is read", E,
     'closed = bars[(bars.index + pd.Timedelta(hours=hours)) <= pd.Timestamp(at)]',
     'closed = bars[bars.index <= pd.Timestamp(at)]'),
    ("too short a history is answered with a guess instead of None", E,
     'if len(closed) < MEAN_BARS + ATR_BARS:', 'if len(closed) < 2:'),
    ("the lean is not divided by the frame's own volatility", E,
     'lean = (float(closed.close.iloc[-1]) - mean) / width',
     'lean = float(closed.close.iloc[-1]) - mean'),
    ("the sign of the lean is inverted", E,
     'lean = (float(closed.close.iloc[-1]) - mean) / width',
     'lean = (mean - float(closed.close.iloc[-1])) / width'),
    # Was recorded as a known miss on the claim that nothing could reach this guard. That claim was
    # WRONG: the developer session found a finite, tiny ATR (1e-320) overflows the division to infinity.
    # The case now has its own test, so this bug is caught (2026-10-27).
    ("a non-finite lean is handed back (nan < 0 is False: the gate opens)", E,
     'return lean if math.isfinite(lean) else None', 'return lean'),
    ("a non-finite width passes the guard", E,
     'if not math.isfinite(mean) or not math.isfinite(width) or width <= 0:',
     'if not math.isfinite(mean) or width <= 0:'),
    ("a zero-width frame divides by zero instead of refusing", E,
     'or width <= 0:', 'or width < 0:'),
    ("a sell is judged by the lean as it stands, not from its own side", E,
     'return lean if side is Side.BUY else -lean', 'return lean'),
    ("the rule can be read from the entry frame itself", E,
     'if entry.seconds >= frame.seconds:', 'if False:'),
    ("an unreadable frame becomes permission to trade (trend)", TB,
     'if lean is None or lean < 0:', 'if lean is not None and lean < 0:'),
    ("an unreadable frame becomes permission to trade (range)", RB,
     'if lean is None or lean < 0:', 'if lean is not None and lean < 0:'),
    ("the trend gate judges the wrong direction", TB,
     'own = Side.SELL if self.direction == "DOWN" else Side.BUY',
     'own = Side.BUY if self.direction == "DOWN" else Side.SELL'),
    ("the range gate judges the wrong side", RB,
     'lean = behind(edge_lean(ctx.frames, at, ctx.market.entry_timeframe), side)',
     'lean = behind(edge_lean(ctx.frames, at, ctx.market.entry_timeframe), Side.BUY)'),
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
        (ROOT / head).write_bytes(body.encode("utf-8"))
        print(f"restored {head} from an interrupted run")
        f.unlink()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    restore_any()
    if not run():
        print("the tests do not pass on the clean source - stopping")
        return 1
    missed = []
    for name, path, old, new in BUGS:
        f = ROOT / path
        src = f.read_bytes().decode("utf-8")
        if src.count(old) != 1 or old == new:
            print(f"SKIP    {name} (the text is not unique in {path})")
            missed.append(name + " [NOT PLANTED]")
            continue
        BACKUP.mkdir(exist_ok=True)
        parked = BACKUP / (path.replace("/", "_") + ".bak")
        parked.write_text(path + "\n" + src, encoding="utf-8")
        try:
            f.write_bytes(src.replace(old, new).encode("utf-8"))
            caught = not run()
        finally:
            f.write_bytes(src.encode("utf-8"))
            parked.unlink(missing_ok=True)
        print(f"{'caught' if caught else 'MISSED'}  {name}")
        if not caught:
            missed.append(name)
    print(f"\n{len(BUGS) - len(missed)}/{len(BUGS)} caught")
    for m in missed:
        print(f"  MISSED: {m}")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
