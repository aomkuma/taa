# SVG tags are intentionally long and kept readable as emitted markup.
# ruff: noqa: E501

"""Create matched M15 path charts for high-ATR gate misses vs blocked losses."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
ADAPTIVE = ROOT / "adaptive_research"
CHARTS = ADAPTIVE / "missed_winner_charts"
BAR_PATH = ROOT.parents[1] / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")


def _price_to_r(value: float, side: int, entry: float, risk: float) -> float:
    return side * (value - entry) / risk


def _x_coordinate(minute: float, left: float, width: float) -> float:
    return left + ((minute + 60) / 540) * width


def _y_coordinate(value: float, top: float, height: float, y_min: float, y_max: float) -> float:
    return top + ((y_max - value) / (y_max - y_min)) * height


def _pre_entry_features(trade: pd.Series, bars: pd.DataFrame) -> dict[str, float]:
    entry_time = pd.Timestamp(trade["entry_time_utc"])
    prior = bars.loc[
        (bars.index >= entry_time - pd.Timedelta(minutes=60)) & (bars.index < entry_time)
    ]
    if len(prior) < 55:
        raise ValueError(f"insufficient pre-entry M1 bars for {trade['trade_key']}")
    side = 1 if trade["side"] == "BUY" else -1
    atr = float(trade["h1_atr"])
    low, high = float(prior["low"].min()), float(prior["high"].max())
    span = max(high - low, 1e-12)
    location = (float(trade["entry"]) - low) / span
    if side == -1:
        location = (high - float(trade["entry"])) / span
    bodies = side * (prior["close"] - prior["open"])
    recent = prior.tail(15)
    return {
        "directional_return_15m_atr": side * (float(recent["close"].iloc[-1]) - float(recent["open"].iloc[0])) / atr,
        "directional_return_60m_atr": side * (float(prior["close"].iloc[-1]) - float(prior["open"].iloc[0])) / atr,
        "entry_location_60m_directional": location,
        "directional_body_fraction_60m": float((bodies > 0).mean()),
        "range_60m_atr": span / atr,
    }


def _context_summary(blocked: pd.DataFrame) -> pd.DataFrame:
    features = (
        "directional_return_15m_atr",
        "directional_return_60m_atr",
        "entry_location_60m_directional",
        "directional_body_fraction_60m",
        "range_60m_atr",
    )
    rows = []
    for feature in features:
        row: dict[str, object] = {"feature": feature}
        for label, group in blocked.groupby("audit_group", sort=False):
            values = group[feature].dropna()
            row[f"{label}_n"] = len(values)
            row[f"{label}_median"] = float(values.median())
            row[f"{label}_iqr"] = float(values.quantile(0.75) - values.quantile(0.25))
        rows.append(row)
    return pd.DataFrame(rows)


def _svg_pair(loss: pd.Series, winner: pd.Series, bars: pd.DataFrame, pair_num: int) -> str:
    width, plot_height = 680, 250
    left, top = 82, 82
    panel_gap = 58
    plot_width = 560
    total_height = 2 * plot_height + panel_gap + 115
    y_min, y_max = -3.0, 8.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}">',
        '<defs><clipPath id="plot-0"><rect x="82" y="82" width="560" height="250"/></clipPath>',
        '<clipPath id="plot-1"><rect x="82" y="390" width="560" height="250"/></clipPath></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font:12px Arial,sans-serif;fill:#202733}.small{font-size:11px}.grid{stroke:#d7dce2;stroke-width:1}.axis{stroke:#657080;stroke-width:1}.win{stroke:#18864b;fill:#18864b}.loss{stroke:#c23b3b;fill:#c23b3b}</style>',
        f'<text x="{left}" y="24" font-size="15" font-weight="600">Matched blocked trades — pair {pair_num:02d}</text>',
        '<text x="82" y="52" class="small">M15 candles from M1 OHLC · move in R · entry blue, modeled exit purple · view clipped to −3R…+8R</text>',
    ]
    for panel, trade, cohort in ((0, loss, "Blocked loss"), (1, winner, "Blocked winner")):
        panel_top = top + panel * (plot_height + panel_gap)
        entry_time = pd.Timestamp(trade["entry_time_utc"])
        side = 1 if trade["side"] == "BUY" else -1
        entry, risk = float(trade["entry"]), float(trade["initial_risk_price"])
        label = (
            f'{cohort}: {trade["trade_key"]} · {trade["side"]} {trade["window"]} · '
            f'{entry_time:%Y-%m-%d %H:%M} UTC · {float(trade["runner_r"]):+.2f}R'
        )
        parts.append(f'<text x="{left}" y="{panel_top - 12}" font-weight="600">{label}</text>')
        for level in (-3, -1, 0, 1, 2, 4, 6, 8):
            y = _y_coordinate(level, panel_top, plot_height, y_min, y_max)
            parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_width}" y2="{y:.1f}" class="grid"/>')
            parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="small">{level}R</text>')
        start, end = entry_time - pd.Timedelta(minutes=60), entry_time + pd.Timedelta(hours=8)
        source = bars.loc[(bars.index >= start.floor("15min")) & (bars.index < end.ceil("15min"))]
        resampler = source["open"].resample("15min", origin="epoch", label="left", closed="left")
        counts = resampler.count()
        candles = source.resample("15min", origin="epoch", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        )
        candles = candles.loc[counts.eq(15)].dropna()
        parts.append(f'<g clip-path="url(#plot-{panel})">')
        for time, candle in candles.iterrows():
            minute = (time - entry_time).total_seconds() / 60
            if minute < -60 or minute >= 480:
                continue
            x = _x_coordinate(minute, left, plot_width)
            opened = _price_to_r(float(candle["open"]), side, entry, risk)
            closed = _price_to_r(float(candle["close"]), side, entry, risk)
            high = max(_price_to_r(float(candle["high"]), side, entry, risk),
                       _price_to_r(float(candle["low"]), side, entry, risk))
            low = min(_price_to_r(float(candle["high"]), side, entry, risk),
                      _price_to_r(float(candle["low"]), side, entry, risk))
            color = "win" if closed >= opened else "loss"
            body_top, body_bottom = sorted((
                _y_coordinate(opened, panel_top, plot_height, y_min, y_max),
                _y_coordinate(closed, panel_top, plot_height, y_min, y_max),
            ))
            body_height = max(body_bottom - body_top, 1.2)
            high_y = _y_coordinate(high, panel_top, plot_height, y_min, y_max)
            low_y = _y_coordinate(low, panel_top, plot_height, y_min, y_max)
            parts.append(f'<line x1="{x:.1f}" y1="{high_y:.1f}" x2="{x:.1f}" y2="{low_y:.1f}" class="{color}"/>')
            parts.append(f'<rect x="{x-4:.1f}" y="{body_top:.1f}" width="8" height="{body_height:.1f}" class="{color}"/>')
        parts.append('</g>')
        for level, style, _caption in ((-1, "#c23b3b", "Stop −1R"), (1, "#18864b", "+1R")):
            y = _y_coordinate(level, panel_top, plot_height, y_min, y_max)
            parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_width}" y2="{y:.1f}" stroke="{style}" stroke-dasharray="4 4"/>')
        entry_x = _x_coordinate(0, left, plot_width)
        parts.append(f'<line x1="{entry_x:.1f}" y1="{panel_top}" x2="{entry_x:.1f}" y2="{panel_top+plot_height}" stroke="#315e91" stroke-dasharray="2 3"/>')
        exit_x = _x_coordinate(float(trade["runner_hold_minutes"]), left, plot_width)
        parts.append(f'<line x1="{exit_x:.1f}" y1="{panel_top}" x2="{exit_x:.1f}" y2="{panel_top+plot_height}" stroke="#7c5c9c" stroke-dasharray="3 3"/>')
        parts.append(f'<line x1="{left}" y1="{panel_top+plot_height}" x2="{left+plot_width}" y2="{panel_top+plot_height}" class="axis"/>')
        for minute in (-60, 0, 60, 120, 180, 240, 300, 360, 420, 480):
            x = _x_coordinate(minute, left, plot_width)
            parts.append(f'<line x1="{x:.1f}" y1="{panel_top+plot_height}" x2="{x:.1f}" y2="{panel_top+plot_height+4}" class="axis"/>')
            parts.append(f'<text x="{x:.1f}" y="{panel_top+plot_height+18}" text-anchor="middle" class="small">{minute}</text>')
        parts.append(f'<text x="{left+plot_width/2}" y="{panel_top+plot_height+35}" text-anchor="middle" class="small">Minutes from entry</text>')
        parts.append(f'<text x="{left+plot_width-4}" y="{panel_top+plot_height-7}" text-anchor="end" class="small">Entry {float(trade["h1_atr_percentile_120"]):.3f} ATR percentile</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def load_bars() -> pd.DataFrame:
    bars = pd.read_parquet(
        BAR_PATH,
        columns=["open_time", "close_time", "open", "high", "low", "close"],
        filters=[
            ("open_time", ">=", pd.Timestamp("2023-09-01", tz="UTC").to_pydatetime()),
            ("open_time", "<", EXAM_START.to_pydatetime()),
        ],
    )
    bars["open_time"] = pd.to_datetime(bars["open_time"], utc=True)
    bars["close_time"] = pd.to_datetime(bars["close_time"], utc=True)
    bars = bars.sort_values("open_time").set_index("open_time")
    if (bars["close_time"] > EXAM_START).any():
        raise AssertionError("Locked exam boundary crossed during chart loading")
    return bars


def main() -> None:
    trades = pd.read_csv(ADAPTIVE / "adaptive_atr_gate_trades.csv")
    trades["entry_time_utc"] = pd.to_datetime(trades["entry_time_utc"], utc=True)
    if trades["entry_time_utc"].max() >= EXAM_START:
        raise AssertionError("Locked exam boundary crossed by journal rows")
    bars = load_bars()
    all_features = pd.DataFrame(
        {
            row.trade_key: _pre_entry_features(pd.Series(row._asdict()), bars)
            for row in trades.itertuples(index=False)
        }
    ).T
    all_features.index.name = "trade_key"
    trades = trades.join(all_features, on="trade_key")
    blocked = trades.loc[~trades["adaptive_keep"]].copy()
    winners = blocked.loc[blocked["runner_r"].gt(0)].copy()
    losses = blocked.loc[blocked["runner_r"].lt(0)].copy()
    blocked["audit_group"] = blocked["runner_r"].gt(0).map(
        {True: "BLOCKED_WINNER", False: "BLOCKED_LOSS"}
    )
    _context_summary(blocked).to_csv(
        ADAPTIVE / "blocked_winner_context.csv", index=False, float_format="%.6f"
    )

    CHARTS.mkdir(exist_ok=True)
    index: list[dict[str, object]] = []
    for number, winner in enumerate(winners.itertuples(index=False), start=1):
        candidates = losses.loc[
            losses["window"].eq(winner.window) & losses["side"].eq(winner.side)
        ].copy()
        if candidates.empty:
            raise AssertionError(f"No same-side/session blocked loss to match {winner.trade_key}")
        candidates["atr_percentile_distance"] = (
            candidates["h1_atr_percentile_120"] - winner.h1_atr_percentile_120
        ).abs()
        loss = candidates.sort_values(
            ["atr_percentile_distance", "entry_time_utc", "trade_key"], kind="stable"
        ).iloc[0]
        winning_row = trades.loc[trades["trade_key"].eq(winner.trade_key)].iloc[0]
        filename = f"missed_winner_{number:02d}_{winner.trade_key.lower()}.svg"
        svg_path = CHARTS / filename
        svg_path.write_text(_svg_pair(loss, winning_row, bars, number), encoding="utf-8")
        index.append(
            {
                "winner_trade_key": winner.trade_key,
                "winner_entry_utc": winner.entry_time_utc.isoformat(),
                "winner_window": winner.window,
                "winner_side": winner.side,
                "winner_r": float(winner.runner_r),
                "winner_atr_percentile": float(winner.h1_atr_percentile_120),
                "loss_trade_key": loss["trade_key"],
                "loss_entry_utc": loss["entry_time_utc"].isoformat(),
                "loss_r": float(loss["runner_r"]),
                "loss_atr_percentile": float(loss["h1_atr_percentile_120"]),
                "loss_path_class": loss["path_class"],
                "chart": svg_path.name,
            }
        )
    pd.DataFrame(index).to_csv(ADAPTIVE / "blocked_winner_chart_index.csv", index=False)


if __name__ == "__main__":
    main()
