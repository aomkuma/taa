"""Hand-worked tests for app/strategy/knowledge.py - the base's checks, its conditions, the owner's windows,
the brief and the frames (TAA-1803; moved from research/2026-10-23-entry/knowledge/test_kb.py)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.strategy import knowledge as kb

CHECKLIST = Path(__file__).resolve().parents[2] / "research/2026-10-23-entry/DECISION_CHECKLIST.md"

ITEMS = {"A1", "A5", "C4"}


def entry(**kw):
    e = {"id": "R01", "kind": "rule", "stage": "pressure", "says": "x", "source": "y", "items": ["A5"]}
    e.update(kw)
    return e


@pytest.mark.parametrize(
    ("value", "spec", "want"),
    [
        (1.2, "> 1.1", True),
        (1.1, "> 1.1", False),
        (1.1, ">= 1.1", True),
        (1.09, ">= 1.1", False),
        (59.9, "< 60", True),
        (60.0, "< 60", False),
        (60.0, "<= 60", True),
        (60.1, "<= 60", False),
        (-0.5, "> -1", True),
        ("up", ["up", "down"], True),
        ("none", ["up", "down"], False),
        ("none", "none", True),
        ("up", "none", False),
        (None, "> 1", False),
        (math.nan, "< 1", False),
        (None, "none", False),
    ],
)
def test_one_condition(value, spec, want):
    assert kb.holds(value, spec) is want


def test_no_when_always_applies():
    assert kb.applies(entry(), {})


def test_a_map_needs_every_condition():
    e = entry(when={"h1_vol": "< 0.9", "phase": "none"})
    assert kb.applies(e, {"h1_vol": 0.8, "phase": "none"})
    assert not kb.applies(e, {"h1_vol": 0.8, "phase": "up"})
    assert not kb.applies(e, {"h1_vol": 0.95, "phase": "none"})
    assert not kb.applies(e, {"phase": "none"})  # an unknown reading never holds


def test_a_list_needs_any_alternative():
    e = entry(when=[{"h1_vol": "> 1.4"}, {"day_range_step": "> 2"}])
    assert kb.applies(e, {"h1_vol": 1.5, "day_range_step": 0.5})
    assert kb.applies(e, {"h1_vol": 1.0, "day_range_step": 2.1})
    assert not kb.applies(e, {"h1_vol": 1.4, "day_range_step": 2.0})


@pytest.mark.parametrize(
    ("utc", "want"),
    [
        ("2026-10-23T00:00", "asia"),  # 07:00 Thai
        ("2026-10-23T01:59", "asia"),  # 08:59 Thai
        ("2026-10-23T02:00", "none"),  # 09:00 Thai
        ("2026-10-23T05:59", "none"),  # 12:59 Thai
        ("2026-10-23T06:00", "london"),  # 13:00 Thai
        ("2026-10-23T07:59", "london"),  # 14:59 Thai
        ("2026-10-23T08:00", "none"),  # 15:00 Thai, 04:00 New York (EDT)
        ("2026-10-23T11:59", "none"),  # 07:59 New York
        ("2026-10-23T12:00", "ny"),  # 08:00 New York (EDT = UTC-4)
        ("2026-10-23T15:29", "ny"),  # 11:29 New York
        ("2026-10-23T15:30", "none"),  # 11:30 New York
        ("2026-01-14T12:59", "none"),  # 07:59 New York (EST = UTC-5)
        ("2026-01-14T13:00", "ny"),  # 08:00 New York in winter
    ],
)
def test_the_owners_windows(utc, want):
    assert kb.session(pd.Timestamp(utc, tz="UTC")) == want


def test_a_sound_base_has_no_problems():
    w = entry(id="W01", kind="weapon", stage="weapon", status="real", animal="tiger", items=[])
    assert kb.validate([entry(when={"h1_vol": "> 1.1"}, conflicts=["W01"]), w], ITEMS) == []


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ([entry(), entry()], "R01: the id is used 2 times"),
        ([entry(kind="shadow")], "R01: the kind 'shadow' does not match the id's letter"),
        ([entry(stage="lunch")], "R01: unknown stage 'lunch'"),
        ([entry(items=["B9"])], "R01: unknown checklist item B9"),
        ([entry(conflicts=["Z99"])], "R01: conflicts with an unknown id Z99"),
        ([entry(id="W01", kind="weapon", status="real")], "W01: a weapon needs its status and its animal"),
        ([entry(when={"moon": "full"})], "R01: unknown reading 'moon'"),
        ([entry(when={"h1_vol": 1.1})], "R01: 'h1_vol' needs a comparison like '> 1.1', not 1.1"),
        (
            [entry(when=[{"phase": ["up", "sideways"]}])],
            "R01: 'phase' takes ['down', 'none', 'up'], not ['up', 'sideways']",
        ),
        ([entry(source="")], "R01: 'source' is missing"),
    ],
)
def test_each_problem_is_named(bad, message):
    assert message in kb.validate(bad, ITEMS)


def test_the_real_base_is_sound():
    import re

    items = set(re.findall(r"^\| ([A-E]\d+) \|", CHECKLIST.read_text(encoding="utf-8"), flags=re.M))
    entries = kb.load(
        CHECKLIST.parents[2] / "app/strategy/kb.yaml"
    )  # the file itself, wherever the module runs
    assert kb.validate(entries, items) == []
    assert len(entries) >= 100


def test_the_brief_lists_what_holds_now_and_the_ids_always_on():
    entries = [
        entry(id="R01", when={"h1_vol": "> 1.1"}, action="stand_aside"),
        entry(id="S01", kind="shadow", when={"yesterday": ["strong_up", "strong_down"]}),
        entry(id="O01", kind="open", when={"h1_vol": "> 1.4"}),
        entry(id="P01", kind="principle", when={"session": "none"}),
        entry(id="P02", kind="principle"),
        entry(id="R02"),
        entry(id="F01", kind="finding"),
    ]
    out = kb.brief(entries, {"h1_vol": 1.2, "yesterday": "strong_down", "session": "none"})
    assert out == ["P01 PRINCIPLE: x", "R01 RULE -> stand_aside: x", "S01 SHADOW: x", "always on: P02, R02"]


def test_render_has_every_entry_and_escapes_pipes():
    entries = [
        entry(says="a | b"),
        entry(id="W01", kind="weapon", stage="weapon", status="shadow", animal="deer"),
    ]
    text = kb.render(entries)
    assert "| R01 | pressure | A5 |  | a / b |" in text
    assert "[status: shadow; animal: deer]" in text
    assert "## Rules (1)" in text
    assert "## Weapons (1)" in text


def test_behaviors_now_lists_the_animals_whose_readings_hold():
    entries = [
        entry(id="O01", kind="open", behavior="elephant", when={"h1_vol": "> 1.4"}),
        entry(id="O02", kind="open", behavior="sweep", when={"sweep": ["low", "high"]}),
        entry(id="O03", kind="open", behavior="thin", when={"m15_relvol": "< 0.4"}),
        entry(id="R01", when={"h1_vol": "> 1.1"}),
    ]
    assert kb.behaviors_now(entries, {"h1_vol": 1.5, "sweep": "low", "m15_relvol": 0.5}) == [
        "elephant",
        "sweep",
    ]
    assert kb.behaviors_now(entries, {"h1_vol": 1.2, "sweep": "none"}) == []


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (
            [entry(id="O01", kind="open", behavior="Big Cat", when={"h1_vol": "> 1"})],
            "O01: a behavior needs a one-word lowercase name and its readings (when)",
        ),
        (
            [entry(id="O01", kind="open", behavior="cat")],
            "O01: a behavior needs a one-word lowercase name and its readings (when)",
        ),
        (
            [
                entry(id="O01", kind="open", behavior="cat", when={"h1_vol": "> 1"}),
                entry(id="O02", kind="open", behavior="cat", when={"h1_vol": "> 2"}),
            ],
            "the behavior 'cat' is named 2 times",
        ),
        ([entry(when={"sweep": "left"})], "R01: 'sweep' takes ['high', 'low', 'none'], not 'left'"),
    ],
)
def test_behavior_problems_are_named(bad, message):
    assert message in kb.validate(bad, ITEMS)


def _m1(start_utc: str, rows: list[tuple[float, float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range(pd.Timestamp(start_utc, tz="UTC"), periods=len(rows), freq="1min")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close", "tick_volume"])


def test_m5_frame_from_the_closed_m1_bars():
    # M1 bars 15:00 .. 15:06 UTC, as_of 15:06: the 15:05 bar closed at 15:06 and is read (the 15:05 M5 bucket
    # holds it alone); the 15:06 bar (open = as_of) is still forming and is not read
    m1 = _m1(
        "2026-10-23T15:00",
        [
            (10, 11, 9, 10.5, 1),
            (10.5, 12, 10, 11, 2),
            (11, 11.5, 10.5, 11, 3),
            (11, 13, 11, 12, 4),
            (12, 12.5, 8, 9, 5),
            (9, 10, 8.5, 9.5, 6),
            (9.5, 99, 1, 50, 7),
        ],
    )
    d5 = kb.m5_frame(m1, pd.Timestamp("2026-10-23T15:06", tz="UTC"))
    assert list(d5.index) == [
        pd.Timestamp("2026-10-23T15:00", tz="UTC"),
        pd.Timestamp("2026-10-23T15:05", tz="UTC"),
    ]
    assert d5.iloc[0].tolist() == [
        10,
        13,
        8,
        9,
        15,
    ]  # open of the first, max high, min low, last close, volume sum
    assert d5.iloc[1].tolist() == [9, 10, 8.5, 9.5, 6]


def test_bars_of_and_the_window_read_closed_bars_only():
    idx = pd.date_range(pd.Timestamp("2026-10-23T10:00", tz="UTC"), periods=4, freq="1h")
    df = pd.DataFrame(
        {
            "open": [1.0, 2, 3, 4],
            "high": [2.0, 3, 4, 5],
            "low": [0.5, 1, 2, 3],
            "close": [1.5, 2.5, 3.5, 4.5],
            "tick_volume": [1, 1, 1, 1],
        },
        index=idx,
    )
    b = kb.bars_of(df, 60)
    assert (b.avail - b.t_open == 3600 * 10**9).all()
    t = pd.Timestamp("2026-10-23T12:30", tz="UTC").value  # the 12:00 bar is forming
    w = kb._window(b, t, 700)
    assert w.c.tolist() == [1.5, 2.5]
    assert kb._window(b, pd.Timestamp("2026-10-23T14:00", tz="UTC").value, 2).c.tolist() == [3.5, 4.5]


class TestD1Regime:
    """F20 / R08: the D1 close vs its 50-day mean, and that mean vs the one 20 days earlier (worked by hand)."""

    def test_a_steady_rise_is_up_and_a_steady_fall_down(self) -> None:
        rise = [100.0 + i for i in range(70)]  # mean of the last 50 = 144.5 < 169; 20 days earlier 124.5
        assert kb.d1_regime(np.array(rise)) == "up"
        assert kb.d1_regime(np.array(rise[::-1])) == "down"

    def test_a_close_back_under_a_rising_mean_is_none(self) -> None:
        closes = [100.0 + i for i in range(69)] + [140.0]  # the mean 144.4 rises, but 140 is under it
        assert kb.d1_regime(np.array(closes)) == "none"

    def test_any_rise_of_the_mean_counts_and_a_level_market_is_none(self) -> None:
        flat = [100.0] * 69 + [105.0]  # over the mean, and the mean rose a little (100.1 vs 100.0): up
        assert kb.d1_regime(np.array(flat)) == "up"
        level = [100.0] * 70  # nothing over and nothing rising
        assert kb.d1_regime(np.array(level)) == "none"

    def test_a_jump_over_a_falling_mean_is_none(self) -> None:
        closes = [169.0 - i for i in range(69)] + [
            160.0
        ]  # 160 over the mean 125.7, but 20 days ago it was 144.5
        assert kb.d1_regime(np.array(closes)) == "none"

    def test_the_earlier_mean_is_the_50_days_ending_20_days_ago(self) -> None:
        # 20 x 100, 30 x 50, 20 x 101: the mean now (30 x 50 + 20 x 101) / 50 = 70.4 vs 20 days ago
        # (20 x 100 + 30 x 50) / 50 = 70.0 -> rising; the 70-day mean (75.7) would call it falling
        closes = [100.0] * 20 + [50.0] * 30 + [101.0] * 20
        assert kb.d1_regime(np.array(closes)) == "up"

    def test_too_few_closes_is_unknown(self) -> None:
        assert kb.d1_regime(np.array([100.0 + i for i in range(69)])) is None

    def test_it_is_a_reading_the_rules_may_name(self) -> None:
        assert kb.WORDS["d1_regime"] == {"up", "down", "none"}


def test_the_app_checklist_equals_the_document():
    # app/strategy/checklist.py mirrors DECISION_CHECKLIST.md's items A-C word for word
    import re

    from app.strategy.checklist import ITEMS as APP_ITEMS

    rows = dict(re.findall(r"^\| ([ABC]\d+) \| (.+?) \|", CHECKLIST.read_text(encoding="utf-8"), flags=re.M))
    assert rows == APP_ITEMS and len(APP_ITEMS) == 22


# R10's own number in the readings (ISSUES 37, DECISION_CHECKLIST D6) ---------------------------------------


def _h1_opens(closes: list[float], start: str = "2026-07-01 00:00") -> pd.DataFrame:
    """An OPEN-stamped H1 frame, the shape of Frames.h1: bar i opens at start + i hours."""
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=len(closes), freq="1h")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"open": c, "high": c + 1.0, "low": c - 1.0, "close": c, "tick_volume": np.ones(len(c))}, index=idx
    )


def test_every_new_reading_is_declared():
    for name in ("h4_lean", "orb_high", "orb_low"):
        assert name in kb.NUMERIC and name in kb.FEATURES
    assert kb.WORDS["orb_break"] == {"up", "down", "none"}
    assert "orb_break" in kb.FEATURES


def test_the_h4_lean_is_positive_going_up_and_negative_going_down():
    up = _h1_opens([4000.0 + i for i in range(400)])
    at = up.index[-1] + pd.Timedelta(hours=1)  # the last bar has closed
    assert kb.h4_lean(up, at) > 0
    down = _h1_opens([4000.0 - i for i in range(400)])
    assert kb.h4_lean(down, at) < 0


def test_the_lean_reads_no_bar_that_has_not_closed():
    """The whole frame at ``as_of`` must give what the frame truncated at ``as_of`` gives."""
    closes = [4000.0 + i for i in range(400)]
    full = _h1_opens(closes)
    at = full.index[300]  # the bar opening here has NOT closed; the one before it has
    truncated = full[full.index < at]
    assert kb.h4_lean(full, at) == pytest.approx(kb.h4_lean(truncated, at))


def test_the_bar_that_closes_exactly_at_as_of_is_included():
    closes = [4000.0 + i for i in range(400)]
    full = _h1_opens(closes)
    opened = full.index[299]  # opens 299h in, closes an hour later
    at = opened + pd.Timedelta(hours=1)
    without = full[full.index < opened]
    assert kb.h4_lean(full, at) != pytest.approx(kb.h4_lean(without, at))


def test_too_short_a_history_is_nan_not_a_number():
    short = _h1_opens([4000.0 + i for i in range(120)])  # 30 H4 bars: under the 50 + 14 needed
    assert math.isnan(kb.h4_lean(short, short.index[-1] + pd.Timedelta(hours=1)))


def test_the_lean_matches_edge_side_on_close_stamped_bars():
    """The readings' number is the same one app/strategy/edge_side.py gives the strategies."""
    from app.core.enums import Timeframe
    from app.strategy.edge_side import edge_lean

    opens = _h1_opens([4000.0 + (i % 37) * 2.0 for i in range(400)])
    at = opens.index[-1] + pd.Timedelta(hours=1)
    stamped = opens.copy()
    stamped.index = opens.index + pd.Timedelta(hours=1)
    assert kb.h4_lean(opens, at) == pytest.approx(edge_lean({Timeframe.H1: stamped}, at, Timeframe.M5))
