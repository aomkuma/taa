"""Maintain docs/TICKETS.md: tick checklist items, set statuses, recompute the progress table.

Usage:
    python scripts/tickets.py --file docs/TICKETS_LEARNING.md sync   # any command, on another ticket file
    python scripts/tickets.py tick TAA-002 1 3        # tick items 1 and 3 of TAA-002
    python scripts/tickets.py tick TAA-001 all        # tick every item
    python scripts/tickets.py status TAA-005 BLOCKED  # set status explicitly
    python scripts/tickets.py show TAA-002            # print a ticket with item numbers
    python scripts/tickets.py sync                    # recompute statuses + progress table

A ticket becomes DONE when all items are ticked, IN PROGRESS when some are (unless BLOCKED).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TICKETS = Path(__file__).resolve().parent.parent / "docs" / "TICKETS.md"
HEAD_RE = re.compile(r"^#### (TAA-[0-9A-Z]+) — ")
ITEM_RE = re.compile(r"^- \[( |x)\] ")
STATUS_RE = re.compile(r"^- \*\*Status:\*\* (\S+(?: \S+)?)$")
PHASE_RE = re.compile(r"^### (Phase .+)$")
PROGRESS_ROW_RE = re.compile(r"^\| M\d+ \|")


def load() -> list[str]:
    return TICKETS.read_text(encoding="utf-8").splitlines()


def save(lines: list[str]) -> None:
    TICKETS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ticket_span(lines: list[str], tid: str) -> tuple[int, int]:
    start = next(
        (i for i, line in enumerate(lines) if HEAD_RE.match(line) and HEAD_RE.match(line).group(1) == tid),
        None,
    )
    if start is None:
        raise SystemExit(f"ticket {tid} not found")
    end = start + 1
    while end < len(lines) and not lines[end].startswith(("#### ", "### ", "## ", "> **")):
        end += 1
    return start, end


def items(lines: list[str], start: int, end: int) -> list[int]:
    return [i for i in range(start, end) if ITEM_RE.match(lines[i])]


def recompute(lines: list[str]) -> None:
    """Derive ticket statuses from checkboxes and rebuild the progress table."""
    phase_stats: dict[str, list[int]] = {}
    phase = None
    i = 0
    while i < len(lines):
        m = PHASE_RE.match(lines[i])
        if m:
            phase = m.group(1)
            phase_stats.setdefault(phase, [0, 0, 0])  # tickets, done, in-progress
        h = HEAD_RE.match(lines[i])
        if h and phase:
            start, end = ticket_span(lines, h.group(1))
            idx = items(lines, start, end)
            ticked = sum(1 for j in idx if lines[j].startswith("- [x]"))
            status_line = next(j for j in range(start, end) if STATUS_RE.match(lines[j]))
            current = STATUS_RE.match(lines[status_line]).group(1)
            if idx and ticked == len(idx):
                new = "DONE"
            elif current == "BLOCKED":
                new = "BLOCKED"
            elif ticked:
                new = "IN PROGRESS"
            else:
                new = current if current in ("IN PROGRESS",) else "TODO"
            lines[status_line] = f"- **Status:** {new}"
            stats = phase_stats[phase]
            stats[0] += 1
            stats[1] += new == "DONE"
            stats[2] += new in ("IN PROGRESS", "BLOCKED")
            i = end
            continue
        i += 1
    for k, line in enumerate(lines):
        if PROGRESS_ROW_RE.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            ms, ph = cells[0], cells[1]
            total, done, active = phase_stats.get(ph, [int(cells[2]), 0, 0])
            if total == 0:
                status = "TODO"
            else:
                status = "DONE" if done == total else ("IN PROGRESS" if done or active else "TODO")
            lines[k] = f"| {ms} | {ph} | {total} | {done} | {status} |"


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    global TICKETS
    if argv[:1] == ["--file"] and len(argv) >= 2:
        TICKETS = Path(argv[1]).resolve()
        argv = argv[2:]
    if not argv:
        raise SystemExit(__doc__)
    cmd, *rest = argv
    lines = load()
    if cmd == "tick":
        tid, *which = rest
        start, end = ticket_span(lines, tid)
        idx = items(lines, start, end)
        targets = idx if which == ["all"] else [idx[int(n) - 1] for n in which]
        for j in targets:
            lines[j] = lines[j].replace("- [ ] ", "- [x] ", 1)
    elif cmd == "untick":
        tid, *which = rest
        start, end = ticket_span(lines, tid)
        idx = items(lines, start, end)
        for n in which:
            lines[idx[int(n) - 1]] = lines[idx[int(n) - 1]].replace("- [x] ", "- [ ] ", 1)
    elif cmd == "status":
        tid, status = rest[0], " ".join(rest[1:])
        start, end = ticket_span(lines, tid)
        j = next(j for j in range(start, end) if STATUS_RE.match(lines[j]))
        lines[j] = f"- **Status:** {status}"
    elif cmd == "show":
        start, end = ticket_span(lines, rest[0])
        n = 0
        for line in lines[start:end]:
            if ITEM_RE.match(line):
                n += 1
                print(f"{n:>2}. {line}")
            elif line.strip():
                print("    " + line)
        return
    elif cmd != "sync":
        raise SystemExit(f"unknown command {cmd}")
    recompute(lines)
    save(lines)


if __name__ == "__main__":
    main(sys.argv[1:])
