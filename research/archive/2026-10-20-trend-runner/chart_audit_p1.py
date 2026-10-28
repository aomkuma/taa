"""Draw deterministic P1 SPLIT winners/losers as dependency-free SVG charts."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd
from tr1.bars import aggregate, atr, confirmed_fractals
from tr1.boundaries import P1
from tr1.data import load_m1
from tr1.structure import structure_events

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
CHART_DIR = HERE / "charts_p1"
PANEL_WIDTH = 760
PANEL_HEIGHT = 275


def deterministic_six(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values(["r", "entry_time", "entry_id"]).reset_index(drop=True)
    indexes = np.rint(np.linspace(0, len(ordered) - 1, 6)).astype(int)
    return ordered.iloc[indexes].copy()


def line(x1: float, y1: float, x2: float, y2: float, color: str, width: float = 1.0) -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{width}" />'
    )


def text(x: float, y: float, value: object, size: int = 11, color: str = "#111827") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Segoe UI, sans-serif" font-size="{size}" '
        f'fill="{color}">{html.escape(str(value))}</text>'
    )


def panel_svg(
    trade: pd.Series,
    m1: pd.DataFrame,
    events: list[object],
    *,
    x_offset: int = 0,
    y_offset: int = 0,
) -> str:
    entry_time = pd.Timestamp(trade["entry_time"])
    exit_time = pd.Timestamp(trade["exit_time"])
    start = entry_time - pd.Timedelta(minutes=30)
    end = exit_time + pd.Timedelta(minutes=10)
    view = m1.loc[(m1.index >= start) & (m1.index <= end)]
    times = np.array([pd.Timestamp(moment).timestamp() for moment in view.index], dtype=float)
    all_prices = np.r_[
        view["low"].to_numpy(float),
        view["high"].to_numpy(float),
        [trade["entry"], trade["initial_stop"], trade["exit_price"]],
    ]
    low = float(np.nanmin(all_prices))
    high = float(np.nanmax(all_prices))
    pad = max((high - low) * 0.08, 0.2)
    low -= pad
    high += pad
    left, right, top, bottom = 48, PANEL_WIDTH - 12, 40, PANEL_HEIGHT - 28
    time_low = min(float(times[0]), entry_time.timestamp())
    time_high = max(float(times[-1] + 60), exit_time.timestamp())

    def x(moment: pd.Timestamp | float) -> float:
        value = moment.timestamp() if isinstance(moment, pd.Timestamp) else float(moment)
        return x_offset + left + (value - time_low) / (time_high - time_low) * (right - left)

    def y(price: float) -> float:
        return y_offset + bottom - (price - low) / (high - low) * (bottom - top)

    items = [
        f'<rect x="{x_offset}" y="{y_offset}" width="{PANEL_WIDTH}" height="{PANEL_HEIGHT}" '
        'fill="#ffffff" stroke="#d1d5db" />'
    ]
    for fraction in (0.0, 0.5, 1.0):
        price = low + fraction * (high - low)
        items.append(line(x_offset + left, y(price), x_offset + right, y(price), "#e5e7eb"))
        items.append(text(x_offset + 2, y(price) + 4, f"{price:.1f}", 9, "#6b7280"))
    previous: tuple[float, float] | None = None
    for moment, row in view.iterrows():
        x_now = x(pd.Timestamp(moment) + pd.Timedelta(seconds=30))
        items.append(line(x_now, y(float(row["low"])), x_now, y(float(row["high"])), "#9ca3af", 0.7))
        current = (x_now, y(float(row["close"])))
        if previous is not None:
            items.append(line(previous[0], previous[1], current[0], current[1], "#2563eb", 1.1))
        previous = current
    entry = float(trade["entry"])
    risk = float(trade["initial_risk"])
    side = int(trade["side"])
    levels = [
        (entry, "#111827", "entry"),
        (float(trade["initial_stop"]), "#dc2626", "initial stop"),
        (entry + side * risk, "#f59e0b", "+1R partial"),
        (entry + side * 3 * risk, "#7c3aed", "+3R graduate"),
    ]
    for price, color, label in levels:
        items.append(line(x_offset + left, y(price), x_offset + right, y(price), color, 1.0))
        items.append(text(x_offset + right - 90, y(price) - 2, label, 9, color))
    for event in events:
        if start <= event.avail <= end:
            color = "#059669" if event.timeframe == "M5" else "#7c3aed"
            items.append(
                f'<circle cx="{x(event.avail):.1f}" cy="{y(event.stop):.1f}" r="2.2" fill="{color}" />'
            )
    items.append(line(x(entry_time), y_offset + top, x(entry_time), y_offset + bottom, "#111827", 1.3))
    items.append(line(x(exit_time), y_offset + top, x(exit_time), y_offset + bottom, "#ef4444", 1.3))
    title = (
        f"id {int(trade['entry_id'])} | {trade['window']} | {'BUY' if side > 0 else 'SELL'} | "
        f"SPLIT {trade['r']:+.2f}R | {trade['reason']} | {trade['holding_minutes']:.1f}m"
    )
    items.append(text(x_offset + 10, y_offset + 18, title, 12))
    detail = (
        f"entry {entry_time.strftime('%Y-%m-%d %H:%M:%S')} UTC | exit {exit_time.strftime('%H:%M:%S')} | "
        f"partial={bool(trade['partial_taken'])} graduate={bool(trade['graduated'])}"
    )
    items.append(text(x_offset + 10, y_offset + 33, detail, 9, "#4b5563"))
    items.append(text(x_offset + left, y_offset + PANEL_HEIGHT - 8, start.strftime("%H:%M"), 9, "#6b7280"))
    items.append(
        text(x_offset + right - 28, y_offset + PANEL_HEIGHT - 8, end.strftime("%H:%M"), 9, "#6b7280")
    )
    return "\n".join(items)


def main() -> None:
    results = pd.read_parquet(HERE / "exit_results_p1.parquet")
    opportunities = pd.read_parquet(HERE / "opportunities_p1.parquet")
    selected = (
        opportunities.loc[(opportunities["threshold"] == 0.25) & (opportunities["timeframe"] == "M1")]
        .sort_values("entry_time")
        .reset_index(drop=True)
    )
    split = results.loc[(results["family"] == "SPLIT") & results["complete"]]
    winners = deterministic_six(split.loc[split["r"] > 0]).assign(audit_group="winner")
    losers = deterministic_six(split.loc[split["r"] < 0]).assign(audit_group="loser")
    audited = pd.concat([winners, losers], ignore_index=True)
    if len(winners) != 6 or len(losers) != 6:
        raise RuntimeError("chart audit requires exactly six winners and six losers")
    m1 = load_m1(BAR_PATH, P1, warmup_start=pd.Timestamp("2025-09-01", tz="UTC"))
    bars = {"M5": aggregate(m1, "5min"), "M15": aggregate(m1, "15min")}
    atrs = {
        name: atr(
            frame["high"].to_numpy(float),
            frame["low"].to_numpy(float),
            frame["close"].to_numpy(float),
            14,
        )
        for name, frame in bars.items()
    }
    pivots = {name: confirmed_fractals(frame, radius=1) for name, frame in bars.items()}
    CHART_DIR.mkdir(exist_ok=True)
    contact_items: list[str] = []
    manifest_rows: list[dict[str, object]] = []
    for position, trade in audited.iterrows():
        entry_time = pd.Timestamp(trade["entry_time"])
        entry_spread = float(selected.loc[int(trade["entry_id"]), "spread"])
        events = []
        for timeframe in ("M5", "M15"):
            events.extend(
                structure_events(
                    bars[timeframe],
                    pivots[timeframe],
                    atrs[timeframe],
                    timeframe=timeframe,
                    side=int(trade["side"]),
                    entry_time=entry_time,
                    entry_spread=entry_spread,
                    end_time=entry_time + pd.Timedelta(hours=8),
                )
            )
        panel = panel_svg(trade, m1, events)
        document = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PANEL_WIDTH}" height="{PANEL_HEIGHT}" '
            f'viewBox="0 0 {PANEL_WIDTH} {PANEL_HEIGHT}">{panel}</svg>'
        )
        filename = f"{position + 1:02d}_{trade['audit_group']}_id{int(trade['entry_id'])}.svg"
        (CHART_DIR / filename).write_text(document, encoding="utf-8", newline="\n")
        column = position % 2
        row = position // 2
        contact_items.append(
            panel_svg(
                trade,
                m1,
                events,
                x_offset=column * PANEL_WIDTH,
                y_offset=row * PANEL_HEIGHT,
            )
        )
        manifest_rows.append(
            {
                "chart": filename,
                "audit_group": trade["audit_group"],
                "entry_id": int(trade["entry_id"]),
                "window": trade["window"],
                "side": int(trade["side"]),
                "entry_time": entry_time,
                "exit_time": trade["exit_time"],
                "reason": trade["reason"],
                "r": float(trade["r"]),
                "partial_taken": bool(trade["partial_taken"]),
                "graduated": bool(trade["graduated"]),
            }
        )
    contact = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * PANEL_WIDTH}" height="{6 * PANEL_HEIGHT}" '
        f'viewBox="0 0 {2 * PANEL_WIDTH} {6 * PANEL_HEIGHT}">' + "\n".join(contact_items) + "</svg>"
    )
    (CHART_DIR / "audit_contact_sheet.svg").write_text(contact, encoding="utf-8", newline="\n")
    pd.DataFrame(manifest_rows).to_csv(HERE / "chart_audit_p1.csv", index=False)
    print(  # noqa: T201
        f"wrote {len(manifest_rows)} audited SPLIT charts: six winners, six losers; "
        f"contact sheet {CHART_DIR / 'audit_contact_sheet.svg'}"
    )


if __name__ == "__main__":
    main()
