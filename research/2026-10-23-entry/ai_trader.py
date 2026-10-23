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
from observe import KEYS, read_all  # noqa: E402

from app.config import load_settings  # noqa: E402

OUT = HERE / "ai" / "decisions.jsonl"
TH = "Asia/Bangkok"
STAND_ASIDE = {"stand_aside", "stand_aside_plan1"}
JOURNAL_CHARS = 5000  # the end of the session journal sent with each call (the cost grows with it)
SUSPENDED = HERE / "ai" / "suspended.json"  # rules the owner suspends for a while: {"R01": "2026-10-23T22:00:00+00:00"}


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
    watch_above: float | None = Field(description="wake me again when an M1 bar closes above this price (or null)")
    watch_below: float | None = Field(description="wake me again when an M1 bar closes below this price (or null)")


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
        "Keep it short: at most four reasons of one line each. Cite the knowledge-base ids you used. You never size beyond 'full'; the code may veto you. "
        "The owner's own trades in the journal are the owner's (ideas and context, not yours to manage); HOLD / EXIT "
        "apply only to the system's own open trades, and the system's position is what the journal records as ours.",
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


def content(as_of: pd.Timestamp, journal: str, f: dict, brief: list[str], reads: str, last: float, levels: str) -> str:
    th = as_of.tz_convert(TH)
    clean = {k: (None if isinstance(v, float) and math.isnan(v) else (round(v, 3) if isinstance(v, float) else v))
             for k, v in f.items()}
    return "\n\n".join([
        f"NOW: {th:%a %d %b %Y %H:%M} Thai time ({as_of:%H:%M} UTC). Bars closed by this time only. The last M1 close: "
        f"{last:.2f} (the readings' 'price' is the last closed M15 bar's close).",
        "READINGS (knowledge base features):\n" + json.dumps(clean),
        "WHAT THE KNOWLEDGE BASE SAYS APPLIES NOW:\n" + "\n".join(brief),
        "THE DAY'S OWN LEVELS (M15 swings of the Thai day, the day's and yesterday's high / low):\n" + levels,
        "THE READERS' OUTPUT:\n" + reads,
        "THE SESSION'S JOURNAL SO FAR (earlier steps, including any open trade):\n" + (journal or "(empty)"),
    ])


def tail(text: str, chars: int) -> str:
    """The end of ``text``, at most ``chars`` long, cut at the start of a heading (## / ###) when one is inside."""
    if len(text) <= chars:
        return text
    cut = text[-chars:]
    k = cut.find("\n#")
    return ("(earlier steps left out)\n" + cut[k + 1:]) if k >= 0 else "(earlier steps left out)\n" + cut


def trim_reads(text: str) -> str:
    """Only the readers' lines that carry a reading (observe.KEYS), as the hourly diary keeps them."""
    return "\n".join(ln.strip() for ln in text.splitlines() if KEYS.search(ln) and not ln.startswith("#"))


def ask_cached(api_key: str, model: str, system: str, user: str) -> dict:
    """One structured call with the system prompt cached for an hour (it only changes when kb.yaml does): cache
    reads cost a tenth of the input price, the first write twice. Returns status, the parsed decision and the spend."""
    import time

    import anthropic

    from app.ai.providers import FALLBACK_BETA, MAX_TOKENS, PRICES

    started = time.perf_counter()
    client = anthropic.Anthropic(api_key=api_key, timeout=180, max_retries=1)
    try:
        r = client.beta.messages.parse(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            messages=[{"role": "user", "content": user}], output_format=StepDecision,
            output_config={"effort": "medium"}, betas=[FALLBACK_BETA], fallbacks="default")
    except anthropic.APIError as exc:
        return {"status": "ERROR", "detail": f"{type(exc).__name__}: {exc}"[:500], "cost_usd": 0.0}
    u = r.usage
    fresh, write = int(u.input_tokens or 0), int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    read, out = int(getattr(u, "cache_read_input_tokens", 0) or 0), int(u.output_tokens or 0)
    pin, pout = PRICES.get(str(r.model), (0.0, 0.0))
    cost = (fresh * pin + write * pin * 2 + read * pin * 0.1 + out * pout) / 1_000_000
    rec = {"status": "OK" if r.parsed_output is not None and r.stop_reason not in ("refusal", "max_tokens") else "INVALID",
           "model": str(r.model), "cost_usd": round(cost, 6), "tokens": {"input": fresh, "cache_write": write,
           "cache_read": read, "output": out}, "latency_ms": round((time.perf_counter() - started) * 1000, 1),
           "detail": str(r.stop_reason)}
    if rec["status"] == "OK":
        rec["parsed"] = r.parsed_output
    return rec


def suspended(now: pd.Timestamp, path: Path = SUSPENDED) -> dict[str, str]:
    """The rules the owner suspended for a while: {id: until (ISO UTC)} from ai/suspended.json, only those not yet
    expired at ``now``."""
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in rows.items() if pd.Timestamp(v) > now}


def brakes(entries: list[dict], f: dict, d: StepDecision, off: frozenset[str] = frozenset()) -> tuple[str, list[str]]:
    """The code's veto: a rule in force with a stand-aside action -> no new trade (rules in ``off`` are suspended)."""
    vetoes = [e["id"] for e in entries if e["kind"] == "rule" and e.get("action") in STAND_ASIDE and e.get("when")
              and e["id"] not in off and kb.applies(e, f)]
    if d.decision in ("SELL", "BUY") and vetoes:
        return "none", vetoes
    return d.size, []


def decide(as_of: pd.Timestamp, journal: str, model: str | None = None, source: str = "manual") -> dict:
    """One AI decision at ``as_of`` with the code's brakes; the raw prompt and answer are kept in ai/raw/."""
    import behaviors as bh
    import zone_wait as zw

    entries = kb.load()
    f = kb.features(as_of)
    brief = kb.brief(entries, f)
    off = suspended(as_of)
    if off:  # the AI is told plainly, and the trades taken meanwhile carry the mark (the rule's cost is measured)
        brief.append("SUSPENDED BY THE OWNER FOR NOW (do NOT stand aside because of these; trades are recorded as taken "
                     "while suspended): " + ", ".join(f"{k} until {pd.Timestamp(v).tz_convert(TH):%a %H:%M} Thai"
                                                      for k, v in off.items()))
    reads = trim_reads(read_all(as_of))
    m1 = zw.load("M1")
    last = float(m1[m1.index <= as_of - pd.Timedelta(minutes=1)].close.iloc[-1])  # the M1 bar closed by as_of
    levels = "\n".join(bh.day_levels(zw.load("M15"), zw.load("D1"), as_of))
    env = load_settings(env_file=str(ROOT / ".env")).env
    if env.AI_API_KEY is None:
        raise SystemExit("AI_API_KEY is not set")
    system, user = system_prompt(entries), content(as_of, tail(journal, JOURNAL_CHARS), f, brief, reads, last, levels)
    raw = HERE / "ai" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    stem = f"{as_of.tz_convert(TH):%Y-%m-%d_%H%M}"
    (raw / f"{stem}_1_system.txt").write_text(system, encoding="utf-8")  # the owner sees exactly what was asked
    (raw / f"{stem}_2_user.txt").write_text(user, encoding="utf-8")
    ans = ask_cached(env.AI_API_KEY.get_secret_value(), model or env.AI_MODEL, system, user)
    parsed = ans.pop("parsed", None)
    rec = {"as_of": as_of.isoformat(), "source": source, **ans}
    if parsed is not None:
        d: StepDecision = parsed
        size, vetoes = brakes(entries, f, d, frozenset(off))
        held = [k for k in off if any(e["id"] == k and kb.applies(e, f) for e in entries)]
        rec.update(decision=d.model_dump(), final_size=size, vetoed_by=vetoes, suspended_applying=held)
    (raw / f"{stem}_3_answer.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def main() -> None:
    as_of = pd.Timestamp(sys.argv[1], tz="UTC")
    journal = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else ""
    print(json.dumps(decide(as_of, journal), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
