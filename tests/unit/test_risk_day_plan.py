"""The trading day's plan as a gate (P26).

The owner recorded "every trading day starts with its plan" as a principle on 2026-10-25, it went into
the knowledge base and into a memory, and on the evening of 2026-10-27 the engine still opened a DEMO
session without one. These cases exist because a note cannot refuse anything and a gate can.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.risk.day_plan import TH, DayPlan, trading_date


def at(hour: int, minute: int = 0, day: int = 27) -> datetime:
    """A moment given in Thai time, returned in UTC as the engine's clock hands it over."""
    return datetime(2026, 10, day, hour, minute, tzinfo=TH).astimezone(UTC)


class TestTheTradingDay:
    """07:00 Thai to 07:00 Thai, so a plan written on Tuesday morning still covers Wednesday's NY hours."""

    def test_the_day_turns_at_seven_in_the_morning_thai(self) -> None:
        assert trading_date(at(6, 59)) == "2026-10-26"  # still the previous trading day
        assert trading_date(at(7, 0)) == "2026-10-27"  # the Asia window opens the new one
        assert trading_date(at(23, 30)) == "2026-10-27"
        assert trading_date(at(2, 0, day=28)) == "2026-10-27"  # the middle of New York

    def test_it_reads_the_thai_clock_whatever_zone_the_moment_arrives_in(self) -> None:
        # 00:30 UTC on the 28th is 07:30 Thai: past the turn, so it is the 28th
        assert trading_date(datetime(2026, 10, 28, 0, 30, tzinfo=UTC)) == "2026-10-28"
        # 23:00 UTC on the 27th is 06:00 Thai on the 28th: BEFORE the turn, so still the 27th
        assert trading_date(datetime(2026, 10, 27, 23, 0, tzinfo=UTC)) == "2026-10-27"


class TestThePlanFile:
    def test_no_file_means_the_day_is_unplanned(self, tmp_path: Path) -> None:
        assert DayPlan(tmp_path).exists(at(9)) is False

    def test_a_written_plan_opens_the_day(self, tmp_path: Path) -> None:
        plan = DayPlan(tmp_path)
        plan.write(at(6, 30), "the condition, the levels, the scenarios")
        assert plan.exists(at(6, 30)) is True

    def test_an_empty_file_is_not_a_plan(self, tmp_path: Path) -> None:
        # a redirect that failed halfway would otherwise open the gate
        plan = DayPlan(tmp_path)
        plan.path(at(9)).parent.mkdir(parents=True, exist_ok=True)
        plan.path(at(9)).write_bytes(b"")
        assert plan.exists(at(9)) is False

    def test_yesterdays_plan_does_not_cover_today(self, tmp_path: Path) -> None:
        plan = DayPlan(tmp_path)
        plan.write(at(9, day=26), "yesterday's plan")
        assert plan.exists(at(9, day=26)) is True
        assert plan.exists(at(9, day=27)) is False

    def test_a_plan_written_in_the_morning_still_covers_the_new_york_hours(self, tmp_path: Path) -> None:
        plan = DayPlan(tmp_path)
        plan.write(at(7, 15), "written as the Asia window opens")
        assert plan.exists(at(2, 0, day=28)) is True  # 02:00 Thai the next morning, mid New York

    def test_a_plan_written_before_seven_is_filed_under_the_day_before(self, tmp_path: Path) -> None:
        """A trap worth a test: 06:45 Thai is still yesterday's trading day, so a plan written then
        does NOT open the day that is about to start. Write it at or after 07:00."""
        plan = DayPlan(tmp_path)
        plan.write(at(6, 45), "too early")
        assert plan.path(at(6, 45)).name == "2026-10-26.md"
        assert plan.exists(at(9)) is False  # 09:00 Thai on the 27th is still unplanned

    def test_a_day_is_not_replanned_over_the_top_of_itself(self, tmp_path: Path) -> None:
        plan = DayPlan(tmp_path)
        plan.write(at(7), "the first plan")
        with pytest.raises(FileExistsError):
            plan.write(at(20), "a second, convenient one")
        assert plan.path(at(7)).read_text(encoding="utf-8") == "the first plan"


class TestTheGapsTheReviewFound:
    """Added after the developer session planted bugs in `day_plan.py` on 2026-10-27 and found four
    contracts that no case asserted: the boundary's direction, "a file, not a directory", the folder
    being created, and the unreadable-path branch. 10 of its 14 mutations were caught before these."""

    def test_the_boundary_faces_the_right_way(self) -> None:
        # flipping `< 07:00` to `> 07:00` passed every earlier case: they only asked that two instants
        # differ, never which trading date each one belongs to
        assert trading_date(at(6, 59)) == "2026-10-26"
        assert trading_date(at(7, 1)) == "2026-10-27"
        assert trading_date(at(12, 0)) == "2026-10-27"

    def test_a_directory_with_the_plan_s_name_is_not_a_plan(self, tmp_path: Path) -> None:
        plan = DayPlan(tmp_path)
        plan.path(at(9)).mkdir(parents=True)  # `is_file()` is what keeps this out
        assert plan.exists(at(9)) is False

    def test_a_file_of_whitespace_is_not_a_plan(self, tmp_path: Path) -> None:
        plan = DayPlan(tmp_path)
        plan.path(at(9)).parent.mkdir(parents=True, exist_ok=True)
        plan.path(at(9)).write_bytes(b"   \n\t\n")
        assert plan.exists(at(9)) is False

    def test_writing_creates_the_folder_and_hands_back_where_it_went(self, tmp_path: Path) -> None:
        plan = DayPlan(tmp_path / "nested" / "plans")
        written = plan.write(at(8), "the plan")
        assert written == plan.path(at(8)) and written.is_file()

    def test_an_unreadable_path_counts_as_unplanned(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        plan = DayPlan(tmp_path)
        plan.write(at(8), "the plan")

        def boom(*_a: object, **_k: object) -> object:
            raise OSError("the mount went away")

        monkeypatch.setattr(Path, "open", boom)  # exists() reads a bounded head, not read_text
        assert plan.exists(at(8)) is False  # fail closed, never "assume it is fine"

    def test_a_moment_given_in_a_third_timezone_reads_the_same(self) -> None:
        from zoneinfo import ZoneInfo

        ny = datetime(2026, 10, 27, 9, 0, tzinfo=ZoneInfo("America/New_York"))  # 20:00 Thai
        assert trading_date(ny) == "2026-10-27"
        early = datetime(2026, 10, 26, 19, 30, tzinfo=ZoneInfo("America/New_York"))  # 06:30 Thai on the 27th
        assert trading_date(early) == "2026-10-26"


def test_a_plan_that_is_not_text_counts_as_unplanned(tmp_path: Path) -> None:
    """Invalid UTF-8 used to escape as an exception instead of a DAY_PLAN refusal: the gate must be able
    to say why it refused (developer session, 2026-10-27)."""
    plan = DayPlan(tmp_path)
    plan.path(at(9)).parent.mkdir(parents=True, exist_ok=True)
    plan.path(at(9)).write_bytes(b"\xff\xfe not text at all")
    assert plan.exists(at(9)) is False


def test_a_very_large_plan_is_not_read_whole(tmp_path: Path) -> None:
    from app.risk.day_plan import READ_LIMIT

    plan = DayPlan(tmp_path)
    plan.path(at(9)).parent.mkdir(parents=True, exist_ok=True)
    plan.path(at(9)).write_bytes(b"x" * (READ_LIMIT * 4))
    assert plan.exists(at(9)) is True  # still a plan, but only the head was read
