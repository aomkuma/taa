"""The AI trader in the shadow (owner 2026-10-23: "trade like a real trader - watch the behaviour, pick the setup with
the most edge"; "will the bot work like us, not dumb as before?" - the judgment goes to the AI, the eyes, memory and
brakes stay code).

At a time AS_OF (bars closed by it only): the readers' text (rhythm_scan, picture_read, routine_read), the knowledge
base's readings and what applies now (knowledge/kb.py), and the session's journal so far go to Claude
(app/ai/providers.AnthropicProvider, the engine's own client; key and model from .env AI_API_KEY / AI_MODEL). It
answers one decision (WAIT / SELL / BUY / HOLD / EXIT with entry, stop, target, size, the knowledge ids it used). The
CODE then applies the brakes: a rule in force with a stand-aside action makes the size 'none' (the AI's view is kept
for the journal). Nothing is sent to a broker. Each decision is appended to ai/decisions.jsonl with its cost.

    .venv/Scripts/python research/2026-10-23-entry/ai_trader.py AS_OF_UTC [JOURNAL.md]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "knowledge"))
import kb  # noqa: E402
from observe import read_all  # noqa: E402

from app.ai.providers import AnthropicProvider  # noqa: E402
from app.ai.schema import Status  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.core.clock import SystemClock  # noqa: E402

OUT = HERE / "ai" / "decisions.jsonl"
TH = "Asia/Bangkok"
STAND_ASIDE = {"stand_aside", "stand_aside_plan1"}


class StepDecision(BaseModel):
    decision: Literal["WAIT", "SELL", "BUY", "HOLD", "EXIT"]
    setup: str = Field(description="the setup in a few words, or what is being waited for")
    entry: float | None = Field(description="entry price; null when waiting")
    stop: float | None
    target: float | None
    trigger: str = Field(description="what must happen to enter (or to change the decision)")
    size: Literal["none", "half", "full"]
    kb_ids: list[str] = Field(description="knowledge-base ids the decision rests on")
    reasons: list[str] = Field(description="at most six short reasons citing the readings")
    confidence: int = Field(description="0-100")


def system_prompt(entries: list[dict]) -> str:
    """The trader's character and the owner's principles and rules, built from the knowledge base itself."""
    lines = [
        "You are the trading judgment of a gold (XAUUSD) trading system, trading like a careful, observant human "
        "trader. At one moment you receive the readings of the market (closed bars only), what the knowledge base "
        "says applies now, and the session's journal so far. Decide ONE thing: WAIT, SELL, BUY (a new trade), HOLD or "
        "EXIT (an open trade). Pick the setup with the most edge at this moment, or wait - waiting is a decision. "
        "Every entry needs: a clear structure on the entry frame, a precise entry (not chasing a move that already "
        "ran, not mid-range), the stop beyond the structure AND outside every liquidity pool, a target before the "
        "next zone line's band, enough room (state the R multiple). Read hundreds of bars of trend, not the last few. "
        "Respect a setup's life cycle: a setup whose move already played out is over. Give prices to two decimals. "
        "Cite the knowledge-base ids you used. You never size beyond 'full'; the code may veto you.",
        "",
        "THE OWNER'S PRINCIPLES (always) AND THE RULES IN FORCE:",
    ]
    for e in entries:
        if e["kind"] in ("principle", "rule"):
            lines.append(f"- {e['id']}: {e['says']}" + (f" [applies when {e['when']}]" if e.get("when") else ""))
    lines.append("")
    lines.append("WEAPONS (status from measurement):")
    for e in entries:
        if e["kind"] == "weapon":
            lines.append(f"- {e['id']} [{e['status']}; {e['animal']}]: {e['says']} Evidence: {e.get('evidence', '-')}")
    lines.append("")
    lines.append("SHADOW RULES and LESSONS (consider, not binding):")
    for e in entries:
        if e["kind"] in ("shadow", "lesson"):
            lines.append(f"- {e['id']}: {e['says']}")
    return "\n".join(lines)


def content(as_of: pd.Timestamp, journal: str, f: dict, brief: list[str], reads: str, last: float) -> str:
    th = as_of.tz_convert(TH)
    clean = {k: (None if isinstance(v, float) and math.isnan(v) else (round(v, 3) if isinstance(v, float) else v))
             for k, v in f.items()}
    return "\n\n".join([
        f"NOW: {th:%a %d %b %Y %H:%M} Thai time ({as_of:%H:%M} UTC). Bars closed by this time only. The last M1 close: "
        f"{last:.2f} (the readings' 'price' is the last closed M15 bar's close).",
        "READINGS (knowledge base features):\n" + json.dumps(clean),
        "WHAT THE KNOWLEDGE BASE SAYS APPLIES NOW:\n" + "\n".join(brief),
        "THE READERS' OUTPUT:\n" + reads,
        "THE SESSION'S JOURNAL SO FAR (earlier steps, including any open trade):\n" + (journal or "(empty)"),
    ])


def brakes(entries: list[dict], f: dict, d: StepDecision) -> tuple[str, list[str]]:
    """The code's veto: a rule in force with a stand-aside action -> no new trade."""
    vetoes = [e["id"] for e in entries if e["kind"] == "rule" and e.get("action") in STAND_ASIDE and e.get("when")
              and kb.applies(e, f)]
    if d.decision in ("SELL", "BUY") and vetoes:
        return "none", vetoes
    return d.size, []


def main() -> None:
    as_of = pd.Timestamp(sys.argv[1], tz="UTC")
    journal = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else ""
    entries = kb.load()
    f = kb.features(as_of)
    brief = kb.brief(entries, f)
    reads = read_all(as_of)
    import zone_wait as zw

    m1 = zw.load("M1")
    last = float(m1[m1.index < as_of - pd.Timedelta(minutes=1)].close.iloc[-1])  # the M1 bar closed by as_of
    env = load_settings(env_file=str(ROOT / ".env")).env
    if env.AI_API_KEY is None:
        raise SystemExit("AI_API_KEY is not set")
    ai = AnthropicProvider(env.AI_API_KEY.get_secret_value(), SystemClock(), model=env.AI_MODEL, effort="medium",
                           timeout_seconds=180)
    system, user = system_prompt(entries), content(as_of, journal, f, brief, reads, last)
    raw = HERE / "ai" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    stem = f"{as_of.tz_convert(TH):%Y-%m-%d_%H%M}"
    (raw / f"{stem}_1_system.txt").write_text(system, encoding="utf-8")  # the owner sees exactly what was asked
    (raw / f"{stem}_2_user.txt").write_text(user, encoding="utf-8")
    ans = ai.ask(f"step-{as_of:%Y%m%d%H%M}", system, user, StepDecision)
    rec = {"as_of": as_of.isoformat(), "status": ans.status.value, "model": ans.model, "cost_usd": ans.cost_usd,
           "tokens": [ans.input_tokens, ans.output_tokens], "latency_ms": ans.latency_ms, "detail": ans.detail}
    if ans.status is Status.OK:
        d: StepDecision = ans.parsed
        size, vetoes = brakes(entries, f, d)
        rec.update(decision=d.model_dump(), final_size=size, vetoed_by=vetoes)
    (raw / f"{stem}_3_answer.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps(rec, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
