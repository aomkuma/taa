"""Planted bugs for app/ai/replay.py and app/engine/ai_replay.py against tests/unit/test_ai_replay.py (plant.main;
TAA-1807).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_replay.py
"""

from __future__ import annotations

from plant import ROOT, main

TEST = ROOT / "tests/unit/test_ai_replay.py"

PROVIDERS = [
    ("the content left out of the hash", [('            "content": content,\n', '')]),
    ("the effort left out of the hash", [('            "effort": effort,\n', '')]),
    ("never replayed", [("        if path.exists():\n            self.hits += 1", "        if False:\n            self.hits += 1")]),
    ("a failure stored", [("if ans.status is Status.OK and ans.parsed is not None:", "if ans.parsed is not None or ans.status is not Status.OK:")]),
    ("the stored cost lost", [('cost_usd=float(row.get("cost_usd", 0.0)),', "cost_usd=0.0,")]),
    ("a miss without inner answers OK", [('                Status.SKIPPED, created_at=self.clock.now_utc(), detail=f"no stored answer', '                Status.OK, created_at=self.clock.now_utc(), detail=f"no stored answer')]),
    ("the CLI gets tools", [('"--tools", "", "--strict', '"--tools", "default", "--strict')]),
    ("the CLI reads the settings", [('"--setting-sources", "", "--no-session', '"--setting-sources", "user,project", "--no-session')]),
    ("the cost of the CLI's own model", [("usage = (out.get(\"modelUsage\") or {}).get(model) or {}", "usage = next(iter((out.get(\"modelUsage\") or {}).values()), {})")]),
    ("an error result taken as an answer", [('if out.get("is_error") or out.get("structured_output") is None:', 'if out.get("structured_output") is None:')]),
]

LANE = [
    ("bars not closed yet", [('searchsorted(pd.Timestamp(now), side="right")', 'searchsorted(pd.Timestamp(now) + pd.Timedelta(minutes=1), side="right")')]),
    ("the clock not set", [("        self.clock.set(at)\n        self.lane.tick()", "        self.lane.tick()")]),
    ("the decision not handed over", [("done = hand_over(strategy, self.symbol, rec, p.pending_minutes)", "done = \"order\"")]),
    ("one bar too few", [("rows = df.iloc[max(0, n - count) : n]", "rows = df.iloc[max(0, n - count + 1) : n]")]),
]

if __name__ == "__main__":
    main("app.ai.replay", TEST, PROVIDERS)
    main("app.engine.ai_replay", TEST, LANE)
