"""Score the ledger's unscored rows against the real bars (eye/METHOD.md section 4).

A row is written with its id, side, entry, stop and target the moment the decision is made, with `why`
left empty. This fills in the fill time, the exit, the reason and R - and nothing else is ever touched.

    python eye/score.py            # score what is pending
    python eye/score.py summary    # the running totals, per reader
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TH = "Asia/Bangkok"
SPREAD = 0.30  # the owner's real account pays about 30 points on gold
FILL_BARS = 24  # 2 hours to fill
LIVE_BARS = 48  # 4 hours to resolve


def bars() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data/history/FBS-Demo/XAUUSD/M5.parquet")
    col = next(c for c in df.columns if "time" in c.lower())
    df[col] = pd.to_datetime(df[col], utc=True)
    return df.set_index(col).sort_index()


def cutoffs() -> dict[str, pd.Timestamp]:
    return {
        r["id"]: pd.Timestamp(r["cutoff_utc"])
        for r in csv.DictReader((HERE / "moments.csv").open(encoding="utf-8"))
    }


def decided(row: dict[str, str], start: pd.Timestamp) -> pd.Timestamp:
    """When the decision was actually made. A moment is where I sit down; the decision comes after however
    long I waited (METHOD section 2b), and the clock for filling and resolving starts there, not at the
    moment I sat down."""
    waited = row.get("decided_at", "")
    if not waited or waited == row["cutoff_thai"]:
        return start
    at = pd.Timestamp(f"{start.tz_convert(TH):%Y-%m-%d} {waited[-5:]}", tz=TH)
    if at < start.tz_convert(TH):
        at += pd.Timedelta(days=1)
    return at.tz_convert("UTC")


def score(row: dict[str, str], m5: pd.DataFrame, cut: pd.Timestamp) -> dict[str, str]:
    side, entry, stop, target = row["side"], float(row["entry"]), float(row["stop"]), float(row["target"])
    buy = side == "BUY"
    window = m5[m5.index >= cut]
    first = window.iloc[:FILL_BARS]
    hit = first[(first.low <= entry) if buy else (first.high >= entry)]
    if hit.empty:
        return {"fill": "", "exit": "", "why": "no fill", "r_net": "0.0"}
    t0 = hit.index[0]
    after = window[window.index >= t0].iloc[: LIVE_BARS + 1]
    for _, b in after.iterrows():
        if (b.low <= stop) if buy else (b.high >= stop):  # a bar touching both counts as the stop
            out, why = stop, "stop"
            break
        if (b.high >= target) if buy else (b.low <= target):
            out, why = target, "target"
            break
    else:
        out, why = float(after.close.iloc[-1]), "time (4 h)"
    move = (out - entry) if buy else (entry - out)
    r = (move - SPREAD) / abs(entry - stop)
    return {
        "fill": f"{t0.tz_convert(TH):%d/%m %H:%M}",
        "exit": f"{out:.2f}",
        "why": why,
        "r_net": f"{r:.2f}",
    }


def main() -> None:
    path = HERE / "ledger.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if sys.argv[1:2] == ["summary"]:
        for reader in sorted({r["reader"] for r in rows}):
            mine = [r for r in rows if r["reader"] == reader]
            taken = [r for r in mine if r["side"] in ("BUY", "SELL")]
            filled = [r for r in taken if r["why"] not in ("no fill", "")]
            rs = [float(r["r_net"]) for r in filled]
            wins = [x for x in rs if x > 0]
            total = sum(rs)
            print(
                f"{reader:7} decisions {len(mine):3}  traded {len(taken):3}  filled {len(filled):3}  "
                f"won {len(wins):3} ({len(wins) / len(filled):.0%})  "
                f"R {total:+7.2f}  per fill {total / len(filled):+6.3f}  "
                f"per decision {total / len(mine):+6.3f}"
                if filled
                else f"{reader:7} decisions {len(mine):3}  nothing filled yet"
            )
        return

    m5, cut = bars(), cutoffs()
    done = 0
    for r in rows:
        if r["why"] or r["side"] not in ("BUY", "SELL"):
            continue
        r.update(score(r, m5, decided(r, cut[r["id"]])))
        print(f"#{r['id']:>3} {r['side']:4} {r['entry']:>9} -> {r['why']:11} {r['r_net']:>6}")
        done += 1
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{done} scored")


if __name__ == "__main__":
    main()
