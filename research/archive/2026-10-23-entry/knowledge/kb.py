"""The research's door to the knowledge base (TAA-1803): the logic lives in app/strategy/knowledge.py (one code
path, PLAN §A37); this wrapper only loads the frames from the stored history and the checklist's item ids.

    .venv/Scripts/python research/2026-10-23-entry/knowledge/kb.py check
    .venv/Scripts/python research/2026-10-23-entry/knowledge/kb.py now [AS_OF_UTC]
    .venv/Scripts/python research/2026-10-23-entry/knowledge/kb.py render
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENTRY))

from app.strategy import knowledge as K  # noqa: E402
from app.strategy.knowledge import (  # noqa: E402,F401  (the research's callers use these names)
    FEATURES, KB, KINDS, NUMERIC, OPS, STAGES, TH, WORDS, applies, behaviors_now, brief, holds, load, render,
    session, validate,
)

CHECKLIST = ENTRY / "DECISION_CHECKLIST.md"


def checklist_items(path: Path = CHECKLIST) -> set[str]:
    return set(re.findall(r"^\| ([A-E]\d+) \|", path.read_text(encoding="utf-8"), flags=re.M))


def frames() -> K.Frames:
    """The stored XAUUSD history (data/history) and the release calendar, as the app's reader takes them."""
    import zone_wait as zw

    from app.news.releases import load_releases

    return K.Frames(zw.load("M1"), zw.load("M15"), zw.load("H1"), zw.load("H4"), zw.load("D1"),
                    load_releases(ROOT / "app/news/us_releases.csv"))


def features(as_of: pd.Timestamp) -> dict[str, Any]:
    """The readings at ``as_of`` - app/strategy/knowledge.features on the stored history."""
    return K.features(frames(), as_of)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    entries = load()
    problems = validate(entries, checklist_items())
    if problems or cmd == "check":
        print("\n".join(problems) or f"kb.yaml: {len(entries)} entries, no problems")
        if problems:
            raise SystemExit(1)
    if cmd == "render":
        (HERE / "KNOWLEDGE.md").write_text(render(entries), encoding="utf-8")
        print(f"KNOWLEDGE.md written ({len(entries)} entries)")
    elif cmd == "now":
        import zone_wait as zw

        as_of = (pd.Timestamp(sys.argv[2], tz="UTC") if len(sys.argv) > 2
                 else zw.load("M1").index[-1] + pd.Timedelta(minutes=1))
        f = features(as_of)
        print(f"# The knowledge base at {as_of.tz_convert(TH):%a %d %b %Y %H:%M} Thai\n")
        print("readings: " + ", ".join(f"{k} {v:.2f}" if isinstance(v, float) else f"{k} {v}" for k, v in f.items()))
        print("\n".join(f"- {x}" for x in brief(entries, f)))


if __name__ == "__main__":
    main()
