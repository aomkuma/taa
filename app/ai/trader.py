"""The AI trader (PLAN §A37, TAA-1804; owner 2026-10-23: "trade like a real trader - watch the behaviour, pick
the setup with the most edge"). Moved from research/2026-10-23-entry/ai_trader.py, which now wraps it.

At ``as_of`` (bars closed by it only): the knowledge base's readings and what applies now
(app/strategy/knowledge.py), the day's own levels, the readers' lines (app/strategy/readout.py) and the end of
the session's journal go to the AI; it answers one :class:`StepDecision`. The code then applies the brakes: a
rule in force with a stand-aside action makes a new trade's size 'none' unless the owner suspended that rule
for a while. Every prompt and answer can be stored. Nothing is sent to a broker here.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.ai.providers import AIProvider
from app.strategy import behaviors as bh
from app.strategy import knowledge as kn
from app.strategy.readout import reader_lines

TH = "Asia/Bangkok"
STAND_ASIDE = {"stand_aside", "stand_aside_plan1"}
JOURNAL_CHARS = 5000  # the end of the session journal sent with each call (the cost grows with it)
EFFORT = "medium"


class StepDecision(BaseModel):
    decision: Literal["WAIT", "SELL", "BUY", "HOLD", "EXIT"]
    setup: str = Field(description="the setup in a few words, or what is being waited for")
    entry: float | None = Field(description="entry price; null when waiting")
    stop: float | None
    target: float | None
    trigger: str = Field(description="what must happen to enter (or to change the decision)")
    size: Literal["none", "half", "full"]
    kb_ids: list[str] = Field(description="knowledge-base ids the decision rests on")
    reasons: list[str] = Field(description="at most four one-line reasons citing the readings")
    confidence: int = Field(description="0-100")
    watch_above: float | None = Field(
        description="wake me again when an M1 bar closes above this price (or null)"
    )
    watch_below: float | None = Field(
        description="wake me again when an M1 bar closes below this price (or null)"
    )


CHARACTER = (
    "You are the trading judgment of a gold (XAUUSD) trading system, trading like a careful, observant "
    "human trader. At one moment you receive the readings of the market (closed bars only), what the "
    "knowledge base says applies now, and the session's journal so far. Decide ONE thing: WAIT, SELL, BUY "
    "(a new trade), HOLD or EXIT (an open trade). Pick the setup with the most edge at this moment, or "
    "wait - waiting is a decision. Every entry needs: a clear structure on the entry frame, a precise "
    "entry (not chasing a move that already ran, not mid-range), the stop beyond the structure AND "
    "outside every liquidity pool, a target before the next zone line's band, enough room (state the R "
    "multiple). Read hundreds of bars of trend, not the last few. Respect a setup's life cycle: a setup "
    "whose move already played out is over. Give prices to two decimals. Keep it short: at most four "
    "reasons of one line each. Cite the knowledge-base ids you used. You never size beyond 'full'; the "
    "code may veto you. The owner's own trades in the journal are the owner's (ideas and context, not "
    "yours to manage); HOLD / EXIT apply only to the system's own open trades, and the system's position "
    "is what the journal records as ours."
)


def system_prompt(entries: list[dict[str, Any]]) -> str:
    """The trader's character and the owner's principles and rules, built from the knowledge base itself (the
    same text for every call while the base is unchanged - it is cached)."""
    lines = [CHARACTER, "", "THE OWNER'S PRINCIPLES (always) AND THE RULES IN FORCE:"]
    for e in entries:
        if e["kind"] in ("principle", "rule"):
            lines.append(
                f"- {e['id']}: {e['says']}" + (f" [applies when {e['when']}]" if e.get("when") else "")
            )
    lines.append("")
    lines.append("WEAPONS (status from measurement):")
    for e in entries:
        if e["kind"] == "weapon":
            evidence = e.get("evidence", "-")
            lines.append(f"- {e['id']} [{e['status']}; {e['animal']}]: {e['says']} Evidence: {evidence}")
    lines.append("")
    lines.append("SHADOW RULES and LESSONS (consider, not binding):")
    for e in entries:
        if e["kind"] in ("shadow", "lesson"):
            lines.append(f"- {e['id']}: {e['says']}")
    return "\n".join(lines)


def content(
    as_of: pd.Timestamp,
    journal: str,
    f: dict[str, Any],
    brief: list[str],
    reads: str,
    last: float,
    levels: str,
) -> str:
    th = as_of.tz_convert(TH)
    clean = {
        k: (None if isinstance(v, float) and math.isnan(v) else (round(v, 3) if isinstance(v, float) else v))
        for k, v in f.items()
    }
    return "\n\n".join(
        [
            f"NOW: {th:%a %d %b %Y %H:%M} Thai time ({as_of:%H:%M} UTC). Bars closed by this time only. "
            f"The last M1 close: {last:.2f} (the readings' 'price' is the last closed M15 bar's close).",
            "READINGS (knowledge base features):\n" + json.dumps(clean),
            "WHAT THE KNOWLEDGE BASE SAYS APPLIES NOW:\n" + "\n".join(brief),
            "THE DAY'S OWN LEVELS (M15 swings of the Thai day, the day's and yesterday's high / low):\n"
            + levels,
            "THE READERS' OUTPUT:\n" + reads,
            "THE SESSION'S JOURNAL SO FAR (earlier steps, including any open trade):\n"
            + (journal or "(empty)"),
        ]
    )


def tail(text: str, chars: int) -> str:
    """The end of ``text``, at most ``chars`` long, cut at the start of a heading (## / ###) when one is
    inside."""
    if len(text) <= chars:
        return text
    cut = text[-chars:]
    k = cut.find("\n#")
    return ("(earlier steps left out)\n" + cut[k + 1 :]) if k >= 0 else "(earlier steps left out)\n" + cut


def suspended(rows: dict[str, str], now: pd.Timestamp) -> dict[str, str]:
    """The owner's suspensions ``{rule id: until (ISO UTC)}`` still running at ``now``."""
    return {k: v for k, v in rows.items() if pd.Timestamp(v) > now}


def brakes(
    entries: list[dict[str, Any]], f: dict[str, Any], d: StepDecision, off: frozenset[str] = frozenset()
) -> tuple[str, list[str]]:
    """The code's veto: a rule in force with a stand-aside action -> no new trade (rules in ``off`` are
    suspended)."""
    vetoes = [
        e["id"]
        for e in entries
        if e["kind"] == "rule"
        and e.get("action") in STAND_ASIDE
        and e.get("when")
        and e["id"] not in off
        and kn.applies(e, f)
    ]
    if d.decision in ("SELL", "BUY") and vetoes:
        return "none", vetoes
    return d.size, []


def last_close(m1: pd.DataFrame, as_of: pd.Timestamp) -> float:
    """The close of the last M1 bar closed by ``as_of``."""
    return float(m1[m1.index <= as_of - pd.Timedelta(minutes=1)].close.iloc[-1])


def prompts(
    entries: list[dict[str, Any]], fr: kn.Frames, as_of: pd.Timestamp, journal: str, off: dict[str, str]
) -> tuple[str, str, dict[str, Any]]:
    """The system and user prompts at ``as_of`` and the readings they came from."""
    f = kn.features(fr, as_of)
    brief = kn.brief(entries, f)
    if off:  # the AI is told plainly, and the trades taken meanwhile carry the mark
        until = ", ".join(f"{k} until {pd.Timestamp(v).tz_convert(TH):%a %H:%M} Thai" for k, v in off.items())
        brief.append(
            "SUSPENDED BY THE OWNER FOR NOW (do NOT stand aside because of these; trades are recorded as "
            "taken while suspended): " + until
        )
    reads = "\n".join(reader_lines(fr, as_of))
    levels = "\n".join(bh.day_levels(fr.m15, fr.d1, as_of))
    user = content(as_of, tail(journal, JOURNAL_CHARS), f, brief, reads, last_close(fr.m1, as_of), levels)
    return system_prompt(entries), user, f


def decide(
    provider: AIProvider,
    entries: list[dict[str, Any]],
    fr: kn.Frames,
    as_of: pd.Timestamp,
    journal: str,
    *,
    model: str | None = None,
    suspensions: dict[str, str] | None = None,
    store: Path | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    """One AI decision at ``as_of`` with the code's brakes. ``store``: a folder for the raw prompts and
    answers (raw/<Thai time>_1_system.txt, _2_user.txt, _3_answer.json) and decisions.jsonl."""
    off = suspended(suspensions or {}, as_of)
    system, user, f = prompts(entries, fr, as_of, journal, off)
    stem = f"{as_of.tz_convert(TH):%Y-%m-%d_%H%M}"
    if store is not None:
        raw = store / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / f"{stem}_1_system.txt").write_text(system, encoding="utf-8")  # the owner sees what was asked
        (raw / f"{stem}_2_user.txt").write_text(user, encoding="utf-8")
    ans = provider.ask(
        f"step-{as_of:%Y%m%d%H%M}", system, user, StepDecision, model=model, effort=EFFORT, cache_system=True
    )
    rec: dict[str, Any] = {
        "as_of": as_of.isoformat(),
        "source": source,
        "status": ans.status.value,
        "model": ans.model,
        "cost_usd": ans.cost_usd,
        "tokens": {
            "input": ans.input_tokens,
            "cache_write": ans.cache_write_tokens,
            "cache_read": ans.cache_read_tokens,
            "output": ans.output_tokens,
        },
        "latency_ms": ans.latency_ms,
        "detail": ans.detail,
    }
    if ans.parsed is not None:
        d: StepDecision = ans.parsed
        size, vetoes = brakes(entries, f, d, frozenset(off))
        held = [k for k in off if any(e["id"] == k and kn.applies(e, f) for e in entries)]
        rec.update(decision=d.model_dump(), final_size=size, vetoed_by=vetoes, suspended_applying=held)
    if store is not None:
        (store / "raw" / f"{stem}_3_answer.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False), "utf-8"
        )
        with (store / "decisions.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    return rec
