"""Planted bugs for d1_orb.py, d2_straddle.py and d2_buckets.py (Task D), each run against its test file in a temporary copy (the
harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_d.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

D1 = [
    ("decide: a late open counts", [("if i0 >= len(t_open) or t_open[i0] - t0 > LATE_OPEN:", "if i0 >= len(t_open) or t_open[i0] - t0 > 2 * LATE_OPEN:")]),
    ("decide: the range one bar short", [("rh, rl = float(h[i0:iL].max()), float(lo[i0:iL].min())", "rh, rl = float(h[i0:iL - 1].max()), float(lo[i0:iL - 1].min())")]),
    ("decide: wide at >= 1.5 H", [("if not np.isfinite(H) or rh - rl > WIDE_H * H:", "if not np.isfinite(H) or rh - rl >= WIDE_H * H:")]),
    ("decide: no H allowed", [("if not np.isfinite(H) or rh - rl > WIDE_H * H:", "if rh - rl > WIDE_H * H:")]),
    ("decide: the window one bar longer", [("iE = int(np.searchsorted(t_open, t0 + (L + ENTRY_WIN) * NS_MIN))", "iE = int(np.searchsorted(t_open, t0 + (L + ENTRY_WIN + 1) * NS_MIN))")]),
    ("decide: a close at the high breaks", [("side = 1 if c[k] > rh else -1 if c[k] < rl else 0", "side = 1 if c[k] >= rh else -1 if c[k] < rl else 0")]),
    ("decide: the stop the range's near side", [("stop=rl if side > 0 else rh, k=k", "stop=rh if side > 0 else rl, k=k")]),
    ("decide: the decision at the bar's open", [("t_dec=int(t_open[k] + NS_MIN)", "t_dec=int(t_open[k])")]),
    # (an earlier bug - "tick: a late fill taken" - was equivalent: simulate3 refuses a fill later than 60 s itself)
    ("tick: out after X + 1 minutes", [("t_limit = int(t[f] + X * NS_MIN)", "t_limit = int(t[f] + (X + 1) * NS_MIN)")]),
    ("tick: the time from the decision", [("t_limit = int(t[f] + X * NS_MIN)", "t_limit = int(t_dec + X * NS_MIN)")]),
    ("tick: the target from the stop", [("tgt = x[\"entry\"] + side * k_r * x[\"risk\"]", "tgt = stop + side * k_r * x[\"risk\"]")]),
    ("m1: a late bar taken", [("if i >= len(o) or t_open[i] != t_open[k_dec] + NS_MIN:", "if i >= len(o):")]),
    ("m1: a buy without the spread", [("entry = o[i] + spr[i] + P2.SLIP if side > 0 else o[i] - P2.SLIP", "entry = o[i] + P2.SLIP if side > 0 else o[i] - P2.SLIP")]),
    ("m1: the target before the stop in one bar", [("        if side * ((ll if side > 0 else hh) - stop) <= 0:\n            px, why, jx = (min(oo, stop) if side > 0 else max(oo, stop)), \"stop\", j\n            break\n        if side * ((hh if side > 0 else ll) - tgt) >= 0:\n            px, why, jx = tgt, \"target\", j\n            break",
                                                    "        if side * ((hh if side > 0 else ll) - tgt) >= 0:\n            px, why, jx = tgt, \"target\", j\n            break\n        if side * ((ll if side > 0 else hh) - stop) <= 0:\n            px, why, jx = (min(oo, stop) if side > 0 else max(oo, stop)), \"stop\", j\n            break")]),
    ("m1: a gap open filled at the stop", [("px, why, jx = (min(oo, stop) if side > 0 else max(oo, stop)), \"stop\", j", "px, why, jx = stop, \"stop\", j")]),
    ("m1: a sell's stop on the bid", [("a = 0.0 if side > 0 else 1.0  # sells exit on the ask", "a = 0.0  # sells exit on the ask")]),
    ("m1: the time exit one bar late", [("        if t_open[j] >= t_lim:", "        if t_open[j] > t_lim:")]),
    ("level: a level at 2 R refuses", [("ok = (d > 0) & (d < k * risk_dec)", "ok = (d > 0) & (d <= k * risk_dec)")]),
    ("level: behind counts", [("ok = (d > 0) & (d < k * risk_dec)", "ok = (d >= 0) & (d < k * risk_dec)")]),
    ("level: the farthest, not the nearest", [("return float(close + side * d[ok].min()) if ok.any() else np.nan", "return float(close + side * d[ok].max()) if ok.any() else np.nan")]),
    ("at_time: the bar complete at t left out", [("k = int(np.searchsorted(avail, t_ns, side=\"right\")) - 1", "k = int(np.searchsorted(avail, t_ns, side=\"left\")) - 1")]),
    ("times: stored as floats", [("    T = pd.DataFrame(rows)\n    for k in TIMES:\n        if k in T:", "    T = pd.DataFrame(rows)\n    for k in ():\n        if k in T:")]),
    ("ADR: 19 days", [("self.adr = pd.Series((d.high - d.low).to_numpy(float)).rolling(20).mean().to_numpy()", "self.adr = pd.Series((d.high - d.low).to_numpy(float)).rolling(19).mean().to_numpy()")]),
]
D2 = [
    ("reference: 31 s still armed", [("if k < 0 or t0 - t[k] > ARM_S * NS_S:", "if k < 0 or t0 - t[k] > (ARM_S + 1) * NS_S:")]),
    ("reference: the tick at t0", [("k = int(np.searchsorted(t, t0, side=\"left\")) - 1", "k = int(np.searchsorted(t, t0, side=\"right\")) - 1")]),
    ("triggered: live 61 s", [("b = int(np.searchsorted(t, t0 + LIVE_S * NS_S, side=\"left\"))", "b = int(np.searchsorted(t, t0 + LIVE_S * NS_S, side=\"right\"))")]),
    ("triggered: ticks before t0 live", [("a = int(np.searchsorted(t, t0, side=\"left\"))\n    b = int", "a = max(int(np.searchsorted(t, t0, side=\"left\")) - 1, 0)\n    b = int")]),
    ("triggered: the sell first", [("return j, (1 if ask[j] >= up else -1)", "return j, (-1 if bid[j] <= dn else 1)")]),
    ("triggered: the buy stop on the bid", [("hit = np.nonzero((ask[a:b] >= up) | (bid[a:b] <= dn))[0]", "hit = np.nonzero((bid[a:b] >= up) | (bid[a:b] <= dn))[0]")]),
    ("straddle: no release slippage", [("entry = ask[j] + P2.SLIP + extra if side > 0 else bid[j] - P2.SLIP - extra", "entry = ask[j] + P2.SLIP if side > 0 else bid[j] - P2.SLIP - extra")]),
    ("straddle: U fixed at 1 USD", [("u = bid0 / UNIT_PRICE", "u = 1.0")]),
    ("straddle: the buy stop from the bid", [("up, dn = ask0 + trig_u * u, bid0 - trig_u * u", "up, dn = bid0 + trig_u * u, bid0 - trig_u * u")]),
    ("straddle: the stop from the trigger", [("stop = entry - side * stop_u * u", "stop = (up if side > 0 else dn) - side * stop_u * u")]),
    ("straddle: a buy exits on the ask", [("px = float((bid if side > 0 else ask)[x])", "px = float(ask[x])")]),
    ("exit: no gap rule", [("    if len(gaps):\n        end, why_end = j + int(gaps[0]), \"break\"", "    if False:\n        end, why_end = j + int(gaps[0]), \"break\"")]),
    ("exit: the time one tick early", [("end = int(np.searchsorted(t, t_limit, side=\"left\"))", "end = int(np.searchsorted(t, t_limit, side=\"left\")) - 1")]),
    ("exit: a stop at the price not taken", [("s = np.nonzero(side * (mkt[j + 1:end + 1] - stop) <= 0)[0]", "s = np.nonzero(side * (mkt[j + 1:end + 1] - stop) < 0)[0]")]),
]

DB = [
    ("minutes: New York at UTC-5 always", [('tz="America/New_York").tz_convert("UTC")', 'tz="Etc/GMT+5").tz_convert("UTC")')]),
    ("minutes: Saturdays", [("        if d.weekday() >= 5:\n            continue\n        for hh, mm in minutes:", "        if d.weekday() >= 6:\n            continue\n        for hh, mm in minutes:")]),
    ("mid: a tick at the time left out", [('k = int(np.searchsorted(t, at, side="right")) - 1', 'k = int(np.searchsorted(t, at, side="left")) - 1')]),
    ("gap: no gap rule", [("    return bool(np.any(np.diff(t[i:j + 1]) > D2.GAP))", "    return False")]),
    ("gap: the data's end ignored", [("    if i < 0 or j >= len(t):\n        return True", "    if i < 0:\n        return True\n    if j >= len(t):\n        j = len(t) - 1")]),
    ("buckets: bucket 1 from the minute, not the fill", [('a_t = int(x["entry_t"]) if b == 1 else t0 + (b - 1) * 30 * NS_MIN', 'a_t = t0 + (b - 1) * 30 * NS_MIN')]),
    ("buckets: the move without the side", [('out.append((x["side"] * d / x["risk"], abs(d)))', 'out.append((d / x["risk"], abs(d)))')]),
    ("buckets: the size signed", [('out.append((x["side"] * d / x["risk"], abs(d)))', 'out.append((x["side"] * d / x["risk"], d))')]),
]


def main() -> None:
    py = Path(sys.executable)
    caught = total = 0
    for mod, test, bugs in ((HERE / "d1_orb.py", HERE / "test_d1_orb.py", D1), (HERE / "d2_straddle.py", HERE / "test_d2_straddle.py", D2),
                            (HERE / "d2_buckets.py", HERE / "test_d2_buckets.py", DB)):
        src = mod.read_text(encoding="utf-8")
        ok, line = run(src, mod, test, py)
        print(f"{mod.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
        if not ok:
            raise SystemExit("the unedited source must pass first")
        for k, (name, edits) in enumerate(bugs, 1):
            ok, line = run(mutate(src, edits), mod, test, py)
            caught += not ok
            total += 1
            print(f"{'MISSED' if ok else 'CAUGHT'}  {mod.stem} #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {total} planted bugs caught")


if __name__ == "__main__":
    main()
