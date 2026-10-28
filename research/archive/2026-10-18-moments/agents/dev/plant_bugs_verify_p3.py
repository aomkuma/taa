"""Planted bugs for verify_p3.py (the second computation of P3's numbers), run against test_verify_p3.py in a temporary
copy (the harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_verify_p3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "verify_p3.py", HERE / "test_verify_p3.py"
BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("metrics: the trail exits not counted", [('EXITS = ("stop", "trail", "target",', 'EXITS = ("stop", "target",')]),
    ("the break-even tick looked for after the exit too", [("if fav[i] >= risk and t[i] <= t[x]]", "if fav[i] >= risk]")]),
    ("the steps before break-even counted", [("keep = st > be", "keep = st >= 0")]),
    ("the stop level never moved", [("lv[i] = max(side * tr[\"entry\"], run[k] if k >= 0 else -np.inf)", "lv[i] = lv[i]")]),
    ("the ticks before the exit not checked", [("crossed = [i for i in range(f + 1, x) if", "crossed = [i for i in range(x, x) if")]),
    ("the trail / stop name not checked", [(" or ((lv[x] != side * tr[\"stop\"]) != (why == \"trail\"))", "")]),
    ("a stale fill passes", [("    if t[f] - tr[\"t_entry\"] > 60 * 10**9:\n        bad.append(", "    if False:\n        bad.append(")]),
    ("the close exit's tick not checked", [('if why in ("structure", "invalid") and not (t[x] >= tr["t_struct"] and t[x - 1] < tr["t_struct"]):',
                                             'if False:')]),
    ("the invalidation price not checked", [('if inv is None or abs(inv - tr["invalid"]) > 1e-9:', "if False:")]),
    ("first_close: the bar before the entry read", [("i0 = int(np.searchsorted(b[\"t_open\"], t_entry, side=\"left\"))\n        i1 = int(np.searchsorted(b[\"avail\"], t_limit, side=\"right\"))\n        for i",
                                                      "i0 = max(int(np.searchsorted(b[\"t_open\"], t_entry, side=\"left\")) - 1, 0)\n        i1 = int(np.searchsorted(b[\"avail\"], t_limit, side=\"right\"))\n        for i")]),
    ("first_close: the bar closing at the limit left out", [("i1 = int(np.searchsorted(b[\"avail\"], t_limit, side=\"right\"))\n        for i", "i1 = int(np.searchsorted(b[\"avail\"], t_limit, side=\"left\"))\n        for i")]),
    ("the trailing values without the buffer", [('ref = b["lt"] - 0.2 * tr["atr"] if side > 0', 'ref = b["lt"] if side > 0')]),
]


def main() -> None:
    py = Path(sys.executable)
    src = MOD.read_text(encoding="utf-8")
    ok, line = run(src, MOD, TEST, py)
    print(f"{MOD.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits), MOD, TEST, py)
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
