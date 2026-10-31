"""Run variants of bot 2e side by side on one date range, fairly: each into its own files, scored in memory.

    python eye/bot_research.py --from 2026-10-01 --to 2026-10-28                          # the set "default"
    python eye/bot_research.py --from 2026-10-01 --to 2026-10-28 --sets default,r3_off    # two variants

A variant is a parameter set in the config database (``eye/bot_config.py``; ``--db``, default
``data/bot_config.db``) of ``--market`` (default XAUUSD). Each variant writes
``eye/research/<market>/<set>/ledger.csv``, ``log.csv`` and ``summary.csv`` (never ``eye/bot_ledger.csv``,
never Claude's ledgers) and is scored with ``eye/score.py`` unchanged; the summary and the printed table carry
the market, set and version. Money is the record in USD from 200 at 0.01 lot: a filled trade is its ``r_net``
x its stop distance x 1 oz. ``r_net`` is net of the spread.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from eye import bot2e, bot_config  # noqa: E402
from eye.score import SPREAD, bars, score, start_of  # noqa: E402

RESEARCH = HERE / "research"
OZ = 1.0  # 0.01 lot of gold = 1 oz: 1.00 of price = 1 USD
START_BALANCE = 200.0
SUMMARY_COLUMNS = [
    "timestamp", "from", "to", "market", "set", "version", "params", "orders", "fills", "wins", "losses",
    "open",
    "r_total", "r_per_fill", "usd_from_200", "deepest_fall", "top_reasons",
]  # fmt: skip

PEAKS: dict[str, dict[str, int]] = {}  # per "market/set": the most orders live / filled-and-open at once


def _order_key(row: dict[str, str]) -> str:
    """Decision order: ``decided_at`` is ``dd/mm HH:MM``, so month first."""
    return row["decided_at"][3:5] + row["decided_at"]


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


def variant_folder(market: str, set_name: str, root: Path = RESEARCH) -> Path:
    """The folder a variant writes into: ``root / market / set_name``. Both names are letters, digits,
    ``_`` and ``-`` only (``bot_config.check_name``), and the resolved folder must be
    ``root / market / set_name``: a name that would leave it (a link, say) is refused (``SystemExit``),
    before anything is run or written."""
    try:
        bot_config.check_name("market", market)
        bot_config.check_name("set", set_name)
    except bot_config.ConfigError as e:
        raise SystemExit(f"bot_research: {e}") from None
    folder = (root / market / set_name).resolve()
    if folder.parent.parent != root.resolve():
        raise SystemExit(f"{market}/{set_name} resolves outside {root}")
    return folder


def run_variant(
    market: str, set_name: str, version: int, p: bot2e.Params, first: str, last: str, full: dict[str, Any],
    m5: Any, root: Path = RESEARCH,
) -> dict[str, Any]:  # fmt: skip
    folder = variant_folder(market, set_name, root)  # refused before the (long) walk when a name is not plain
    label = bot2e.config_label(market, set_name, version)
    rows, logs = bot2e.walk_days(bot2e.days_between(first, last), p, full, label=label)
    rows = scored_rows(rows, m5, p.spread)
    folder.mkdir(parents=True, exist_ok=True)
    bot2e._write(folder / "ledger.csv", bot2e.LEDGER_COLUMNS, rows)
    bot2e._write(folder / "log.csv", bot2e.LOG_COLUMNS, logs)
    counts = Counter(r["reason"] for r in logs if r["reason"] not in ("market closed", "outside window"))
    top = "; ".join(f"{k} {v}" for k, v in counts.most_common(3))
    PEAKS[f"{market}/{set_name}"] = dict(bot2e.PEAK)
    result = {
        "market": market,
        "set": set_name,
        "version": version,
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
        f"{'market/set@version':22} {'orders':>6} {'fills':>5} {'wins':>4} {'loss':>4} {'open':>4} "
        f"{'R':>7} {'R/fill':>7} {'USD':>8} {'fall':>7}  top reasons"
    )
    lines = [head]
    for r in results:
        name = f"{r['market']}/{r['set']}@v{r['version']}"
        lines.append(
            f"{name:22} {r['orders']:6d} {r['fills']:5d} {r['wins']:4d} {r['losses']:4d} "
            f"{r['open']:4d} {r['r_total']:+7.2f} {r['r_per_fill']:+7.3f} {r['usd_from_200']:8.2f} "
            f"{r['deepest_fall']:7.2f}  {r['top_reasons']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run parameter sets of bot 2e on one range.")
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    ap.add_argument("--db", default=str(bot2e.CONFIG_DB), help="the parameter database")
    ap.add_argument("--market", default=bot2e.MARKET)
    ap.add_argument("--sets", default="default", help="comma-separated set names, one variant each")
    a = ap.parse_args(argv)
    names = a.sets.split(",")
    loaded = [
        (n, *bot2e.load_set(a.db, a.market, n)) for n in names
    ]  # every set is read before any bar is loaded
    for n in names:
        variant_folder(a.market, n, RESEARCH)  # every name is checked before the first variant runs
    full, m5 = bot2e.load_frames(), bars()
    results = [run_variant(a.market, n, v, p, a.first, a.last, full, m5, RESEARCH) for n, p, v in loaded]
    print(table(results))
    for r in results:
        pk = PEAKS[f"{r['market']}/{r['set']}"]
        print(
            f"  {r['market']}/{r['set']}@v{r['version']}: peak live {pk['live']}, "
            f"filled-and-open {pk['filled']}"
        )
        for line in r["trades"]:
            print(f"    {line}")


if __name__ == "__main__":
    main()
