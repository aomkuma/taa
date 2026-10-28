# ruff: noqa: E501
"""Planted-bug harness for the fixed Trend Runner code (2026-10-22).

Each mutant replaces one exact source fragment in place, runs the hand-worked tests in a fresh process, and restores
the file (also on error). A mutant counts as caught when the tests fail. Bugs B1, B3, B6-B10 of DEBUG_2026-10-22.md
are planted back as mutants too, so the tests are shown to catch the original faults.

    .venv\\Scripts\\python research\\2026-10-21-trend-runner-retest-continuation\\plant_bugs_2026-10-22.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TR1 = HERE.parents[0] / "2026-10-20-trend-runner"
V1_TESTS = [
    "test_candidate.py",
    "test_source_ticks.py",
    "test_journal_fields.py",
    "test_observer.py",
    "test_source_adapter.py",
]
TR1_TESTS = [str(TR1 / "tests")]

C, T, S, A, J = "candidate.py", "ticks.py", "source_ticks.py", "source_adapter.py", "journal_fields.py"
OPP = TR1 / "tr1" / "opportunity.py"
SHADOW = HERE.parents[0] / "2026-10-20-trend-runner-shadow"
SH_DET = SHADOW / "shadow" / "detector.py"
SH_OUT = SHADOW / "shadow" / "outcomes.py"
SH_ADA = SHADOW / "shadow" / "adapter.py"
SH_OAD = SHADOW / "shadow" / "outcome_adapter.py"
SHADOW_TESTS = [
    "tests/test_debug_2026_10_22.py",
    "tests/test_hand_2026_10_22.py",
    "tests/test_outcomes.py",
    "tests/test_detector.py",
]

MUTANTS: list[tuple[str, str | Path, str, str]] = [
    # --- M5 bars / ATR
    (
        "complete bar dropped at data end",
        C,
        'm5.loc[m5["close_time"] <= data_end]',
        'm5.loc[m5["close_time"] < data_end]',
    ),
    (
        "forming bar used as a signal",
        C,
        'm5.loc[m5["close_time"] <= data_end]',
        'm5.loc[m5["close_time"] <= data_end + pd.Timedelta(minutes=5)]',
    ),
    (
        "ATR without previous close and with bar 0",
        C,
        'm5["atr14"] = mt5_atr(\n',
        'm5["atr14"] = (lambda h, lo, c, n: pd.Series(h - lo).rolling(n).mean().to_numpy())(\n',
    ),
    (
        "SELL bars not lifted by spread",
        C,
        'offset = m1["spread"] * POINT if side < 0 else 0.0',
        "offset = 0.0",
    ),
    # --- reclaim / retest / invalidation / continuation
    (
        "reclaim on the bar closing at the stop",
        C,
        'after_stop = m5.loc[(m5["close_time"] > stop_time)',
        'after_stop = m5.loc[(m5["close_time"] >= stop_time)',
    ),
    ("reclaim window end exclusive", C, '& (m5["close_time"] <= end)]', '& (m5["close_time"] < end)]'),
    (
        "SELL reclaim direction flipped",
        C,
        'else after_stop["close"] < original_entry',
        'else after_stop["close"] > original_entry',
    ),
    ("retest window seven bars", C, "RETEST_BARS = 6", "RETEST_BARS = 7"),
    (
        "retest close need not hold",
        C,
        'held = row["close"] >= original_entry if side > 0 else row["close"] <= original_entry',
        "held = True",
    ),
    (
        "buffer min instead of max",
        C,
        "buffer = max(source_spread, 0.10 * atr)",
        "buffer = min(source_spread, 0.10 * atr)",
    ),
    (
        "stop from retest close",
        C,
        'provisional = float(retest["low"] - buffer',
        'provisional = float(retest["close"] - buffer',
    ),
    ("invalidation ignored", C, "        if breached:\n", "        if False:\n"),
    ("continuation not strict", C, '(row["close"] > retest["high"])', '(row["close"] >= retest["high"])'),
    ("confirmation window three bars", C, "CONFIRM_BARS = 2", "CONFIRM_BARS = 3"),
    (
        "B3: retest expires 8 h after the stop",
        C,
        "        if touched and held:\n",
        '        if touched and held and row["close_time"] <= end:\n',
    ),
    # --- entry
    (
        "B6: BUY entry at the bid",
        C,
        'entry = float(first["ask"] + slippage) if side > 0',
        'entry = float(first["bid"] + slippage) if side > 0',
    ),
    ("entry on the last quote of the minute", C, "first = window.iloc[0]", "first = window.iloc[-1]"),
    ("slippage favourable", C, 'float(first["ask"] + slippage)', 'float(first["ask"] - slippage)'),
    (
        "entry through stop accepted",
        C,
        "if (entry - initial_stop) * side <= 0:",
        "if (entry - initial_stop) * side < -1:",
    ),
    # --- management
    (
        "B6: stop booked at the stop price",
        C,
        "return _done(reason, t, price, stop, entry, entry_time, risk, side, mfe, mae)",
        "return _done(reason, t, stop, stop, entry, entry_time, risk, side, mfe, mae)",
    ),
    (
        "BUY marked on the ask",
        C,
        'mark = chunk["bid"].to_numpy(float) if side > 0',
        'mark = chunk["ask"].to_numpy(float) if side > 0',
    ),
    (
        "time before stop on the same quote",
        C,
        "            if (price <= stop) if side > 0 else (price >= stop):\n",
        "            if t >= deadline:\n"
        '                return _done("TIME", t, price, stop, entry, entry_time, risk, side, mfe, mae)\n'
        "            if (price <= stop) if side > 0 else (price >= stop):\n",
    ),
    (
        "time exit only after the deadline",
        C,
        "            if t >= deadline:\n",
        "            if t > deadline:\n",
    ),
    (
        "pivot applied before confirmation",
        C,
        "pivots[pivot_idx][0] <= t:",
        "pivots[pivot_idx][0] <= t + pd.Timedelta(minutes=5):",
    ),
    (
        "stop may loosen",
        C,
        "return max(current, candidate) if side > 0 else min(current, candidate)",
        "return candidate",
    ),
    ("pre-entry pivot trails", C, "        if m5.index[pivot] < formed_from:\n            continue\n", ""),
    (
        "pivot buffer without entry spread",
        C,
        "buffer = max(entry_spread, 0.10 * value)",
        "buffer = 0.10 * value",
    ),
    (
        "trail guessed past the supplied bars",
        C,
        "            if t > bars_known_until:\n",
        "            if False:\n",
    ),
    # --- exam guard and tick reader
    (
        "exam guard off by a day",
        T,
        "if start < EXAM_END and end > EXAM_START:",
        "if start < EXAM_END and end > EXAM_START + pd.Timedelta(days=1):",
    ),
    ("tick day read without the guard", T, "        refuse_exam(day, day + pd.Timedelta(days=1))\n", ""),
    (
        "tick day sorted by price",
        T,
        'frame = frame.sort_values("time_utc", kind="stable")',
        'frame = frame.sort_values(["time_utc", "bid"], ascending=[True, False])',
    ),
    # --- source eligibility
    ("stop after the +1R partial counted as eligible", S, " and not bool(partial_taken)", ""),
    ("time exit counted as stop", S, 'reason == "STOP"', 'reason in ("STOP", "TIME")'),
    ("long slices allowed", S, "MAX_SPAN = pd.Timedelta(days=21)", "MAX_SPAN = pd.Timedelta(days=60)"),
    (
        "B10: equal-time quotes refused",
        A,
        "        if not times.is_monotonic_increasing:\n",
        "        if times.has_duplicates or not times.is_monotonic_increasing:\n",
    ),
    # --- journal fields
    ("Thai time zone wrong", J, 'THAI = "Asia/Bangkok"', 'THAI = "Asia/Tokyo"'),
    ("ATR from the forming bar", J, "<= moment]", "<= moment + pd.Timedelta(minutes=30)]"),
    (
        "week from the UTC date",
        J,
        "    local = utc(ts).tz_convert(THAI)\n    monday",
        "    local = utc(ts)\n    monday",
    ),
    (
        "SELL excursions on the bid",
        J,
        'mark = quotes["bid"].to_numpy(float) if side > 0 else quotes["ask"].to_numpy(float)',
        'mark = quotes["bid"].to_numpy(float)',
    ),
    # --- TR1 first pullback
    (
        "B1: later pullback substituted",
        OPP,
        '            reasons["no_continuation"] += 1\n            return None, reasons\n        value',
        '            reasons["no_continuation"] += 1\n            continue\n        value',
    ),
    ("TR1 depth band narrowed", OPP, "0.20 <= ratio <= 0.65", "0.20 <= ratio <= 0.45"),
    # --- shadow TR1 detector / fill / RUNNER outcome (2026-10-20-trend-runner-shadow)
    (
        "S1: shadow later pullback substituted",
        SH_DET,
        "        return None\n    return None\n",
        "    return None\n",
    ),
    ("shadow ATR window 13", SH_DET, "rolling(length).mean()", "rolling(length - 1).mean()"),
    ("shadow impulse 0.30 H", SH_DET, "distance = 0.25 * h1_atr", "distance = 0.30 * h1_atr"),
    ("shadow depth band narrowed", SH_DET, "not 0.20 <= ratio <= 0.65", "not 0.20 <= ratio <= 0.45"),
    ("shadow BUY fills at the bid", SH_DET, "entry = ask if detection.side > 0 else bid", "entry = bid"),
    (
        "shadow buffer min",
        SH_DET,
        "buffer = max(spread, 0.10 * detection.entry_atr)",
        "buffer = min(spread, 0.10 * detection.entry_atr)",
    ),
    (
        "shadow risk band widened",
        SH_DET,
        "if not 0.05 <= risk_h1 <= 0.50:",
        "if not 0.05 <= risk_h1 <= 0.90:",
    ),
    (
        "S2: adapter ticks reordered",
        SH_ADA,
        '.sort_values("time_utc", kind="stable")',
        '.sort_values(["time_utc", "bid"], ascending=[True, False])',
    ),
    (
        "S2: outcome ticks reordered",
        SH_OAD,
        '.sort_values("time_utc", kind="stable")',
        '.sort_values(["time_utc", "bid"], ascending=[True, False])',
    ),
    (
        "shadow stop booked at the stop price",
        SH_OUT,
        "            event_index += 1\n        if _stopped(side, price, stop):\n            return _finish(\n                family, ExitReason.STOP, side, entry, risk, entry_time, time, price, stop,",
        "            event_index += 1\n        if _stopped(side, price, stop):\n            return _finish(\n                family, ExitReason.STOP, side, entry, risk, entry_time, time, stop, stop,",
    ),
    (
        "shadow partial one half",
        SH_OUT,
        "(1.0 / 3.0) + (2.0 / 3.0) * raw_r",
        "(1.0 / 2.0) + (1.0 / 2.0) * raw_r",
    ),
    (
        "shadow graduation at 2R",
        SH_OUT,
        "target_3r = entry + side * 3.0 * risk",
        "target_3r = entry + side * 2.0 * risk",
    ),
    # (" and event.avail >= graduation_time" removed is an equivalent mutant: events are applied once, in time
    # order, so an M15 pivot confirmed before graduation is already consumed before graduation happens.)
    (
        "shadow M5 trail kept after graduation",
        SH_OUT,
        '    if not graduated:\n        return event.timeframe == "M5"\n',
        '    if not graduated or event.timeframe == "M5":\n        return event.timeframe == "M5"\n',
    ),
    (
        "shadow stop may loosen",
        SH_OUT,
        "return max(current, candidate) if side > 0 else min(current, candidate)",
        "return candidate",
    ),
    (
        "shadow time exit after the deadline",
        SH_OUT,
        "if runner and time >= runner_end:",
        "if runner and time > runner_end:",
    ),
    ("shadow target at the gap price", SH_OUT, "time, target_2r, stop", "time, price, stop"),
]


def run_tests(tests: list[str], cwd: Path) -> bool:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def main() -> None:
    if not (run_tests(V1_TESTS, HERE) and run_tests(TR1_TESTS, TR1) and run_tests(SHADOW_TESTS, SHADOW)):
        raise SystemExit("the unmutated code must pass first")
    caught = 0
    for name, file, old, new in MUTANTS:
        path = file if isinstance(file, Path) else HERE / file
        source = path.read_text(encoding="utf-8")
        if source.count(old) != 1:
            raise SystemExit(f"mutant '{name}': fragment found {source.count(old)} times in {path.name}")
        try:
            path.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
            if path == OPP:
                passed = run_tests(TR1_TESTS, TR1)
            elif SHADOW in path.parents:
                passed = run_tests(SHADOW_TESTS, SHADOW)
            else:
                passed = run_tests(V1_TESTS, HERE)
        finally:
            path.write_text(source, encoding="utf-8", newline="\n")
        caught += not passed
        print(f"{'CAUGHT' if not passed else 'MISSED'}  {path.name:18} {name}", flush=True)  # noqa: T201
    print(f"\n{caught} of {len(MUTANTS)} planted bugs caught")  # noqa: T201
    if caught != len(MUTANTS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
