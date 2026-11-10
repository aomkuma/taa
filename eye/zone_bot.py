"""The run-zone setup (eye/ZONE_RULES.md), the simulation driver (command line, outputs, charts).

The logic - the step, the grids, the visits, the setups, the numbers - is ``app/zone/core.py`` (ZONE_LIVE L0),
shared with the real-time runner; its names are re-exported here, so ``eye.zone_bot.<name>`` still works. Pure
functions over stored bars - a simulation, no orders anywhere.

Independent of the Fibonacci bot (rule 0): nothing is imported from ``bot2e``, ``bot_config`` or
``bot_research``.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.zone.core import (  # noqa: E402, F401
    MARKET_DIRS,
    PER_H,
    STATE_FRAMES,
    TH,
    Bars,
    BarValues,
    ExecBars,
    Fill,
    Grid,
    H1Reader,
    Months,
    Outcome,
    PivotSet,
    Position,
    RunResult,
    Setup,
    SetupLife,
    SetupPlan,
    Visit,
    ZoneError,
    _ns,
    apply_rules,
    bar_values,
    build_grids,
    build_state,
    check_frame,
    cluster_anchor,
    cut_bars,
    find_visits,
    fixed_pivots,
    frame_trends,
    grid_index,
    grids_from_events,
    h1_indicators,
    is_trend,
    load_bars,
    month_remake_needed,
    month_steps,
    new_grid_needed,
    off_lines,
    plan_setup,
    positions_of,
    run_zone,
    setup_r,
    sideways_share,
    simulate_setup,
    skip_abnormal,
    skip_busy,
    skip_momentum,
    skip_trend,
    start_life,
    step_setup,
    summary_stats,
    thai,
    traded,
    visits_at_bar,
    warmup_index,
    weekly_atr,
)
from app.zone.params import (  # noqa: E402
    DEFAULT_DB,
    FIELD_NAMES,
    ConfigError,
    ZoneParams,
    load_params,
    param_to_text,
)


def position_rows(outcomes: list[Outcome], ex: ExecBars) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for k, s in enumerate(traded(outcomes)):
        for p in positions_of(s):
            rows.append(
                {
                    "setup": k + 1,
                    "visit": thai(s.visit.time),
                    "pos": p.fill.name,
                    "side": s.visit.side,
                    "line": s.visit.line,
                    "S": s.visit.step,
                    "p1": s.p1,
                    "p2": s.p2,
                    "entry_t": thai(ex.close_time.iloc[p.fill.j]),
                    "entry": p.fill.price,
                    "sl": s.sl,
                    "tp": s.tp,
                    "be_sl": s.be_sl,
                    "be_time": thai(ex.close_time.iloc[s.be_j]) if s.be_j is not None else "",
                    "exit_t": thai(ex.close_time.iloc[s.exit_j if s.exit_j is not None else 0]),
                    "exit": s.exit_price,
                    "how": s.how,
                    "risk": p.risk,
                    "pnl": p.pnl,
                }
            )
    return rows


def visit_rows(outcomes: list[Outcome]) -> list[dict[str, Any]]:
    rows = []
    for o in outcomes:
        v = o.visit
        rows.append(
            {
                "visit": thai(v.time),
                "side": v.side,
                "line": v.line,
                "S": v.step,
                "anchor": v.anchor,
                "outcome": o.reason,
                "mom_body": v.mom_body,
                "mom_median": v.mom_median,
                "mom_run": v.mom_run,
                "ema_dist": v.ema_dist,
                "atr": v.atr,
                "trend_D1": v.trends[0],
                "trend_H4": v.trends[1],
                "trend_H1": v.trends[2],
                "trend_M15": v.trends[3],
                "share": v.share,
            }
        )
    return rows


def summary_rows(
    zone: str, params: ZoneParams, start: pd.Timestamp, end: pd.Timestamp, stats: dict[str, Any]
) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = [("zone", zone)]
    rows += [(f"param.{n}", param_to_text(n, getattr(params, n))) for n in FIELD_NAMES]
    rows += [("start", thai(start)), ("end", thai(end))]
    for k in (
        "setups",
        "open",
        "be_exits",
        "pending",
        "r_per_setup",
        "tp_share",
        "usd",
        "drawdown",
        "months",
        "negative_months",
    ):
        rows.append((k, stats[k]))
    rows += [(f"outcome.{k}", v) for k, v in sorted(stats["reasons"].items())]
    rows += [
        (f"year.{y}", f"setups={n} R={r:.6f} usd={u:.6f}")
        for y, (n, r, u) in sorted(stats["by_year"].items())
    ]
    rows += [(f"month.{m}", f"{u:.6f}") for m, u in sorted(stats["by_month"].items())]
    return rows


POSITION_COLUMNS = [
    "setup", "visit", "pos", "side", "line", "S", "p1", "p2", "entry_t", "entry", "sl", "tp",
    "be_sl", "be_time", "exit_t", "exit", "how", "risk", "pnl",
]  # fmt: skip
VISIT_COLUMNS = [
    "visit", "side", "line", "S", "anchor", "outcome", "mom_body", "mom_median", "mom_run", "ema_dist", "atr",
    "trend_D1", "trend_H4", "trend_H1", "trend_M15", "share",
]  # fmt: skip
GRID_COLUMNS = ["start", "anchor", "step", "cause"]


def summary_text(v: Any) -> str:
    """A summary value as text: floats to 6 decimals, everything else as it is."""
    if isinstance(v, (float, np.floating)):
        return f"{float(v):.6f}"
    return str(v)


def write_outputs(
    out_dir: Path, zone: str, params: ZoneParams, start: pd.Timestamp, end: pd.Timestamp, res: RunResult
) -> dict[str, Any]:
    """Rule 11: positions, visits, grids and summary CSVs (numbers to 6 decimals, times in Thai ISO)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%.6f"
    # explicit columns: an empty run still writes its header
    pos = pd.DataFrame(position_rows(res.outcomes, res.ex), columns=POSITION_COLUMNS)
    pos.to_csv(out_dir / "positions.csv", index=False, float_format=fmt)
    vis = pd.DataFrame(visit_rows(res.outcomes), columns=VISIT_COLUMNS)
    vis.to_csv(out_dir / "visits.csv", index=False, float_format=fmt)
    grid_rows = [
        {"start": thai(g.start), "anchor": g.anchor, "step": g.step, "cause": g.cause} for g in res.grids
    ]
    pd.DataFrame(grid_rows, columns=GRID_COLUMNS).to_csv(out_dir / "grids.csv", index=False, float_format=fmt)
    stats = summary_stats(res.outcomes)
    rows = [(n, summary_text(v)) for n, v in summary_rows(zone, params, start, end, stats)]
    pd.DataFrame(rows, columns=["name", "value"]).to_csv(out_dir / "summary.csv", index=False)
    return stats


# --- rule 11: the charts ------------------------------------------------------------------------------------


def chart_name(n: int, s: Setup, usd: float) -> str:
    """``<nn>_<win|loss|open>_<YYYYMMDD>.png`` (the date is the visit's, Thai)."""
    kind = "open" if s.how == "open" else ("win" if usd > 0 else "loss")
    return f"{n:02d}_{kind}_{s.visit.time.tz_convert(TH):%Y%m%d}.png"


def chart_window(df: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.DataFrame:
    """The bars of a frame that open at or after ``t0`` and close at or before ``t1``."""
    return df[(df["open_time"] >= t0) & (df["close_time"] <= t1)]


def draw_chart(
    path: Path,
    s: Setup,
    grid: Grid,
    bars: Bars,
    params: ZoneParams,
    usd: float,
    candle_xs: list[np.ndarray] | None = None,
    on_figure: Callable[[Any], None] | None = None,
) -> list[float]:
    """One setup, two panels (H1 from 6 days before the first fill to 1 day after the exit; ``exec_tf`` from
    10 hours before to 3 hours after), drawn as MT5 does: on a bar-index axis, candles side by side in order,
    market closures not drawn as empty space, the tick labels the bars' Thai times. Every grid line in view,
    the setup's line thick, fills marked and labelled at their bars, the SL and TP drawn at least a sixth of
    the panel wide with their distances, the exit marked.
    Returns each SL / TP segment's drawn length as a share of its panel's width (read from the artists);
    ``candle_xs``, if given, collects each panel's candle x positions; ``on_figure``, if given, is called with
    the finished figure just before it is saved (a hook for tests to read the drawn artists)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ex = bars.frame(params.exec_tf)
    v = s.visit
    first = ex["close_time"].iloc[s.fills[0].j]
    last = ex["close_time"].iloc[s.exit_j if s.exit_j is not None else s.end_j]
    spans = (
        (bars.h1, first - pd.Timedelta(days=6), last + pd.Timedelta(days=1), "H1"),
        (ex, first - pd.Timedelta(hours=10), last + pd.Timedelta(hours=3), params.exec_tf),
    )
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    fractions: list[float] = []
    for ax, (df, t0, t1, label) in zip(axes, spans, strict=True):
        w = chart_window(df, t0, t1)
        n = len(w)
        xs = np.arange(n)  # the bar index: consecutive, whatever the clock gap between bars
        open_ns = _ns(w["open_time"])

        def pos_of(exec_row: int, open_ns: np.ndarray = open_ns, n: int = n) -> int:
            """The panel position of the bar that contains the exec bar ``exec_row``."""
            t = int(ex["open_time"].iloc[exec_row].value)
            return int(min(max(int(np.searchsorted(open_ns, t, side="right")) - 1, 0), n - 1))

        colors = np.where((w["close"] >= w["open"]).to_numpy(), "#2a7a3b", "#b3302a")
        ax.vlines(xs, w["low"], w["high"], color=colors, linewidth=0.8)
        body = (w["close"] - w["open"]).abs().clip(lower=0.01)
        ax.bar(xs, body, bottom=np.minimum(w["open"], w["close"]), width=0.7, color=colors)
        if candle_xs is not None:
            candle_xs.append(xs)
        prices = [float(w["low"].min()), float(w["high"].max()), s.sl, s.tp, v.line]
        lo, hi = min(prices), max(prices)
        pad = (hi - lo) * 0.04
        ax.set_ylim(lo - pad, hi + pad)
        k0 = math.ceil((lo - pad - grid.anchor) / grid.step)
        k1 = math.floor((hi + pad - grid.anchor) / grid.step)
        for k in range(k0, k1 + 1):
            ln = round(grid.anchor + k * grid.step, 2)
            thick = ln == v.line
            ax.axhline(ln, color="#555555", linewidth=2.6 if thick else 0.6, alpha=0.9 if thick else 0.5)
        left = -0.5
        seg_start = pos_of(s.fills[0].j)
        exit_pos = pos_of(s.exit_j if s.exit_j is not None else s.end_j)
        # the panel's right edge, final: the last bar, the exit, and far enough that the SL / TP segment (from
        # the first fill's bar to that edge) is at least a sixth of the panel as drawn
        right = max(n - 0.5, exit_pos + 0.5, seg_start + max(seg_start - left, 0.0) / 4)
        segments = []
        for name, px, col in (("SL", s.sl, "#b3302a"), ("TP", s.tp, "#2a7a3b")):
            segments.append(ax.hlines(px, seg_start, right, color=col, linewidth=2.2))
            ax.text(
                seg_start,
                px,
                f" {name} {px:.2f} ({abs(px - v.line):.2f} from the line)",
                color=col,
                fontsize=8,
            )
        if s.be_sl is not None and s.be_j is not None and s.be_j + 1 < len(ex):
            bx = pos_of(s.be_j + 1)  # the break-even SL works from the bar after its trigger
            ax.hlines(s.be_sl, bx, right, color="#b3302a", linewidth=1.8, linestyle="--")
            ax.text(
                bx,
                s.be_sl,
                f" BE SL {s.be_sl:.2f} ({abs(s.be_sl - v.line):.2f} from the line)",
                color="#b3302a",
                fontsize=8,
                va="top",
            )
        for f in s.fills:
            fx = pos_of(f.j)
            ax.plot([fx], [f.price], marker="^" if v.sgn > 0 else "v", color="#1f4e9c", markersize=9)
            ax.text(fx, f.price, f" {f.name} {f.price:.2f}", color="#1f4e9c", fontsize=8, va="top")
        if s.exit_j is not None and s.exit_price is not None:
            ax.plot([exit_pos], [s.exit_price], marker="X", color="black", markersize=11)
            ax.text(exit_pos, s.exit_price, f" exit {s.how} {s.exit_price:.2f}", fontsize=8, va="bottom")
        ax.set_xlim(left, right)
        ticks = np.unique(np.linspace(0, n - 1, min(8, n)).round().astype(int))
        ax.set_xticks(ticks)
        ax.set_xticklabels(
            [w["open_time"].iloc[int(i)].tz_convert(TH).strftime("%m-%d %H:%M") for i in ticks],
            rotation=20,
            ha="right",
        )
        lo_x, hi_x = ax.get_xlim()
        for lc in segments:  # read back from the drawn artists
            (x0, _), (x1, _) = lc.get_segments()[0]
            fractions.append((x1 - x0) / (hi_x - lo_x))
        ax.set_ylabel(label)
        ax.tick_params(axis="x", labelsize=7)
    fills = ", ".join(f"{f.name} {f.price:.2f}" for f in s.fills)
    fig.suptitle(
        f"{v.side} line {v.line:.2f} step {v.step:.2f} | fills {fills} | SL {s.sl:.2f} TP {s.tp:.2f} | "
        f"{s.how} {usd:+.2f} USD | visit {thai(v.time)}",
        fontsize=10,
    )
    fig.tight_layout()
    if on_figure is not None:
        on_figure(fig)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=80)
    plt.close(fig)
    return fractions


def write_charts(
    out_dir: Path, res: RunResult, bars: Bars, params: ZoneParams, fractions: list[float] | None = None
) -> list[Path]:
    """One PNG per traded setup (a setup with no fill has nothing to draw). The PNGs of an earlier run in
    ``<out>/charts`` are removed first (nothing else in the folder is touched). ``fractions``, if given,
    collects every SL / TP segment's drawn share of its panel's width."""
    charts = out_dir / "charts"
    if charts.is_dir():
        for old in charts.glob("*.png"):
            old.unlink()
    gstart = grid_index(res.grids)
    paths = []
    for n, s in enumerate(traded(res.outcomes), start=1):
        g = res.grids[int(np.searchsorted(gstart, s.visit.time.value, side="right")) - 1]
        usd = sum(p.pnl for p in positions_of(s))
        path = charts / chart_name(n, s, usd)
        shares = draw_chart(path, s, g, bars, params, usd)
        if fractions is not None:
            fractions.extend(shares)
        paths.append(path)
    return paths


# --- the command line ---------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The run-zone setup on stored bars (eye/ZONE_RULES.md).")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--market", default="XAUUSD")
    ap.add_argument("--set", dest="set_name", default="default")
    ap.add_argument("--start", default="2023-10-01", help="Thai date")
    ap.add_argument("--end", default=None, help="Thai date, exclusive (default: the last stored H1 bar)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-charts", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.market not in MARKET_DIRS:
            raise ZoneError(f"no bars for {a.market}")
        params, version = load_params(a.db, a.market, a.set_name)
        bars = load_bars(a.market)
        start = pd.Timestamp(a.start, tz=TH)
        end = pd.Timestamp(a.end, tz=TH) if a.end else bars.h1["close_time"].iloc[-1]
        zone = f"zone={a.market}/{a.set_name}@v{version}"
        out_dir = Path(a.out) if a.out else ROOT / "eye" / "research" / "zone" / a.market / a.set_name
        res = run_zone(bars, params, start, end)
        stats = write_outputs(out_dir, zone, params, start, end, res)
        n_charts = 0 if a.no_charts else len(write_charts(out_dir, res, bars, params))
    except (ConfigError, ZoneError) as e:
        print(f"zone_bot: {e}", file=sys.stderr)
        return 1
    print(
        f"{zone}: setups {stats['setups']}, {stats['r_per_setup']:+.3f} R a setup, "
        f"TP {stats['tp_share']:.0%}, "
        f"USD {stats['usd']:+.1f}, drawdown {stats['drawdown']:.1f}, open {stats['open']}, "
        f"pending {stats['pending']}, charts {n_charts}; skips {stats['reasons']}; out {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
