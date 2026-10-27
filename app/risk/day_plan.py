"""The trading day's plan, as a gate rather than a reminder (P26).

The owner, 2026-10-25: every trading day starts with the plan - the market's condition, yesterday's
levels, the trend, the side with the edge, the turn/go-on scenarios - written and summarised before
anything is traded. It was recorded as a principle (P26), as a knowledge-base entry and as a memory, and
on the evening of 2026-10-27 the engine still opened a DEMO session with no plan at all. The owner:
*"I went to the trouble of telling you to write it down as a principle."*

A note cannot stop anything. So the plan is now a **file whose presence is the permission**, exactly
like the kill switch: one ``stat`` per gate check, no tooling needed to satisfy it, and nothing to
forget. Without today's plan the mode gate fails and no broker order is sent; positions already open are
still managed, because refusing to manage them would be more dangerous than the missing plan.

**The day is the owner's trading day, 07:00 Thai to 07:00 Thai**, not the calendar date: a plan written
on Tuesday morning still covers Wednesday 02:00 Thai, in the middle of the New York session.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TH = ZoneInfo("Asia/Bangkok")
DAY_STARTS = time(7)  # the owner's trading day opens with the Asia window
DEFAULT_DIR = Path("data/plans")
READ_LIMIT = 64 * 1024  # enough to tell prose from an empty file

log = logging.getLogger(__name__)


def trading_date(now: datetime) -> str:
    """The Thai trading day ``now`` belongs to, as ``YYYY-MM-DD``.

    02:00 Thai on Wednesday is still Tuesday's trading day; 07:00 Thai starts the new one.
    """
    th = now.astimezone(TH)
    return (th.date() - timedelta(days=1) if th.time() < DAY_STARTS else th.date()).isoformat()


class DayPlan:
    """Is today's complete plan written?"""

    def __init__(self, directory: Path | str = DEFAULT_DIR) -> None:
        self.directory = Path(directory)

    def path(self, now: datetime) -> Path:
        return self.directory / f"{trading_date(now)}.md"

    def exists(self, now: datetime) -> bool:
        """True when the day's plan contains its condition, levels, edge side and scenarios."""
        return self.check(now)[0]

    def check(self, now: datetime) -> tuple[bool, str]:
        """Check the bounded plan text and name every required section that is missing."""
        p = self.path(now)
        try:
            if not p.is_file():
                return False, f"the day's plan is missing or is not a file: {p} (P26)"
            with p.open("rb") as fh:
                head = fh.read(READ_LIMIT)
            text = head.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            log.warning("cannot read the day plan at %s; treating the day as unplanned", p)
            return False, f"the day's plan is unreadable or not UTF-8: {p} (P26)"

        if not text.strip():
            return False, f"the day's plan is empty or whitespace-only: {p} (P26)"

        lowered = text.casefold()
        missing = [
            name
            for name, markers in (
                ("condition", (r"\bcondition\b",)),
                ("levels", (r"\blevels\b",)),
                ("side with the edge", (r"\bside with the edge\b", r"\bedge_side\b")),
                ("scenarios", (r"\bscenarios\b",)),
            )
            if not any(re.search(marker, lowered) for marker in markers)
        ]
        if missing:
            return False, "the day's plan is incomplete; missing: " + ", ".join(missing) + f" ({p}, P26)"
        return True, f"the day's plan has condition, levels, side with the edge and scenarios ({p})"

    def write(self, now: datetime, text: str) -> Path:
        """Record the day's plan. Refuses to overwrite one: a day has one plan, added to, not replaced."""
        p = self.path(now)
        if self.exists(now):
            raise FileExistsError(f"the plan for {trading_date(now)} is already written: {p}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        log.info("the plan for %s is recorded (%s)", trading_date(now), p)
        return p
