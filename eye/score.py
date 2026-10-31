"""Score the ledger's unscored rows against the real bars (eye/METHOD.md section 4).

A row is written with its id, side, entry, stop and target the moment the decision is made, with `why`
left empty. This fills in the fill time, the exit, the reason and R - and nothing else is ever touched.

    python eye/score.py            # score what is pending
    python eye/score.py summary    # the running totals, per reader
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import numpy as np
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
    day = pd.Timestamp(row["cutoff_thai"][:10])
    # ``decided_at`` is ``dd/mm HH:MM``, the last bar's open: for a decision at 00:00 that is 23:55 of the day
    # before ``cutoff_thai``'s date, so the date moves back one day (BOT_RULES, Code status).
    before = day - pd.Timedelta(days=1)
    if row["decided_at"][:5] == f"{before:%d/%m}":
        day = before
    return pd.Timestamp(f"{day:%Y-%m-%d} {row['decided_at'][-5:]}", tz=TH).tz_convert("UTC") + SEEN


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


LIFE_MARK = re.compile(r"order_life_bars=(\d+)")
H100_MARK = re.compile(r"withdraw beyond (-?\d+(?:\.\d+)?)")
# a fade leg (BOT_RULES rule 2): a new extreme beyond E - a BUY: a low under it, a SELL: a high over it
FADE_MARK = re.compile(r"withdraw (under|over) (-?\d+(?:\.\d+)?)")


def score_limit(
    row: dict[str, str], window: pd.DataFrame, life: int, spread: float, at_text: str
) -> dict[str, str]:
    """A plain limit order scored by eye/BOT_RULES.md rule 12 (the fib rows carry ``order_life_bars=``).

    Fill: on the first of the ``life`` M5 bars after the decision whose low (BUY) / high (SELL) reaches the
    price, at min(open, price) / max(open, price). Withdrawn by an M5 bar BEFORE the fill bar only: its target
    touched, a leg's ``H100`` crossed strictly (marker ``withdraw beyond``); a bar
    that fills and withdraws keeps the fill. Not filled within ``life`` bars: ``no fill``. Held until the stop
    or the target: on the fill bar only the stop counts, later a bar touching both counts as the stop; a bar
    that opens beyond the stop exits at its open. R is realised: (exit - fill - spread) / |order - stop|."""
    buy = row["side"] == "BUY"
    entry, stop, target = float(row["entry"]), float(row["stop"]), float(row["target"])
    structure = row.get("structure", "")
    first = window.iloc[:life]
    n = len(first)
    touched = ((first.low <= entry) if buy else (first.high >= entry)).to_numpy()
    by_target = ((first.high >= target) if buy else (first.low <= target)).to_numpy()
    by_h100 = np.zeros(n, dtype=bool)
    h100 = H100_MARK.search(structure)
    fade = FADE_MARK.search(structure)
    if h100:
        level = float(h100.group(1))
        by_h100 = ((first.high > level) if buy else (first.low < level)).to_numpy()
    elif fade:
        level = float(fade.group(2))
        by_h100 = ((first.low < level) if buy else (first.high > level)).to_numpy()
    gone = by_target | by_h100
    at_fill = int(touched.argmax()) if touched.any() else n
    if gone[:at_fill].any():
        k = int(gone[:at_fill].argmax())
        # SPEC-QUESTION: BOT_RULES says the scorer writes the reason but not its text; the two new ones
        #  start with
        # "no fill" so the summaries count them as unfilled.
        if by_target[k]:
            why = "no fill (stop or target first)"
        else:
            beyond = h100.group(1) if h100 else (fade.group(2) if fade else "")
            why = f"no fill (withdrawn: beyond {beyond})"
        missed = (first.low.min() - entry) if buy else (entry - first.high.max())
        return {
            "fill": "", "exit": "", "why": why, "r_net": "0.0",
            "at_decision_r": at_text, "missed_by": f"{max(missed, 0.0):.2f}",
        }  # fmt: skip
    if not touched.any():
        if n < life:  # the fill window is not over in the stored bars
            return {
                "fill": "", "exit": "", "why": "open", "r_net": "",
                "at_decision_r": at_text, "missed_by": "",
            }  # fmt: skip
        missed = (first.low.min() - entry) if buy else (entry - first.high.max())
        return {
            "fill": "", "exit": "", "why": "no fill", "r_net": "0.0",
            "at_decision_r": at_text, "missed_by": f"{max(missed, 0.0):.2f}",
        }  # fmt: skip
    t0 = first.index[at_fill]
    after = window[window.index >= t0]
    opens, highs, lows = (after[c].to_numpy(dtype=float) for c in ("open", "high", "low"))
    # SPEC-QUESTION: a fill bar that opens beyond the stop fills at its open and exits at its open (literal
    #  rule 12).
    fill = min(opens[0], entry) if buy else max(opens[0], entry)
    exit_price, why = None, "open"
    for i in range(len(after)):
        stop_hit = (lows[i] <= stop) if buy else (highs[i] >= stop)
        target_hit = i > 0 and ((highs[i] >= target) if buy else (lows[i] <= target))
        if stop_hit:
            gapped = (opens[i] < stop) if buy else (opens[i] > stop)
            exit_price, why = (float(opens[i]) if gapped else stop), "stop"
            break
        if target_hit:
            exit_price, why = target, "target"
            break
    stamp = f"{t0.tz_convert(TH):%d/%m %H:%M}"
    if exit_price is None:
        return {
            "fill": stamp, "exit": "", "why": "open", "r_net": "",
            "at_decision_r": at_text, "missed_by": "0.00",
        }  # fmt: skip
    unit = abs(entry - stop)  # rule 12: the planned risk (order price to stop), the same for every fill
    move = (exit_price - fill) if buy else (fill - exit_price)
    return {
        "fill": stamp, "exit": f"{exit_price:.2f}", "why": why, "r_net": f"{(move - spread) / unit:.2f}",
        "at_decision_r": at_text, "missed_by": "0.00",
    }  # fmt: skip


def score(row: dict[str, str], m5: pd.DataFrame, cut: pd.Timestamp, spread: float = SPREAD) -> dict[str, str]:
    side, entry, stop, target = row["side"], float(row["entry"]), float(row["stop"]), float(row["target"])
    buy = side == "BUY"
    window = m5[m5.index >= cut]
    if window.empty:  # no bar after the decision is stored yet
        return {"fill": "", "exit": "", "why": "open", "r_net": "", "at_decision_r": "", "missed_by": ""}
    first = window.iloc[:FILL_BARS]

    # What the same idea would have paid taken at the market, at the price on the screen when the decision
    # was made. The owner, 2026-10-28: an obvious level may never be reached, because it is obvious - so
    # waiting for a better price has a cost, and this column is that cost, measured.
    seen = float(window.open.iloc[0])
    # Filled on the spot, and held under the same rule as a planned trade after its fill (C3).
    at_out, at_why = resolve(window.iloc[:LIVE_BARS], seen, stop, target, buy)
    at_move = (at_out - seen) if buy else (seen - at_out)
    at_r = (at_move - spread) / abs(seen - stop) if abs(seen - stop) > 0 else 0.0
    at_text = "" if at_why == "open" else f"{at_r:.2f}"

    # The fib path's rows (BOT_RULES rule 12) carry ``order_life_bars=`` in their parameters and are scored by
    # ``score_limit``; every other row - every earlier ledger - goes on below exactly as before.
    life = LIFE_MARK.search(row.get("structure", ""))
    if life:
        return score_limit(row, window, int(life.group(1)), spread, at_text)

    # The order fills when price trades through the entry from the side it was on at the decision - a limit
    # (a buy under price, a sell over it - 2e's retest entry, written once the low has broken) and a stop (a
    # sell under price) alike. It used to treat every BUY as a buy limit and every SELL as a sell limit,
    # which fills a sell stop on the first bar whose high is above it, before price ever broke
    # (RULES_REVIEW M1).
    from_above = entry <= seen
    trigger = row.get("trigger", "")
    if trigger:
        # A stop limit, for 2e's "break the low, then retest" (the owner asked on 2026-10-28 whether the
        # entry should be a stop limit; it is the order that matches). The order wakes only when price trades
        # through `trigger` (a sell: down to it, under the low; a buy: up to it), then rests as a limit at
        # `entry` - the broken level - filled on the retest. Price reaching the stop before the trigger means
        # the setup failed: withdrawn. The limit rests from the bar after the trigger bar - five-minute bars
        # cannot say whether a retest inside the trigger bar came after the break - with its own 24 bars.
        level = float(trigger)
        woke = ((first.low <= level) if not buy else (first.high >= level)).to_numpy()
        failed = ((first.high >= stop) if not buy else (first.low <= stop)).to_numpy()
        k = int(woke.argmax()) if woke.any() else len(first)
        if failed[: k + 1].any() and not (woke.any() and not failed[:k].any()):
            return {
                "fill": "", "exit": "", "why": "no fill (stop or target first)", "r_net": "0.0",
                "at_decision_r": at_text, "missed_by": "",
            }  # fmt: skip
        if not woke.any():
            done = len(first) >= FILL_BARS
            return {
                "fill": "", "exit": "", "why": "no fill (never triggered)" if done else "open",
                "r_net": "0.0" if done else "", "at_decision_r": at_text, "missed_by": "",
            }  # fmt: skip
        window = window[window.index > first.index[k]]
        if window.empty:
            return {
                "fill": "",
                "exit": "",
                "why": "open",
                "r_net": "",
                "at_decision_r": at_text,
                "missed_by": "",
            }
        first = window.iloc[:FILL_BARS]
        from_above = buy  # now a plain limit: a sell above price, a buy below it
    touched = ((first.low <= entry) if from_above else (first.high >= entry)).to_numpy()
    # Rule 8: the order fills only while the idea is intact. If the stop or the target trades on a bar before
    # the one that reaches the entry, the idea failed or played out without us, and the order is withdrawn
    # (reviewer, 2026-10-28: a 2e sell stop at 4055 would otherwise fill after price had gone through 4071).
    gone = (
        ((first.low <= stop) | (first.high >= target))
        if buy
        else ((first.high >= stop) | (first.low <= target))
    )
    # Revision 7, R19 (a fib row only): the bot writes "withdraw beyond <H100>" into the structure text; the
    # order is also withdrawn when price trades beyond that level before the fill. Rows without the marker
    # (every earlier ledger) score exactly as before.
    marker = re.search(r"withdraw beyond (-?\d+(?:\.\d+)?)", row.get("structure", ""))
    if marker:
        h100 = float(marker.group(1))
        gone = gone | ((first.high > h100) if buy else (first.low < h100))
    at_fill = int(touched.argmax()) if touched.any() else len(first)
    if gone.to_numpy()[:at_fill].any() or not touched.any():
        if not touched.any() and not gone.to_numpy().any() and len(first) < FILL_BARS:
            return {
                "fill": "",
                "exit": "",
                "why": "open",
                "r_net": "",
                "at_decision_r": at_text,
                "missed_by": "",
            }  # fmt: skip  - the fill window is not over in the stored bars
        missed = (first.low.min() - entry) if from_above else (entry - first.high.max())
        why = "no fill (stop or target first)" if touched.any() else "no fill"
        return {
            "fill": "", "exit": "", "why": why, "r_net": "0.0",
            "at_decision_r": at_text, "missed_by": f"{max(missed, 0.0):.2f}",
        }  # fmt: skip
    t0 = first.index[at_fill]
    # A stop order (a sell under price, a buy over it) that a bar gaps through is
    # filled at that bar's open, not at its price; a limit is filled at its price.
    stop_order = from_above != buy
    bar_open = float(first.open.iloc[at_fill])
    gapped = stop_order and ((bar_open < entry) if not buy else (bar_open > entry))
    price = bar_open if gapped else entry
    after = window[window.index >= t0].iloc[:LIVE_BARS]  # held from the fill bar to the stop or the target
    out, why = resolve(after, price, stop, target, buy)
    if why == "open":
        return {
            "fill": f"{t0.tz_convert(TH):%d/%m %H:%M}", "exit": "", "why": "open", "r_net": "",
            "at_decision_r": at_text, "missed_by": "0.00",
        }  # fmt: skip
    move = (out - price) if buy else (price - out)
    r = (move - spread) / abs(entry - stop)  # the R unit is the planned risk
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
    if not rows:  # a ledger with a header and no row yet (the bot's, on a day it wrote nothing)
        print(f"{name}: no rows")
        if "summary" in sys.argv[1:]:
            windows()
        return
    if "summary" in sys.argv[1:]:  # `score.py ledger_control.csv summary` used to score instead
        for reader in sorted({r["reader"] for r in rows}):
            mine = [r for r in rows if r["reader"] == reader]
            taken = [r for r in mine if r["side"] in ("BUY", "SELL")]
            filled = [r for r in taken if r["why"] not in ("open", "") and not r["why"].startswith("no fill")]
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
