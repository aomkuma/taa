"""Planted bugs for verify_d.py (the second computation of Task D), run against test_verify_d.py in a temporary copy (the
harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_verify_d.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "verify_d.py", HERE / "test_verify_d.py"
BUGS = [
    ("metrics: R from the pnl alone", [('rs = [r["pnl"] / r["risk"] for r in rows]', 'rs = [r["pnl"] for r in rows]')]),
    ("metrics: a zero pnl wins", [('return dict(n=n, win=sum(r["pnl"] > 0 for r in rows) / n,', 'return dict(n=n, win=sum(r["pnl"] >= 0 for r in rows) / n,')]),
    ("metrics: the drawdown from zero", [("        peak = max(peak, cum)\n", "        peak = max(0.0, cum)\n")]),
    ("walk: no gap rule", [("        if t[k] - t[k - 1] > 30 * NS_MIN:", "        if False:")]),
    # (an earlier bug - "walk: the target before the stop" - was equivalent: one tick's price cannot be at the stop and
    # at the target at once)
    ("walk: the time before the stop", [("        px = bid[k] if side > 0 else ask[k]\n        if side * (px - stop) <= 0:",
                                         "        px = bid[k] if side > 0 else ask[k]\n        if t[k] >= t_limit:\n            return px, \"time\", t[k]\n        if side * (px - stop) <= 0:")]),
    ("walk: a sell on the bid", [("        px = bid[k] if side > 0 else ask[k]\n", "        px = bid[k]\n")]),
    ("decision: a late open accepted", [("if i0 >= len(D.t) or D.t[i0] > t0 + 5 * NS_MIN:", "if i0 >= len(D.t) or D.t[i0] > t0 + 10 * NS_MIN:")]),
    ("decision: wide at 2 H", [("if math.isnan(H) or hi - lo > 1.5 * H:", "if math.isnan(H) or hi - lo > 2.0 * H:")]),
    ("decision: a close at the high breaks", [("        if D.c[i] > hi:", "        if D.c[i] >= hi:")]),
    ("m1: no spread on a buy", [("entry = D.o[i] + D.spr[i] + SLIP if side > 0 else D.o[i] - SLIP", "entry = D.o[i] + SLIP if side > 0 else D.o[i] - SLIP")]),
    ("straddle: the reference 60 s old allowed", [("if k < 0 or t0 - t[k] > 30 * NS_S:", "if k < 0 or t0 - t[k] > 60 * NS_S:")]),
    ("straddle: no extra slippage", [("entry = ask[j] + SLIP + extra if side > 0 else bid[j] - SLIP - extra", "entry = ask[j] + SLIP if side > 0 else bid[j] - SLIP - extra")]),
    ("events: New York without summer time", [('tz="America/New_York").tz_convert("UTC")', 'tz="Etc/GMT+5").tz_convert("UTC")')]),
    ("select: D1L keeps the level days", [('        if name.startswith("D1L"):\n            rows = [r for r in rows if lv(r)]', '        if name.startswith("D1L"):\n            rows = [r for r in rows if True or lv(r)]')]),
    ("mid: a tick at the time left out", [("    k = bisect.bisect_right(t, at) - 1\n    return (bid[k] + ask[k]) / 2", "    k = bisect.bisect_left(t, at) - 1\n    return (bid[k] + ask[k]) / 2")]),
    ("gap: 40 minutes allowed", [("    return any(t[x + 1] - t[x] > 30 * NS_MIN for x in range(i, j))", "    return any(t[x + 1] - t[x] > 40 * NS_MIN for x in range(i, j))")]),
    ("select: the season at > 63.3", [('rows = [r for r in rows if r["adr20"] >= 63.3]', 'rows = [r for r in rows if r["adr20"] >= 65.0]')]),
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
