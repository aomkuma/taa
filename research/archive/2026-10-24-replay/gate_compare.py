"""Three readings of the owner's edge-side principle, on the same candidates (2026-10-28).

The owner's principle is not in question: every trade takes only the side with the edge on a timeframe
larger than the entry frame. What is in question is the reading that implements it. Three are compared:

- **lean_h4** - the shipped rule R10: the H4 close less its 50-bar mean, in H4 ATR(14), behind the trade
  and at least 0. It measures DISTANCE FROM A MEAN, which is also what a mean-reversion system reads.
- **trend_h4** - the same frame judged with its slope included (`knowledge.d1_regime` applied to H4, the
  reading already shipped as `h4_trend`): the close beyond its 50-bar mean AND that mean beyond where it
  was 20 bars earlier. "none" refuses both sides.
- **lean_h1_first** - the owner's own ordering, H1 then H4 then D1 (corrected 2026-10-28; both
  RULES_LOCKED.md and the memory had it backwards). The nearest frame that speaks decides: H1's lean when
  it can be read, else H4's, else D1's; a lean of 0 passes, as the measured rule says.

**What this can and cannot show.** The candidates are the entries the system actually proposed over
2026-07-06 and 07, and those were produced by an AI whose prompt already told it R10 exists - so the
candidate set is biased toward what R10 allows, and a gate cannot be credited here for candidates that
were never proposed. This measures which reading filters THIS set better, not what the system would have
done under another reading. Two days and a handful of candidates settle nothing either way; the point is
to see each reading's refusals side by side on real trades.

Outcomes come from the M1 bars, with the order's life held at ``VALID_MINUTES`` for every gate so the only
difference between columns is the gate. A bar that touches both the stop and the target counts as the stop
(the project's rule for bar-based fills).

    .venv/Scripts/python research/2026-10-24-replay/gate_compare.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))  # the repo's own modules, as the other research scripts do

from app.core.enums import Timeframe  # noqa: E402
from app.strategy import knowledge as kn  # noqa: E402
from app.strategy.edge_side import edge_lean  # noqa: E402

STORE = ROOT / "data/replay/ai/store"
TH = "Asia/Bangkok"
VALID_MINUTES = 60  # the same order life for every gate; the shipped default is 30 (ISSUES 42)
DAYS = ("2026-07-06", "2026-07-07")


@dataclass
class Candidate:
    at: pd.Timestamp
    side: str
    entry: float
    stop: float
    target: float | None
    source: str


def m1() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet")
    col = next(c for c in df.columns if "time" in c.lower())
    df[col] = pd.to_datetime(df[col], utc=True)
    return df.set_index(col).sort_index()


def h1() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data/history/FBS-Demo/XAUUSD/H1.parquet")
    col = next(c for c in df.columns if "time" in c.lower())
    df[col] = pd.to_datetime(df[col], utc=True)
    df = df.set_index(col).sort_index()
    df.index = df.index + pd.Timedelta(hours=1)  # the research history is open-stamped; edge_lean wants closes
    return df


def candidates() -> list[Candidate]:
    """Every entry the system proposed on those days: a step decision, a WAIT's own order, or a priced
    scenario of one of the day's plans."""
    out: list[Candidate] = []
    for line in (STORE / "decisions.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["as_of"][:10] not in DAYS:
            continue
        d = r.get("decision") or {}
        side = d.get("decision") if d.get("decision") in ("BUY", "SELL") else d.get("wait_order")
        if side not in ("BUY", "SELL"):
            continue
        if d.get("entry") is None or d.get("stop") is None:
            continue
        kind = "decision" if d.get("decision") == side else "wait_order"
        out.append(
            Candidate(
                pd.Timestamp(r["as_of"]), side, float(d["entry"]), float(d["stop"]),
                None if d.get("target") is None else float(d["target"]), kind,
            )  # fmt: skip
        )
    for line in (STORE / "plans.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["as_of"][:10] not in DAYS:
            continue
        for s in (r.get("plan") or {}).get("scenarios") or []:
            if s.get("entry") is None or s.get("stop") is None or s.get("take_profit") is None:
                continue
            out.append(
                Candidate(
                    pd.Timestamp(r["as_of"]), s["side"], float(s["entry"]), float(s["stop"]),
                    float(s["take_profit"]), f"plan {r['kind']} {s['name']}",
                )  # fmt: skip
            )
    return sorted(out, key=lambda c: c.at)


def behind(lean: float | None, side: str) -> float | None:
    if lean is None:
        return None
    return lean if side == "BUY" else -lean


def gates(c: Candidate, hourly: pd.DataFrame) -> dict[str, bool]:
    """Each reading's verdict on one candidate. An unreadable reading refuses, never passes."""
    frames = {Timeframe.H1: hourly}
    h4 = edge_lean(frames, c.at, Timeframe.M5, frame=Timeframe.H4)
    hour = edge_lean(frames, c.at, Timeframe.M1, frame=Timeframe.H1)
    day = edge_lean(frames, c.at, Timeframe.M5, frame=Timeframe.D1)

    b4 = behind(h4, c.side)
    verdicts = {"lean_h4": b4 is not None and b4 >= 0}

    closes = hourly[hourly.index <= c.at]
    bars = closes.resample("4h", offset="0h").agg({"close": "last"}).dropna()
    word = kn.d1_regime(bars.close.to_numpy(float))
    verdicts["trend_h4"] = word == ("up" if c.side == "BUY" else "down")

    first = next((behind(x, c.side) for x in (hour, h4, day) if x is not None), None)
    verdicts["lean_h1_first"] = first is not None and first >= 0
    return verdicts


def outcome(c: Candidate, bars: pd.DataFrame) -> tuple[str, float]:
    """R if the order filled within its life and then resolved; ('no fill', 0) when price never reached it."""
    end = c.at + pd.Timedelta(minutes=VALID_MINUTES)
    window = bars[(bars.index >= c.at) & (bars.index < end)]
    buy = c.side == "BUY"
    reached = window[(window.low <= c.entry) if buy else (window.high >= c.entry)]
    if reached.empty:
        return "no fill", 0.0
    risk = abs(c.entry - c.stop)
    if risk <= 0:
        return "no stop", 0.0
    after = bars[bars.index >= reached.index[0]]
    for _, b in after.iterrows():
        hit_sl = (b.low <= c.stop) if buy else (b.high >= c.stop)
        hit_tp = c.target is not None and ((b.high >= c.target) if buy else (b.low <= c.target))
        if hit_sl:  # a bar touching both counts as the stop
            return "stop", -1.0
        if hit_tp:
            return "target", abs(c.target - c.entry) / risk  # type: ignore[operator]
    last = float(after.close.iloc[-1])
    r = ((last - c.entry) if buy else (c.entry - last)) / risk
    return "open at the end", r


def main() -> None:
    bars, hourly = m1(), h1()
    cands = candidates()
    names = ("lean_h4", "trend_h4", "lean_h1_first")
    print(f"# Three readings of the edge side, {len(cands)} candidates over {DAYS[0]} and {DAYS[1]}\n")
    print(f"Order life {VALID_MINUTES} minutes for every gate. A bar touching both levels counts as the stop.\n")
    print("| Thai | side | source | entry | stop | target | outcome | R | " + " | ".join(names) + " |")
    print("|---|---|---|---|---:|---:|---|---:|" + "---|" * len(names))
    totals: dict[str, list[float]] = {n: [] for n in names}
    for c in cands:
        g = gates(c, hourly)
        how, r = outcome(c, bars)
        marks = " | ".join("take" if g[n] else "refuse" for n in names)
        tgt = "-" if c.target is None else f"{c.target:.2f}"
        print(
            f"| {c.at.tz_convert(TH):%m-%d %H:%M} | {c.side} | {c.source} | {c.entry:.2f} | {c.stop:.2f} "
            f"| {tgt} | {how} | {r:+.2f} | {marks} |"
        )
        for n in names:
            if g[n] and how != "no fill":
                totals[n].append(r)
    print("\n## What each reading would have traded\n")
    print("| reading | trades | R total | R a trade |")
    print("|---|---:|---:|---:|")
    for n in names:
        rs = totals[n]
        mean = f"{sum(rs) / len(rs):+.3f}" if rs else "-"
        print(f"| {n} | {len(rs)} | {sum(rs):+.2f} | {mean} |")
    print(
        "\nCandidates with no fill are excluded from the totals: an order that price never reached costs"
        "\nnothing and tells us nothing about the gate."
    )


if __name__ == "__main__":
    main()
