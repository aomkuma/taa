"""Roll the replay store back to the start of a Thai day, to replay it again (with changed code or knowledge).

Removes the day's (and later) decisions, raw prompts, session notes from 07:00 Thai on, the backtest folders and
the ledger rows; the watch state becomes the one the previous day closed with (its watch_state_end.json, else
rebuilt from the last decision before the day).

    .venv/Scripts/python research/2026-10-24-replay/rollback.py 2026-07-07
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1] / "data/replay/ai"
LEDGER = HERE / "ledger.csv"


def lesson_day(section: str) -> date | None:
    """The date of a journal section headed 'Mon 06 Jul 2026 - ...'; None for other sections."""
    try:
        return datetime.strptime(section[:15], "%a %d %b %Y").date()
    except ValueError:
        return None


def main() -> None:
    day = date.fromisoformat(sys.argv[1])
    st = RUN / "store"
    rows = [json.loads(x) for x in (st / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    keep = [r for r in rows if r["as_of"] < day.isoformat()]
    (st / "decisions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in keep), encoding="utf-8")
    live = st / "trades_live.jsonl"  # the live trade rows of this day and later
    if live.exists():
        rows_l = [
            x for x in live.read_text(encoding="utf-8").splitlines() if json.loads(x)["at"] < day.isoformat()
        ]
        live.write_text("".join(x + "\n" for x in rows_l), encoding="utf-8")
    plans = st / "plans.jsonl"  # the day plans of this day and later (P26)
    if plans.exists():
        rows_p = [
            x
            for x in plans.read_text(encoding="utf-8").splitlines()
            if json.loads(x)["as_of"] < day.isoformat()
        ]
        plans.write_text("".join(x + "\n" for x in rows_p), encoding="utf-8")
    first = f"{day.isoformat()}_0700"  # raw stems are Thai time; the day starts 07:00 Thai
    gone = [p for p in (st / "raw").iterdir() if p.name[:15] >= first]
    for p in gone:
        p.unlink()
    for s in st.glob("session_*.md"):
        stem = s.stem.removeprefix("session_")
        if stem > day.isoformat():
            s.unlink()
        elif stem == day.isoformat():  # the Thai date's 00:00-07:00 calls belong to the previous replay day
            parts = s.read_text(encoding="utf-8").split("\n### ")
            s.write_text(
                "\n### ".join([parts[0]] + [p for p in parts[1:] if p[:5] < "07:00"]), encoding="utf-8"
            )
    journal = st / "journal.md"  # the day lessons of this day and later would be the future: cut them
    if journal.exists():
        parts = journal.read_text(encoding="utf-8").split("\n## ")
        kept = [parts[0]] + [p for p in parts[1:] if not (lesson_day(p) is not None and lesson_day(p) >= day)]
        journal.write_text("\n## ".join(kept), encoding="utf-8")
    for d in (RUN / "days").iterdir():
        if d.name >= day.isoformat():
            shutil.rmtree(d)
    end = RUN / "days" / (day - timedelta(days=1)).isoformat() / "watch_state_end.json"
    if end.exists():
        state = json.loads(end.read_text(encoding="utf-8"))
    elif not keep:  # back to the first day: the watcher starts fresh
        state = None
    else:
        last = keep[-1]
        d = last.get("decision") or {}
        before = json.loads((st / "watch_state.json").read_text(encoding="utf-8"))
        state = dict(
            before,
            last_call=last["as_of"],
            watch_above=d.get("watch_above"),
            watch_below=d.get("watch_below"),
        )
    if state is not None and keep and str(state.get("last_call") or "") >= day.isoformat():
        state["last_call"] = keep[-1]["as_of"]  # the removed call of this day is not the last call
    if state is not None and str(state.get("last_plan") or "")[:10] >= day.isoformat():
        state["last_plan"] = None  # a plan of this day (written at the previous run's last bar) is redone
        state["plan_levels"], state["plan_orders"] = [], []
    if state is None:
        (st / "watch_state.json").unlink(missing_ok=True)
    else:
        (st / "watch_state.json").write_text(json.dumps(state), encoding="utf-8")
    if LEDGER.exists():
        led = [r for r in csv.DictReader(LEDGER.open(encoding="utf-8")) if r["date"] < day.isoformat()]
        with LEDGER.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["date", "trades", "r", "acct300", "acct100", "wakes"])
            w.writeheader()
            w.writerows(led)
    print(f"rolled back to {day}: {len(keep)} decisions kept, {len(gone)} raw files removed, state {state}")


if __name__ == "__main__":
    main()
