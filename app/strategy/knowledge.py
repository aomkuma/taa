"""The knowledge base at the moment of a decision (owner 2026-10-23: "has everything we discussed been
recorded and used in the decisions?"; PLAN §A37, TAA-1803). Moved from
research/2026-10-23-entry/knowledge/kb.py, which now wraps it with the research's file loaders.

``kb.yaml`` (next to this module) is the one source of truth: the owner's principles, the rules in force, the
weapons, shadows, findings, failed methods, lessons and open drafts, each with the readings it applies to.
:func:`features` reads the market at ``as_of`` from the frames handed in (bars closed by ``as_of`` only; no
file reads); :func:`brief` says which entries apply now.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from app.news.releases import Release
from app.strategy import behaviors as bh
from app.strategy import context_read as cr
from app.strategy import level_momentum as lm
from app.strategy import picture as pc
from app.strategy import structure_read as sr
from app.strategy import zone_grid as zg
from app.strategy.plan1_b2 import Bars, mt5_atr
from app.strategy.rhythm import rhythm
from app.strategy.strong_levels import closed

KB = Path(__file__).with_name("kb.yaml")
KINDS = {
    "P": "principle",
    "R": "rule",
    "W": "weapon",
    "S": "shadow",
    "F": "finding",
    "X": "failed",
    "L": "lesson",
    "O": "open",
}
STAGES = {
    "forest", "plan", "trend", "pressure", "clock", "animal", "weapon", "picture",
    "entry", "stop", "target", "exit", "size", "after", "method", "observer",
}  # fmt: skip
NUMERIC = {
    "h1_vol", "d1_atr20", "h1_atr", "release_min", "day_range_step", "bars_at_line",
    "m15_range12_atr", "line_dist_step", "line_touches", "h1_eff12", "m15_relvol",
}  # fmt: skip
_UPDOWN = {"up", "down", "none"}
WORDS: dict[str, set[str]] = {
    "session": {"asia", "london", "ny", "none"},
    "phase": _UPDOWN,
    "yesterday": {"strong_up", "strong_down", "none"},
    **{f"{tf}_rhythm": _UPDOWN for tf in ("m15", "h1", "h4", "d1")},
    **{f"{tf}_big": _UPDOWN for tf in ("h1", "h4", "d1")},
    "m15_leg": _UPDOWN,
    "line_worn": {"yes", "no"},
    "line_break": _UPDOWN,
    "climax": {"top", "bottom", "none"},
    "runaway": _UPDOWN,
    "asia_break": {"up", "down", "both", "none"},
    "sweep": {"low", "high", "none"},
}
FEATURES = NUMERIC | set(WORDS)
OPS = re.compile(r"^(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)$")
TH, NY = "Asia/Bangkok", "America/New_York"
MINUTES = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}
WINDOW = 700  # bars of each frame handed to the readers (the big trend needs 500)
PICTURE_BARS = 72  # the M5 bars the pool reader reads (research picture_read.N)
DAY_NS = 24 * 3600 * 10**9


def load(path: Path = KB) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return entries


def _maps(when: Any) -> list[dict[str, Any]]:
    """``when`` as a list of alternatives (each a map whose conditions must all hold); [] = always."""
    if when is None:
        return []
    return [when] if isinstance(when, dict) else list(when)


def validate(entries: list[dict[str, Any]], items: set[str]) -> list[str]:
    """Every problem found (empty = the base is sound); ``items`` = the decision checklist's item ids."""
    out: list[str] = []
    ids = [e.get("id", "?") for e in entries]
    out += [f"{i}: the id is used {ids.count(i)} times" for i in sorted(set(ids)) if ids.count(i) > 1]
    names = [e["behavior"] for e in entries if "behavior" in e]
    out += [
        f"the behavior '{b}' is named {names.count(b)} times"
        for b in sorted(set(names))
        if names.count(b) > 1
    ]
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
        if "behavior" in e and not (re.fullmatch(r"[a-z]+", str(e["behavior"])) and e.get("when")):
            out.append(f"{i}: a behavior needs a one-word lowercase name and its readings (when)")
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
    return bool(value == spec)


def applies(entry: dict[str, Any], f: dict[str, Any]) -> bool:
    alts = _maps(entry.get("when"))
    return not alts or any(all(holds(f.get(k), v) for k, v in alt.items()) for alt in alts)


def session(at: pd.Timestamp) -> str:
    """The owner's windows: Asia 07:00-09:00 Thai, London 13:00-15:00 Thai, New York 08:00-11:30 New York."""
    th, ny = at.tz_convert(TH), at.tz_convert(NY)
    h, m = th.hour + th.minute / 60, ny.hour + ny.minute / 60
    return "asia" if 7 <= h < 9 else "london" if 13 <= h < 15 else "ny" if 8 <= m < 11.5 else "none"


@dataclass(frozen=True)
class Frames:
    """The bars a reading needs: bar-open UTC index, columns open / high / low / close / tick_volume; the
    whole D1 history (the zone grid's anchors), the other frames at least ``WINDOW`` bars back."""

    m1: pd.DataFrame
    m15: pd.DataFrame
    h1: pd.DataFrame
    h4: pd.DataFrame
    d1: pd.DataFrame
    releases: tuple[Release, ...]


def _ns(index: pd.Index) -> np.ndarray:
    ns: Any = pd.DatetimeIndex(index).as_unit("ns")  # .asi8 exists at runtime; the pandas stubs lack it
    return np.asarray(ns.asi8, dtype=np.int64)


def bars_of(df: pd.DataFrame, minutes: int) -> Bars:
    t = _ns(df.index)
    return Bars(
        t,
        t + minutes * 60 * 10**9,
        df.open.to_numpy(float),
        df.high.to_numpy(float),
        df.low.to_numpy(float),
        df.close.to_numpy(float),
    )


def _window(b: Bars, t: int, n: int) -> Bars:
    j = int(np.searchsorted(b.avail, t, side="right"))
    s = slice(max(0, j - n), j)
    return Bars(b.t_open[s], b.avail[s], b.o[s], b.h[s], b.lo[s], b.c[s])


def features(fr: Frames, as_of: pd.Timestamp) -> dict[str, Any]:
    """The readings at ``as_of`` (bars closed by it), from the bot's modules."""
    t = as_of.value
    dfs = {"M15": fr.m15, "H1": fr.h1, "H4": fr.h4, "D1": fr.d1}
    data = {tf: bars_of(dfs[tf], MINUTES[tf]) for tf in MINUTES}
    w = {tf: _window(data[tf], t, WINDOW) for tf in MINUTES}
    d1 = data["D1"]
    st = zg.grid_at(zg.grid_rows(d1.t_open, d1.o, d1.h, d1.lo, d1.c), t)
    price = float(closed(w["M15"], t).c[-1])
    day = cr.last_day(w["D1"], t)
    ph = sr.phase(w["D1"], t)
    run, rng = cr.day_so_far(w["H1"], t, price, 1, st.step)
    word = {1: "up", -1: "down", 0: "none"}
    f: dict[str, Any] = {
        "price": price,
        "h1_vol": cr.vol_ratio(w["H1"], t),
        "d1_atr20": st.step,
        "day_range_step": rng,
        "session": session(as_of),
        "phase": word[int(ph)],
        "yesterday": ("strong_up" if day.direction > 0 else "strong_down") if day.strong else "none",
    }
    m15_atr = math.nan
    for tf in ("M15", "H1", "H4", "D1"):
        r = rhythm(closed(w[tf], t), t)
        f[f"{tf.lower()}_rhythm"] = word[r.sign]
        if tf != "M15":
            f[f"{tf.lower()}_big"] = word[int(r.big.sign)]
        if tf == "H1":
            f["h1_atr"] = r.atr
        if tf == "M15":
            f["m15_leg"], m15_atr = word[int(np.sign(r.leg))], r.atr
    gaps = [abs((pd.Timestamp(x.at) - as_of).total_seconds()) / 60 for x in fr.releases]
    f["release_min"] = min(gaps) if gaps else math.nan

    # the behaviours' readings (app/strategy/behaviors.py; the drafts O11-O22)
    half = st.step / 2
    near = st.anchor + round((price - st.anchor) / half) * half  # the nearest line, main or half
    f["line_dist_step"] = abs(price - near) / st.step
    main_line, _, _ = zg.nearest_line(
        st, price
    )  # the deer as routine_read reads it: M15 bars at the main line
    f["bars_at_line"] = lm.level_momentum(w["M15"], t, main_line, 0.15 * st.step, 1, t - DAY_NS).bars_at_line
    mo = lm.level_momentum(w["H1"], t, near, 0.15 * st.step, 1 if near < price else -1, t - 5 * DAY_NS)
    f["line_touches"], f["line_worn"] = mo.touches, "yes" if mo.worn else "no"
    xm, xh = closed(w["M15"], t), closed(w["H1"], t)
    f["m15_range12_atr"] = pc.squeeze_range(xm.h, xm.lo, m15_atr)
    f["h1_eff12"] = bh.efficiency(xh.c, 12)
    f["line_break"] = bh.line_break(xm.c, st.anchor, half, 4)
    yd = closed(w["D1"], t)
    f["runaway"] = bh.runaway(price, float(yd.h[-1]), float(yd.lo[-1]), run)
    h1df = fr.h1[fr.h1.index + pd.Timedelta(hours=1) <= as_of].iloc[-101:]
    b = h1df.iloc[-1]
    v_mean = float(h1df.tick_volume.iloc[:-1].mean())
    f["climax"] = bh.climax(b.open, b.high, b.low, b.close, b.tick_volume, f["h1_atr"], v_mean)
    m15df = fr.m15[fr.m15.index + pd.Timedelta(minutes=15) <= as_of].iloc[-200:]
    hi15, lo15 = m15df.high.to_numpy(float), m15df.low.to_numpy(float)
    f["asia_break"] = bh.asia_break(pd.DatetimeIndex(m15df.index), hi15, lo15, as_of)
    t15 = _ns(fr.m15.index)
    i15 = int(np.searchsorted(t15, m15df.index[-1].value))
    f["m15_relvol"] = cr.rel_volume(t15, fr.m15.tick_volume.to_numpy(float), i15)
    d5 = m5_frame(fr.m1, as_of)
    h5, lo5, c5, v5 = (d5[k].to_numpy(float) for k in ("high", "low", "close", "tick_volume"))
    atr5 = float(mt5_atr(h5, lo5, c5, 14)[-1])
    n = PICTURE_BARS
    f["sweep"] = bh.recent_sweep(h5[-n:], lo5[-n:], c5[-n:], v5[-n:], atr5, 6)
    if f["sweep"] == "none":  # L14: the day's own levels and the zone lines are pools too
        before = d5.index[-6]  # the window's first bar opens here: levels known before it
        k0 = math.floor((price - st.anchor) / half)
        lines = [st.anchor + k * half for k in range(k0 - 2, k0 + 4)]
        levels = bh.level_prices(fr.m15, fr.d1, before) + lines
        f["sweep"] = bh.level_sweep(h5, lo5, c5, levels, atr5, 6)
    return f


def m5_frame(m1: pd.DataFrame, as_of: pd.Timestamp, bars: int = PICTURE_BARS + 40) -> pd.DataFrame:
    """M5 bars built from the M1 bars that opened in the ``bars`` x 5 minutes before ``as_of`` (research
    picture_read.frame). The last bucket may hold fewer than five M1 bars when ``as_of`` is not on a 5-minute
    mark; all its M1 bars are closed."""
    x = m1[(m1.index >= as_of - pd.Timedelta(minutes=5 * bars)) & (m1.index < as_of)]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}
    return x.resample("5min").agg(agg).dropna()


def behaviors_now(entries: list[dict[str, Any]], f: dict[str, Any]) -> list[str]:
    """The price behaviours (animals) whose readings hold now, in the base's order."""
    return [e["behavior"] for e in entries if "behavior" in e and applies(e, f)]


def brief(entries: list[dict[str, Any]], f: dict[str, Any]) -> list[str]:
    """What the base says now: the conditional entries whose readings hold (rules first), then the ids always
    on."""
    order = list(KINDS.values())
    hits = sorted(
        (e for e in entries if e.get("when") and applies(e, f)),
        key=lambda e: (order.index(e["kind"]), e["id"]),
    )
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

    out = [
        "# The knowledge base (generated from kb.yaml by kb.py render - do not edit here)\n",
        "Precedence at a decision: principle > rule > weapon > shadow (shown, never applied) > finding > "
        "failed (never retried as it was) > lesson > open. `when` = the readings an entry applies to (none = "
        "always).\n",
    ]
    for kind in KINDS.values():
        rows = [e for e in entries if e["kind"] == kind]
        if not rows:
            continue
        out.append(f"\n## {kind.capitalize()}s ({len(rows)})\n")
        out.append("| id | stage | items | when | says | evidence | source |\n|---|---|---|---|---|---|---|")
        for e in rows:
            says = e["says"] + (
                f" [status: {e['status']}; animal: {e['animal']}]" if kind == "weapon" else ""
            )
            out.append(
                f"| {e['id']} | {e['stage']} | {cell(', '.join(e.get('items') or []))} | "
                f"{cell(e.get('when'))} | "
                f"{cell(says)} | {cell(e.get('evidence'))} | {cell(e.get('source'))} |"
            )
    return "\n".join(out) + "\n"
