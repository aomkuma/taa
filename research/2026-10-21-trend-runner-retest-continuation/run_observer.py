"""Run isolated RETEST-CONTINUATION V1 observation from read-only shadow inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from journal import CandidateJournal
from source_adapter import process_forward_source

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DB = ROOT / "research/2026-10-20-trend-runner-shadow/shadow_journal.sqlite"
DEFAULT_M1 = ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet"
DEFAULT_TICKS = ROOT / "data/ticks/XAUUSD"
DEFAULT_CANDIDATE_DB = Path(__file__).resolve().parent / "candidate_journal.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--m1", type=Path, default=DEFAULT_M1)
    parser.add_argument("--tick-root", type=Path, default=DEFAULT_TICKS)
    parser.add_argument("--candidate-db", type=Path, default=DEFAULT_CANDIDATE_DB)
    args = parser.parse_args()

    journal = CandidateJournal(args.candidate_db)
    journal.initialize()
    counts = process_forward_source(
        args.source_db, m1_path=args.m1, tick_root=args.tick_root, journal=journal
    )
    print(json.dumps({"status_counts": counts, "journal": journal.counts()}, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()
