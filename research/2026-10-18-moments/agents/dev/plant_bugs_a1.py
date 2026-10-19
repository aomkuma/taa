"""Planted bugs for checkpoint A1: each bug is a small edit of a module's source; its tests must fail on every one
(CAUGHT). Two targets: sweep_detector.py with test_sweep_detector.py (.venv), charts_a1.py with test_charts_a1.py
(data/venv-research, which has matplotlib). The unedited source runs first through the same harness and must pass (the
control). Each edit's text must occur exactly once in the source, so no bug is a silent no-op.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_a1.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PIN = ("HERE = Path(__file__).resolve().parent", f'HERE = Path(r"{HERE}")')  # the copy still finds the data and paths

B1_FIRST = '    b1 = int(np.searchsorted(t, t_rel + first_s * NS_S, side="left"))\n    d = mid[a:b1] - p0'
B1_RACE = '    b1 = int(np.searchsorted(t, t_rel + first_s * NS_S, side="left"))\n    end ='
BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("p0 = the tick at the release, not the one before",
     [('k0 = int(np.searchsorted(t, t_rel, side="left")) - 1', 'k0 = int(np.searchsorted(t, t_rel, side="right")) - 1')]),
    ("the first minute takes the tick at +60 s too", [(B1_FIRST, B1_FIRST.replace('side="left"', 'side="right"'))]),
    ("a first leg needs more than LEG (strict)", [("np.nonzero(np.abs(d) >= leg)[0]", "np.nonzero(np.abs(d) > leg)[0]")]),
    ("the side = the first LEG-USD move always (the researcher's)",
     [('s1 = s_first if side_rule == "first" or up1 == dn1 else (1 if up1 > dn1 else -1)', "s1 = s_first")]),
    ("a tie goes down instead of to the side that reached LEG first",
     [('if side_rule == "first" or up1 == dn1 else', 'if side_rule == "first" else')]),
    ("leg1 = the first LEG tick, not the minute's extreme", [("x = int(np.argmax(sd))", "x = int(np.nonzero(sd >= leg)[0][0])")]),
    ("t_leg = the first LEG tick either way", [("t_leg=int(t[a + h1])", "t_leg=int(t[a + int(hit[0])])")]),
    ("give_back with the wrong sign", [('give_back=float(leg1 - s1 * (out["c1"] - p0))', 'give_back=float(leg1 + s1 * (out["c1"] - p0))')]),
    ("two_sided by the larger move", [("two_sided=bool(min(up1, dn1) >= leg)", "two_sided=bool(max(up1, dn1) >= leg)")]),
    ("swept_pre counts touching the low", [('bool(p0 - leg1 < out["pre_lo"])', 'bool(p0 - leg1 <= out["pre_lo"])')]),
    ("the pre-release range is 60 minutes", [("t_rel - pre_min * NS_MIN", "t_rel - 2 * pre_min * NS_MIN")]),
    ("the pre-release range takes the first tick after the release", [("pre = mid[min(pa, k0):k0 + 1]", "pre = mid[min(pa, k0):k0 + 2]")]),
    ("c1 = the first tick after the first minute", [("c1=float(mid[b1 - 1]) if b1 > a else p0", "c1=float(mid[b1]) if b1 > a else p0")]),
    ("the race starts at the release (the first minute inside it)",
     [(B1_RACE, B1_RACE.replace("t_rel + first_s * NS_S", "t_rel"))]),
    ("the first research definition: continued = RUN past p0 its way, raced from the release",
     [(B1_RACE, B1_RACE.replace("t_rel + first_s * NS_S", "t_rel")),
      ("np.nonzero(e > leg1 + cont_extra)[0]", "np.nonzero(e >= run)[0]")]),
    ("continued ignores cont_extra (any new extreme)", [("e > leg1 + cont_extra", "e > leg1")]),
    ("continued counts exactly one LEG beyond", [("e > leg1 + cont_extra", "e >= leg1 + cont_extra")]),
    ("faked needs more than RUN (strict)", [("np.nonzero(e <= -run)[0]", "np.nonzero(e < -run)[0]")]),
    ("the race window counts from the decision, not the release",
     [("end = int(np.searchsorted(t, t_rel + win_min * NS_MIN", "end = int(np.searchsorted(t, t_rel + first_s * NS_S + win_min * NS_MIN")]),
    ("the sweep = where it first passed RUN, not its extreme", [("j = b1 + int(np.argmin(e))", "j = b1 + fi")]),
    ("back measured from p0, not from the sweep's extreme", [("back = float(after[k] + sweep)", "back = float(after[k])")]),
    ("back's window counts from the release", [("t[j] + back_min * NS_MIN", "t_rel + back_min * NS_MIN")]),
    ("the third leg needs more than p0 (strict)", [("after[k] >= 0", "after[k] > 0")]),
    ("came_down needs more than half (strict)", [("back >= came_down * sweep", "back > came_down * sweep")]),
    ("swept_other looks at the wrong side", [('fm["pre_hi"]) if s1 < 0 else', 'fm["pre_hi"]) if s1 > 0 else')]),
    ("t_back one tick early", [("t_back=int(t[j + 1 + k])", "t_back=int(t[j + k])")]),
    ("a faked one decided at the sweep's extreme", [("t_decided=int(t[b1 + fi])", "t_decided=int(t[j])")]),
    ("a continued one decided at its extreme", [("t_decided=int(t[b1 + ci])", "t_decided=int(t[j])")]),
    ("cont measured from p0, not from leg1", [("cont=float(e[j - b1] - leg1)", "cont=float(e[j - b1])")]),
    ("detect ignores side_rule", [("fm = first_minute(t, mid, t_rel, side_rule=side_rule)", "fm = first_minute(t, mid, t_rel)")]),
    ("the exam guard lets the exam's first day in", [("if d >= EXAM_START:", "if d > EXAM_START:")]),
    ("the fixed minutes in UTC, not New York", [("minute=mm, tz=NY)", 'minute=mm, tz="UTC")')]),
    ("the fixed minutes take Saturdays", [("if d.weekday() >= 5:", "if d.weekday() >= 6:")]),
    ("the fixed minutes may reach the exam",
     [('    if end > EXAM_START:\n        raise ExamPeriodError("the event list may not reach the exam period")\n    rows = []',
       "    rows = []")]),
    ("the calendar may reach the exam",
     [('    if end > EXAM_START:\n        raise ExamPeriodError("the event list may not reach the exam period")\n    a = gold',
       "    a = gold")]),
    ("the extra releases read as UTC", [('.dt.tz_localize(NY).dt.tz_convert("UTC")', '.dt.tz_localize("UTC")')]),
    ("the calendar keeps releases after the end", [("c = c[(c.t >= start) & (c.t < end)]", "c = c[(c.t >= start)]")]),
    ("the calendar keeps one name a minute", [('"+".join(sorted(set(s)))', "s.iloc[0]")]),
    ("scan detects on the bid, not the mid", [("mid = (bid + ask) / 2", "mid = bid")]),
    ("scan drops the event's columns", [("rows.append({**r._asdict(), **x})", "rows.append(x)")]),
    ("M1 labelled by the minute's close", [("m = (t[s] // NS_MIN) * NS_MIN", "m = (t[s] // NS_MIN + 1) * NS_MIN")]),
    ("M1 close = the minute's high", [("close=g.last()", "close=g.max()")]),
    ("Thai time = Tokyo time", [('"Asia/Bangkok"', '"Asia/Tokyo"')]),
    ("summary swaps faked and continued",
     [('faked=int(oc.get("faked", 0)), continued=int(oc.get("continued", 0))',
       'faked=int(oc.get("continued", 0)), continued=int(oc.get("faked", 0))')]),
    ("summary counts the faked days only", [("days=len(D)", "days=len(F)")]),
    # the three the measurer's own planted bugs found missing (2026-10-19 11:16 Thai)
    ("a tie always goes up",
     [('s1 = s_first if side_rule == "first" or up1 == dn1 else (1 if up1 > dn1 else -1)',
       's1 = s_first if side_rule == "first" else (1 if up1 >= dn1 else -1)')]),
    ("swept_pre counts touching the high", [('bool(p0 + leg1 > out["pre_hi"])', 'bool(p0 + leg1 >= out["pre_hi"])')]),
    ("the third leg = back >= 0.9 x the sweep",
     [("third=bool(len(after) and after[k] >= 0)", "third=bool(len(after) and back >= 0.9 * sweep)")]),
]


def mutate(src: str, edits: list[tuple[str, str]]) -> str:
    for old, new in edits:
        n = src.count(old)
        if n != 1:
            raise ValueError(f"the bug's text occurs {n} times, not once: {old!r}")
        src = src.replace(old, new)
    return src


CHART_BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("pick: the median of the cases left, not of all",
     [("dist = (v - v.median()).abs()", "dist = (v[~v.index.isin(used)] - v[~v.index.isin(used)].median()).abs()")]),
    ("pick: a tie goes to the later case", [(".abs().sort_index().sort_values(", ".abs().sort_index(ascending=False).sort_values(")]),
    ("pick: continued cases at minutes without a release too",
     [('C = fx[(fx.outcome == "continued") & (fx.names != "")]', 'C = fx[(fx.outcome == "continued")]')]),
    ("pick: 'largest' does not skip the cases drawn", [("v = v[~v.index.isin(used)].sort_index()", "v = v.sort_index()")]),
    ("pick: the side rules compared at new extreme +0",
     [("(A.cont_extra == CONT_EXTRA)]\n           .pivot_table", "(A.cont_extra == 0.0)]\n           .pivot_table")]),
    ("pick: the strict rule read on the first-move side",
     [('(A.side_rule == "larger") & (A.cont_extra == 0.0)', '(A.side_rule == "first") & (A.cont_extra == 0.0)')]),
    ("headline: the sweep's side not flipped",
     [('other = "down" if r["first"] > 0 else "up"', 'other = "up" if r["first"] > 0 else "down"')]),
    ("headline: 'through p0' never said", [('(", through p0)" if r.third else ")")', '")"')]),
    ("variant_labels: the detector not first", [("ascending=[True, False, False]", "ascending=[False, False, False]")]),
    ("xmin in seconds", [("return (t_ns - rel) / NS_MIN", "return (t_ns - rel) / NS_S")]),
    ("draw: the exam guard checks the release only",
     [("if rel + AFTER * NS_MIN >= EXAM_START.value:", "if rel >= EXAM_START.value:")]),
    ("draw: the title in UTC, not Thai time",
     [('th = pd.Timestamp(rel, tz="UTC").tz_convert("Asia/Bangkok")', 'th = pd.Timestamp(rel, tz="UTC")')]),
]
TARGETS = [  # (the module, its tests, the python that runs them, the bugs)
    (HERE / "sweep_detector.py", HERE / "test_sweep_detector.py", Path(sys.executable), BUGS),
    (HERE / "charts_a1.py", HERE / "test_charts_a1.py", ROOT / "data/venv-research/Scripts/python.exe", CHART_BUGS),
]


def run(src: str, mod: Path, test: Path, py: Path) -> tuple[bool, str]:
    """The tests on this source in a temporary copy: (passed, the first failing test or the summary line)."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / mod.name).write_text(mutate(src, [PIN]), encoding="utf-8")
        shutil.copy(test, d / test.name)
        r = subprocess.run([str(py), "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-W", "ignore", str(d / test.name)],
                           cwd=ROOT, capture_output=True, text=True, check=False)
        failed = re.findall(r"FAILED \S+::(\S+)", r.stdout)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]
        return r.returncode == 0, failed[0] if failed else last


def main() -> None:
    total = caught = 0
    for mod, test, py, bugs in TARGETS:
        src = mod.read_text(encoding="utf-8")
        ok, line = run(src, mod, test, py)
        print(f"\n{mod.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
        if not ok:
            raise SystemExit("the unedited source must pass first")
        for name, edits in bugs:
            total += 1
            ok, line = run(mutate(src, edits), mod, test, py)
            caught += not ok
            print(f"{'MISSED' if ok else 'CAUGHT'}  #{total:02d} {mod.stem}: {name}  ({line})", flush=True)
    print(f"\n{caught} of {total} planted bugs caught")


if __name__ == "__main__":
    main()
