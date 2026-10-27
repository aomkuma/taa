"""One-way daily orchestration for the non-ordering shadow journal."""

from __future__ import annotations

from pathlib import Path

from .adapter import scan
from .journal import ShadowJournal
from .outcome_adapter import settle
from .report import write_report
from .service import score_pending


def run_cycle(
    journal: ShadowJournal,
    *,
    m1_path: Path,
    tick_root: Path,
    start_day: str,
    end_day: str,
    report_output: Path,
) -> dict[str, object]:
    """Advance entries, decisions, outcomes and report in causal order."""
    journal.initialize()
    scan_counts = scan(
        journal,
        m1_path=m1_path,
        tick_root=tick_root,
        start_day=start_day,
        end_day=end_day,
    )
    decisions_added = score_pending(journal)
    settlement_counts = settle(journal, m1_path=m1_path, tick_root=tick_root)
    report = write_report(journal, report_output)
    return {
        "mode": "SHADOW_ONLY_NO_ORDER_CAPABILITY",
        "range": {"start": start_day, "end": end_day},
        "scan": scan_counts,
        "decisions_added": decisions_added,
        "settlement": settlement_counts,
        "report": report,
    }
