# ruff: noqa: T201
"""Command-line interface for the non-ordering shadow journal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapter import scan
from .journal import ShadowJournal
from .outcome_adapter import settle
from .pipeline import run_cycle
from .report import build_report, write_report
from .schema import Opportunity, Outcome
from .service import policy_manifest, score_pending


def _records(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list) and all(isinstance(value, dict) for value in raw):
        return raw
    raise ValueError("input JSON must be an object or a list of objects")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="TREND-RUNNER shadow journal (no order capability)")
    result.add_argument("--db", type=Path, required=True)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    opportunity = commands.add_parser("ingest-opportunity")
    opportunity.add_argument("json_file", type=Path)
    outcome = commands.add_parser("ingest-outcome")
    outcome.add_argument("json_file", type=Path)
    commands.add_parser("score")
    scan_command = commands.add_parser("scan")
    scan_command.add_argument("--m1", type=Path, required=True)
    scan_command.add_argument("--tick-root", type=Path, required=True)
    scan_command.add_argument("--start", required=True)
    scan_command.add_argument("--end", required=True)
    settle_command = commands.add_parser("settle")
    settle_command.add_argument("--m1", type=Path, required=True)
    settle_command.add_argument("--tick-root", type=Path, required=True)
    cycle_command = commands.add_parser("cycle")
    cycle_command.add_argument("--m1", type=Path, required=True)
    cycle_command.add_argument("--tick-root", type=Path, required=True)
    cycle_command.add_argument("--start", required=True)
    cycle_command.add_argument("--end", required=True)
    cycle_command.add_argument("--report-output", type=Path, required=True)
    commands.add_parser("status")
    report = commands.add_parser("report")
    report.add_argument("--output", type=Path, required=True)
    commands.add_parser("policies")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    journal = ShadowJournal(args.db)
    if args.command == "init":
        journal.initialize()
        print(json.dumps({"status": "initialized", "db": str(journal.path), "mode": "NO_ORDERS"}))
        return 0
    journal.initialize()
    if args.command == "ingest-opportunity":
        added = sum(
            journal.record_opportunity(Opportunity.from_dict(raw)) for raw in _records(args.json_file)
        )
        print(json.dumps({"added": added}))
    elif args.command == "ingest-outcome":
        added = sum(journal.record_outcome(Outcome.from_dict(raw)) for raw in _records(args.json_file))
        print(json.dumps({"added": added}))
    elif args.command == "score":
        print(json.dumps({"decisions_added": score_pending(journal)}))
    elif args.command == "scan":
        print(
            json.dumps(
                scan(
                    journal,
                    m1_path=args.m1,
                    tick_root=args.tick_root,
                    start_day=args.start,
                    end_day=args.end,
                ),
                indent=2,
            )
        )
    elif args.command == "settle":
        print(
            json.dumps(
                settle(journal, m1_path=args.m1, tick_root=args.tick_root),
                indent=2,
            )
        )
    elif args.command == "cycle":
        print(
            json.dumps(
                run_cycle(
                    journal,
                    m1_path=args.m1,
                    tick_root=args.tick_root,
                    start_day=args.start,
                    end_day=args.end,
                    report_output=args.report_output,
                ),
                indent=2,
            )
        )
    elif args.command == "status":
        print(json.dumps(build_report(journal), indent=2))
    elif args.command == "report":
        print(json.dumps(write_report(journal, args.output), indent=2))
    elif args.command == "policies":
        print(policy_manifest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
