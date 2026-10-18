"""The US release calendar (official dates: BLS, BEA, the Federal Reserve; research/2026-10-18-moments/
build_calendar.py): one row per release, ``date,time_et,event[,note]`` with the time in New York local time.

Setup OWN S2 (the CPI / NFP release-minute straddle, docs/OWN_SETUP.md) trades at these instants; a missing or
malformed file is a :class:`ConfigError` (fail closed: no calendar, no release trades).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.errors import ConfigError

NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class Release:
    at: datetime  # UTC
    event: str  # CPI, NFP, PPI, PCE, GDP, FOMC, ...


def parse_releases(rows: Iterable[dict[str, str]]) -> tuple[Release, ...]:
    out = []
    for n, row in enumerate(rows, start=2):
        try:
            day = date.fromisoformat(row["date"].strip())
            hours, _, minutes = row["time_et"].strip().partition(":")
            local = datetime.combine(day, time(int(hours), int(minutes)), tzinfo=NEW_YORK)
            event = row["event"].strip().upper()
        except (KeyError, ValueError, AttributeError) as exc:
            raise ConfigError(f"release calendar line {n}: {exc}") from exc
        if not event:
            raise ConfigError(f"release calendar line {n}: no event")
        out.append(Release(local.astimezone(ZoneInfo("UTC")), event))
    return tuple(sorted(out, key=lambda r: r.at))


def load_releases(path: Path) -> tuple[Release, ...]:
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            return parse_releases(csv.DictReader(fh))
    except OSError as exc:
        raise ConfigError(f"release calendar {path}: {exc}") from exc


def of_events(releases: Sequence[Release], events: Iterable[str]) -> tuple[Release, ...]:
    wanted = {e.upper() for e in events}
    return tuple(r for r in releases if r.event in wanted)
