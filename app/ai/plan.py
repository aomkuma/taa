"""The day's plan, written by the AI trader before it trades (owner 2026-10-25, KB P26, checklist E8: "before
trading each day, look at the market - yesterday's support / resistance and key levels, the likely trend, the
opportunities, the side with the edge, where price may turn or go on - and summarise it to me"; "you need the
levels on the smaller frames to trade during the day too").

At the start of each of the owner's windows (Asia 07:00 Thai = the morning plan; London and New York = an
update with the day's own M15 / M5 levels so far) the watcher asks the same AI, on the same readings, for a
:class:`DayPlan`. The plan goes into the AI's journal (so every later decision reads it), into ``plans.jsonl``
and the raw files of the store, and its readiness check is the forest items of the decision checklist answered
for the day plus the code's own facts. One code path for the replay and the engine (PLAN §A37).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.ai.providers import AIProvider
from app.ai.trader import EFFORT, MIN_TAKE_PROFIT, TH, CheckAnswer, rule_vetoes, system_prompt
from app.core.enums import Side
from app.strategy import behaviors as bh
from app.strategy import knowledge as kn
from app.strategy import liquidity as lq
from app.strategy.ai_lane import AIOrder
from app.strategy.checklist import ITEMS, KINDS
from app.strategy.readout import reader_lines

Kind = Literal["morning", "london", "ny"]
KIND_OF_SESSION: dict[str, Kind] = {"asia": "morning", "london": "london", "ny": "ny"}
FOREST = tuple(k for k in ITEMS if k.startswith("A"))  # the day's readiness: the forest items A1 .. A8
READINGS = (
    "price", "d1_big", "d1_regime", "d1_rhythm", "h4_trend", "h4_rhythm", "h1_trend", "h1_rhythm",
    "m15_rhythm", "phase", "yesterday", "h1_vol", "h1_atr", "d1_atr20", "release_min", "runaway", "session",
    "asia_break",
)  # fmt: skip


class Level(BaseModel):
    price: float
    frame: Literal["D1", "H4", "H1", "M15", "M5"]
    role: Literal["support", "resistance", "both"]
    what: str = Field(description="what the level is, e.g. yesterday's high, M15 equal lows x3, round 4,200")


class Scenario(BaseModel):
    name: str = Field(description="A, B, C ...")
    side: Literal["BUY", "SELL"]
    where: Literal["turn", "go on"] = Field(description="a turn at a level, or the move going on through it")
    entry: float | None = Field(
        description="the price where this trade is entered: a pending order sits there, and the AI is woken "
        "when price arrives"
    )
    trigger: str = Field(
        description="ONE price event at the entry - price reaching it (a pending order), or one M1 / M5 "
        "close back across the level (e.g. an M5 close back under 4,195) - never a chain of confirmations "
        "(L20)"
    )
    stop: float | None = Field(description="past the liquidate zone beyond the structure")
    take_profit: float | None = Field(
        description="the next swing, >= 5 USD, short of the next main line's band"
    )
    why: str


class DayPlan(BaseModel):
    condition: str = Field(
        description="the market now: the D1 side, the H4 / H1 trend, volatility, the phase"
    )
    big_levels: list[Level] = Field(
        description="support / resistance on D1 / H4 / H1 and yesterday's: its high / low, strong levels, "
        "zone lines with their bands, round numbers"
    )
    intraday_levels: list[Level] = Field(
        description="the levels to trade during the day on M15 / M5: the overnight / today's swings, equal "
        "highs / lows, the Asia range, volume nodes - the nearest ones above and below price"
    )
    trend_today: str = Field(description="the likely path today and why")
    opportunities: list[str] = Field(description="the trades the day may offer, in the owner's windows")
    edge_side: Literal["BUY", "SELL", "both", "none"] = Field(
        description="the side with the edge today (both: each at its own level)"
    )
    edge_why: str
    scenarios: list[Scenario] = Field(description="the points where price may turn or go on")
    releases: str = Field(description="today's scheduled releases and the windows")
    readiness: list[CheckAnswer] = Field(
        description="the forest items A1 .. A8 of the decision checklist answered for the day"
    )
    summary_th: str = Field(description="the plan in at most six short lines of Thai, for the owner")


TASK = {
    "morning": "THE MORNING PLAN (P26): before trading the day, write the day's plan (D1 names the side with "
    "the edge; H4 / H1 against it is a pullback whose end is the trade, L21)",
    "london": "THE LONDON UPDATE (P26): before the London window, update the day's plan",
    "ny": "THE NEW YORK UPDATE (P26): before the New York window, update the day's plan",
}


def plan_due(now: pd.Timestamp, last: str | None) -> Kind | None:
    """The plan due at ``now``: the window ``now`` is in, once a Thai day (``last`` = 'YYYY-MM-DD:kind')."""
    kind = KIND_OF_SESSION.get(kn.session(now))
    if kind is None:
        return None
    key = f"{now.tz_convert(TH):%Y-%m-%d}:{kind}"
    return None if key == last else kind


def plan_key(now: pd.Timestamp, kind: Kind) -> str:
    return f"{now.tz_convert(TH):%Y-%m-%d}:{kind}"


def plan_inputs(fr: kn.Frames, as_of: pd.Timestamp) -> tuple[str, dict[str, Any]]:
    """What the plan is written from (bars closed by ``as_of``): the readings, yesterday's and today's own
    levels, the readers' lines, the liquidity map (the stop side) and today's releases."""
    f = kn.features(fr, as_of)
    th = as_of.tz_convert(TH)
    start = pd.Timestamp(f"{th.date()} 07:00", tz=TH).tz_convert("UTC")
    # the previous trading day (Friday's on a Monday): its last M15 bar before today's 05:00 Thai
    before = fr.m15[fr.m15.index + pd.Timedelta(minutes=15) <= start - pd.Timedelta(hours=2)]
    prev_end = before.index[-1] + pd.Timedelta(minutes=15) if len(before) else start
    # day_levels' own D1 line there is the bar BEFORE that day: name the last closed D1 bar explicitly instead
    yesterday = [x for x in bh.day_levels(fr.m15, fr.d1, prev_end) if not x.startswith("yesterday's D1")]
    d1_done = fr.d1[fr.d1.index + pd.Timedelta(days=1) <= as_of]
    if len(d1_done):
        b = d1_done.iloc[-1]
        named = d1_done.index[-1] + pd.Timedelta(hours=12)  # the broker's day: its bar opens 21:00 UTC before
        yesterday.append(
            f"the last closed D1 bar ({named:%a %d %b}): high {b.high:.2f}, low {b.low:.2f}, "
            f"close {b.close:.2f}"
        )
    today = bh.day_levels(fr.m15, fr.d1, as_of) if as_of > start else []
    m5 = kn.m5_frame(fr.m1, as_of)
    liq = lq.liquidity_lines(fr.m1, m5, fr.m15, fr.h1, fr.d1, as_of)
    day_end = start + pd.Timedelta(days=1)
    rel = [x for x in fr.releases if start <= pd.Timestamp(x.at) < day_end]
    readings = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in f.items() if k in READINGS}
    parts = [
        f"NOW: {th:%a %d %b %Y %H:%M} Thai time. Bars closed by this time only.",
        "READINGS:\n" + json.dumps(readings),
        "YESTERDAY'S OWN LEVELS (the previous Thai day):\n" + ("\n".join(yesterday) or "(none)"),
        "TODAY'S OWN LEVELS SO FAR (M15 swings, the day's high / low):\n"
        + ("\n".join(today) or "(none yet)"),
        "THE READERS' OUTPUT (rhythm per frame, pictures, the zone plan, strong levels):\n"
        + "\n".join(reader_lines(fr, as_of)),
        "THE LIQUIDITY MAP (liquidate zones - the stop side, never take-profit points):\n" + "\n".join(liq),
        "TODAY'S SCHEDULED US RELEASES (Thai time):\n"
        + (
            "\n".join(f"{pd.Timestamp(x.at).tz_convert(TH):%H:%M} {getattr(x, 'name', '')}" for x in rel)
            or "none"
        ),
        "THE OWNER'S WINDOWS: Asia 07:00-09:00, London 13:00-15:00 Thai, New York 08:00-11:30 New York time.",
    ]
    return "\n\n".join(parts), f


def readiness_facts(f: dict[str, Any], as_of: pd.Timestamp, fr: kn.Frames) -> list[str]:
    """The code's own readiness facts for the day: the bars' freshness, volatility (R01), releases (R07)."""
    closed = fr.m1.index[fr.m1.index + pd.Timedelta(minutes=1) <= as_of]
    last = closed[-1] + pd.Timedelta(minutes=1) if len(closed) else None
    fresh = last is not None and (as_of - last) <= pd.Timedelta(minutes=5)
    vol = f.get("h1_vol")
    return [
        f"bars current: {'yes' if fresh else 'NO'} (the last M1 close {last})",
        f"volatility (R01): h1_vol {vol:.2f} - {'stand aside' if vol > 1.1 else 'tradable'}"
        if isinstance(vol, float)
        else "volatility (R01): no reading",
        f"the nearest US release: {f.get('release_min')} minutes away (R07 within 60)",
    ]


def plan_markdown(plan: DayPlan, as_of: pd.Timestamp, kind: Kind, facts: list[str]) -> str:
    """The plan as the journal section the AI reads at every later step (and the owner reads)."""
    th = as_of.tz_convert(TH)
    title = {"morning": "the morning plan", "london": "the London update", "ny": "the New York update"}[kind]

    def lv(x: Level) -> str:
        return f"{x.price:.2f} {x.frame} {x.role} ({x.what})"

    lines = [
        f"## {th:%a %d %b %Y} - {title} ({th:%H:%M} Thai, written by the AI, P26)",
        f"- condition: {plan.condition}",
        "- big levels: " + "; ".join(lv(x) for x in plan.big_levels),
        "- intraday levels (M15 / M5): " + "; ".join(lv(x) for x in plan.intraday_levels),
        f"- the trend today: {plan.trend_today}",
        f"- the side with the edge: {plan.edge_side} - {plan.edge_why}",
    ]
    for s in plan.scenarios:
        lines.append(
            f"- {s.name} ({s.side}, {s.where}): {s.trigger}; stop {s.stop}, take-profit {s.take_profit} - "
            f"{s.why}"
        )
    lines.append("- opportunities: " + "; ".join(plan.opportunities))
    lines.append(f"- releases / windows: {plan.releases}")
    fails = [a.item for a in plan.readiness if a.verdict == "fail"]
    lines.append(f"- readiness (A1-A8): failed {', '.join(fails) or 'none'}; " + "; ".join(facts))
    return "\n".join(lines) + "\n"


def window_end(as_of: pd.Timestamp, kind: Kind) -> pd.Timestamp:
    """The end of the window a plan is written for: 09:00 / 15:00 Thai, 11:30 New York."""
    if kind == "ny":
        ny = as_of.tz_convert("America/New_York")
        return pd.Timestamp(f"{ny.date()} 11:30", tz="America/New_York").tz_convert("UTC")
    th = as_of.tz_convert(TH)
    return pd.Timestamp(f"{th.date()} {'09:00' if kind == 'morning' else '15:00'}", tz=TH).tz_convert("UTC")


def next_release(fr: kn.Frames, as_of: pd.Timestamp) -> str | None:
    """The next scheduled US release after ``as_of`` (ISO), None without one."""
    later = sorted(pd.Timestamp(x.at) for x in fr.releases if pd.Timestamp(x.at) > as_of)
    return later[0].isoformat() if later else None


def plan_orders(rec: dict[str, Any]) -> list[AIOrder]:
    """The plan's scenarios as pending orders, placed in advance and checked by the code (owner 2026-10-25:
    every planned trade of 06-07 Jul printed and none was taken): an entry, stop and take-profit point each;
    the stop moved out to the map's stop past the liquidate zone when nearer (C4); the take-profit point 5 USD
    or more from the entry (C5); no side a rule in force stops now (R01 / R07 / R09 ...); none against the D1
    regime (owner 2026-10-26: a trend needs the stop orders with it); half size."""
    plan = rec.get("plan")
    if plan is None:
        return []
    at = pd.Timestamp(rec["as_of"]).to_pydatetime()
    until = pd.Timestamp(rec["valid_until"]).to_pydatetime()
    if rec.get("next_release"):  # R07: an hour either side of a release is the news weapon's alone
        until = min(until, (pd.Timestamp(rec["next_release"]) - pd.Timedelta(minutes=60)).to_pydatetime())
    if until <= at:
        return []
    stops = rec.get("map_stops") or {}
    d1 = rec.get("d1_side", "none")  # the side with the edge (owner 10-20: D1 names it)
    out = []
    for s in plan["scenarios"]:
        side, entry, stop, tp = s["side"], s.get("entry"), s.get("stop"), s.get("take_profit")
        if entry is None or stop is None or tp is None or (rec.get("vetoes") or {}).get(side):
            continue
        sell = side == "SELL"
        if (sell and d1 == "up") or (not sell and d1 == "down"):
            continue  # against D1: 06-08 Jul, 5 of the 7 counter-D1 plan orders lost (-3.8 R); L21
        if stops.get(side) is not None:  # never inside the liquidate zone: out to the map's stop at least
            stop = max(stop, stops[side]) if sell else min(stop, stops[side])
        if (stop - entry if sell else entry - stop) <= 0 or abs(tp - entry) < MIN_TAKE_PROFIT:
            continue
        if (entry - tp if sell else tp - entry) <= 0:
            continue
        out.append(
            AIOrder(
                side=Side.SELL if sell else Side.BUY,
                entry=float(entry),
                stop=float(stop),
                target=float(tp),
                risk_scale=0.5,
                setup=f"plan {rec['kind']} {s['name']}: {s['trigger']}",
                reasons=(s["why"],),
                kb_ids=("P26",),
                confidence=0,
                decided_at=at,
                valid_until=until,
                key=f"plan-{rec['kind']}-{pd.Timestamp(rec['as_of']):%Y%m%d%H%M}-{s['name']}",
            )
        )
    return out


def make_plan(
    provider: AIProvider,
    entries: list[dict[str, Any]],
    fr: kn.Frames,
    as_of: pd.Timestamp,
    kind: Kind,
    *,
    model: str | None = None,
    store: Path | None = None,
    journal: Path | None = None,
) -> dict[str, Any]:
    """Ask the AI for the plan due at ``as_of``; append it to ``journal`` and ``store``/plans.jsonl. Never
    raises on a failed answer: the record says so and nothing is appended to the journal."""
    inputs, f = plan_inputs(fr, as_of)
    forest = "\n".join(f"- {k} [{KINDS[k]}]: {ITEMS[k]}" for k in FOREST)
    user = (
        f"{TASK[kind]} - every heading of the plan, the levels on the big frames AND the M15 / M5 levels to "
        "trade during the day, each scenario with its trigger, stop (past the liquidate zone) and "
        "take-profit point (the next swing, >= 5 USD, short of the next main line's band), and the forest "
        f"items for the day:\n{forest}\n\n{inputs}"
    )
    system = system_prompt(entries)
    stem = f"{as_of.tz_convert(TH):%Y-%m-%d_%H%M}_plan_{kind}"
    if store is not None:
        raw = store / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / f"{stem}_2_user.txt").write_text(user, encoding="utf-8")
    ans = provider.ask(
        f"plan-{kind}-{as_of:%Y%m%d%H%M}",
        system,
        user,
        DayPlan,
        model=model,
        effort=EFFORT,
        cache_system=True,
    )
    rec: dict[str, Any] = {
        "as_of": as_of.isoformat(),
        "kind": kind,
        "status": ans.status.value,
        "model": ans.model,
        "cost_usd": ans.cost_usd,
        "latency_ms": ans.latency_ms,
        "detail": ans.detail,
    }
    if ans.parsed is not None:
        plan: DayPlan = ans.parsed
        facts = readiness_facts(f, as_of, fr)
        st = lq.structure_now(fr.m1, kn.m5_frame(fr.m1, as_of), fr.m15, fr.d1, fr.h1, as_of)
        rec.update(
            plan=plan.model_dump(),
            facts=facts,
            map_stops=None if st is None else {"SELL": st.sell_stop, "BUY": st.buy_stop},
            vetoes={s: rule_vetoes(entries, f, s) for s in ("BUY", "SELL")},
            valid_until=window_end(as_of, kind).isoformat(),
            next_release=next_release(fr, as_of),
            d1_side=f.get("d1_regime", "none"),
        )
        if journal is not None:
            journal.parent.mkdir(parents=True, exist_ok=True)
            with journal.open("a", encoding="utf-8") as fh:
                fh.write("\n" + plan_markdown(plan, as_of, kind, facts))
    if store is not None:
        (store / "raw" / f"{stem}_3_answer.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False), "utf-8"
        )
        with (store / "plans.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
