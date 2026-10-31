"""Run variants of bot 2e side by side on one date range, fairly: each into its own files, scored in memory.

    python eye/bot_research.py --from 2026-10-01 --to 2026-10-28                 # the built-in variants
    python eye/bot_research.py --from 2026-10-01 --to 2026-10-28 --variants v.json --only r3_off

The built-in variants are ``r3_now`` (every parameter at its default) and ``r3_off`` (``m5_trend`` off: rule 3
not applied). ``v.json`` is ``{"name": {"m5_trend": "off", ...}}``: overrides of the current ``Params``.
Each variant writes ``eye/research/<name>/ledger.csv``, ``log.csv`` and ``summary.csv`` (never
``eye/bot_ledger.csv``, never Claude's ledgers) and is scored with ``eye/score.py`` unchanged. Money is the
record in USD from 200 at 0.01 lot: a filled trade is its ``r_net`` x its stop distance x 1 oz. ``r_net`` is
net of the spread.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
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
    "timestamp", "from", "to", "variant", "params", "orders", "fills", "wins", "losses", "open",
    "r_total", "r_per_fill", "usd_from_200", "deepest_fall", "top_reasons",
]  # fmt: skip

PEAKS: dict[str, dict[str, int]] = {}  # per variant: the most orders live / filled-and-open at once

DEFAULT_VARIANTS: dict[str, dict[str, Any]] = {
    "r3_now": {},
    "r3_off": {"m5_trend": "off"},
}


def _order_key(row: dict[str, str]) -> str:
    """Decision order: ``decided_at`` is ``dd/mm HH:MM``, so month first."""
    return row["decided_at"][3:5] + row["decided_at"]


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
    """Orders, fills, wins, losses, open, R (net of spread), R a fill, USD from 200 and the deepest fall."""
    filled = [r for r in rows if r["why"] in ("target", "stop")]
    open_ = [r for r in rows if r["why"] == "open"]
    balance = peak = START_BALANCE
    fall = r_total = 0.0
    gone = ""  # once the balance reaches 0 or below, no more money is counted (R keeps counting all trades)
    for r in sorted(rows, key=_order_key):  # month then day/time text
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
        "orders": len(rows),
        "fills": len(filled),
        "wins": sum(1 for r in filled if r["why"] == "target"),
        "losses": sum(1 for r in filled if r["why"] == "stop"),
        "open": len(open_),
        "r_total": round(r_total, 2),
        "r_per_fill": round(r_total / len(filled), 3) if filled else 0.0,
        "usd_from_200": round(balance, 2),
        "deepest_fall": round(fall, 2),
        "account_gone": gone,
    }


NAME_OK = re.compile(r"[A-Za-z0-9_-]+")


def variant_folder(name: str, root: Path = RESEARCH) -> Path:
    """The folder a variant writes into: ``root / name``. The name is letters, digits, ``_`` and ``-`` only,
    and the resolved folder must be a direct child of ``root`` - a name that would leave it (``..``, a path,
    an absolute path) is refused (``SystemExit``), before anything is run or written."""
    if not NAME_OK.fullmatch(name):
        raise SystemExit(f"variant name {name!r}: only letters, digits, _ and - are allowed")
    folder = (root / name).resolve()
    if folder.parent != root.resolve():
        raise SystemExit(f"variant name {name!r} resolves outside {root}")
    return folder


def run_variant(
    name: str, overrides: dict[str, Any], first: str, last: str, full: dict[str, Any], m5: Any,
    root: Path = RESEARCH,
) -> dict[str, Any]:  # fmt: skip
    folder = variant_folder(name, root)  # refused before the (long) walk when the name is not a plain name
    p = make_params(overrides)
    rows, logs = bot2e.walk_days(bot2e.days_between(first, last), p, full)
    rows = scored_rows(rows, m5, p.spread)
    folder.mkdir(parents=True, exist_ok=True)
    bot2e._write(folder / "ledger.csv", bot2e.LEDGER_COLUMNS, rows)
    bot2e._write(folder / "log.csv", bot2e.LOG_COLUMNS, logs)
    counts = Counter(r["reason"] for r in logs if r["reason"] not in ("market closed", "outside window"))
    top = "; ".join(f"{k} {v}" for k, v in counts.most_common(3))
    PEAKS[name] = dict(bot2e.PEAK)
    result = {
        "variant": name,
        "params": json.dumps(asdict(p)),
        **(m := money(rows)),
        "top_reasons": top
        + (f"; account gone at {m['account_gone']} (R counts all trades)" if m["account_gone"] else ""),
        "trades": trade_lines(rows),
    }
    write_summary(result, folder, first, last)
    return result


def kind_of(row: dict[str, str]) -> str:
    """The kind of an order from its record: ``retest`` (rule 17), ``fade`` (a fade leg) or ``trend``."""
    text = row.get("structure", "")
    if "break and retest" in text:
        return "retest"
    if "Fade leg" in text:
        return "fade"
    return "trend"


def trade_lines(rows: list[dict[str, str]]) -> list[str]:
    """One line per filled trade: Thai fill time, side, kind, entry, stop, target, result R (net of spread)"""
    return [
        f"{r['fill']}  {r['side']:4}  {kind_of(r):6}  entry {r['entry']}  stop {r['stop']}  "
        f"target {r['target']}  {r['why']}  R {float(r['r_net']):+.2f}"
        for r in sorted(rows, key=_order_key)
        if r["why"] in ("target", "stop")
    ]


def write_summary(result: dict[str, Any], folder: Path, first: str, last: str) -> None:
    """The variant's own ``summary.csv`` (one row), beside its ledger and log."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerow({"timestamp": stamp, "from": first, "to": last, **result})


def table(results: list[dict[str, Any]]) -> str:
    head = (
        f"{'variant':10} {'orders':>6} {'fills':>5} {'wins':>4} {'loss':>4} {'open':>4} "
        f"{'R':>7} {'R/fill':>7} {'USD':>8} {'fall':>7}  top reasons"
    )
    lines = [head]
    for r in results:
        lines.append(
            f"{r['variant']:10} {r['orders']:6d} {r['fills']:5d} {r['wins']:4d} {r['losses']:4d} "
            f"{r['open']:4d} {r['r_total']:+7.2f} {r['r_per_fill']:+7.3f} {r['usd_from_200']:8.2f} "
            f"{r['deepest_fall']:7.2f}  {r['top_reasons']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run named variants of bot 2e on one range.")
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    ap.add_argument("--variants", help="JSON file {name: {Params overrides}}; default: r3_now and r3_off")
    ap.add_argument("--only", help="comma-separated variant names to run")
    a = ap.parse_args(argv)
    variants = json.loads(Path(a.variants).read_text(encoding="utf-8")) if a.variants else DEFAULT_VARIANTS
    if a.only:
        variants = {k: variants[k] for k in a.only.split(",")}
    for n in variants:
        variant_folder(n)  # every name is checked before the first variant runs
    full, m5 = bot2e.load_frames(), bars()
    results = [run_variant(n, o, a.first, a.last, full, m5) for n, o in variants.items()]
    print(table(results))
    for r in results:
        pk = PEAKS[r["variant"]]
        print(f"  {r['variant']}: peak live {pk['live']}, filled-and-open {pk['filled']}")
        for line in r["trades"]:
            print(f"    {line}")


if __name__ == "__main__":
    main()
