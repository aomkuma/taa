"""The observer - the bot's eyes when no one is trading (owner 2026-10-23: "the bot - and you, an AI agent who is like
a person - must have the personality of someone who always remembers and always observes price").

Run every hour of the trading day by Windows Task Scheduler (scripts/observe.cmd). Read-only, never trades:
1. refresh the XAUUSD bars from MT5 (scripts/download_history.py: the read-only gateway; merged into the stored
   Parquet, never overwritten). A failed refresh is written into the entry and the stored bars are read;
2. score the previous observation against what price did since (how far with / against the M15 rhythm in USD,
   which half line was reached first) and flag SURPRISES - what no reading prepared for - into diary/TO_STUDY.md;
3. read the market now with the bot's own readers (rhythm_scan, picture_read, routine_read; bars closed by AS_OF)
   and record the observation (the reading BEFORE the next hour is known);
4. append a digest to diary/<Thai date>.md and the record to diary/observations.jsonl; the full reads go to
   diary/raw/.

    .venv/Scripts/python research/2026-10-23-entry/observe.py [--no-fetch] [AS_OF_UTC]
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import rhythm_scan as RS  # noqa: E402
import zone_wait as ZW  # noqa: E402
from candidates import frame  # noqa: E402

from app.strategy import zone_grid as zg  # noqa: E402
from app.strategy.strong_levels import closed  # noqa: E402

DIARY = Path(os.environ.get("TAA_DIARY", HERE / "diary"))  # TAA_DIARY: a trial run's own folder
LOG = DIARY / "observations.jsonl"
TH = "Asia/Bangkok"
BIG_RANGE, AGAINST, RUN = 2.0, 1.0, 1.5  # surprise thresholds, in H1 ATR (see score())
KEYS = re.compile(r"\| rhythm|^\s+now |equal (bottoms|tops)|SWEEP|squeeze|steps|nearest line|strong levels|"
                  r"volatility|phase|structure:|ELEPHANT|TIGER|BOAR|DEER|RABBIT|nothing clear|^- \d\d:\d\d T\d")


def fetch() -> str:
    """Refresh the bars read-only; returns '' when fine, else the reason it failed."""
    cmd = [sys.executable, str(ROOT / "scripts/download_history.py"), "--symbols", "XAUUSD",
           "--timeframes", "M1,M5,M15,H1,H4,D1", "--days", "3"]
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600, check=False)  # noqa: S603
    except subprocess.TimeoutExpired:
        return "the refresh timed out after 10 minutes"
    return "" if r.returncode == 0 else f"the refresh failed (exit {r.returncode}): {(r.stderr or r.stdout)[-300:]}"


def observe(as_of: pd.Timestamp, m1: pd.DataFrame) -> dict:
    """The reading at ``as_of`` that the next hour is scored against (bars closed by ``as_of`` only)."""
    t = as_of.value
    rec: dict = {"as_of": as_of.isoformat(), "price": float(m1.close.iloc[-1])}
    for tf in ("M15", "H1", "H4", "D1"):
        sign, atr, _, _, big = RS.rhythm(closed(RS.load(tf, as_of), t), t)
        rec[f"{tf}_rhythm"], rec[f"{tf}_atr"], rec[f"{tf}_big"] = sign, atr, big.sign
    D1 = frame("D1")[1]
    st = zg.grid_at(zg.grid_rows(D1.t_open, D1.o, D1.h, D1.lo, D1.c), t)
    half = zg.GridState(st.anchor, st.step / 2, st.last_shift, st.row)
    rec["step"] = st.step
    rec["line_above"] = zg.next_line(half, rec["price"], 1, 0.05)
    rec["line_below"] = zg.next_line(half, rec["price"], -1, 0.05)
    return rec


def score(prev: dict, m1: pd.DataFrame, as_of: pd.Timestamp) -> dict:
    """What price did from the previous reading to now, against what that reading said."""
    seg = m1[(m1.index >= pd.Timestamp(prev["as_of"])) & (m1.index < as_of)]
    if seg.empty:
        return {"bars": 0}
    p, s, atr = prev["price"], prev["M15_rhythm"], prev["H1_atr"]
    hi, lo, last = float(seg.high.max()), float(seg.low.min()), float(seg.close.iloc[-1])
    up, down = hi - p, p - lo
    first = "neither"
    for bar in seg.itertuples():
        a, b = bar.high >= prev["line_above"], bar.low <= prev["line_below"]
        if a or b:
            first = "both in one bar" if a and b else f"above {prev['line_above']:.2f}" if a else f"below {prev['line_below']:.2f}"
            break
    out = {"bars": len(seg), "high": hi, "low": lo, "last": last, "first_line": first, "surprises": []}
    if s:
        out["with"], out["against"] = (up, down) if s > 0 else (down, up)
        out["rhythm_held"] = out["with"] > out["against"]
        if out["against"] >= AGAINST * atr:
            out["surprises"].append(f"went {out['against']:.1f} USD ({out['against'] / atr:.1f} H1 ATR) AGAINST the M15 rhythm "
                                    f"({'up' if s > 0 else 'down'}) read at {p:.2f}")
    elif max(up, down) >= RUN * atr:
        out["surprises"].append(f"ran {'up' if up > down else 'down'} {max(up, down):.1f} USD ({max(up, down) / atr:.1f} H1 ATR) "
                                f"with NO M15 rhythm read beforehand")
    if hi - lo >= BIG_RANGE * atr:
        out["surprises"].append(f"a big hour: range {hi - lo:.1f} USD = {(hi - lo) / atr:.1f} H1 ATR")
    return out


def read_all(as_of: pd.Timestamp) -> str:
    env = dict(os.environ, TAA_OBSERVER="1")  # routine_read then leaves live/ to the trader's own reads
    parts = []
    for script in ("rhythm_scan.py", "picture_read.py", "routine_read.py"):
        r = subprocess.run([sys.executable, str(HERE / script), as_of.strftime("%Y-%m-%dT%H:%M")],  # noqa: S603
                           cwd=ROOT, capture_output=True, text=True, env=env, timeout=600, check=False)
        parts.append(r.stdout if r.returncode == 0 else f"[{script} failed]\n{r.stderr[-500:]}")
    return "\n".join(parts)


def scorecard(rows: list[dict]) -> str:
    scored = [r["score"] for r in rows if r.get("score", {}).get("rhythm_held") is not None][-20:]
    if not scored:
        return "no hour with an M15 rhythm scored yet"
    held = sum(x["rhythm_held"] for x in scored)
    w = sum(x["with"] for x in scored) / len(scored)
    a = sum(x["against"] for x in scored) / len(scored)
    return (f"the last {len(scored)} hours read with an M15 rhythm: it held {held}; mean move with it {w:.1f} USD, "
            f"against it {a:.1f} USD")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    problem = "" if "--no-fetch" in sys.argv else fetch()
    m1 = ZW.load("M1")
    as_of = pd.Timestamp(args[0], tz="UTC") if args else m1.index[-1] + pd.Timedelta(minutes=1)
    m1 = m1[m1.index < as_of]
    DIARY.mkdir(exist_ok=True)
    (DIARY / "raw").mkdir(exist_ok=True)
    rows = [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines()] if LOG.exists() else []
    if rows and pd.Timestamp(rows[-1]["as_of"]) >= as_of:
        print(f"no new bars since {rows[-1]['as_of']} (market closed or the refresh brought nothing){': ' + problem if problem else ''}")
        return
    rec = observe(as_of, m1)
    rec["fetch_problem"] = problem
    if rows:
        rec["score"] = score(rows[-1], m1, as_of)
    th = as_of.tz_convert(TH)
    text = read_all(as_of)
    (DIARY / "raw" / f"{th:%Y-%m-%d_%H%M}.txt").write_text(text, encoding="utf-8")

    out = [f"\n## {th:%H:%M} Thai - price {rec['price']:.2f}\n"]
    if problem:
        out.append(f"- DATA: {problem} - the stored bars were read")
    sc = rec.get("score")
    if sc and sc.get("bars"):
        prev = rows[-1]
        held = sc.get("rhythm_held")
        out.append(f"- since {pd.Timestamp(prev['as_of']).tz_convert(TH):%H:%M} ({prev['price']:.2f}): high {sc['high']:.2f}, low "
                   f"{sc['low']:.2f}, now {sc['last']:.2f}; first half line reached: {sc['first_line']}"
                   + ("" if held is None else f"; the M15 rhythm {'HELD' if held else 'did NOT hold'} "
                      f"(with {sc['with']:.1f} / against {sc['against']:.1f} USD)"))
        for x in sc["surprises"]:
            out.append(f"- SURPRISE: {x}")
    side = {1: "UP", -1: "DOWN", 0: "none"}
    out.append(f"- reading: rhythm M15 {side[rec['M15_rhythm']]}, H1 {side[rec['H1_rhythm']]}, H4 {side[rec['H4_rhythm']]}, "
               f"D1 {side[rec['D1_rhythm']]}; half lines {rec['line_below']:.2f} below / {rec['line_above']:.2f} above "
               f"(step {rec['step']:.1f}); H1 ATR {rec['H1_atr']:.2f}")
    out.append("- what the readers saw:")
    out += [f"    {ln.strip()}" for ln in text.splitlines() if KEYS.search(ln) and not ln.startswith("#")]
    out.append(f"- scorecard: {scorecard([*rows, rec])}")
    day = DIARY / f"{th:%Y-%m-%d}.md"
    head = "" if day.exists() else (f"# Market diary - {th:%a %d %b %Y} (Thai time; written by observe.py, the reading "
                                    "before the hour it is scored on)\n")
    with day.open("a", encoding="utf-8") as f:
        f.write(head + "\n".join(out) + "\n")
    if sc and sc.get("surprises"):
        study = DIARY / "TO_STUDY.md"
        new = "" if study.exists() else "# Surprises to study - what no reading prepared for (observe.py)\n\n"
        with study.open("a", encoding="utf-8") as f:
            f.write(new + "".join(f"- [ ] {th:%Y-%m-%d %H:%M} Thai: {x} (raw/{th:%Y-%m-%d_%H%M}.txt)\n" for x in sc["surprises"]))
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=lambda v: None if isinstance(v, float) and math.isnan(v) else v) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
