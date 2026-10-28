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
# No time limit: a trade is held until its stop or its target (the owner, 2026-10-28: "hold it"). The
# twelve trades in the ledgers were scored under the old 4-hour window (48 bars) and keep those scores;
# only unscored rows are scored, and they are scored this way.
LIVE_BARS: int | None = None
SEEN = pd.Timedelta(minutes=5)  # a `Now` label is the last bar seen; the next one is the first unseen


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


def start_of(row: dict[str, str], cuts: dict[str, pd.Timestamp]) -> pd.Timestamp:
    """The row's own starting point: a sampled moment by id, or - for a real trading day - the date in
    ``cutoff_thai`` with the time in ``decided_at`` (the owner, 2026-10-28: run real days, one at a time)."""
    if row["id"] in cuts:
        return decided(row, cuts[row["id"]])
    day = row["cutoff_thai"][:10]
    return pd.Timestamp(f"{day} {row['decided_at'][-5:]}", tz=TH).tz_convert("UTC") + SEEN


def decided(row: dict[str, str], start: pd.Timestamp) -> pd.Timestamp:
    """When the decision was actually made. A moment is where I sit down; the decision comes after however
    long I waited (METHOD section 2b), and the clock for filling and resolving starts there, not at the
    moment I sat down.

    ``decided_at`` is the ``Now`` label ``walk.py`` printed: the open time of the last bar already on the
    screen, so the first bar that can judge the decision opens five minutes later. Reading it as the first
    bar scored one bar the reader had already seen, and when the label fell before the cut-off (#15:
    20:25 against 20:30) it rolled the clock a whole day forward - #15 was scored from a Saturday and
    filled on the Monday (reviewer, 2026-10-28, `eye/RULES_REVIEW.md` C1)."""
    waited = row.get("decided_at", "")
    if not waited or waited == row["cutoff_thai"]:
        return start
    at = pd.Timestamp(f"{start.tz_convert(TH):%Y-%m-%d} {waited[-5:]}", tz=TH) + SEEN
    if at < start.tz_convert(TH):  # the walk went past midnight
        at += pd.Timedelta(days=1)
    return at.tz_convert("UTC")


def resolve(bars: pd.DataFrame, entry: float, stop: float, target: float, buy: bool) -> tuple[float, str]:
    """The first of stop or target from the fill bar on; a bar touching both counts as the stop."""
    for _, b in bars.iterrows():
        if (b.low <= stop) if buy else (b.high >= stop):
            return stop, "stop"
        if (b.high >= target) if buy else (b.low <= target):
            return target, "target"
    return float(bars.close.iloc[-1]), "open"  # neither reached in the stored bars: not a result yet


def score(row: dict[str, str], m5: pd.DataFrame, cut: pd.Timestamp) -> dict[str, str]:
    side, entry, stop, target = row["side"], float(row["entry"]), float(row["stop"]), float(row["target"])
    buy = side == "BUY"
    window = m5[m5.index >= cut]
    first = window.iloc[:FILL_BARS]

    # What the same idea would have paid taken at the market, at the price on the screen when the decision
    # was made. The owner, 2026-10-28: an obvious level may never be reached, because it is obvious - so
    # waiting for a better price has a cost, and this column is that cost, measured.
    seen = float(window.open.iloc[0])
    # Filled on the spot, and held under the same rule as a planned trade after its fill (C3).
    at_out, at_why = resolve(window.iloc[:LIVE_BARS], seen, stop, target, buy)
    at_move = (at_out - seen) if buy else (seen - at_out)
    at_r = (at_move - SPREAD) / abs(seen - stop) if abs(seen - stop) > 0 else 0.0
    at_text = "" if at_why == "open" else f"{at_r:.2f}"

    # The order fills when price trades through the entry from the side it was on at the decision - a limit
    # (a buy under price, a sell over it) and a stop (METHOD 2e's entry on the break: a sell under price)
    # alike. It used to treat every BUY as a buy limit and every SELL as a sell limit, which fills a sell
    # stop on the first bar whose high is above it, before price ever broke (RULES_REVIEW M1).
    from_above = entry <= seen
    hit = first[(first.low <= entry) if from_above else (first.high >= entry)]
    if hit.empty:
        missed = (first.low.min() - entry) if from_above else (entry - first.high.max())
        return {
            "fill": "", "exit": "", "why": "no fill", "r_net": "0.0",
            "at_decision_r": at_text, "missed_by": f"{missed:.2f}",
        }  # fmt: skip
    t0 = hit.index[0]
    after = window[window.index >= t0].iloc[:LIVE_BARS]  # held from the fill bar to the stop or the target
    out, why = resolve(after, entry, stop, target, buy)
    if why == "open":
        return {
            "fill": f"{t0.tz_convert(TH):%d/%m %H:%M}", "exit": "", "why": "open", "r_net": "",
            "at_decision_r": at_text, "missed_by": "0.00",
        }  # fmt: skip
    move = (out - entry) if buy else (entry - out)
    r = (move - SPREAD) / abs(entry - stop)
    return {
        "fill": f"{t0.tz_convert(TH):%d/%m %H:%M}",
        "exit": f"{out:.2f}",
        "why": why,
        "r_net": f"{r:.2f}",
        "at_decision_r": at_text,
        "missed_by": "0.00",
    }


def windows() -> None:
    """The denominator: every window walked, trade or no trade (METHOD section 2c)."""
    p = HERE / "sessions.csv"
    if not p.exists():
        return
    # A window marked excluded (01/04 New York: scoring an earlier trade had already shown its outcome)
    # is a record, not part of the denominator (C10).
    rows = [r for r in csv.DictReader(p.open(encoding="utf-8")) if "excluded" not in r["window"]]
    steps = sum(int(r["steps"]) for r in rows)
    print(
        f"{'windows':7} walked {len(rows):3}  steps advanced {steps:3}  "
        f"days {len({r['date'] for r in rows}):3}"
    )
    # `reach` is what the method could do with the window (METHOD 2c). `shut` and `open-missed` leave no
    # row in the ledger, so they are the two a summary has to show on purpose.
    counts = {k: 0 for k in ("no-setup", "shut", "open-missed", "open-taken")}
    for r in rows:
        counts[r.get("reach") or "no-setup"] += 1
    print(f"{'reach':7} " + "  ".join(f"{k} {v}" for k, v in counts.items()))


def main() -> None:
    name = next((a for a in sys.argv[1:] if a.endswith(".csv")), "ledger.csv")
    path = HERE / name
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if sys.argv[1:2] == ["summary"]:
        for reader in sorted({r["reader"] for r in rows}):
            mine = [r for r in rows if r["reader"] == reader]
            taken = [r for r in mine if r["side"] in ("BUY", "SELL")]
            filled = [r for r in taken if r["why"] not in ("no fill", "open", "")]
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
            onsight = [float(r["at_decision_r"]) for r in taken if r["at_decision_r"]]
            if onsight:
                print(
                    f"{'':7} the same ideas taken at the price on the screen: "
                    f"R {sum(onsight):+7.2f}  per trade {sum(onsight) / len(onsight):+6.3f}  "
                    f"(the 4 USD rule, METHOD rule 7)"
                )
        windows()
        return

    m5, cut = bars(), cutoffs()
    done = 0
    for r in rows:
        if (r["why"] and r["why"] != "open") or r["side"] not in ("BUY", "SELL"):
            continue
        r.update(score(r, m5, start_of(r, cut)))
        print(f"#{r['id']:>3} {r['side']:4} {r['entry']:>9} -> {r['why']:11} {r['r_net']:>6}")
        done += 1
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{done} scored")


if __name__ == "__main__":
    main()
