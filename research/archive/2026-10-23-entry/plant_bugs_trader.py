"""Planted bugs for app/ai/trader.py against tests/unit/test_ai_trader.py (plant.main; TAA-1804).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_trader.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("the tail cut not at a heading", [('k = cut.find("\\n#")', 'k = -1')]),
    ("the tail keeps the start", [("cut = text[-chars:]", "cut = text[:chars]")]),
    ("a suspension never expires", [("return {k: v for k, v in rows.items() if pd.Timestamp(v) > now}", "return dict(rows)")]),
    ("a suspension expires a minute late", [("if pd.Timestamp(v) > now}", "if pd.Timestamp(v) >= now}")]),
    ("the brakes ignore suspensions", [('        and e["id"] not in off\n', "")]),
    ("the brakes veto HOLD too", [('if d.decision in ("SELL", "BUY") and vetoes:', "if vetoes:")]),
    ("no prompt cache", [("cache_system=True", "cache_system=False")]),
    ("the effort low", [('EFFORT = "medium"', 'EFFORT = "low"')]),
    ("the model ignored", [("model=model,", "model=None,")]),
    ("the system and user files swapped", [('(raw / f"{stem}_1_system.txt").write_text(system', '(raw / f"{stem}_1_system.txt").write_text(user')]),
    ("the source fixed", [('"source": source,', '"source": "manual",')]),
    ("the held list empty", [("rec.update(decision=d.model_dump(), final_size=size, vetoed_by=vetoes, suspended_applying=held)",
                              "rec.update(decision=d.model_dump(), final_size=size, vetoed_by=vetoes, suspended_applying=[])")]),
    ("cache reads not recorded", [('"cache_read": ans.cache_read_tokens,', '"cache_read": 0,')]),
]

if __name__ == "__main__":
    main("app.ai.trader", ROOT / "tests/unit/test_ai_trader.py", BUGS)
