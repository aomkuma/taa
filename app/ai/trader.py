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
from app.strategy import liquidity as lq
from app.strategy.checklist import HARD, ITEMS, checklist_lines
from app.strategy.readout import reader_lines

TH = "Asia/Bangkok"
STAND_ASIDE = {"stand_aside"}  # R02 (stand_aside_plan1) is PLAN-1's switch, not the AI's (owner 2026-10-25)
HIDDEN = ("sell_stop_beyond", "buy_stop_beyond")  # the code's own stops, kept out of the readings
# the end of the session journal sent with each call: above the watcher's own parts (the journal's 3,500, its
# calls' 1,500, the plan's orders, the position), so nothing is cut twice from the front (07-06: the position
# note and the plan fell out at 5,000)
JOURNAL_CHARS = 9000
EFFORT = "medium"
QUIET_EFFORT = "low"  # a wake for the regular check only: nothing new to judge (owner 2026-10-25: the quota)
# the principles about my method of working, not about the trade (P20 never stop, P21 no coin flip,
# P22 observe, P25 the loop): kept out of the AI's prompt to save the owner's quota; the rest stay
NOT_FOR_THE_TRADE = frozenset({"P20", "P21", "P22", "P25"})
LESSON_CHARS = 260  # a lesson / shadow in the prompt: its first sentence
NEWS_WEAPON = "W01"  # the NY straddle, the only weapon while R07 holds
MIN_TAKE_PROFIT = 5.0  # USD: the take-profit point at least this far from the entry (P09, checklist C5)
MIN_RISK_REWARD = 0.2  # the ai lane's min_risk_reward (config.yaml): a C4-widened stop keeps it


class CheckAnswer(BaseModel):
    item: str = Field(description="the checklist item id, A1 .. C9")
    verdict: Literal["pass", "fail", "n/a"]
    note: str = Field(description="one short line: what the readings / the picture show for this item")


class StepDecision(BaseModel):
    decision: Literal["WAIT", "SELL", "BUY", "HOLD", "EXIT"]
    weapon: str = Field(
        description="the weapon id (W..) this decision uses - for a WAIT the one being waited for - or 'none'"
    )
    setup: str = Field(description="the setup in a few words, or what is being waited for")
    entry: float | None = Field(description="entry price; null when waiting")
    stop: float | None
    target: float | None
    trigger: str = Field(description="what must happen to enter (or to change the decision)")
    size: Literal["none", "half", "full"]
    kb_ids: list[str] = Field(description="knowledge-base ids the decision rests on")
    reasons: list[str] = Field(description="at most four one-line reasons citing the readings")
    confidence: int = Field(
        description="0-100: the chance the decision's trade reaches its take-profit point before its stop "
        "(the odds of the side taken); for WAIT / HOLD / EXIT the chance the decision is right"
    )
    watch_above: float | None = Field(
        description="wake me again when an M1 bar closes above this price (or null)"
    )
    watch_below: float | None = Field(
        description="wake me again when an M1 bar closes below this price (or null)"
    )
    buy_side: str = Field(
        description="the buy at this moment: entry / stop / target / R, or why there is none"
    )
    sell_side: str = Field(
        description="the sell at this moment: entry / stop / target / R, or why there is none"
    )
    buy_odds: int = Field(description="0-100: the chance a buy here reaches its target before its stop")
    sell_odds: int = Field(description="0-100: the chance a sell here reaches its target before its stop")
    exit_level: float | None = Field(
        default=None,
        description="for a BUY / SELL (or a wait_order): the level the trade is built on - the range edge it "
        "breaks or the level it turns at; 3 M5 closes back across it end the trade early (C6)",
    )
    wait_order: Literal["none", "BUY", "SELL"] = Field(
        default="none",
        description="for a WAIT that names an entry zone: the side of the pending order at entry / stop / "
        "target (placed by the code, braked like an entry; answer the checklist for it)",
    )
    valid_minutes: int = Field(
        default=30,
        description="for a BUY / SELL: how long the order waits for its entry, 1-240 minutes (the expiry)",
    )
    checklist: list[CheckAnswer] = Field(
        description="for a new trade (BUY / SELL): every item A1 .. C9 of the decision checklist answered; "
        "empty for WAIT / HOLD / EXIT"
    )


CHARACTER = (
    "You are the trading judgment of a gold (XAUUSD) trading system, trading like a careful, observant "
    "human trader. At one moment you receive the readings of the market (closed bars only), what the "
    "knowledge base says applies now, and the session's journal so far. Decide ONE thing: WAIT, SELL, BUY "
    "(a new trade), HOLD or EXIT (an open trade). Pick the setup with the most edge at this moment, or "
    "wait - waiting is a decision. Every entry needs: a clear structure on the entry frame, a precise "
    "entry (not chasing a move that already ran; never mid-price except a pullback, P17), the stop BEYOND "
    "THE STRUCTURE that proves the idea wrong AND past the liquidate zone beyond it (the liquidity map "
    "gives the code's stop for each side) - past the top of the peak for a sell, the bottom of the dip for "
    "a buy - never inside a liquidate zone to keep it small; the take-profit point quick (P09, C5): the "
    "next swing, at least 5 USD from the entry and short of the next main line's band - take the profit "
    "and leave (state the R multiple). Liquidate zones are for the stop, never a take-profit point. D1 "
    "(d1_big) names the side with the edge; H4 / H1 against it is a pullback, and its end at a level is the "
    "trade (L21). If you would wait for a confirmation, place the order instead (owner 2026-10-25): a LIMIT "
    "at the level (a sell above / a buy below the price) or a STOP beyond the trigger (a sell below / a buy "
    "above the price: the break), as the situation needs, with its expiry in valid_minutes. "
    "Two ways in, as a trader does: (1) a PENDING ORDER at a scenario's "
    "entry when price is near it - your entry is that price, the code fills it when price gets there "
    "(valid 30 minutes, renewed at your next call); (2) AT MARKET NOW, the scalp on the spot, when the setup "
    "is live at this moment: the rejection or the sweep closed back, or the break, is printing now and price "
    "is still within C3's distance. Never WAIT only to see one more bar of a setup that is live or a zone "
    "you are at - that is how 06 and 07 Jul missed every planned trade (L20). The risk checks accept R from "
    "0.2: a quick take-profit (5 USD or more) against a stop past the liquidate zone is the design (P09 + "
    "P16), so 'no room' is no reason to refuse when R is 0.2 or more. A WAIT that names an entry zone is "
    "answered with the pending order at that zone instead (limit or stop, with valid_minutes to the "
    "window's end): set wait_order to its side and fill entry, stop and target. An EXIT before the stop or "
    "the take-profit stands only after 3 M5 closes back across the level the trade is built on (C6: set "
    "exit_level to the range edge it breaks or the level it turns at; none = the entry) or 60 minutes held "
    "- else the code keeps the trade. A stop short of the map's 'stop beyond it' is moved out to it by the "
    "code when R stays 0.2 or more, else the trade is refused (C4). A limit or stop order never fills at "
    "the first touch: it waits for a signal at its level, read by the code - on M5 a sweep and close back, "
    "an M / W, or (a stop order) an M5 close through the level; on M15-H1 a pin bar or an engulfing "
    "bar (owner 2026-10-26). So place the order at the level and let the signal decide the moment. Read "
    "hundreds of bars of trend, not the last few. Respect a setup's life cycle: a setup whose move already "
    "played out is over. Give prices to two decimals. Keep it short: at most four reasons of one line "
    "each. Cite the knowledge-base ids you used. You never size beyond 'full'; the code may veto you. The "
    "owner's own trades in the journal are the owner's (ideas and context, not yours to manage); HOLD / "
    "EXIT apply only to the system's own open trades, and the system's position is what the journal "
    "records as ours. For an open trade: the code moves the stop to break-even when price touches +1 R; "
    "EXIT when, after +0.5 R, an entry-frame bar closes against the trade, or at the time stop (a scalp 60 "
    "minutes, longer only while the entry frame's structure holds). The weapons whose conditions hold now "
    "are listed as WEAPON under what applies now: judge each of them, name the one you take (or wait for) "
    "in 'weapon', and when you take none of them, say why in the reasons. Always weigh BOTH sides: give "
    "the buy and the sell at this moment (entry, stop, take-profit point, R - or why there is none) with "
    "each side's chance of reaching its take-profit point before its stop, then decide. The owner's goal "
    "is a trade every day - about three, one in each of the owner's windows (P01, P11): inside a window, "
    "look actively for that window's best trade; waiting a whole window out needs a stated reason. "
    "Outside the windows the code stops a new trade unless your confidence is at least 70 (R09: only a "
    "really clean picture). Before a new trade, answer every item of THE DECISION CHECKLIST in "
    "'checklist' (pass / fail / n/a as each item defines them, one line each, quoting the reading): a "
    "failed or unanswered HARD item stops the trade (the code enforces it); a failed WEIGHTED item is "
    "evidence against, weighed with the rest."
)


def first_sentence(text: str, limit: int = LESSON_CHARS) -> str:
    """A lesson's or shadow's first sentence, at most ``limit`` characters (the full text stays in the
    base)."""
    end = text.find(". ")
    short = text if end < 0 else text[: end + 1]
    return short if len(short) <= limit else short[: limit - 3].rstrip() + "..."


def system_prompt(entries: list[dict[str, Any]]) -> str:
    """The trader's character and the owner's principles and rules, built from the knowledge base itself (the
    same text for every call while the base is unchanged - it is cached)."""
    lines = [CHARACTER, "", "THE OWNER'S PRINCIPLES (always) AND THE RULES IN FORCE:"]
    for e in entries:
        if e["kind"] in ("principle", "rule") and e["id"] not in NOT_FOR_THE_TRADE:
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
            lines.append(f"- {e['id']}: {first_sentence(e['says'])}")
    lines.append("")
    lines.append("THE DECISION CHECKLIST (answer every item before a new trade):")
    lines += checklist_lines()
    return "\n".join(lines)


def content(
    as_of: pd.Timestamp,
    journal: str,
    f: dict[str, Any],
    brief: list[str],
    reads: str,
    last: float,
    levels: str,
    liquidity: str = "",
) -> str:
    th = as_of.tz_convert(TH)
    clean = {
        k: (None if isinstance(v, float) and math.isnan(v) else (round(v, 3) if isinstance(v, float) else v))
        for k, v in f.items()
        if k not in HIDDEN
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
            "THE LIQUIDITY MAP (where the stops sit; the stop goes PAST the liquidation zone, not into it):\n"
            + (liquidity or "(none)"),
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


def rule_vetoes(
    entries: list[dict[str, Any]], f: dict[str, Any], side: str, off: frozenset[str] = frozenset()
) -> list[str]:
    """The rules in force that stop a new ``side`` trade (BUY / SELL) now - see :func:`brakes`."""
    live = [
        e
        for e in entries
        if e["kind"] == "rule"
        and e["id"] not in off
        and (not e.get("when") or kn.applies(e, f))
        and e.get("side") in (None, side)
    ]
    vetoes = [e["id"] for e in live if e.get("action") in STAND_ASIDE and e.get("when")]
    against = "down" if side == "BUY" else "up"
    vetoes += [
        e["id"]
        for e in live
        if e.get("action") == "stand_aside_against"
        and e.get("trend")
        and all(f.get(k) == against for k in e["trend"])
    ]
    return vetoes


def brakes(
    entries: list[dict[str, Any]], f: dict[str, Any], d: StepDecision, off: frozenset[str] = frozenset()
) -> tuple[str, list[str]]:
    """The code's veto: a rule in force with a stand-aside action -> no new trade; a rule with the action
    ``stand_aside_against`` -> no new trade against every trend reading it lists (``trend``: a BUY while all
    of them read down, a SELL while all read up). A rule's ``side`` limits it to that side (S11: no SELL in a
    bull regime). A rule's ``unless_confidence`` lets a trade the AI rates at least that sure pass (R09:
    outside the owner's windows only a really clean picture). Rules in ``off`` are suspended. Also stopped: a
    release within the hour unless the weapon is W01 (R07), a HARD checklist item failed or unanswered, a
    take-profit point under 5 USD from the entry (C5); a weapon in shadow status trades at half size (A8)."""
    if d.decision not in ("SELL", "BUY"):
        return d.size, []
    passes = {e["id"] for e in entries if d.confidence >= e.get("unless_confidence", 101)}
    vetoes = [v for v in rule_vetoes(entries, f, d.decision, off) if v not in passes]
    vetoes += [  # R07: a release within the hour - only the news weapon
        e["id"]
        for e in entries
        if e["kind"] == "rule"
        and e.get("action") == "news_weapon_only"
        and e["id"] not in off
        and kn.applies(e, f)
        and d.weapon.strip().upper() != NEWS_WEAPON
    ]
    gaps = checklist_gaps(d)  # a HARD item failed or unanswered (owner 2026-10-25)
    vetoes += [f"checklist {k}" for k in HARD if k in gaps["failed"] or k in gaps["missing"]]
    if d.entry is not None and d.target is not None and abs(d.target - d.entry) < MIN_TAKE_PROFIT:
        vetoes.append("C5 under 5 USD")
    if vetoes:
        return "none", vetoes
    status = {e["id"]: e.get("status") for e in entries if e["kind"] == "weapon"}
    if status.get(d.weapon.strip().upper()) == "shadow" and d.size == "full":
        return "half", []  # a weapon still in shadow status trades at half size (owner 2026-10-25, A8)
    return d.size, []


def checklist_gaps(d: StepDecision) -> dict[str, list[str]]:
    """A new trade's checklist: the items it failed and the items it left unanswered."""
    answered = {a.item.strip().upper(): a.verdict for a in d.checklist}
    return {
        "failed": [k for k in ITEMS if answered.get(k) == "fail"],
        "missing": [k for k in ITEMS if k not in answered],
    }


def last_close(m1: pd.DataFrame, as_of: pd.Timestamp) -> float:
    """The close of the last M1 bar closed by ``as_of``."""
    return float(m1[m1.index <= as_of - pd.Timedelta(minutes=1)].close.iloc[-1])


def stop_check(d: StepDecision, f: dict[str, Any]) -> dict[str, Any] | None:
    """A new trade's stop against the code's stop past the liquidation zone (2026-07-08 14:05: on the pool,
    swept by 0.3): ``beyond`` True when the AI's stop is at or past it."""
    key = {"SELL": "sell_stop_beyond", "BUY": "buy_stop_beyond"}.get(d.decision)
    if key is None or d.stop is None or f.get(key) is None:
        return None
    code = float(f[key])
    beyond = d.stop >= code if d.decision == "SELL" else d.stop <= code
    return {"ai": d.stop, "code": code, "beyond": beyond}


def c4_keeps_r(d: StepDecision, code: float) -> bool:
    """With its stop moved out to the code's ``code`` (past the liquidate zone), the trade still pays at least
    MIN_RISK_REWARD R to its target (no entry given: the lane's own R check decides at the fill)."""
    if d.entry is None or d.target is None:
        return True
    return abs(d.target - d.entry) >= MIN_RISK_REWARD * abs(d.entry - code)


def weapons_in_play(entries: list[dict[str, Any]], f: dict[str, Any]) -> list[str]:
    """The weapons whose conditions hold in the readings ``f``: what the code sees (compared with the AI)."""
    return [e["id"] for e in entries if e["kind"] == "weapon" and e.get("when") and kn.applies(e, f)]


def same_picture(code: list[str], weapon: str | None) -> bool:
    """The AI's weapon is one the code sees in play (or both see none)."""
    w = (weapon or "none").strip().upper()
    return w in code if w != "NONE" else not code


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
    m5 = kn.m5_frame(fr.m1, as_of)
    liq = "\n".join(lq.liquidity_lines(fr.m1, m5, fr.m15, fr.h1, fr.d1, as_of))
    st = lq.structure_now(fr.m1, m5, fr.m15, fr.d1, fr.h1, as_of)
    if st is not None:  # the code's stops, to compare the AI's with (not shown as readings)
        f = {**f, "sell_stop_beyond": st.sell_stop, "buy_stop_beyond": st.buy_stop}
    user = content(
        as_of, tail(journal, JOURNAL_CHARS), f, brief, reads, last_close(fr.m1, as_of), levels, liq
    )
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
    effort: str = EFFORT,
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
        f"step-{as_of:%Y%m%d%H%M}", system, user, StepDecision, model=model, effort=effort, cache_system=True
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
        braked = d  # a WAIT with its pending order is braked as that entry (07-07, ISSUES 26)
        if d.decision == "WAIT" and d.wait_order != "none" and d.entry is not None and d.stop is not None:
            braked = d.model_copy(
                update={"decision": d.wait_order, "size": "half" if d.size == "none" else d.size}
            )
            rec.update(order_side=d.wait_order)
        size, vetoes = brakes(entries, f, braked, frozenset(off))
        check = stop_check(braked, f)
        dumped = d.model_dump()
        if braked.decision in ("BUY", "SELL") and check is not None and not check["beyond"]:
            if c4_keeps_r(braked, check["code"]):  # C4 by the code: the stop goes out past the zone
                dumped["stop"] = check["code"]
                rec.update(stop_widened={"from": d.stop, "to": check["code"]})
            else:  # 07-08 07:25: the AI's stop sat 42 short of the zone and was run
                size, vetoes = "none", [*vetoes, "C4 stop inside the liquidate zone"]
        held = [k for k in off if any(e["id"] == k and kn.applies(e, f) for e in entries)]
        rec.update(decision=dumped, final_size=size, vetoed_by=vetoes, suspended_applying=held)
        # the shadows with a stand-aside action: the trades they would have stopped (recorded, never applied)
        shadows = [dict(e, kind="rule") for e in entries if e["kind"] == "shadow" and e.get("action")]
        rec.update(shadow_vetoes=brakes(shadows, f, d)[1])
        rec.update(stop_check=check)
        rec.update(map_stops_now={"SELL": f.get("sell_stop_beyond"), "BUY": f.get("buy_stop_beyond")})
        code = weapons_in_play(entries, f)  # both sides of the picture: the code's reading and the AI's
        rec.update(weapons_in_play=code, same_picture=same_picture(code, d.weapon))
        rec.update(side_vetoes={s: rule_vetoes(entries, f, s, frozenset(off)) for s in ("BUY", "SELL")})
        if d.decision in ("BUY", "SELL"):  # the decision checklist, answered before the trade
            rec.update(checklist=checklist_gaps(d))
    if store is not None:
        (store / "raw" / f"{stem}_3_answer.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False), "utf-8"
        )
        with (store / "decisions.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    return rec
