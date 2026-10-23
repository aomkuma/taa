"""The knowledge base at the moment of a decision (owner 2026-10-23: "has everything we discussed been recorded and
used in the decisions?" - "the bot and you must always remember and observe").

kb.yaml is the one source of truth; this module checks it, reads the market's state at a time (bars closed by
AS_OF only, the bot's own code) and says which entries apply now, and renders KNOWLEDGE.md from it.

    .venv/Scripts/python research/2026-10-23-entry/knowledge/kb.py check
    .venv/Scripts/python research/2026-10-23-entry/knowledge/kb.py now [AS_OF_UTC]
    .venv/Scripts/python research/2026-10-23-entry/knowledge/kb.py render
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parents[1]
KB = HERE / "kb.yaml"
CHECKLIST = ENTRY / "DECISION_CHECKLIST.md"

KINDS = {"P": "principle", "R": "rule", "W": "weapon", "S": "shadow", "F": "finding", "X": "failed", "L": "lesson",
         "O": "open"}
STAGES = {"forest", "plan", "trend", "pressure", "clock", "animal", "weapon", "picture", "entry", "stop", "target",
          "exit", "size", "after", "method", "observer"}
NUMERIC = {"h1_vol", "d1_atr20", "h1_atr", "release_min", "day_range_step"}
WORDS = {"session": {"asia", "london", "ny", "none"}, "phase": {"up", "down", "none"},
         "yesterday": {"strong_up", "strong_down", "none"},
         **{f"{tf}_rhythm": {"up", "down", "none"} for tf in ("m15", "h1", "h4", "d1")},
         **{f"{tf}_big": {"up", "down", "none"} for tf in ("h1", "h4", "d1")}}
FEATURES = NUMERIC | set(WORDS)
OPS = re.compile(r"^(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)$")
TH, NY = "Asia/Bangkok", "America/New_York"


def load(path: Path = KB) -> list[dict[str, Any]]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def checklist_items(path: Path = CHECKLIST) -> set[str]:
    return set(re.findall(r"^\| ([A-E]\d+) \|", path.read_text(encoding="utf-8"), flags=re.M))


def _maps(when: Any) -> list[dict[str, Any]]:
    """``when`` as a list of alternatives (each a map whose conditions must all hold); [] = always."""
    if when is None:
        return []
    return [when] if isinstance(when, dict) else list(when)


def validate(entries: list[dict[str, Any]], items: set[str]) -> list[str]:
    """Every problem found (empty = the base is sound)."""
    out: list[str] = []
    ids = [e.get("id", "?") for e in entries]
    out += [f"{i}: the id is used {ids.count(i)} times" for i in sorted(set(ids)) if ids.count(i) > 1]
    known = set(ids)
    for e in entries:
        i = e.get("id", "?")
        out += [f"{i}: '{k}' is missing" for k in ("id", "kind", "stage", "says", "source") if not e.get(k)]
        if KINDS.get(str(i)[:1]) != e.get("kind"):
            out.append(f"{i}: the kind '{e.get('kind')}' does not match the id's letter")
        if e.get("stage") not in STAGES:
            out.append(f"{i}: unknown stage '{e.get('stage')}'")
        out += [f"{i}: unknown checklist item {x}" for x in e.get("items") or [] if x not in items]
        out += [f"{i}: conflicts with an unknown id {x}" for x in e.get("conflicts") or [] if x not in known]
        if e.get("kind") == "weapon" and not (e.get("status") and e.get("animal")):
            out.append(f"{i}: a weapon needs its status and its animal")
        for alt in _maps(e.get("when")):
            for k, v in alt.items():
                if k not in FEATURES:
                    out.append(f"{i}: unknown reading '{k}'")
                elif k in NUMERIC and not (isinstance(v, str) and OPS.match(v)):
                    out.append(f"{i}: '{k}' needs a comparison like '> 1.1', not {v!r}")
                elif k in WORDS and not set(v if isinstance(v, list) else [v]) <= WORDS[k]:
                    out.append(f"{i}: '{k}' takes {sorted(WORDS[k])}, not {v!r}")
    return out


def holds(value: Any, spec: Any) -> bool:
    """One condition; an unknown reading (None / NaN) never holds - NaN fails every comparison by itself."""
    if value is None:
        return False
    if isinstance(spec, list):
        return value in spec
    m = OPS.match(spec) if isinstance(spec, str) else None
    if m:
        op, x = m.group(1), float(m.group(2))
        v = float(value)
        return v > x if op == ">" else v >= x if op == ">=" else v < x if op == "<" else v <= x
    return value == spec


def applies(entry: dict[str, Any], f: dict[str, Any]) -> bool:
    alts = _maps(entry.get("when"))
    return not alts or any(all(holds(f.get(k), v) for k, v in alt.items()) for alt in alts)


def session(at: pd.Timestamp) -> str:
    """The owner's windows: Asia 07:00-09:00 Thai, London 13:00-15:00 Thai, New York 08:00-11:30 New York time."""
    th, ny = at.tz_convert(TH), at.tz_convert(NY)
    h, m = th.hour + th.minute / 60, ny.hour + ny.minute / 60
    return "asia" if 7 <= h < 9 else "london" if 13 <= h < 15 else "ny" if 8 <= m < 11.5 else "none"


def features(as_of: pd.Timestamp) -> dict[str, Any]:
    """The readings at ``as_of`` (bars closed by it), from the bot's modules."""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ENTRY))
    import rhythm_scan as rs
    from candidates import FRAMES, frame, window

    from app.news.releases import load_releases
    from app.strategy import context_read as cr
    from app.strategy import structure_read as sr
    from app.strategy import zone_grid as zg
    from app.strategy.strong_levels import closed

    t = as_of.value
    data = {tf: frame(tf)[1] for tf in FRAMES}
    w = {tf: window(data[tf], t, 700) for tf in FRAMES}
    d1 = data["D1"]
    st = zg.grid_at(zg.grid_rows(d1.t_open, d1.o, d1.h, d1.lo, d1.c), t)
    price = float(closed(w["M15"], t).c[-1])
    day = cr.last_day(w["D1"], t)
    ph = sr.phase(w["D1"], t)
    _, rng = cr.day_so_far(w["H1"], t, price, 1, st.step)
    word = {1: "up", -1: "down", 0: "none"}
    f: dict[str, Any] = {"price": price, "h1_vol": cr.vol_ratio(w["H1"], t), "d1_atr20": st.step,
                         "day_range_step": rng, "session": session(as_of), "phase": word[int(ph)],
                         "yesterday": ("strong_up" if day.direction > 0 else "strong_down") if day.strong else "none"}
    for tf in ("M15", "H1", "H4", "D1"):
        sign, atr, _, _, big = rs.rhythm(closed(rs.load(tf, as_of), t), t)
        f[f"{tf.lower()}_rhythm"] = word[sign]
        if tf != "M15":
            f[f"{tf.lower()}_big"] = word[int(big.sign)]
        if tf == "H1":
            f["h1_atr"] = atr
    rel = load_releases(ROOT / "app/news/us_releases.csv")
    gaps = [abs((pd.Timestamp(r.at) - as_of).total_seconds()) / 60 for r in rel]
    f["release_min"] = min(gaps) if gaps else math.nan
    return f


def brief(entries: list[dict[str, Any]], f: dict[str, Any]) -> list[str]:
    """What the base says now: the conditional entries whose readings hold (rules first), then the ids always on."""
    order = list(KINDS.values())
    hits = sorted((e for e in entries if e.get("when") and applies(e, f)), key=lambda e: (order.index(e["kind"]), e["id"]))
    out = []
    for e in hits:
        act = f" -> {e['action']}" if e.get("action") else ""
        out.append(f"{e['id']} {e['kind'].upper()}{act}: {e['says']}")
    always = [e["id"] for e in entries if not e.get("when") and e["kind"] in ("principle", "rule")]
    out.append(f"always on: {', '.join(always)}")
    return out


def render(entries: list[dict[str, Any]]) -> str:
    def cell(x: Any) -> str:
        return str(x).replace("|", "/").replace("\n", " ") if x not in (None, [], "") else ""

    out = ["# The knowledge base (generated from kb.yaml by kb.py render - do not edit here)\n",
           "Precedence at a decision: principle > rule > weapon > shadow (shown, never applied) > finding > failed "
           "(never retried as it was) > lesson > open. `when` = the readings an entry applies to (none = always).\n"]
    for kind in KINDS.values():
        rows = [e for e in entries if e["kind"] == kind]
        if not rows:
            continue
        out.append(f"\n## {kind.capitalize()}s ({len(rows)})\n")
        out.append("| id | stage | items | when | says | evidence | source |\n|---|---|---|---|---|---|---|")
        for e in rows:
            says = e["says"] + (f" [status: {e['status']}; animal: {e['animal']}]" if kind == "weapon" else "")
            out.append(f"| {e['id']} | {e['stage']} | {cell(', '.join(e.get('items') or []))} | {cell(e.get('when'))} | "
                       f"{cell(says)} | {cell(e.get('evidence'))} | {cell(e.get('source'))} |")
    return "\n".join(out) + "\n"


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
        sys.path.insert(0, str(ENTRY))
        import zone_wait as zw

        as_of = (pd.Timestamp(sys.argv[2], tz="UTC") if len(sys.argv) > 2
                 else zw.load("M1").index[-1] + pd.Timedelta(minutes=1))
        f = features(as_of)
        print(f"# The knowledge base at {as_of.tz_convert(TH):%a %d %b %Y %H:%M} Thai\n")
        print("readings: " + ", ".join(f"{k} {v:.2f}" if isinstance(v, float) else f"{k} {v}" for k, v in f.items()))
        print("\n".join(f"- {x}" for x in brief(entries, f)))


if __name__ == "__main__":
    main()
