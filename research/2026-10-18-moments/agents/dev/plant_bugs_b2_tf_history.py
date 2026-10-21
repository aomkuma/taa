"""Planted bugs for b2_tf_history.py, each run against test_b2_tf_history.py in a temporary copy (the harness of
plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_b2_tf_history.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

BUGS = [
    ("ticks: the switch on 2025-09-01", [('TICK_SWITCH = pd.Timestamp("2025-10-01", tz="UTC")', 'TICK_SWITCH = pd.Timestamp("2025-09-01", tz="UTC")')]),
    ("ticks: the D: folder without the symbol", [('OLD_TICKS = Path("D:/taa-data/ticks/XAUUSD")', 'OLD_TICKS = Path("D:/taa-data/ticks")')]),
    ("ticks: a day from 2026-04-18 opened", [("    if day >= EXAM_START:", "    if False:")]),
    ("ticks: the switch day itself on D:", [("folder = OLD_TICKS if day < TICK_SWITCH else NEW_TICKS", "folder = OLD_TICKS if day <= TICK_SWITCH else NEW_TICKS")]),
    ("ticks: not sorted by time", [('o = np.argsort(t, kind="stable")', "o = np.arange(len(t))")]),
    ("m1: a cut one day past the exam start allowed", [("    if before > EXAM_START:", "    if before > EXAM_START + DAY:")]),
    ("m1: a leaked row at the cut let through", [("if len(m) and m.index.max() >= before:", "if False:")]),
    ("m1: a duplicate keeps the first", [('m = m[~m.index.duplicated(keep="last")].sort_index()', 'm = m[~m.index.duplicated(keep="first")].sort_index()')]),
    ("years: the end included", [("lab[(t >= a.value) & (t < b.value)] = y", "lab[(t >= a.value) & (t <= b.value)] = y")]),
    ("years: 2024-25 cut at 2025-09-01", [('"2024-25": (pd.Timestamp("2024-09-01", tz="UTC"), TICK_SWITCH)', '"2024-25": (pd.Timestamp("2024-09-01", tz="UTC"), pd.Timestamp("2025-09-01", tz="UTC"))')]),
    ("tiles: cut on Sundays", [("(5 - a.dayofweek) % 7 or 7", "(6 - a.dayofweek) % 7 or 7")]),
    ("tiles: every 35 days", [("        s += pd.Timedelta(days=28)", "        s += pd.Timedelta(days=35)")]),
    ("b2: M5 only not applied", [("cands = cands[cands.tf == tf_only].reset_index(drop=True)", "cands = cands")]),
    ("b2: decisions past the end kept", [("if start.value <= r.t_entry < end.value]", "if start.value <= r.t_entry]")]),
    ("b2: the entry TF lost", [("exit=r.exit, tf=r.tf) for r in", 'exit=r.exit, tf="M1") for r in')]),
    ("run: 7 days of warm-up", [("(m_all.index >= s - pd.Timedelta(days=F.WARM_DAYS))", "(m_all.index >= s - pd.Timedelta(days=7))")]),
    ("run: later tiles located from their start", [("back = locate_first if k == 0 else F.LOCATE_BACK", "back = locate_first")]),
    ("run: decisions before the tile kept", [("X = X[X.t_dec.astype(np.int64) >= s.value].copy()", "X = X.copy()")]),
    ("run: M5 only runs every TF", [('for name, only in (("W", None), ("M5 only", "M5")):', 'for name, only in (("W", None), ("M5 only", None)):')]),
    ("stats: a 0 counted as a win", [("win=float(np.mean(pnl > 0))", "win=float(np.mean(pnl >= 0))")]),
    ("stats: the population sd", [("np.std(R, ddof=1)", "np.std(R, ddof=0)")]),
    ("table: W's M5 split takes M1", [('("W: M5", X[(X.stream == "W") & (X.tf == "M5")])', '("W: M5", X[(X.stream == "W") & (X.tf == "M1")])')]),
    ("table: in / out swapped", [('("in", Gy[Gy.band]), ("out", Gy[~Gy.band])', '("in", Gy[~Gy.band]), ("out", Gy[Gy.band])')]),
    ("pass: R > 0.15", [("p.R >= 0.15", "p.R > 0.15")]),
    ("pass: 41 trades", [("p.n >= 40", "p.n > 40")]),
    ("pass: a lower end of 0 passes", [("p.lo > 0", "p.lo >= 0")]),
    ("pass: 2 of 5 years", [("better >= 3", "better >= 2")]),
    ("pass: a tie counts as better", [('A.loc[(m5, y), "R"] > A.loc[("W: M1", y), "R"]', 'A.loc[(m5, y), "R"] >= A.loc[("W: M1", y), "R"]')]),
    ("commands: run without a year", [("if bad or len(a) < 2:", "if bad:")]),
]


def main() -> None:
    py = Path(sys.executable)
    mod, test = HERE / "b2_tf_history.py", HERE / "test_b2_tf_history.py"
    src = mod.read_text(encoding="utf-8")
    ok, line = run(src, mod, test, py)
    print(f"b2_tf_history.py: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits), mod, test, py)
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
