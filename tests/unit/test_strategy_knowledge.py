"""Hand-worked tests for app/strategy/knowledge.py - the base's checks, its conditions, the owner's windows,
the brief and the frames (TAA-1803; moved from research/2026-10-23-entry/knowledge/test_kb.py)."""

from __future__ import annotations

import math
from pathlib import Path

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
