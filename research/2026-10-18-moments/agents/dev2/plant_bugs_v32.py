"""Planted bugs for V3-2 (v32.py, tsim32.py, v32_run.py's metrics, swings.py rules 18-19), each run against
test_v32.py in a temporary copy of the modules; every one must make a test fail (CAUGHT). The loaders are not mutated.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/plant_bugs_v32.py > research/2026-10-18-moments/agents/dev2/out_plant_bugs_v32.txt
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FILES = ["swings.py", "v32.py", "tsim32.py", "v32_run.py", "test_swings.py", "test_v32.py"]
TEST = "test_v32.py"
# pins: swings' data paths and tsim32's tick folder stay the real ones; v32 / v32_run / the tests import from the copy
PINS = {"swings.py": [("HERE = Path(__file__).resolve().parent", f'HERE = Path(r"{HERE}")')],
        "tsim32.py": [('TICKS = Path(__file__).resolve().parents[4] / "data" / "ticks" / "XAUUSD"', f'TICKS = Path(r"{ROOT}") / "data" / "ticks" / "XAUUSD"')]}

BUGS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("v32.py", "window: Asia to 03:00 UTC", [('out[(u >= 0) & (u < 120)] = "Asia"', 'out[(u >= 0) & (u < 180)] = "Asia"')]),
    ("v32.py", "window: New York on a fixed UTC-4 (no summer time)", [('    ny = t.tz_convert("America/New_York")\n    n = np.asarray(ny.hour', '    ny = t.tz_convert("Etc/GMT+4")\n    n = np.asarray(ny.hour')]),
    ("v32.py", "window: the NY open ends at 13:00", [('out[(n >= 570) & (n < 810)] = "NYopen"', 'out[(n >= 570) & (n < 780)] = "NYopen"')]),
    ("v32.py", "entry TF: the low tercile includes q1", [('np.where(h < q1, "M1"', 'np.where(h <= q1, "M1"')]),
    ("v32.py", "entry TF: low volatility -> M15", [('np.where(h < q1, "M1", np.where(h < q2, "M5", "M15"))', 'np.where(h < q1, "M15", np.where(h < q2, "M5", "M1"))')]),
    ("v32.py", "entry 1: the stop on the wrong side of the extreme", [('    df["stop"] = df.ext - df.side * BUF * df.S\n    df["line"]', '    df["stop"] = df.ext + df.side * BUF * df.S\n    df["line"]')]),
    ("v32.py", "entry 1: traded against the break", [('"side": rf.side.to_numpy(int)', '"side": -rf.side.to_numpy(int)')]),
    ("v32.py", "entry 1: 'first' marks the second fail", [('rf.groupby(["tag", "obj"]).cumcount() == 0', 'rf.groupby(["tag", "obj"]).cumcount() == 1')]),
    ("v32.py", "aligned: H1 left out", [("    for x in UP_TFS[UP_TFS.index(tf):]:", "    for x in UP_TFS[UP_TFS.index(tf):-1]:")]),
    ("v32.py", "reading: the mode ignored (always the bars)", [('    r = mk.R[f"{tf}@M1"] if mode == "path" and tf != "M1" else mk.R[tf]', '    r = mk.R[tf]')]),
    ("v32.py", "base: 3 x ATR", [("BASE_ATR = 2.0", "BASE_ATR = 3.0")]),
    ("v32.py", "base: 5 bars", [("BASE_N = 6", "BASE_N = 5")]),
    ("v32.py", "base: the ATR at the base's last bar", [("    atr_prev = np.r_[np.full(BASE_N, np.nan), atr[:-BASE_N]] if n > BASE_N else np.full(n, np.nan)", "    atr_prev = atr")]),
    ("v32.py", "base: a trigger on every bar it holds", [("        trig = cond & ~np.r_[False, cond[:-1]]", "        trig = cond")]),
    ("v32.py", "base: no need to sit beyond the pivot", [("        beyond = (hi6 < pprice) if side < 0 else (lo6 > pprice)", "        beyond = np.ones(n, bool)")]),
    ("v32.py", "entry 2: the stop inside", [('    df["stop"] = df.piv - df.side * BUF * df.S', '    df["stop"] = df.piv + df.side * BUF * df.S')]),
    ("v32.py", "entry 3: traded with the break", [('    df["side"] = -df.brk', '    df["side"] = df.brk')]),
    ("v32.py", "entry 3: the ext stop on the wrong side", [('    df["stop_ext"] = df.ext - df.side * hb', '    df["stop_ext"] = df.ext + df.side * hb')]),
    ("v32.py", "entry 3: the mirrored stop from the wrong side", [("    same_stop = df.rext.to_numpy(float) - df.brk.to_numpy(float) * buf", "    same_stop = df.rext.to_numpy(float) + df.brk.to_numpy(float) * buf")]),
    ("v32.py", "entry 3: the break's extreme from the decision bar only", [("        seg = slice(int(bb[i]), int(e.bar) + 1)", "        seg = slice(int(e.bar), int(e.bar) + 1)")]),
    ("v32.py", "entry 4: the fake leg 0.5 x S", [("FAKE_A = 0.3", "FAKE_A = 0.5")]),
    ("v32.py", "entry 4: p0 from the second bar", [("        p0 = mo[i0]\n", "        p0 = mo[i0 + 1]\n")]),
    ("v32.py", "trail: pivots from before the decision", [("    sel = (pk == want) & (pb >= j_dec) & (pc > j_dec)", "    sel = (pk == want) & (pc > j_dec)")]),
    ("v32.py", "trail: the buffer on the wrong side", [("            out.append((int(av[c]), float(p - side * BUF * s)))", "            out.append((int(av[c]), float(p + side * BUF * s)))")]),
    ("v32.py", "trail: dated at the pivot's own bar", [("    for p, c in zip(pp[sel], pc[sel]):", "    for p, c in zip(pp[sel], pb[sel]):")]),
    ("tsim32.py", "fill: a buy at the bid", [("    fill = ask[f] + slip if side > 0 else bid[f] - slip", "    fill = bid[f] + slip if side > 0 else bid[f] - slip")]),
    ("tsim32.py", "stop: filled at the stop price, not the market", [('        i, why, px = i_s, "stop", mkt[i_s]', '        i, why, px = i_s, "stop", stop_arr[i_s]')]),
    ("tsim32.py", "one tick reaching both: the target", [("    if i_s < len(tt) and i_s <= i_t:", "    if i_s < len(tt) and i_s < i_t:")]),
    ("tsim32.py", "trail: a looser step taken", [("np.maximum(stop_arr[k:], lvl) if side > 0 else np.minimum(stop_arr[k:], lvl)", "np.maximum(stop_arr[k:], lvl) if side > 0 else np.full(len(stop_arr) - k, lvl)")]),
    ("tsim32.py", "gap: 60 minutes", [("GAP_NS = 30 * NS_MIN", "GAP_NS = 60 * NS_MIN")]),
    ("tsim32.py", "no fill: 10 minutes allowed", [("MAX_LAG_NS = 5 * NS_MIN", "MAX_LAG_NS = 10 * NS_MIN")]),
    ("tsim32.py", "mirror: the distance from this side's own fill", [("        same = bid[f] - slip if side > 0 else ask[f] + slip", "        same = fill")]),
    ("tsim32.py", "time: the tick before t_out", [('    end = int(np.searchsorted(t, t_out, side="left"))\n    kind_end', '    end = int(np.searchsorted(t, t_out, side="left")) - 1\n    kind_end')]),
    # (no mutant widens the exam guard: a mutant that passed it would read an exam tick file)
    ("tsim32.py", "cache: the oldest-by-date evicted (the KeyError seen in the first run)", [("            for k in list(self.days)[:-4]:", "            for k in sorted(self.days)[:-4]:")]),
    ("v32_run.py", "one at a time: a fill at the previous exit dropped", [("        if a < busy:", "        if a <= busy:")]),
    ("v32_run.py", "drawdown: not from 0", [("    eq = np.r_[0.0, np.cumsum(pnl)]", "    eq = np.cumsum(pnl)")]),
    ("v32_run.py", "streak: a zero is not a loss", [("        cur = cur + 1 if x <= 0 else 0\n        best = max(best, cur)\n    return best", "        cur = cur + 1 if x < 0 else 0\n        best = max(best, cur)\n    return best")]),
    ("v32_run.py", "win: pnl >= 0", [('win=float(np.mean(pnl > 0))', 'win=float(np.mean(pnl >= 0))')]),
    ("v32_run.py", "loser reason: wrong way under 1 R", [("    wrong = T.mfe.to_numpy(float) < 0.5 * risk", "    wrong = T.mfe.to_numpy(float) < 1.0 * risk")]),
    ("swings.py", "path: the TF's ATR term dropped", [("    return np.maximum(s, np.where(j >= 0, TF_ATR * a[np.maximum(j, 0)], 0.0))", "    return s")]),
    ("swings.py", "path: the TF bar complete at the close left out", [('    j = np.searchsorted(_ns(b["avail"]), t, side="right") - 1\n    return np.maximum(s,', '    j = np.searchsorted(_ns(b["avail"]), t, side="left") - 1\n    return np.maximum(s,')]),
    ("swings.py", "readings_at: the path mode ignored", [('        r = R[f"{tf}@M1"] if mode == "path" and tf != "M1" else R[tf]', '        r = R[tf]')]),
    ("swings.py", "box tests: no need to leave", [("        if armed and reach[i]:", "        if reach[i]:")]),
    ("swings.py", "box tests: leaving measured from the top", [("        reach, left = h >= q, lo <= q - s", "        reach, left = h >= q, lo <= top - s")]),
]


def mutate(src: str, edits: list[tuple[str, str]]) -> str:
    for old, new in edits:
        n = src.count(old)
        if n != 1:
            raise ValueError(f"the bug's text occurs {n} times, not once: {old!r}")
        src = src.replace(old, new)
    return src


def run(mut: dict[str, str]) -> tuple[bool, str]:
    for _ in range(3):
        ok, line = _run_once(mut)
        if ok or " error" not in line:
            return ok, line
    return True, f"ERROR, not a catch: {line}"


def _run_once(mut: dict[str, str]) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name in FILES:
            src = mut.get(name, (HERE / name).read_text(encoding="utf-8"))
            (d / name).write_text(mutate(src, PINS.get(name, [])), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-W", "ignore", str(d / TEST)],
                           cwd=ROOT, capture_output=True, text=True, check=False)
        failed = re.findall(r"FAILED \S+::(\S+)", r.stdout)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]
        if not failed and " error" in last:
            errs = [x for x in r.stdout.splitlines() if x.startswith(("ERROR", "E "))][:3]
            last = f"{last} | {' / '.join(errs)}"
        return r.returncode == 0, failed[0] if failed else last


def main() -> None:
    ok, line = run({})
    print(f"control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited sources must pass first")
    caught = 0
    for k, (name, what, edits) in enumerate(BUGS, 1):
        src = (HERE / name).read_text(encoding="utf-8")
        ok, line = run({name: mutate(src, edits)})
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}: {what}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
