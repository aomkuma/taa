"""Planted bugs for swings.py (V3-1), each run against test_swings.py in a temporary copy; every one must make a test
fail (CAUGHT). The loaders are not mutated: a mutant that widened their filter would read the exam period.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/plant_bugs_v31.py > research/2026-10-18-moments/agents/dev2/out_plant_bugs_v31.txt
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MOD, TEST = HERE / "swings.py", HERE / "test_swings.py"
PRE = HERE.parent / "precursors"

BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("zigzag: a tie moves the peak to the later bar", [("            if h[i] > h[ext]:\n                ext = i", "            if h[i] >= h[ext]:\n                ext = i")]),
    ("zigzag: the reversal must exceed the threshold (>)", [("            elif h[ext] - lo[i] >= thr[i]:", "            elif h[ext] - lo[i] > thr[i]:")]),
    ("zigzag: one bar both extends and confirms (two turns)", [("            elif h[ext] - lo[i] >= thr[i]:", "            if h[ext] - lo[i] >= thr[i]:")]),
    ("zigzag: the first pivot from one wide bar", [("if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr[i]:", "if h[hi_i] - lo[lo_i] >= thr[i]:")]),
    ("zigzag: the later extreme taken as the first pivot", [("                if lo_i < hi_i:", "                if lo_i > hi_i:")]),
    ("zigzag: the trough tracked from the peak's own bar", [("                piv.append((ext, float(h[ext]), 1, i))\n                direction, ext = -1, i",
                                                             "                piv.append((ext, float(h[ext]), 1, i))\n                direction, ext = -1, ext")]),
    ("size: 0.5 x the H1 ATR", [("S_ATR = 0.6", "S_ATR = 0.5")]),
    ("size: the H1 bar complete at the close left out", [('k = np.searchsorted(_ns(m_h1["avail"]), t_ns, side="right") - 1', 'k = np.searchsorted(_ns(m_h1["avail"]), t_ns, side="left") - 1')]),
    ("size: the floor 10 dropped", [("    out[ok] = np.maximum(S_FLOOR, S_ATR * a[k[ok]])", "    out[ok] = S_ATR * a[k[ok]]")]),
    ("atr warm-up: the first bar's true range left NaN", [("        tr[0] = h[0] - lo[0]", "        tr[0] = np.nan")]),
    ("threshold: the TF's ATR term dropped", [("    return np.maximum(s, TF_ATR * a)", "    return s")]),
    ("structure: the running low ignored", [("        if dirs[j] == -1 and troughs and lo[e] < pp[troughs[-1]]:", "        if False:")]),
    ("structure: the running high ignored", [("        if dirs[j] == 1 and peaks and h[e] > pp[peaks[-1]]:", "        if False:")]),
    ("structure: up on HH alone", [('st["label"][j] = 1.0 if hs == 1 and ls == 1 else', 'st["label"][j] = 1.0 if hs == 1 else')]),
    ("structure: equal counts as higher", [("    return 1.0 if new > old else -1.0 if new < old else 0.0", "    return 1.0 if new >= old else -1.0 if new < old else 0.0")]),
    ("bias: a close AT the peak breaks it", [("if peaks and not pk_broken and c[j] > pp[peaks[-1]]:", "if peaks and not pk_broken and c[j] >= pp[peaks[-1]]:")]),
    ("bias: a trough broken again and again", [("if troughs and not tr_broken and c[j] < pp[troughs[-1]]:", "if troughs and c[j] < pp[troughs[-1]]:")]),
    ("box: the band 2 x S", [("BOX_MAX = 3.0", "BOX_MAX = 2.0")]),
    ("box: no halves rule", [("    return all((p >= mid) if k == 1 else (p <= mid) for p, k in zip(prices, kinds))", "    return True")]),
    ("box: born with 3 pivots", [("BOX_MIN = 4", "BOX_MIN = 3")]),
    ("box: members from before the accepted break", [("                    if pb[x] <= last_accept:\n                        break", "                    if False:\n                        break")]),
    ("break: one close accepts", [("ACCEPT = 2", "ACCEPT = 1")]),
    ("retest: no need to move away first", [('        if self.state == "wait_away":\n            if lx <= lv - rt:', '        if self.state == "wait_away":\n            if True:')]),
    ("retest: fails at a close below the level itself", [("            if cx < lv - rt:", "            if cx < lv:")]),
    ("retest: the retest distance 0.5 x S", [("RT = 0.25", "RT = 0.5")]),
    ("reclaim: one close back", [("        if self.rc == ACCEPT:", "        if self.rc == 1:")]),
    ("lines: the support anchor by the smallest slope", [("k = int(np.argmax(slopes)) if kind == -1 else int(np.argmin(slopes))", "k = int(np.argmin(slopes)) if kind == -1 else int(np.argmax(slopes))")]),
    ("lines: closes between the anchors not checked", [("ok = (sl > 0 and not np.any(c[between] < vals)) if kind == -1", "ok = (sl > 0) if kind == -1")]),
    ("lines: the touch tolerance 0.1 x S", [("TOUCH = 0.2", "TOUCH = 0.1")]),
    ("lines: one earlier pivot tried", [("LINE_BACK = 5", "LINE_BACK = 1")]),
    ("lines: the value one minute late", [('v = row["pa"] + row["slope"] * (t_min[j] - row["ta"])', 'v = row["pa"] + row["slope"] * (t_min[j] + 1 - row["ta"])')]),
    ("fib: the levels on the wrong side", [("levels={f: end - f * (end - start) for f in FIB}", "levels={f: end + f * (end - start) for f in FIB}")]),
    ("fib: the first leg, not the last", [("    start, end = float(pp[-2]), float(pp[-1])", "    start, end = float(pp[0]), float(pp[1])")]),
    ("edge tests: the top half, not the quarter", [("TOP_Q = 0.25", "TOP_Q = 0.5")]),
    ("inner swings: 0.5 x S", [("        inn = zigzag(h, lo, INNER * s_bar)", "        inn = zigzag(h, lo, 0.5 * s_bar)")]),
    ("tf_bars: avail = the last minute's open", [('    b["avail"] = b["last"] + pd.Timedelta(minutes=1)\n    b["t"]', '    b["avail"] = b["last"]\n    b["t"]')]),
    ("readings_at: the next bar's reading", [('out[f"{tf}_{what}"] = np.where(j >= 0, v[np.maximum(j, 0)], np.nan)',
                                             'out[f"{tf}_{what}"] = np.where(j >= 0, v[np.minimum(j + 1, len(v) - 1)], np.nan)')]),
    ("readings_at: the bias column holds the label", [('            v = r.struct[what].to_numpy(float)', '            v = r.struct["label"].to_numpy(float)')]),
    ("D1: the clock day, not the server day", [('    if rule in ("4h", "1D"):\n        key = m.index.tz_convert("Europe/Athens")',
                                                '    if rule in ("4h",):\n        key = m.index.tz_convert("Europe/Athens")')]),
    ("side: H1 against not checked", [("        buy = (d1 == 1) & (h4 == 1) & (h1 != -1)", "        buy = (d1 == 1) & (h4 == 1)")]),
    ("side: H1 must agree (mixed refused)", [("        sell = (d1 == -1) & (h4 == -1) & (h1 != 1)", "        sell = (d1 == -1) & (h4 == -1) & (h1 == -1)")]),
    ("side: D1 alone", [("        buy = (d1 == 1) & (h4 == 1) & (h1 != -1)", "        buy = (d1 == 1) & (h1 != -1)")]),
    ("side: unknown read as no side", [('        out[f"side{sfx}"] = np.where(known, np.where(buy, 1.0, np.where(sell, -1.0, 0.0)), np.nan)',
                                        '        out[f"side{sfx}"] = np.where(buy, 1.0, np.where(sell, -1.0, 0.0))')]),
    ("trend: H1 left out", [("        up = (a == 1) & (b == 1) & (c == 1)", "        up = (a == 1) & (b == 1)")]),
    ("trend: the bias reading takes the labels", [('    for what, sfx in (("label", ""), ("bias", "_bias")):', '    for what, sfx in (("label", ""), ("label", "_bias")):')]),
    ("at: the bar complete at the moment left out", [('return np.searchsorted(_ns(self.bars["avail"]), np.asarray(t_ns, np.int64), side="right") - 1',
                                                     'return np.searchsorted(_ns(self.bars["avail"]), np.asarray(t_ns, np.int64), side="left") - 1')]),
]

# the temporary copy keeps the real folders for its imports and data
PIN_MOD = ("HERE = Path(__file__).resolve().parent", f"HERE = Path(r\"{HERE}\")")
PIN_TEST = ('sys.path.insert(0, str(HERE.parent / "precursors"))', f'sys.path.insert(1, r"{PRE}")')


def mutate(src: str, edits: list[tuple[str, str]]) -> str:
    for old, new in edits:
        n = src.count(old)
        if n != 1:
            raise ValueError(f"the bug's text occurs {n} times, not once: {old!r}")
        src = src.replace(old, new)
    return src


def run(src: str) -> tuple[bool, str]:
    """An error (not a failing test) is no catch: the run is repeated up to 3 times (Windows temp-folder races were
    seen while another job ran); an error left after that is reported as ERROR."""
    for _ in range(3):
        ok, line = _run_once(src)
        if ok or " error" not in line:
            return ok, line
    return True, f"ERROR, not a catch: {line}"


def _run_once(src: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / MOD.name).write_text(mutate(src, [PIN_MOD]), encoding="utf-8")
        (d / TEST.name).write_text(mutate(TEST.read_text(encoding="utf-8"), [PIN_TEST]), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-W", "ignore", str(d / TEST.name)],
                           cwd=ROOT, capture_output=True, text=True, check=False)
        failed = re.findall(r"FAILED \S+::(\S+)", r.stdout)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]
        if not failed and " error" in last:  # an error is not a catch: show it
            errs = [x for x in r.stdout.splitlines() if x.startswith(("ERROR", "E "))][:3]
            last = f"{last} | {' / '.join(errs)}"
        return r.returncode == 0, failed[0] if failed else last


def main() -> None:
    src = MOD.read_text(encoding="utf-8")
    ok, line = run(src)
    print(f"{MOD.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits))
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
