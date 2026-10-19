"""Planted bugs for Task P: each a small edit of the source run against its tests in a temporary copy (the harness of
plant_bugs_a1.py); every one must make a test fail (CAUGHT). Two targets: patterns.py with test_patterns.py (.venv) and
charts_p.py with test_charts_p.py (data/venv-research). The unedited source runs first.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_p.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import ROOT, mutate, run  # noqa: E402

NM = '    n = int(np.searchsorted(pc, d, side="right"))\n    tr = pp[:n]'
NS = '    n = int(np.searchsorted(pc, d, side="right"))\n    out = [('
BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("load_m1 may read into the exam", [('    if end > EXAM_START:\n        raise ExamPeriodError("M1 may not be read into the exam period")\n', "")]),
    ("a TF bar known one minute early", [('b["avail"] = b.index + pd.Timedelta(minutes=minutes)', 'b["avail"] = b.index + pd.Timedelta(minutes=minutes - 1)')]),
    ("a TF bar's close = its high", [("close=g.close.last()", "close=g.close.max()")]),
    ("zigzag: the first pivot needs more than the threshold", [("if h[hi_i] - lo[lo_i] >= thr:", "if h[hi_i] - lo[lo_i] > thr:")]),
    ("zigzag: a peak needs more than the threshold", [("elif h[ext] - lo[i] >= thr:", "elif h[ext] - lo[i] > thr:")]),
    ("zigzag: a trough needs more than the threshold", [("elif h[i] - lo[ext] >= thr:", "elif h[i] - lo[ext] > thr:")]),
    ("zigzag: an equal high does not move the peak", [("if h[i] >= h[ext]:", "if h[i] > h[ext]:")]),
    ("zigzag: an equal low does not move the trough", [("if lo[i] <= lo[ext]:", "if lo[i] < lo[ext]:")]),
    ("zigzag: the first pivot is the later extreme", [("if lo_i < hi_i:", "if lo_i > hi_i:")]),
    ("structure: a pivot confirmed AT d left out", [(NS, NS.replace('side="right"', 'side="left"'))]),
    ("structure: the running extreme includes the pivot's own bar", [("seg = slice(last_b + 1, d + 1)", "seg = slice(last_b, d + 1)")]),
    ("structure: the running trough's tie goes to the later bar",
     [("j = last_b + 1 + int(np.argmin(lo[seg]))", "j = d - int(np.argmin(lo[seg][::-1]))")]),
    ("structure: one pivot too many kept", [("range(max(n - keep, 0), n)", "range(max(n - keep - 1, 0), n)")]),
    ("first close: at the line counts as above", [("c[d] > line[-1]", "c[d] >= line[-1]")]),
    ("first close: the pattern's last low bar not checked", [("np.all(c[a:d] <= line[:-1])", "np.all(c[a + 1:d] <= line[1:-1])")]),
    ("find_buy: the last trough is always the last item", [("k3 = len(seq) - 1 if seq[-1][2] == -1 else len(seq) - 2", "k3 = len(seq) - 1")]),
    ("W: equal lows strict", [("if abs(t3[1] - t2[1]) <= eq:", "if abs(t3[1] - t2[1]) < eq:")]),
    ("W: EQ ignores the height", [("eq = max(EQ_ATR * atr, EQ_H * hgt)", "eq = EQ_ATR * atr")]),
    ("W: the swept second low may go twice as deep", [("t2[1] - SWEEP_W_H * hgt <= t3[1]", "t2[1] - 2 * SWEEP_W_H * hgt <= t3[1]")]),
    ("W: 5 bars more span", [('if d - t2[0] <= SPAN["w"]:', 'if d - t2[0] <= SPAN["w"] + 5:')]),
    ("the higher low needs no margin", [("t3[1] > t2[1] + eq:", "t3[1] > t2[1]:")]),
    ("IHS: the head need not be 0.5 ATR lower", [("t2[1] < min(t1[1], t3[1]) - HEAD_ATR * atr", "t2[1] < min(t1[1], t3[1])")]),
    ("IHS: the shoulders twice as loose", [("abs(t1[1] - t3[1]) <= SHOULDER_H * hgt", "abs(t1[1] - t3[1]) <= 2 * SHOULDER_H * hgt")]),
    ("IHS: no neckline slope rule", [("and abs(p2[1] - p1[1]) <= NECK_H * hgt and", "and")]),
    ("IHS: the height from the left neck point", [("hgt = p1[1] + slope * (t2[0] - p1[0]) - t2[1]", "hgt = p1[1] - t2[1]")]),
    ("IHS: the trigger = the right neck point", [("trigger=float(line[-1])", "trigger=float(p2[1])")]),
    ("IHS: the span strict", [('if d - t1[0] <= SPAN["ihs"] and', 'if d - t1[0] < SPAN["ihs"] and')]),
    ("IHS: the neckline anchored on the wrong point", [("np.arange(t3[0], d + 1) - p1[0])", "np.arange(t3[0], d + 1) - p2[0])")]),
    ("base: the width from the breakout bar's ATR", [("w = BASE_W * atr[d - 1]", "w = BASE_W * atr[d]")]),
    ("base: 7 bars are enough", [("if n >= BASE_MIN:", "if n >= BASE_MIN - 1:")]),
    ("base: a close at the high breaks it", [("side = 1 if c[d] > hi", "side = 1 if c[d] >= hi")]),
    ("base: the box one bar short", [("box=(d - n, d - 1, low, hi)", "box=(d - n + 1, d - 1, low, hi)")]),
    ("mirror: the kinds not flipped", [("return pb, -pp, -pk, pc", "return pb, -pp, pk, pc")]),
    ("unmirror: the trigger stays mirrored", [('for key in ("extreme", "trigger", "higher_low"):', 'for key in ("extreme", "higher_low"):')]),
    ("the stop on the wrong side", [('p["stop"] = p["extreme"] - p["side"] * STOP_ATR * atr[d]', 'p["stop"] = p["extreme"] + p["side"] * STOP_ATR * atr[d]')]),
    ("at_level: exactly one zone away is out", [("if abs(ext - lv) <= z:", "if abs(ext - lv) < z:")]),
    ("at_level: the sweep may go twice as far", [("elif 0 < past <= sweep and", "elif 0 < past <= 2 * sweep and")]),
    ("at_level: a sweep need not close back", [("elif 0 < past <= sweep and s * (close - (lv - s * z)) > 0:", "elif 0 < past <= sweep:")]),
    ("at_level: the sweep-turn may sit at the level", [('(how != "swept" or', '(how not in ("swept", "at") or')]),
    ("at_level: the higher low need not be back", [(' or s * (p["higher_low"] - (lv - s * z)) < 0)', ")")]),
    ("at_level: the base must cover the level itself", [("(lo_b <= lv + z and hi_b >= lv - z)", "(lo_b <= lv and hi_b >= lv)")]),
    ("at_level: the first level wins, not the nearest", [('if best is None or dist < best["dist"]:', "if best is None:")]),
    ("next_level: the pattern's own level not excluded", [("(np.abs(levels - own) > z) & ", "")]),
    ("next_level: min / max swapped", [("float(v.min() if side > 0 else v.max())", "float(v.max() if side > 0 else v.min())")]),
    ("m_structure: up on either", [("if tr[1] > tr[0] and pk_[1] > pk_[0]:", "if tr[1] > tr[0] or pk_[1] > pk_[0]:")]),
    ("m_structure: a pivot confirmed AT d left out", [(NM, NM.replace('side="right"', 'side="left"'))]),
    ("locate: the decision at the bar's open", [("t_dec = int(tf.avail[d])", "t_dec = int(tf.t_open[d])")]),
    ("locate: the entry at the decision bar's close", [("entry = float(tf.o[e_i]) if", "entry = close if")]),
    ("locate: the news level lives 30 minutes", [("(t_dec <= news.t_rel + NEWS_MIN * NS_MIN)", "(t_dec <= news.t_rel + 2 * NEWS_MIN * NS_MIN)")]),
    ("locate: the news side not flipped", [('(news["first"] == -p["side"])', '(news["first"] == p["side"])')]),
    ("locate: decisions before the learning start kept", [("if not (LEARN_START.value <= t_dec < EXAM_START.value):", "if not (t_dec < EXAM_START.value):")]),
    ("news_levels: the wrong side of the release bar", [('lv = m1.lo[j] if fm["first"] < 0 else m1.h[j]', 'lv = m1.h[j] if fm["first"] < 0 else m1.lo[j]')]),
    ("agree: no time window", [(" & (B.t_dec >= r.t_dec - AGREE_MIN * NS_MIN)", "")]),
    ("agree: any level", [(" & ((B.level - r.level).abs() <= r.zone)", "")]),
    ("agree: either side", [("q = B[(B.side == r.side) &", "q = B[(B.side == B.side) &")]),
    ("patterns_at: the height cap twice as loose", [('p["height"] <= HEIGHT_ATR * atr[d]]', 'p["height"] <= 2 * HEIGHT_ATR * atr[d]]')]),
    ("unmirror: the sell keeps the buy name", [('    q["variant"] = SELL_NAMES[p["variant"]]\n', "")]),
    ("unmirror: the sell keeps the buy labels", [("SELL_LABELS.get(lab, lab)", "lab")]),
]


CHART_BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("pick: the earliest, not the nearest the middle", [('dist=(q.t_dec - MID[s["part"]]).abs()', "dist=q.t_dec")]),
    ("pick: a tie not broken by the earlier", [('.sort_values(["dist", "t_dec"], kind="stable")', '.sort_values(["dist"], kind="stable")')]),
    ("pick: a moment drawn before may be drawn again", [("used.add((r.tf, r.t_dec))", "used.add((r.tf, r.t_dec, r.family))")]),
    ("pick: an M5 entry without an M1 pattern", [('            q = q[q.other_pattern != ""]\n', "")]),
    ("pick: H1 slots take catches off the H1 levels",
     [('q = q[q.at_h1] if s["where"] == "h1" else q[q.at_news]', 'q = q if s["where"] == "h1" else q[q.at_news]')]),
    ("pick: the side ignored", [('        if s["side"]:\n            q = q[q.side == s["side"]]\n', "")]),
    ("pick: the owner's release not first",
     [('if s["where"] == "news" and s["part"] == "P1" and (q.news_t == OWNER_NEWS).any():', "if False:")]),
    ("pick: the owner's release, the latest catch",
     [('q = q[q.news_t == OWNER_NEWS].sort_values("t_dec")', 'q = q[q.news_t == OWNER_NEWS].sort_values("t_dec", ascending=False)')]),
    ("slots: the families in another order", [('FAMILIES = ("ihs", "w", "st", "base")', 'FAMILIES = ("w", "ihs", "st", "base")')]),
    ("title: the risk signed", [("risk = abs(r.entry - r.stop)", "risk = r.entry - r.stop")]),
    ("thai: UTC on the axis", [('tz_convert("Asia/Bangkok").strftime(fmt)', 'tz_convert("UTC").strftime(fmt)')]),
    ("agreement: the other TF named wrong", [('other = "M5" if r.tf == "M1" else "M1"', 'other = "M1" if r.tf == "M1" else "M5"')]),
    ("label_below: a sell's tops below", [('return lab in ("T", "N1", "N2")', 'return lab not in ("T", "N1", "N2")')]),
]
TARGETS = [  # (the module, its tests, the python that runs them, the bugs)
    (HERE / "patterns.py", HERE / "test_patterns.py", Path(sys.executable), BUGS),
    (HERE / "charts_p.py", HERE / "test_charts_p.py", ROOT / "data/venv-research/Scripts/python.exe", CHART_BUGS),
]


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
