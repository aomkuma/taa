"""Stream the replay's decisions and plans as they are written (owner 2026-10-25: "report every step as it is
reported and compare the decisions in real time while the test runs").

One line per new record of data/replay/ai/store/decisions.jsonl and plans.jsonl: the Thai time, the decision,
weapon, size, vetoes and failed HARD checklist items, the setup; and - for the comparison - the last M1 close and
what price did in the next 30 minutes (high / low, from the stored M1 bars: hindsight, labelled). Exits when the
replay process writes the day's report (the day's .md grows past its table) or after ``--minutes``.

    .venv/Scripts/python research/2026-10-24-replay/live_watch.py 2026-07-07
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

STORE = ROOT / "data/replay/ai/store"
TH = "Asia/Bangkok"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # type: ignore[attr-defined]
    day = sys.argv[1]
    t0 = pd.Timestamp(day, tz="UTC")
    since = pd.Timestamp(sys.argv[2], tz="UTC") if len(sys.argv) > 2 else t0 - pd.Timedelta(minutes=1)
    raw = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None)
    m1 = (
        raw.assign(t=pd.to_datetime(raw.open_time, utc=True)).drop_duplicates("t", keep="last").set_index("t")
    )
    m1 = m1.sort_index()
    seen = {"decisions.jsonl": 0, "plans.jsonl": 0, "trades_live.jsonl": 0}
    report = HERE / f"day_{day}.md"
    start = time.time()
    while True:
        for name in seen:
            path = STORE / name
            if not path.exists():
                continue
            rows = path.read_text(encoding="utf-8").splitlines()
            for line in rows[seen[name] :]:
                r = json.loads(line)
                at = pd.Timestamp(r.get("as_of") or r["at"])
                if not t0 <= at < t0 + pd.Timedelta(days=1, minutes=1) or at <= since:
                    continue  # outside the day, or already reported before a re-armed watch
                print(event(name, r, at, m1), flush=True)
            seen[name] = len(rows)
        if report.exists() and "## Trades:" in report.read_text(encoding="utf-8", errors="ignore"):
            print(f"DONE: the day report {report.name} is written", flush=True)
            return
        if time.time() - start > 6 * 3600:
            print("STOP: six hours without the day report", flush=True)
            return
        time.sleep(2)


def event(name: str, r: dict, at: pd.Timestamp, m1: pd.DataFrame) -> str:
    th = at.tz_convert(TH)
    before = m1[m1.index + pd.Timedelta(minutes=1) <= at]
    last = float(before.close.iloc[-1]) if len(before) else float("nan")
    nxt = m1[(m1.index >= at) & (m1.index < at + pd.Timedelta(minutes=30))]
    after = f"next 30 min {nxt.low.min():.2f}-{nxt.high.max():.2f}" if len(nxt) else "next 30 min -"
    if name == "trades_live.jsonl":  # the trade at once, when it opens and when it closes (owner 2026-10-25)
        if r["event"] == "OPEN":
            return f"TRADE OPEN {th:%H:%M} {r['side']} at {r['entry']:.2f}, stop {r['sl']}, take-profit {r['tp']}"
        r_txt = "-" if r.get("r") is None else f"{r['r']:+.2f} R"
        return (
            f"TRADE CLOSE {th:%H:%M} {r['side']} {r['entry']:.2f} -> {r['exit']:.2f} ({r['reason']}): {r_txt}, "
            f"{r['usd']:+.2f} USD at {r['lots']} lot"
        )
    if name == "plans.jsonl":
        p = r.get("plan")
        if p is None:
            return f"PLAN {th:%H:%M} {r['kind']}: FAILED {r['status']}"
        sc = " | ".join(f"{s['name']} {s['side']}: {s['trigger'][:70]}" for s in p["scenarios"])
        return f"PLAN {th:%H:%M} {r['kind']}: edge {p['edge_side']} | price {last:.2f} | {sc}"
    d = r.get("decision") or {}
    if d.get("decision") in ("BUY", "SELL"):  # the order the AI gave: at market or pending at its level
        kind = "MARKET" if abs((d.get("entry") or last) - last) <= 1.0 else "PENDING"
        order = f" | ORDER {kind} entry {d.get('entry')} stop {d.get('stop')} tp {d.get('target')}"
    else:
        order = ""
    veto = ",".join(r.get("vetoed_by") or []) or "-"
    gaps = (r.get("checklist") or {}).get("failed") or []
    return (
        f"STEP {th:%H:%M} {d.get('decision', r.get('status'))} {d.get('weapon', '-')} size {r.get('final_size')} "
        f"veto {veto} fails {','.join(gaps) or '-'} | price {last:.2f} | {after} (hindsight) | "
        f"{(d.get('setup') or r.get('detail') or '')[:110]}{order}"
    )


if __name__ == "__main__":
    main()
