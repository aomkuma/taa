"""Run variants of bot 2e side by side on one date range, fairly: each into its own files, scored in memory.

    python eye/bot_research.py --from 2026-10-01 --to 2026-10-27                 # the built-in variants
    python eye/bot_research.py --from 2026-10-01 --to 2026-10-27 --variants v.json --only base_strict,h4_side

``v.json`` is ``{"name": {"band_frac": 0.15, ...}, ...}`` - overrides of ``bot2e.Params``. Each variant writes
``eye/research/<name>/ledger.csv`` and ``log.csv`` (never ``eye/bot_ledger.csv``, never Claude's ledgers), is
scored with ``eye/score.py`` unchanged, and appends one row to ``eye/research/summary.csv``. Money is the
record in USD from 200 at 0.01 lot: a filled trade is its ``r_net`` x its stop distance x 1 oz.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict, fields, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from eye import bot2e  # noqa: E402
from eye.score import SPREAD, bars, score, start_of  # noqa: E402

RESEARCH = HERE / "research"
OZ = 1.0  # 0.01 lot of gold = 1 oz: 1.00 of price = 1 USD
START_BALANCE = 200.0
SUMMARY_COLUMNS = [
    "timestamp", "from", "to", "variant", "params", "decisions", "filled", "won", "lost", "open",
    "r_total", "usd_from_200", "deepest_fall", "top_reasons",
]  # fmt: skip

PEAKS: dict[str, dict[str, int]] = {}  # per variant: the most orders live / filled-and-open at once

DEFAULT_VARIANTS: dict[str, dict[str, Any]] = {
    "base_strict": {},
    "base_lows": {"h1_mode": "lows"},
    "both_strict": {"div_mode": "both"},
    "h4_side": {"h1_tf": "H4"},
    "swings3": {"h1_swings": 3},
    "m15_only": {"entry_tfs": "M15"},
    "band015": {"band_frac": 0.15},
    "band020": {"band_frac": 0.20},
    "window30": {"counter_pivots": 30},
    "lows_m15": {"h1_mode": "lows", "entry_tfs": "M15"},
    "lows_band015": {"h1_mode": "lows", "band_frac": 0.15},
}


def make_params(overrides: dict[str, Any]) -> bot2e.Params:
    known = {f.name for f in fields(bot2e.Params)}
    bad = set(overrides) - known
    if bad:
        raise SystemExit(f"unknown Params fields: {sorted(bad)}")
    return replace(bot2e.Params(), **overrides)


def scored_rows(rows: list[dict[str, str]], m5: Any, spread: float = SPREAD) -> list[dict[str, str]]:
    """Each decision scored in memory by score.py; the result is written beside the row."""
    out = []
    for r in rows:
        row = dict(r)
        row.update(score(row, m5, start_of(row, {}), spread))
        out.append(row)
    return out


def money(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Decisions, fills, wins, losses, open, R, USD from 200 and the deepest fall, in decision order."""
    filled = [r for r in rows if r["why"] in ("target", "stop")]
    open_ = [r for r in rows if r["why"] == "open"]
    balance = peak = START_BALANCE
    fall = r_total = 0.0
    gone = ""  # once the balance reaches 0 or below, no more money is counted (R keeps counting all trades)
    for r in sorted(rows, key=lambda r: r["decided_at"][3:5] + r["decided_at"]):  # month then day/time text
        if r["why"] not in ("target", "stop"):
            continue
        r_total += float(r["r_net"])
        if gone:
            continue
        balance += float(r["r_net"]) * abs(float(r["entry"]) - float(r["stop"])) * OZ
        peak = max(peak, balance)
        fall = max(fall, peak - balance)
        if balance <= 0:
            gone = r["decided_at"][:5]  # dd/mm of the trade that ended the account
    return {
        "decisions": len(rows),
        "filled": len(filled),
        "won": sum(1 for r in filled if r["why"] == "target"),
        "lost": sum(1 for r in filled if r["why"] == "stop"),
        "open": len(open_),
        "r_total": round(r_total, 2),
        "usd_from_200": round(balance, 2),
        "deepest_fall": round(fall, 2),
        "account_gone": gone,
    }


def run_variant(
    name: str, overrides: dict[str, Any], first: str, last: str, full: dict[str, Any], m5: Any,
    root: Path = RESEARCH,
) -> dict[str, Any]:  # fmt: skip
    p = make_params(overrides)
    rows, logs = bot2e.walk_days(bot2e.days_between(first, last), p, full)
    rows = scored_rows(rows, m5, p.spread)
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    bot2e._write(folder / "ledger.csv", bot2e.LEDGER_COLUMNS, rows)
    bot2e._write(folder / "log.csv", bot2e.LOG_COLUMNS, logs)
    counts = Counter(r["reason"] for r in logs if r["reason"] not in ("market closed", "outside window"))
    top = "; ".join(f"{k} {v}" for k, v in counts.most_common(3))
    PEAKS[name] = dict(bot2e.PEAK)
    return {
        "variant": name,
        "params": json.dumps(asdict(p)),
        **(m := money(rows)),
        "top_reasons": top
        + (f"; account gone at {m['account_gone']} (R counts all trades)" if m["account_gone"] else ""),
    }


def append_summary(results: list[dict[str, Any]], first: str, last: str, root: Path = RESEARCH) -> None:
    path = root / "summary.csv"
    new = not path.exists()
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in results:
            w.writerow({"timestamp": stamp, "from": first, "to": last, **r})


def table(results: list[dict[str, Any]]) -> str:
    head = (
        f"{'variant':14} {'dec':>3} {'fill':>4} {'won':>3} {'lost':>4} {'open':>4} "
        f"{'R':>7} {'USD':>8} {'fall':>7}  top reasons"
    )
    lines = [head]
    for r in results:
        lines.append(
            f"{r['variant']:14} {r['decisions']:3d} {r['filled']:4d} {r['won']:3d} {r['lost']:4d} "
            f"{r['open']:4d} "
            f"{r['r_total']:+7.2f} {r['usd_from_200']:8.2f} {r['deepest_fall']:7.2f}  {r['top_reasons']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run named variants of bot 2e on one range.")
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    ap.add_argument("--variants", help="JSON file {name: {Params overrides}}; default: the built-in eleven")
    ap.add_argument("--only", help="comma-separated variant names to run")
    a = ap.parse_args(argv)
    variants = json.loads(Path(a.variants).read_text(encoding="utf-8")) if a.variants else DEFAULT_VARIANTS
    if a.only:
        variants = {k: variants[k] for k in a.only.split(",")}
    full, m5 = bot2e.load_frames(), bars()
    results = [run_variant(n, o, a.first, a.last, full, m5) for n, o in variants.items()]
    append_summary(results, a.first, a.last)
    print(table(results))
    for n, pk in PEAKS.items():
        print(f"  peak {n}: live {pk['live']}, filled-and-open {pk['filled']}")


if __name__ == "__main__":
    main()
