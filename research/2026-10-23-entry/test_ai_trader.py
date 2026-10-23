"""Hand-worked tests for the AI trader's prompt trimming and brakes (no API call).

    .venv/Scripts/python -m pytest research/2026-10-23-entry/test_ai_trader.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_trader as at  # noqa: E402
import pandas as pd  # noqa: E402


def test_tail_keeps_short_text_whole():
    assert at.tail("## a\nx", 100) == "## a\nx"


def test_tail_cuts_at_a_heading():
    text = "## one\n" + "a" * 50 + "\n## two\nbb\n### three\ncc"
    # the end "\n## two\nbb\n### three\ncc" is 23 chars; the last 25 start with "aa", so the cut moves to "## two"
    assert at.tail(text, 25) == "(earlier steps left out)\n## two\nbb\n### three\ncc"


def test_tail_without_a_heading_inside():
    assert at.tail("x" * 30, 10) == "(earlier steps left out)\n" + "x" * 10


def test_trim_reads_keeps_reading_lines_only():
    text = "# Every timeframe\nM15 ATR 11 | big trend DOWN | rhythm DOWN\n    swings: H 1, L 2\n  SWEEP under it at 21:40\nnoise"
    assert at.trim_reads(text) == "M15 ATR 11 | big trend DOWN | rhythm DOWN\nSWEEP under it at 21:40"


class _D:
    def __init__(self, decision, size):
        self.decision, self.size = decision, size


def test_brakes_veto_a_new_trade_only():
    entries = [{"id": "R01", "kind": "rule", "action": "stand_aside", "when": {"h1_vol": "> 1.1"}}]
    assert at.brakes(entries, {"h1_vol": 1.3}, _D("SELL", "half")) == ("none", ["R01"])
    assert at.brakes(entries, {"h1_vol": 1.3}, _D("HOLD", "half")) == ("half", [])  # an open trade is managed
    assert at.brakes(entries, {"h1_vol": 1.0}, _D("BUY", "full")) == ("full", [])


def test_a_suspended_rule_does_not_veto():
    entries = [{"id": "R01", "kind": "rule", "action": "stand_aside", "when": {"h1_vol": "> 1.1"}},
               {"id": "R02", "kind": "rule", "action": "stand_aside_plan1", "when": {"d1_atr20": "< 60"}}]
    assert at.brakes(entries, {"h1_vol": 1.3, "d1_atr20": 74}, _D("SELL", "half"), frozenset({"R01"})) == ("half", [])
    assert at.brakes(entries, {"h1_vol": 1.3, "d1_atr20": 50}, _D("SELL", "half"), frozenset({"R01"})) == ("none", ["R02"])


def test_suspended_reads_only_unexpired_rules(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"R01": "2026-10-23T22:00:00+00:00", "R02": "2026-10-23T10:00:00+00:00"}', encoding="utf-8")
    now = pd.Timestamp("2026-10-23T16:00", tz="UTC")
    assert at.suspended(now, p) == {"R01": "2026-10-23T22:00:00+00:00"}
    assert at.suspended(pd.Timestamp("2026-10-23T22:00", tz="UTC"), p) == {}  # expired at its time
    assert at.suspended(now, tmp_path / "none.json") == {}
