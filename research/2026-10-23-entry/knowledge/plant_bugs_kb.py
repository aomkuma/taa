"""Planted bugs for kb.py against test_kb.py (plant.main_script).

    .venv/Scripts/python research/2026-10-23-entry/knowledge/plant_bugs_kb.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from plant import main_script  # noqa: E402

BUGS = [
    ("'>' read as '>='", [('return v > x if op == ">" else', 'return v >= x if op == ">" else')]),
    ("'<' read as '<='", [('v < x if op == "<" else v <= x', 'v <= x if op == "<" else v <= x')]),
    ("a negative threshold not parsed", [(r'(-?\d+(?:\.\d+)?)', r'(\d+(?:\.\d+)?)')]),
    ("an unknown reading holds", [("        return False\n    if isinstance(spec, list):", "        return True\n    if isinstance(spec, list):")]),
    ("a map needs any condition, not all", [("any(all(holds(f.get(k), v)", "any(any(holds(f.get(k), v)")]),
    ("a list needs every alternative", [("return not alts or any(all(", "return not alts or all(all(")]),
    ("no when never applies", [("return not alts or any(", "return bool(alts) and any(")]),
    ("Asia to 10:00 Thai", [('"asia" if 7 <= h < 9 else', '"asia" if 7 <= h < 10 else')]),
    ("London from 12:00 Thai", [('"london" if 13 <= h < 15 else', '"london" if 12 <= h < 15 else')]),
    ("the NY window in Thai time", [("th, ny = at.tz_convert(TH), at.tz_convert(NY)", "th, ny = at.tz_convert(TH), at.tz_convert(TH)")]),
    ("the NY window ends at 12:00", [('"ny" if 8 <= m < 11.5 else', '"ny" if 8 <= m < 12 else')]),
    ("duplicate ids not reported", [("if ids.count(i) > 1]", "if ids.count(i) > 2]")]),
    ("the kind letter not checked", [("if KINDS.get(str(i)[:1]) != e.get(\"kind\"):", "if False:")]),
    ("unknown checklist items pass", [("if x not in items]", "if x in set()]")]),
    ("unknown conflicts pass", [("if x not in known]", "if x in set()]")]),
    ("a weapon needs only a status", [('(e.get("status") and e.get("animal"))', 'e.get("status")')]),
    ("a numeric reading takes a bare number", [("elif k in NUMERIC and not (isinstance(v, str) and OPS.match(v)):", "elif False:")]),
    ("a word reading takes any word", [("elif k in WORDS and not set(", "elif False and not set(")]),
    ("the brief shows non-matching entries", [('if e.get("when") and applies(e, f)', 'if e.get("when")')]),
    ("the brief's always-on line takes shadows", [('e["kind"] in ("principle", "rule")]', 'e["kind"] in ("principle", "rule", "shadow", "finding")]')]),
    ("the brief drops the action", [("act = f\" -> {e['action']}\" if e.get(\"action\") else \"\"", 'act = ""')]),
    ("render keeps the pipes", [('.replace("|", "/")', "")]),
]

if __name__ == "__main__":
    main_script(HERE / "kb.py", HERE / "test_kb.py", BUGS)
