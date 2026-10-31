"""What the bot reads on one Thai day, drawn in the look of the owner's MT5 screen (black background, plain
candles, Thai time). Research only: nothing is traded, nothing is written to a ledger.

The bot's decision logic (``eye/bot2e.py``) is run at every M5 close inside the owner's three windows, with
nothing written and ``used`` kept for the run (a leg that has produced an order is not counted again;
``max_orders`` is not applied, so every order the rules would write is drawn). Drawn:

* M5 candles from 06:00 to 23:59 Thai, the three windows shaded faintly;
* strip 1: rule 16's side at every M5 bar (green BUY / red SELL / grey none);
* strip 2: rule 3's M5 trend at every window bar (green UP / red DOWN / grey none) - the reading of the
  fixed M5 pivots in the setup look, whatever the leg;
* strip 3: the rule that stopped each window bar (legend below), or ORDER;
* for every order: the leg's Fibo (L0 0 %, 23.6, 38.2, 61.8, H100 100 %) from L0 to the end of the day, the
  order price, stop and target from the decision bar with planned R, and where it would fill and exit, scored
  by ``eye/score.py`` (BOT_RULES rule 12).

Usage: bot_read_day.py 2026-10-07 [market=XAUUSD] [set=default] [db=PATH] [name=value ...]

The base ``Params`` are the stored set ``market`` / ``set`` of the config database ``db`` (default
``data/bot_config.db``); ``name=value`` overrides (``bot2e.Params`` fields, e.g. fib_entry=0.382) apply
on top, for drawing only. The drawing's title names the set, its version and every override. The market
is checked before any bar is loaded.
"""

from __future__ import annotations

import re
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e  # noqa: E402
from eye.score import score, start_of  # noqa: E402

TH = bot2e.TH
FIB_LEVELS = (
    0.0,
    0.236,
    0.382,
    0.5,
    0.618,
    0.786,
    1.0,
    1.272,
    1.618,
)  # 100 % is the end, beyond it the extensions
SIDE_COLOUR = {"BUY": "#26a65b", "SELL": "#e0433b", "none": "#555555"}
TREND_COLOUR = {"UP": "#26a65b", "DOWN": "#e0433b", "none": "#555555"}
# The rule that stopped a window bar: (legend text, colour). Several reasons of one rule share an entry.
REASON_STYLE: list[tuple[str, str, tuple[str, ...]]] = [
    ("warm-up", "#3a3a3a", ("warm-up", "order pending")),
    ("no live leg", "#6c7a89", ("fib: no live leg", "fib: leg already used")),
    ("leg has run (rule 10)", "#b9770e", ("fib: leg has run (100 % traded)",)),
    (
        "no M5 trend of its side", "#8e44ad",
        ("fib: no M5 trend of its side", "fib: M5 trend (H100 not above the M5 high)"),
    ),
    ("against the H4 trend", "#d63384", ("fib: against the H4 trend",)),
    ("against the M15 side", "#c2185b", ("fib: against the M15 side",)),
    ("no M15 event (rule 16)", "#7f8c8d", ("side: no M15 event",)),
    ("count (rule 4)", "#16a085", ("fib: count outside 3-5 and no M", "fib: no divergence")),
    ("trend run at the limit (rule 5)", "#c8b400", ("fib: trend run at the limit",)),
    (
        "no bounce / price not above the order price (rule 6)", "#2e86de",
        ("fib: no bounce above the order price", "fib: price not above the order price"),
    ),
    ("no target / R under the floor", "#48c9b0", ("fib: no target above the order price", "reward under 2R")),
    ("setup already played out", "#a2a84a", ("setup already played out",)),
    ("order price too far (rule 9)", "#ff8c69", ("fib: order price too far from price",)),
    ("ORDER", "#2ecc71", ("order written",)),
]  # fmt: skip
STYLE_OF = {reason: (label, colour) for label, colour, reasons in REASON_STYLE for reason in reasons}


def split_base(args: list[str]) -> tuple[dict[str, str], list[str]]:
    """Take ``market=``, ``set=`` and ``db=`` out of the ``name=value`` words: (the base choice, the rest)."""
    base = {"market": bot2e.MARKET, "set": "default", "db": str(bot2e.CONFIG_DB)}
    rest: list[str] = []
    for a in args:
        name, sep, text = a.partition("=")
        if sep and name in base:
            base[name] = text
        else:
            rest.append(a)
    return base, rest


def resolve_params(base: dict[str, str], overrides: dict[str, Any]) -> tuple[bot2e.Params, int]:
    """(the stored set with the overrides on top, the set's version). The market is checked first and a
    database error stops with its message (``bot2e.load_set``); an override that makes the set
    invalid stops."""
    params, version = bot2e.load_set(base["db"], base["market"], base["set"])  # the one read of the set
    return apply_overrides(params, overrides), version


def apply_overrides(params: bot2e.Params, overrides: dict[str, Any]) -> bot2e.Params:
    """The loaded ``params`` with the overrides on top, checked by ``Params``; an invalid result stops."""
    try:
        return replace(params, **overrides)
    except ValueError as e:
        raise SystemExit(f"bad override: {e}") from None


def config_line(base: dict[str, str], version: int, overrides: dict[str, Any]) -> str:
    """The set a drawing was made from and every override: ``config=XAUUSD/default@v21; overrides: none``."""
    shown = " ".join(f"{k}={bot2e.param_to_text(k, v)}" for k, v in overrides.items()) or "none"
    return f"{bot2e.config_label(base['market'], base['set'], version)}; overrides: {shown}"


def parse_overrides(args: list[str]) -> dict[str, Any]:
    """``name=value`` words to ``Params`` keyword arguments, read by ``bot2e.param_from_text``."""
    known = {f.name for f in fields(bot2e.Params)}
    out: dict[str, Any] = {}
    for a in args:
        name, sep, text = a.partition("=")
        if not sep or name not in known:
            raise SystemExit(f"unknown parameter override {a!r}")
        try:
            out[name] = bot2e.param_from_text(name, text)
        except ValueError as e:
            raise SystemExit(f"bad parameter override {a!r}: {e}") from None
    return out


def day_bounds(day: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The drawn stretch of a Thai day, in UTC: 06:00 to 23:59 (the last bar opens at 23:55)."""
    mid = pd.Timestamp(day, tz=TH)
    return (mid + pd.Timedelta(hours=6)).tz_convert("UTC"), (mid + pd.Timedelta(hours=24)).tz_convert("UTC")


def reason_style(reason: str) -> tuple[str, str]:
    """(legend label, colour) of the rule that stopped a bar."""
    return STYLE_OF.get(reason, (reason, "#999999"))


def trend_word(state_in_view: str, sign: int) -> str:
    """Rule 3's reading in real terms from the view's: a BUY's view "UP" is UP, a SELL's is DOWN."""
    if state_in_view == "none":
        return "none"
    return state_in_view if sign > 0 else ("DOWN" if state_in_view == "UP" else "UP")


def leg_from_log(key: str, leg_text: str) -> tuple[pd.Timestamp, float, pd.Timestamp, float]:
    """(0 % time, 0 % price, 100 % time, 100 % price), real prices, from a written setup's key
    (``SIDE|TF|time of the 0 %``, UTC) and the log's ``leg`` text. A trend leg: ``L0 p@dd/mm hh:mm
    H100[?] p@dd/mm hh:mm leg x`` (0 % = L0, the start; 100 % = H100, the end; ``?`` = a provisional end).
    A fade leg: ``fade S p@dd/mm hh:mm E p@dd/mm hh:mm run x`` (0 % = E, the run's end, the key's time;
    100 % = S, the run's start). The other end's time is read from the text (Thai, the year taken from the
    key's time)."""
    parts = key.split("|")
    trend = re.match(r"L0\s+(-?[\d.]+)@\S+ \S+ H100\??\s+(-?[\d.]+)@(\d\d/\d\d \d\d:\d\d)", leg_text)
    fade = re.match(r"fade S\s+(-?[\d.]+)@(\d\d/\d\d \d\d:\d\d) E\s+(-?[\d.]+)@", leg_text)
    if (trend is None and fade is None) or len(parts) != 3:
        raise ValueError(f"cannot read the leg from {key!r} / {leg_text!r}")
    t0 = pd.Timestamp(parts[2])
    year = t0.tz_convert(TH).year
    if trend is not None:
        t100 = thai_stamp(trend.group(3), year)
        if t100 < t0:  # across New Year
            t100 = thai_stamp(trend.group(3), year + 1)
        return t0, float(trend.group(1)), t100, float(trend.group(2))
    if fade is None:  # not reachable: the first test above passed
        raise ValueError(leg_text)
    t100 = thai_stamp(fade.group(2), year)  # S is before E
    if t100 > t0:
        t100 = thai_stamp(fade.group(2), year - 1)
    return t0, float(fade.group(3)), t100, float(fade.group(1))


def is_fade(leg_text: str) -> bool:
    """True when the log's ``leg`` text is a fade leg (rule 2)."""
    return leg_text.startswith("fade ")


def is_early(leg_text: str) -> bool:
    """True when the log's ``leg`` text marks a provisional H100 (``H100?``)."""
    return "H100?" in leg_text


def fib_prices(l0: float, h100: float, levels: tuple[float, ...] = FIB_LEVELS) -> dict[float, float]:
    """The drawn levels: ``l0 + x * (h100 - l0)``; for a SELL ``l0`` is the top and ``h100`` the low."""
    return {x: l0 + x * (h100 - l0) for x in levels}


def exit_bar(
    bars: pd.DataFrame, fill_time: pd.Timestamp, buy: bool, stop: float, target: float
) -> pd.Timestamp | None:
    """The open time of the bar a filled order exits on (rule 12: on the fill bar only the stop counts;
    later a bar touching both counts as the stop), or None while it is still open."""
    after = bars[bars.index >= fill_time]
    lows, highs = after["low"].to_numpy(dtype=float), after["high"].to_numpy(dtype=float)
    for i in range(len(after)):
        stop_hit = lows[i] <= stop if buy else highs[i] >= stop
        target_hit = i > 0 and (highs[i] >= target if buy else lows[i] <= target)
        if stop_hit or target_hit:
            return pd.Timestamp(after.index[i])
    return None


def thai_stamp(text: str, year: int) -> pd.Timestamp:
    """``dd/mm HH:MM`` (Thai, as ``score.py`` writes a fill) to a UTC timestamp."""
    return pd.Timestamp(f"{year}-{text[3:5]}-{text[:2]} {text[6:]}", tz=TH).tz_convert("UTC")


def walk_day(day: str, p: bot2e.Params, full: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Run the decision logic at every scheduled M5 close of ``day`` (BOT_RULES rule 0: all 288 times with
    ``windows`` off, the three windows with it on); nothing is written. A time outside the three windows is
    listed under the name "all day"."""
    window_rows: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    used: set[str] = set()
    for now in bot2e.day_times(day, p):
        nu = now.tz_convert("UTC")
        name = bot2e.window_of(nu) or "all day"
        frames = bot2e.cut(full, nu)
        res = bot2e.decide(frames, nu, p, frozenset(used))
        reason = res.log["reason"]
        if reason != "market closed":
            trend = "none"
            if reason != "warm-up":
                fi = bot2e.fib_inputs(frames, nu, p)
                trend = trend_word(bot2e.m5_state(fi.datas[0].m5_pv)[0], 1)
            window_rows.append({"close": nu, "window": name, "reason": reason, "trend": trend})
            if res.decision is not None:
                used.add(res.key)
                t0, l0, t100, h100 = leg_from_log(res.key, res.log["leg"])
                orders.append({"close": nu, "row": res.decision, "key": res.key, "log": res.log,
                               "t0": t0, "l0": l0, "t100": t100, "h100": h100})  # fmt: skip
    return {"rows": window_rows, "orders": orders}


def score_orders(orders: list[dict[str, Any]], p: bot2e.Params, m5: pd.DataFrame) -> None:
    """Add the scored ``fill`` / ``exit`` / ``why`` / R and the fill and exit bars to each order."""
    for o in orders:
        row = dict(o["row"])
        row["id"] = "X"
        got = score(row, m5, start_of(row, {}), p.spread)
        o["scored"] = got
        o["fill_time"] = o["exit_time"] = None
        if got["fill"]:
            o["fill_time"] = thai_stamp(got["fill"], o["close"].tz_convert(TH).year)
            if got["why"] in ("stop", "target"):
                o["exit_time"] = exit_bar(
                    m5, o["fill_time"], row["side"] == "BUY", float(row["stop"]), float(row["target"])
                )


def draw(
    day: str, p: bot2e.Params, overrides: dict[str, Any], full: dict[str, pd.DataFrame], config: str = ""
) -> Path:
    m5 = full["M5"]
    start, end = day_bounds(day)
    bars = m5[(m5.index >= start) & (m5.index < end)]
    walked = walk_day(day, p, full)
    orders = walked["orders"]
    score_orders(orders, p, m5)
    pos = {t: k for k, t in enumerate(bars.index)}

    def x_of(ts: pd.Timestamp) -> float:
        return float(np.clip(bars.index.searchsorted(ts), 0, len(bars) - 1))

    plt.style.use("dark_background")
    fig, (ax, s1, s2, s3) = plt.subplots(
        4,
        1,
        figsize=(20, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [14, 0.7, 0.7, 0.9], "hspace": 0.04},
    )
    for k, (o, h, lo, c) in enumerate(bars[["open", "high", "low", "close"]].to_numpy()):
        col = "#2ecc71" if c >= o else "#ff4d4d"
        ax.plot([k, k], [lo, h], color=col, lw=0.8)
        ax.add_patch(plt.Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.05), color=col))
    mid = pd.Timestamp(day, tz=TH)
    for name, a, b in bot2e.WINDOWS:
        x0 = x_of((mid + pd.Timedelta(minutes=a)).tz_convert("UTC"))
        x1 = x_of((mid + pd.Timedelta(minutes=b)).tz_convert("UTC"))
        for axis in (ax, s1, s2, s3):
            axis.axvspan(x0 - 0.5, x1 + 0.5, color="#4a6fa5", alpha=0.10 if axis is ax else 0.0, lw=0)
        ax.text(x0, 0.995, name, transform=ax.get_xaxis_transform(), color="#7aa2d6", fontsize=9, va="top")

    # strip 1: rule 16's H4 reading at every M5 bar of the day (green up, red down, grey not clear)
    h4_states: list[str] = []
    for t in bars.index:
        nu = t + bot2e.STEP["M5"]
        state, _ = bot2e.read_h4(bot2e.cut(full, nu), p)
        h4_states.append({"up": "BUY", "down": "SELL"}.get(state, "none"))
    for k, sd in enumerate(h4_states):
        s1.axvspan(k - 0.5, k + 0.5, color=SIDE_COLOUR[sd], lw=0)
    # strips 2 and 3: the window bars
    for r in walked["rows"]:
        bar = pos.get(r["close"] - bot2e.STEP["M5"])
        if bar is None:
            continue
        s2.axvspan(bar - 0.5, bar + 0.5, color=TREND_COLOUR[r["trend"]], lw=0)
        s3.axvspan(bar - 0.5, bar + 0.5, color=reason_style(r["reason"])[1], lw=0)

    fills = results = 0
    total_r = 0.0
    lo_all, hi_all = float(bars.low.min()), float(bars.high.max())
    for n, o in enumerate(orders, 1):
        row, got = o["row"], o["scored"]
        side, entry, stop, target = row["side"], float(row["entry"]), float(row["stop"]), float(row["target"])
        colour = SIDE_COLOUR[side]
        xs = x_of(o["close"] - bot2e.STEP["M5"])  # the decision bar
        for lvl, price in fib_prices(o["l0"], o["h100"]).items():
            x_start = x_of(o["t0"])
            ax.plot([x_start, len(bars) - 1], [price, price], color="#c39bff", lw=0.8, ls="--", alpha=0.8)
            word = (
                {0.0: "E 0 %", 1.0: "S 100 %"}
                if is_fade(o["log"]["leg"])
                else {0.0: "L0 0 %", 1.0: "H100? 100 %" if is_early(o["log"]["leg"]) else "H100 100 %"}.get(
                    lvl, f"{lvl * 100:.1f} %"
                )
            )
            ax.text(len(bars) - 0.5, price, f" {word} {price:.2f}", color="#c39bff", fontsize=8, va="center")
        planned = o["log"].get("r", "")
        for price, name, ls in ((entry, "order", "-"), (stop, "stop", ":"), (target, "target", ":")):
            ax.plot([xs, len(bars) - 1], [price, price], color=colour, lw=1.4, ls=ls)
            extra = f" R {planned}" if name == "target" else ""
            ax.text(xs, price, f"#{n} {side} {name} {price:.2f}{extra}", color=colour, fontsize=8,
                    va="bottom", ha="left")  # fmt: skip
        ax.plot([xs], [entry], marker="v" if side == "SELL" else "^", color=colour, ms=10)
        lo_all, hi_all = min(lo_all, stop, target), max(hi_all, stop, target)
        if o["fill_time"] is not None:
            fills += 1
            xf = x_of(o["fill_time"])
            note = f"#{n} fill {got['fill']}"
            if got["why"] in ("stop", "target"):
                results += 1
                total_r += float(got["r_net"])
                note += f", {got['why']} {got['exit']} R {got['r_net']}"
            else:
                note += ", open"
            inside = o["fill_time"] < end
            if inside:
                ax.plot([xf], [entry], marker="o", color="white", ms=8, mfc="none")
                ax.text(xf, entry, " " + note, color="white", fontsize=8, va="top")
            if o["exit_time"] is not None and o["exit_time"] < end:
                xe = x_of(o["exit_time"])
                price = target if got["why"] == "target" else float(got["exit"])
                ax.plot(
                    [xe], [price], marker="X", color="white" if got["why"] == "target" else "#ff4d4d", ms=9
                )
            print(f"  order #{n} {side} {entry} stop {stop} target {target} R {planned} -> {note}"
                  f"{'' if inside else ' (after the drawn day)'}")  # fmt: skip
        else:
            print(f"  order #{n} {side} {entry} stop {stop} target {target} R {planned} -> {got['why']}")

    span = hi_all - lo_all
    ax.set_ylim(lo_all - 0.03 * span, hi_all + 0.05 * span)
    ax.set_xlim(-1, len(bars) + 12)
    ax.yaxis.tick_right()
    ax.grid(alpha=0.15)
    ticks = [
        k for k, t in enumerate(bars.index) if t.tz_convert(TH).minute == 0 and t.tz_convert(TH).hour % 2 == 0
    ]
    s3.set_xticks(ticks)
    s3.set_xticklabels(
        [f"{bars.index[k].tz_convert(TH):%d/%m %H:%M}" for k in ticks], rotation=45, fontsize=9
    )
    for axis, label in ((s1, "H4 trend"), (s2, "M5 trend"), (s3, "stopped by")):
        axis.set_yticks([])
        axis.set_ylabel(label, fontsize=9, rotation=0, ha="right", va="center")
    n_rows = len(walked["rows"])
    keys = ["fib_tf", "fib_entry", "fib_stop", "fib_count", "fib_target"]
    keys += ["max_entry_frac", "m5_trend", "setup_days", "fib_lean", "min_r"]
    shown = ", ".join(f"{k}={getattr(p, k)}" for k in keys)
    counts = (f"{n_rows} window bars, {len(orders)} orders, {fills} filled, {results} resolved, "
              f"R {total_r:+.2f}")  # fmt: skip
    ax.set_title(
        f"XAUUSD M5  {day} (Thai)  |  {counts}\n{shown}   [no max_orders; used kept per run]\n{config}",
        fontsize=11,
    )
    seen = {r["reason"] for r in walked["rows"]}
    handles = [Patch(color=c, label=label) for label, c, reasons in REASON_STYLE if seen & set(reasons)]
    for label, key in (("BUY / UP", "BUY"), ("SELL / DOWN", "SELL"), ("none", "none")):
        handles.append(Patch(color=SIDE_COLOUR[key], label=label))
    fig.legend(
        handles=handles, loc="lower center", ncol=5, fontsize=9, frameon=False, bbox_to_anchor=(0.5, -0.04)
    )
    out = HERE.parent / "trades" / f"bot_read_{day}.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    print(f"{day}: {counts}")
    print(out)
    return out


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit("usage: bot_read_day.py YYYY-MM-DD [name=value ...]")
    base, rest = split_base(argv[1:])
    overrides = parse_overrides(rest)
    params, version = resolve_params(base, overrides)  # before any bar is loaded
    line = config_line(base, version, overrides)
    print(line)
    draw(argv[0], params, overrides, bot2e.load_frames(), line)


if __name__ == "__main__":
    main(sys.argv[1:])
