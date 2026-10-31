"""The bot's chart at one moment, as the owner sees it in MT5. Research only: nothing is traded or written.

Candles of M5 or M15 around a Thai moment (the bars after it faded: what the bot could not see),
MT5's ZigZag as known at the moment (fixed pivots joined in yellow, prices labelled; the moving last point
dashed), the Fibo the bot would draw on its latest leg of each side (rule 2; MT5's Fibo tool: lines from the
leg's start to the right edge at 0, 23.6, 38.2, 50, 61.8, 78.6, 100, 127.2, 161.8 %), and the bot's
decision in plain words.

Usage: bot_view.py 2026-10-07 07:00 [tf=M5|M15] [hours_before=8] [hours_after=8] [market=XAUUSD] [set=default]
       [db=PATH] [name=value ...]
       bot_view.py 2026-10-07 legs [tf=M5|M15] [...]   one image at every moment of the day's windows where
       a NEW leg first appears to the bot (a leg key not seen before that day), per side
``tf`` is also the bot's setup timeframe (``fib_tf``) unless ``fib_tf=`` is given. The moment is the M5 close
the bot decides at (07:00 = the bar that opened 06:55); the window test is off.
The base ``Params`` are the stored set ``market`` / ``set`` of the config database ``db`` (default
``data/bot_config.db``); ``name=value`` overrides apply on top, for drawing only. The text names the set, its
version and every override. The market is checked before any bar is loaded.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e  # noqa: E402
from eye.research import bot_read_day as day_tools  # noqa: E402

TH = bot2e.TH
LADDER = day_tools.FIB_LEVELS
LEG_COLOUR = {"BUY": "#4fc3f7", "SELL": "#ffa726"}
ZIGZAG_COLOUR = "#ffeb3b"
USAGE = (
    "usage: bot_view.py YYYY-MM-DD HH:MM|legs [tf=M5|M15] [hours_before=8] [hours_after=8] "
    "[market=XAUUSD] [set=default] [db=PATH] [name=value ...]"
)


def parse_args(argv: list[str]) -> dict[str, Any]:
    """``date HH:MM [tf=..] [hours_before=..] [hours_after=..] [Params overrides]`` to a dict."""
    if len(argv) < 2:
        raise SystemExit(USAGE)
    rest = {a.partition("=")[0]: a.partition("=")[2] for a in argv[2:] if "=" in a}
    tf = rest.pop("tf", "M5")
    if tf not in ("M5", "M15"):
        raise SystemExit(f"tf must be M5 or M15, got {tf!r}")
    before, after = float(rest.pop("hours_before", 8)), float(rest.pop("hours_after", 8))
    base, others = day_tools.split_base([f"{k}={v}" for k, v in rest.items()])
    overrides = day_tools.parse_overrides(others)
    return {
        "base": base,
        "date": argv[0],
        "hhmm": None if argv[1] == "legs" else argv[1],
        "tf": tf,
        "before": before,
        "after": after,
        "overrides": overrides,
    }


def config_of(args: dict[str, Any]) -> tuple[bot2e.Params, int, str]:
    """(the stored set with ``fib_tf`` = ``tf`` and the overrides on top, the set's version, the config line).
    A ``tf`` that changes the set's ``fib_tf`` is listed among the overrides in the line."""
    stored, version = bot2e.load_set(args["base"]["db"], args["base"]["market"], args["base"]["set"])
    shown = dict(args["overrides"])
    if "fib_tf" not in shown and args["tf"] != stored.fib_tf:
        shown = {"fib_tf": args["tf"], **shown}
    p = day_tools.apply_overrides(stored, {"fib_tf": args["tf"], **args["overrides"]})  # the set is read once
    return p, version, day_tools.config_line(args["base"], version, shown)


def params_of(args: dict[str, Any]) -> tuple[bot2e.Params, int]:
    """(the stored set, with ``fib_tf`` = ``tf`` and the overrides on top; the set's version)."""
    p, version, _ = config_of(args)
    return p, version


def view_bounds(
    date: str, hhmm: str, before: float, after: float
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:  # fmt: skip
    """(the moment, the chart's first bar time, the chart's end), UTC; ``hhmm`` is Thai."""
    now = pd.Timestamp(f"{date} {hhmm}", tz=TH).tz_convert("UTC")
    return now, now - pd.Timedelta(hours=before), now + pd.Timedelta(hours=after)


def ladder(l0: float, h100: float) -> dict[float, float]:
    """The Fibo lines of a leg (``l0`` = 0 %, ``h100`` = 100 %, for a SELL the mirror)."""
    return day_tools.fib_prices(l0, h100, LADDER)


def level_label(x: float, price: float) -> str:
    """MT5's label: ``61.8 (4155.20)``."""
    return f"{x * 100:g} ({price:.2f})"


def moving_point(df: pd.DataFrame, last_pivot: Any) -> tuple[int, float]:
    """MT5's moving last point: after the last fixed pivot, the highest high (if it was a LOW) or the lowest
    low (if it was a HIGH) of the closed bars; (position in ``df``, price)."""
    start = last_pivot.pivot_pos + 1
    if start >= len(df):
        return int(last_pivot.pivot_pos), float(last_pivot.price)
    if last_pivot.kind.value == "LOW":
        highs = df["high"].to_numpy(dtype=float)[start:]
        return start + int(highs.argmax()), float(highs.max())
    lows = df["low"].to_numpy(dtype=float)[start:]
    return start + int(lows.argmin()), float(lows.min())


def leg_geometry(
    d: Any, p: bot2e.Params
) -> tuple[pd.Timestamp, float, pd.Timestamp, float, bool, Any, bool] | None:
    """(0 % time, 0 % price, 100 % time, 100 % price, early, key, fade) in real prices of a side's latest
    leg (rule 2; a trend leg: 0 % = L0, 100 % = H100, ``early`` = H100 is provisional; a fade leg: 0 % = E,
    the run's end, 100 % = S, its start), or None - exactly ``bot2e.find_leg`` (the setup look included).
    ``key`` is what makes the leg the same leg: the 0 % time (rule 2)."""
    found = bot2e.find_leg(d, p)
    if found is None:
        return None
    s = d.sign
    t0, t100 = pd.Timestamp(d.times[found.l0.pos]), pd.Timestamp(d.times[found.h100.pos])
    key: Any = t0  # one leg per start (rule 2): an early leg and the fixed leg after it share it
    return (
        t0,
        bot2e._real(s, found.l0.price),
        t100,
        bot2e._real(s, found.h100.price),
        found.early,
        key,
        found.fade,
    )


def side_sentence(side: str, geometry: Any, outcome: Any, trend: str) -> str:
    """One side in plain words: the leg or why none, the M5 trend it needs, the order or why none."""
    need = "UP" if side == "BUY" else "DOWN"
    if geometry is None:
        leg = "no leg (" + day_tools.reason_style(outcome.reason)[0] + ")"
    else:
        t0, p0, t100, p100, early = geometry[:5]
        if len(geometry) > 6 and geometry[6]:
            leg = (
                f"fade leg S {p100:.2f} ({t100.tz_convert(TH):%d/%m %H:%M}) -> "
                f"E {p0:.2f} ({t0.tz_convert(TH):%d/%m %H:%M})"
            )
        else:
            leg = (
                f"leg L0 {p0:.2f} ({t0.tz_convert(TH):%d/%m %H:%M}) -> "
                f"H100{'?' if early else ''} {p100:.2f} ({t100.tz_convert(TH):%d/%m %H:%M})"
            )
    if outcome.setup is not None:
        s = outcome.setup
        verdict = f"ORDER {s.order:.2f}, SL {s.stop:.2f}, TP {s.target:.2f}, R {s.r:.2f}"
    else:
        verdict = "no order: " + day_tools.reason_style(outcome.reason)[0]
    return f"{side}: {leg}; M5 trend {trend} (a {side} needs {need}); {verdict}"


def retest_sentence(side: str, outcome: Any) -> str:
    """Rule 17 in plain words: the break and retest of the fixed leg's end, as ordered or why not."""
    if outcome.setup is not None:
        s = outcome.setup
        verdict = f"ORDER limit {s.order:.2f}, SL {s.stop:.2f}, TP {s.target:.2f} ({s.step}), R {s.r:.2f}"
    else:
        verdict = "no order: " + day_tools.reason_style(outcome.reason)[0]
    return f"{side}: the end of the leg has just been broken - break and retest: {verdict}"


def first_seen(events: Any) -> list[tuple[Any, str, Any]]:
    """From ``(moment, side, key)`` in time order, the events whose ``(side, key)`` was not seen before."""
    seen: set[tuple[str, Any]] = set()
    out: list[tuple[Any, str, Any]] = []
    for moment, side, key in events:
        if (side, key) not in seen:
            seen.add((side, key))
            out.append((moment, side, key))
    return out


def new_leg_moments(
    date: str, p: bot2e.Params, full: dict[str, pd.DataFrame]
) -> list[tuple[pd.Timestamp, str, Any]]:
    """Every window M5 close of the Thai day at which a side's leg (L0 time, H100 time) is new that day."""
    mid = pd.Timestamp(date, tz=TH)
    events: list[tuple[pd.Timestamp, str, Any]] = []
    for _, a, b in bot2e.WINDOWS:
        now = mid + pd.Timedelta(minutes=a)
        while now <= mid + pd.Timedelta(minutes=b):
            nu = now.tz_convert("UTC")
            frames = bot2e.cut(full, nu)
            full_frames = all(len(frames[t]) >= bot2e.FIB_BARS for t in bot2e.TIMEFRAMES)
            if full_frames and frames["M5"].index[-1] + bot2e.STEP["M5"] == nu:
                for d in bot2e.fib_inputs(frames, nu, p).datas:
                    geo = leg_geometry(d, p)
                    if geo is not None:
                        events.append((nu, d.side, geo[5]))
            now += pd.Timedelta(minutes=5)
    return first_seen(events)


def summary_line(full: dict[str, pd.DataFrame], p: bot2e.Params, nu: pd.Timestamp, side: str) -> str:
    """One line for the list: time, side, L0, H100 and the bot's decision at that moment."""
    frames = bot2e.cut(full, nu)
    res = bot2e.decide(frames, nu, p, windowed=False)
    d = next(x for x in bot2e.fib_inputs(frames, nu, p).datas if x.side == side)
    geo = leg_geometry(d, p)
    if geo is None:
        raise ValueError(f"no {side} leg at {nu}")
    out = bot2e.analyse_leg(d, p)
    if res.decision is not None:
        r = res.decision
        decision = f"ORDER {r['side']} {r['entry']} SL {r['stop']} TP {r['target']}"
    else:
        decision = "no order: " + day_tools.reason_style(res.log["reason"])[0]
    own = "ORDER on this leg" if out.setup is not None else day_tools.reason_style(out.reason)[0]
    return (
        f"{nu.tz_convert(TH):%H:%M}  {side:4}  {'E' if geo[6] else 'L0'} {geo[1]:.2f} "
        f"({geo[0].tz_convert(TH):%d/%m %H:%M})  "
        f"{'S' if geo[6] else 'H100'}{'?' if geo[4] else ''} {geo[3]:.2f} "
        f"({geo[2].tz_convert(TH):%d/%m %H:%M})  "
        f"this leg: {own}; bot: {decision}"
    )


def legs_mode(args: dict[str, Any]) -> list[Path]:
    resolved = config_of(args)  # before any bar is loaded; one snapshot of the set for every image
    p = resolved[0]
    full = bot2e.load_frames()
    paths: list[Path] = []
    rows = new_leg_moments(args["date"], p, full)
    print(f"{len(rows)} new legs on {args['date']} ({args['tf']}):")
    for nu, side, _ in rows:
        one = {**args, "hhmm": f"{nu.tz_convert(TH):%H:%M}"}
        paths.append(draw(one, full, side, resolved=resolved))
    print()
    print(f"New legs of {args['date']} ({args['tf']}), Thai time of the moment:")
    for (nu, side, _), path in zip(rows, paths, strict=True):
        print("  " + summary_line(full, p, nu, side))
        print(f"      {path}")
    return paths


def draw(
    args: dict[str, Any],
    full: dict[str, pd.DataFrame] | None = None,
    only_side: str | None = None,
    resolved: tuple[bot2e.Params, int, str] | None = None,
) -> Path:
    """One image. ``resolved`` is the (params, version, config line) a legs run took once; alone, the set is
    read here."""
    p, _, config = resolved if resolved is not None else config_of(args)  # market checked before bars load
    full = full if full is not None else bot2e.load_frames()
    tf = args["tf"]
    now, start, end = view_bounds(args["date"], args["hhmm"], args["before"], args["after"])
    frames = bot2e.cut(full, now)
    df_all = full[tf]
    bars = df_all[(df_all.index >= start) & (df_all.index < end)]
    closed = bars.index + bot2e.STEP[tf] <= now
    n_closed = int(closed.sum())

    res = bot2e.decide(frames, now, p, windowed=False)
    reason = res.log["reason"]
    fi = bot2e.fib_inputs(frames, now, p) if reason not in ("warm-up", "market closed") else None
    # the ZigZag as known at the moment, on the bot's own frame of this timeframe
    tail = frames[tf].tail(bot2e.FIB_BARS)
    all_piv = bot2e._zigzag(tail)
    piv = [q for q in all_piv if tail.index[q.pivot_pos] >= start]  # the pivots in the drawn stretch

    def x_of(ts: pd.Timestamp) -> float:
        return float(bars.index.searchsorted(ts))

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(18, 9))
    for k, (o, h, lo, c) in enumerate(bars[["open", "high", "low", "close"]].to_numpy()):
        col = "#2ecc71" if c >= o else "#ff4d4d"
        a = 1.0 if closed[k] else 0.3
        ax.plot([k, k], [lo, h], color=col, lw=0.8, alpha=a)
        ax.add_patch(plt.Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.05), color=col, alpha=a))
    xs = [x_of(pd.Timestamp(tail.index[q.pivot_pos])) for q in piv]
    ax.plot(xs, [q.price for q in piv], color=ZIGZAG_COLOUR, lw=1.3)
    for q, x in zip(piv, xs, strict=True):
        if 0 <= x < len(bars):
            ax.text(x, q.price, f"{q.price:.2f}", color=ZIGZAG_COLOUR, fontsize=8, ha="center",
                    va="bottom" if q.kind.value == "HIGH" else "top")  # fmt: skip
    if all_piv:
        pos, price = moving_point(tail, all_piv[-1])
        x_last = x_of(pd.Timestamp(tail.index[all_piv[-1].pivot_pos]))
        x_end = x_of(pd.Timestamp(tail.index[pos]))
        ax.plot([x_last, x_end], [all_piv[-1].price, price], color=ZIGZAG_COLOUR, lw=1.3, ls="--")
    ax.axvline(n_closed - 0.5, color="white", lw=1, ls=":")  # the moment: bars to its right are not seen
    ax.text(n_closed - 0.5, 1.0, f" now {now.tz_convert(TH):%d/%m %H:%M}", transform=ax.get_xaxis_transform(),
            color="white", fontsize=10, va="bottom")  # fmt: skip

    lo_all, hi_all = float(bars.low.min()), float(bars.high.max())
    span = hi_all - lo_all
    boxes: list[tuple[str, str]] = []
    lines = [
        f"Bot at {now.tz_convert(TH):%d/%m/%Y %H:%M} Thai, {tf} chart, fib_entry {p.fib_entry}, "
        f"m5_trend {p.m5_trend}, fib_lean {p.fib_lean}",
        config,
    ]
    if fi is None:
        lines.append(f"No decision: {reason}.")
    else:
        lines.append(fi.h4_text)
        for d in fi.datas:
            out = bot2e.analyse_leg(d, p)
            geo = leg_geometry(d, p)
            trend = day_tools.trend_word(bot2e.m5_state(d.m5_pv)[0], d.sign)
            lines.append(side_sentence(d.side, geo, out, trend))
            retest = bot2e.analyse_retest(d, p)
            if retest is not None:
                lines.append(retest_sentence(d.side, retest))
            if geo is None:
                boxes.append((d.side, f"{d.side}: no leg - {day_tools.reason_style(out.reason)[0]}"))
                continue
            if only_side is not None and d.side != only_side:
                continue  # a leg image draws that leg's Fibo only; the text still reads both sides
            t0, p0, t100, p100, early, _, fade = geo
            x_start = max(0.0, x_of(min(t0, t100)))
            low_first = p0 < p100  # a BUY leg starts at a low and ends at a high; a SELL leg the other way
            for when, price, tag in (
                (t0, p0, f"{'E' if fade else 'L0'} {p0:.2f}"),
                (t100, p100, f"{'S' if fade else 'H100'}{'?' if early else ''} {p100:.2f}"),
            ):
                ax.text(x_of(when), price, tag, color=LEG_COLOUR[d.side], fontsize=9, fontweight="bold",
                        va="top" if (price == p0) == low_first else "bottom", ha="center")  # fmt: skip
            for x, price in ladder(p0, p100).items():
                if lo_all - span <= price <= hi_all + span:
                    lo_all, hi_all = min(lo_all, price), max(hi_all, price)
                ax.plot([x_start, len(bars)], [price, price], color=LEG_COLOUR[d.side], lw=0.8, alpha=0.9)
                ax.text(len(bars) + 0.3, price, level_label(x, price), color=LEG_COLOUR[d.side], fontsize=8,
                        va="center")  # fmt: skip
        if res.decision is not None:
            r = res.decision
            lines.append(
                f"Decision: {r['side']} order at {r['entry']}, SL {r['stop']}, TP {r['target']}, "
                f"R {res.log['r']}."
            )
        else:
            lines.append(f"Decision: no order ({day_tools.reason_style(reason)[0]}).")
    ax.text(0.01, 0.99, "\n".join(lines), transform=ax.transAxes, fontsize=9, va="top", ha="left",
            bbox={"facecolor": "black", "alpha": 0.8, "edgecolor": "#888888"})  # fmt: skip
    for i, (side, text) in enumerate(boxes):
        edge = {"facecolor": "black", "alpha": 0.8, "edgecolor": LEG_COLOUR[side]}
        ax.text(0.01, 0.02 + 0.05 * i, text, transform=ax.transAxes, fontsize=9, va="bottom",
                color=LEG_COLOUR[side], bbox=edge)  # fmt: skip
    pad = 0.05 * (hi_all - lo_all)
    ax.set_ylim(lo_all - pad, hi_all + pad)
    ax.set_xlim(-1, len(bars) + 14)
    ax.yaxis.tick_right()
    ax.grid(alpha=0.15)
    ticks = [k for k, t in enumerate(bars.index) if t.tz_convert(TH).minute == 0]
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        [f"{bars.index[k].tz_convert(TH):%d/%m %H:%M}" for k in ticks], rotation=45, fontsize=9
    )
    ax.set_title(f"XAUUSD {tf}  {args['date']} {args['hhmm']} (Thai)", fontsize=12)
    stamp = args["hhmm"].replace(":", "")
    tail_name = f"_{only_side}" if only_side else ""
    out_path = HERE.parent / "trades" / f"bot_view_{args['date']}_{stamp}_{tf}{tail_name}.png"
    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=90, bbox_inches="tight")
    plt.close(fig)
    if only_side:
        print(f"--- new {only_side} leg at {args['hhmm']} ---")
    print("\n".join(lines))
    for _, t in boxes:
        print(t)
    print(out_path)
    return out_path


if __name__ == "__main__":
    parsed = parse_args(sys.argv[1:])
    if parsed["hhmm"] is None:
        legs_mode(parsed)
    else:
        draw(parsed)
