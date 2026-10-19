"""Planted bugs for verify_p2.py (the second, separate computation of P2's numbers): each a small edit run against
test_verify_p2.py in a temporary copy (the harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_verify_p2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "verify_p2.py", HERE / "test_verify_p2.py"
BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("weekdays: Saturdays counted", [("n += d.weekday() < 5", "n += d.weekday() < 6")]),
    ("metrics: R from the risk without the side", [('rs = [r["pnl"] / (r["side"] * (r["entry"] - r["stop"])) for r in rows]', 'rs = [r["pnl"] / (r["entry"] - r["stop"]) for r in rows]')]),
    ("metrics: the population sd", [("/ (n - 1) if n > 1", "/ n if n > 1")]),
    ("metrics: the drawdown from the first trade, not from 0", [("cum, peak, dd = 0.0, 0.0, 0.0", "cum, peak, dd = 0.0, -1e18, 0.0")]),
    ("metrics: a flat trade in the losing streak", [('if r["pnl"] < 0:', 'if r["pnl"] <= 0:')]),
    ("metrics: not in time order", [('rows = sorted(rows, key=lambda r: r["entry_t"])\n    n = len(rows)', "n = len(rows)")]),
    ("metrics: a flat trade a win", [('win=sum(r["pnl"] > 0 for r in rows) / n', 'win=sum(r["pnl"] >= 0 for r in rows) / n')]),
    ("raw_ticks: milliseconds", [('.dt.as_unit("ns").astype("int64")', '.astype("int64")')]),
    ("raw_ticks: the exam read", [("    if day >= EXAM:\n        return pd.DataFrame(columns=[\"t\", \"bid\", \"ask\"])\n", "")]),
    ("rederive: the slippage sign", [("want = ask[f] + SLIP if side > 0 else bid[f] - SLIP", "want = ask[f] - SLIP if side > 0 else bid[f] + SLIP")]),
    ("rederive: the ticks before the exit not checked", [("past = [i for i in range(f + 1, x) if", "past = [i for i in range(x, x) if")]),
    ("rederive: a sell's stop read on the bid", [("mkt = bid if side > 0 else ask", "mkt = bid")]),
    ("rederive: the target's first hit not checked", [("if not hit or hit[0] != x or abs(px - tg) > 1e-9:", "if not hit or abs(px - tg) > 1e-9:")]),
    ("rederive: the time exit tick not checked", [('if why == "time" and not (t[x] >= tr["t_limit"] and t[x - 1] < tr["t_limit"]):', 'if why == "time" and not (t[x] >= tr["t_limit"]):')]),
    ("rederive: a gap of exactly 30 minutes is a break", [("t[x + 1] - t[x] > GAP", "t[x + 1] - t[x] >= GAP")]),
    ("rederive: the USD not checked", [('if abs(usd - tr["pnl"]) > 1e-9 or abs(', 'if abs(')]),
    ("one_at_a_time: an entry at the exit counted", [('rows[i]["entry_t"] < rows[i - 1]["exit_t"]', 'rows[i]["entry_t"] <= rows[i - 1]["exit_t"]')]),
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
