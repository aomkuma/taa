"""Every trade's stop against the liquidate zone (owner 2026-10-26: "is the stop really past the liquidate zone -
I mean every trade"). For each OPEN in data/replay/ai/store/trades_live.jsonl: the liquidity map the AI read last
before the fill (its raw prompt: the structure line - the 2-hour top / bottom and the code's stop past the zone
for each side), the trade's stop, and how far past the structure and the code's stop it sits.

    .venv/Scripts/python research/2026-10-24-replay/audit_stops.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "data/replay/ai/store"
TH = "Asia/Bangkok"
LINE = re.compile(
    r"the structure \(2 h of M5\): top ([\d.]+), bottom ([\d.]+); a SELL's stop beyond it ([\d.]+), "
    r"a BUY's stop beyond it ([\d.]+) \(M5 ATR ([\d.]+)\)"
)


def last_map(at: pd.Timestamp) -> tuple[str, tuple[float, ...]] | None:
    """The latest prompt (a decision or a plan) written at or before ``at`` with a structure line."""
    best = None
    for f in sorted((STORE / "raw").glob("*_2_user.txt")):
        stamp = pd.Timestamp(f.name[:15].replace("_", " ")[:13] + ":" + f.name[13:15], tz=TH)
        if stamp > at.tz_convert(TH):
            break
        m = LINE.search(f.read_text(encoding="utf-8"))
        if m:
            best = (f.name, tuple(float(x) for x in m.groups()))
    return best


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    rows = [json.loads(x) for x in (STORE / "trades_live.jsonl").read_text(encoding="utf-8").splitlines()]
    print(
        "| opened (Thai) | side | entry | stop | 2h top / bottom | code stop | past the structure | vs code stop | map from |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["event"] != "OPEN":
            continue
        at = pd.Timestamp(r["at"])
        got = last_map(at)
        if got is None:
            print(
                f"| {at.tz_convert(TH):%m-%d %H:%M} | {r['side']} | {r['entry']:.2f} | {r['sl']} | - | - | - | - | none |"
            )
            continue
        name, (top, bottom, sell_stop, buy_stop, atr) = got
        sl = float(r["sl"])
        if r["side"] == "SELL":
            past, code = sl - top, sell_stop
            vs = sl - code
        else:
            past, code = bottom - sl, buy_stop
            vs = code - sl
        print(
            f"| {at.tz_convert(TH):%m-%d %H:%M} | {r['side']} | {r['entry']:.2f} | {sl:.2f} | {top:.2f} / {bottom:.2f} | "
            f"{code:.2f} | {past:+.2f} ({past / atr:+.2f} ATR) | {vs:+.2f} | {name[:15]} |"
        )


if __name__ == "__main__":
    main()
