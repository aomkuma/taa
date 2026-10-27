"""Compare pre-entry M1 context and representative M15 paths for selected trades."""
# Report prose intentionally exceeds the source line-length limit.
# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT = Path(__file__).resolve().parent
JOURNAL = ROOT / "trade_journal.csv"
BAR_PATH = ROOT.parents[1] / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
PRE_FEATURES = [
    "directional_return_15m_atr",
    "directional_return_60m_atr",
    "entry_location_60m_directional",
    "directional_body_fraction_60m",
    "range_60m_atr",
]
LABELS = {
    "directional_return_15m_atr": "15m directional return / H1 ATR",
    "directional_return_60m_atr": "60m directional return / H1 ATR",
    "entry_location_60m_directional": "Entry location in prior 60m range (directional, 0-1)",
    "directional_body_fraction_60m": "Directional M1 body fraction in prior 60m",
    "range_60m_atr": "Prior 60m high-low range / H1 ATR",
}


def build_pre_entry_features(trade: pd.Series, bars: pd.DataFrame) -> dict[str, float]:
    entry_time = pd.Timestamp(trade["entry_time_utc"])
    prior = bars.loc[(bars.index >= entry_time - pd.Timedelta(minutes=60)) & (bars.index < entry_time)]
    if len(prior) < 55:
        raise ValueError(f"insufficient pre-entry M1 bars for {trade['trade_key']}: {len(prior)}")
    side = 1 if trade["side"] == "BUY" else -1
    entry = float(trade["entry"])
    atr = float(trade["h1_atr"])
    recent15 = prior.tail(15)
    directional_15m = side * (float(recent15["close"].iloc[-1]) - float(recent15["open"].iloc[0])) / atr
    directional_60m = side * (float(prior["close"].iloc[-1]) - float(prior["open"].iloc[0])) / atr
    range_low, range_high = float(prior["low"].min()), float(prior["high"].max())
    span = max(range_high - range_low, 1e-12)
    entry_location = (entry - range_low) / span if side == 1 else (range_high - entry) / span
    directional_bodies = side * (prior["close"] - prior["open"])
    return {
        "directional_return_15m_atr": directional_15m,
        "directional_return_60m_atr": directional_60m,
        "entry_location_60m_directional": entry_location,
        "directional_body_fraction_60m": float((directional_bodies > 0).mean()),
        "range_60m_atr": span / atr,
    }


def _median_pair(losers: pd.DataFrame, winners: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    loser_order = losers
    loser_order = loser_order.assign(
        mfe_distance=(loser_order["mfe_before_exit_r_including_exit_bar"]
                      - loser_order["mfe_before_exit_r_including_exit_bar"].median()).abs()
    )
    loser = loser_order.sort_values(["mfe_distance", "entry_time_utc", "trade_key"]).iloc[0]
    candidates = winners
    scale = pd.concat([loser[PRE_FEATURES].to_frame().T, candidates[PRE_FEATURES]]).std(ddof=0)
    scale = scale.replace(0, 1.0).fillna(1.0)
    distances = ((candidates[PRE_FEATURES] - loser[PRE_FEATURES]) / scale).pow(2).sum(axis=1)
    winner = candidates.loc[distances.sort_values(kind="stable").index[0]]
    loser = loser.copy()
    winner = winner.copy()
    loser["trade_key"] = loser.name
    winner["trade_key"] = winner.name
    return loser, winner


def _to_directional_r(value: float, side: int, entry: float, risk: float) -> float:
    return side * (value - entry) / risk


def make_pair_chart(
    loss: pd.Series,
    win: pd.Series,
    bars: pd.DataFrame,
    pair_num: int,
    output: Path,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.2), sharex=True, constrained_layout=True)
    for ax, trade, group in zip(axes, [loss, win], ["Early stop", "Selected winner"], strict=True):
        entry_time = pd.Timestamp(trade["entry_time_utc"])
        lo = entry_time - pd.Timedelta(minutes=60)
        hi = entry_time + pd.Timedelta(hours=8)
        chart_start = lo.floor("15min")
        chart_end = hi.ceil("15min")
        source_path = bars.loc[(bars.index >= chart_start) & (bars.index < chart_end)].copy()
        resampler = source_path["open"].resample(
            "15min", origin="epoch", label="left", closed="left"
        )
        candle_count = resampler.count()
        path = source_path.resample("15min", origin="epoch", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        )
        path = path.loc[
            candle_count.eq(15)
            & (path.index >= lo.ceil("15min"))
            & (path.index + pd.Timedelta(minutes=15) <= hi)
        ].dropna()
        side = 1 if trade["side"] == "BUY" else -1
        entry = float(trade["entry"])
        risk = float(trade["initial_risk_price"])
        for time, candle in path.iterrows():
            x = (time - entry_time).total_seconds() / 60
            o = _to_directional_r(candle["open"], side, entry, risk)
            c = _to_directional_r(candle["close"], side, entry, risk)
            h = max(
                _to_directional_r(candle["high"], side, entry, risk),
                _to_directional_r(candle["low"], side, entry, risk),
            )
            low_r = min(
                _to_directional_r(candle["high"], side, entry, risk),
                _to_directional_r(candle["low"], side, entry, risk),
            )
            color = "#18864b" if c >= o else "#c23b3b"
            ax.vlines(x, low_r, h, color=color, linewidth=0.9)
            ax.bar(x, max(abs(c - o), 0.012), bottom=min(o, c), width=10.5,
                   color=color, edgecolor=color, linewidth=0.5)
        ax.axhline(0, color="#4c5968", linewidth=0.8)
        ax.axhline(-1, color="#c23b3b", linewidth=0.9, linestyle="--", label="Initial stop (-1R)")
        ax.axhline(1, color="#18864b", linewidth=0.8, linestyle=":", label="+1R")
        ax.axvline(0, color="#2d5e9e", linewidth=1.0, label="Entry")
        hold = float(trade["runner_hold_minutes"])
        ax.axvline(hold, color="#7c5c9c", linewidth=0.9, linestyle="-.", label="Modeled exit")
        ax.set_ylim(-3, 8)
        ax.set_ylabel("Directional move (R)")
        ax.set_title(
            f"{group}: {trade['trade_key']} Â· {trade['side']} {trade['window']} Â· "
            f"{entry_time:%Y-%m-%d %H:%M} UTC Â· result {trade['runner_r']:+.2f}R"
        )
        ax.grid(axis="y", alpha=0.18)
        ax.legend(loc="upper left", ncol=4, fontsize=8)
    axes[-1].set_xlim(-60, 480)
    axes[-1].set_xticks(np.arange(-60, 481, 60))
    axes[-1].set_xlabel("Minutes from entry (M15 candles; source bars are M1)")
    fig.suptitle(
        f"Matched illustrative pair {pair_num:02d}: same side/session Â· y-view clipped at -3/+8R",
        fontsize=14,
    )
    fig.savefig(output, dpi=150)
    plt.close(fig)


def _group_feature_summary(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for feature in PRE_FEATURES:
        row: dict[str, object] = {"Feature": LABELS[feature]}
        for cohort, group in data.groupby("audit_group", sort=False):
            values = group[feature].dropna()
            row[f"{cohort} n"] = len(values)
            row[f"{cohort} median"] = values.median()
            row[f"{cohort} IQR"] = values.quantile(0.75) - values.quantile(0.25)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    trades = pd.read_csv(JOURNAL)
    trades["entry_time_utc"] = pd.to_datetime(trades["entry_time_utc"], utc=True)
    trades["runner_exit_time_utc"] = pd.to_datetime(trades["runner_exit_time_utc"], utc=True)
    if trades["entry_time_utc"].max() >= EXAM_START:
        raise AssertionError("Locked historical exam boundary crossed")
    bars = pd.read_parquet(
        BAR_PATH,
        columns=["open_time", "close_time", "open", "high", "low", "close"],
        filters=[("open_time", ">=", pd.Timestamp("2023-09-01", tz="UTC").to_pydatetime()),
                 ("open_time", "<", EXAM_START.to_pydatetime())],
    )
    bars["open_time"] = pd.to_datetime(bars["open_time"], utc=True)
    bars["close_time"] = pd.to_datetime(bars["close_time"], utc=True)
    bars = bars.sort_values("open_time").set_index("open_time")
    if (bars["close_time"] > EXAM_START).any():
        raise AssertionError("Exam boundary crossed by a chart candle")

    features = pd.DataFrame(
        {row.trade_key: build_pre_entry_features(pd.Series(row._asdict()), bars)
         for row in trades.itertuples(index=False)}
    ).T
    features.index.name = "trade_key"
    trades = trades.join(features, on="trade_key")
    selected = trades.loc[trades["action"].eq("RUNNER")].copy()
    selected["audit_group"] = "OTHER_SELECTED"
    selected.loc[selected["runner_r"].gt(0), "audit_group"] = "SELECTED_WIN"
    selected.loc[
        selected["runner_r"].lt(0) & selected["path_class"].eq("STOP_BEFORE_1R"), "audit_group"
    ] = "STOP_BEFORE_1R_LOSS"
    if (selected["audit_group"].eq("STOP_BEFORE_1R_LOSS").sum() != 146
            or selected["audit_group"].eq("SELECTED_WIN").sum() != 95):
        raise AssertionError("Unexpected frozen cohort sizes")

    early = selected.loc[selected["audit_group"].eq("STOP_BEFORE_1R_LOSS")]
    wins = selected.loc[selected["audit_group"].eq("SELECTED_WIN")]
    strata = ["window", "side"]
    context = selected.groupby(strata, sort=True).agg(
        early_stops=("audit_group", lambda values: int(values.eq("STOP_BEFORE_1R_LOSS").sum())),
        selected_wins=("audit_group", lambda values: int(values.eq("SELECTED_WIN").sum())),
    ).reset_index()
    context = context.loc[context["early_stops"].gt(0) & context["selected_wins"].gt(0)]
    pairs = []
    chart_dir = AUDIT / "matched_charts"
    chart_dir.mkdir(exist_ok=True)
    for pair_num, (_, row) in enumerate(context.iterrows(), start=1):
        loss_group = early.loc[early["window"].eq(row["window"]) & early["side"].eq(row["side"])]
        win_group = wins.loc[wins["window"].eq(row["window"]) & wins["side"].eq(row["side"])]
        loss, win = _median_pair(loss_group.set_index("trade_key"), win_group.set_index("trade_key"))
        filename = f"pair_{pair_num:02d}_{row['window'].lower()}_{row['side'].lower()}.png"
        make_pair_chart(loss, win, bars, pair_num, chart_dir / filename)
        pairs.append({
            "window": row["window"],
            "side": row["side"],
            "early_stop_n": int(row["early_stops"]),
            "winner_n": int(row["selected_wins"]),
            "early_stop_trade": loss["trade_key"],
            "early_stop_entry_utc": loss["entry_time_utc"].isoformat(),
            "early_stop_r": float(loss["runner_r"]),
            "early_stop_mfe_before_exit_r": float(loss["mfe_before_exit_r_including_exit_bar"]),
            "winner_trade": win["trade_key"],
            "winner_entry_utc": win["entry_time_utc"].isoformat(),
            "winner_r": float(win["runner_r"]),
            "winner_mfe_before_exit_r": float(win["mfe_before_exit_r_including_exit_bar"]),
            "chart": f"matched_charts/{filename}",
            **{f"early_{feature}": float(loss[feature]) for feature in PRE_FEATURES},
            **{f"winner_{feature}": float(win[feature]) for feature in PRE_FEATURES},
        })

    summary = _group_feature_summary(selected.loc[selected["audit_group"].isin(
        ["STOP_BEFORE_1R_LOSS", "SELECTED_WIN"]
    )])
    summary.to_csv(AUDIT / "pre_entry_context_comparison.csv", index=False, float_format="%.6f")
    pd.DataFrame(pairs).to_csv(AUDIT / "matched_pair_index.csv", index=False, float_format="%.6f")
    with (AUDIT / "matched_pair_index.json").open("w", encoding="utf-8") as handle:
        json.dump(pairs, handle, indent=2, default=str)

    feature_table = [
        "| Pre-entry feature (known at entry) | Early stops median (IQR) | Selected winners median (IQR) |",
        "|---|---:|---:|",
    ]
    for _, row in summary.iterrows():
        feature = row["Feature"]
        early_med = row["STOP_BEFORE_1R_LOSS median"]
        early_iqr = row["STOP_BEFORE_1R_LOSS IQR"]
        win_med = row["SELECTED_WIN median"]
        win_iqr = row["SELECTED_WIN IQR"]
        feature_table.append(
            f"| {feature} | {early_med:+.3f} ({early_iqr:.3f}) | {win_med:+.3f} ({win_iqr:.3f}) |"
        )

    lines = [
        "# Early-stop vs winner chart/context comparison",
        "",
        "## Method",
        "",
        "Compare 146 exact selected STOP_BEFORE_1R losses with 95 positive selected RUNNER trades from the same frozen 3-year journal. Pre-entry features use only the prior 15 or 60 completed M1 bars; winner/loss labels are retrospective and are not features. Charts use only complete M15 candles resampled from M1, normalize price directionally by initial risk, and show one illustrative pair for every window x side stratum. Within each stratum, the loss is the median pre-exit-MFE case; its winner is the nearest standardized match on pre-entry features. Charts are illustrative, not evidence of statistical significance.",
        "",
        "## Pre-entry context across all trades",
        "",
        *feature_table,
        "",
        "IQR is the interquartile range. Directional returns are side-adjusted and normalized by each trade's H1 ATR. Entry location 0 means the unfavorable edge and 1 the favorable edge of the prior 60-minute range; values above 1 indicate entry beyond that favorable edge. A difference is descriptive and must not be converted directly into a filter.",
        "",
        "The cohort medians are nearly identical on all five measured pre-entry features: 15m/60m directional return, range location, candle-body agreement, and prior-range size. The simple M1 context measured here does not distinguish the groups; that weakens the case for adding a same-sample pre-entry filter based on these variables.",
        "",
        "## Matched chart cases",
        "",
        "| Window | Side | Cohort N: loss / win | Early stop (R, pre-exit MFE) | Winner (R, pre-exit MFE) | Chart |",
        "|---|---|---:|---|---|---|",
    ]
    for pair in pairs:
        lines.append(
            f"| {pair['window']} | {pair['side']} | {pair['early_stop_n']} / {pair['winner_n']} | "
            f"{pair['early_stop_trade']} ({pair['early_stop_r']:+.2f}R, "
            f"{pair['early_stop_mfe_before_exit_r']:+.2f}R MFE) | "
            f"{pair['winner_trade']} ({pair['winner_r']:+.2f}R, "
            f"{pair['winner_mfe_before_exit_r']:+.2f}R MFE) | `{pair['chart']}` |"
        )
    lines += [
        "",
        "## Interpretation and research decision",
        "",
        "Read the paired charts as examples, not as a causal comparison: even after matching side/session and coarse pre-entry context, the winning label is known only after the fact. The 146 early-stop paths mostly show very little favorable movement before exit; that is more consistent with failed follow-through than a trailing exit cutting off an already-large open gain. Whether a confirmation delay, pullback/retest entry, or initial-stop geometry is responsible remains unresolved.",
        "",
        "A separate RETEST-CONTINUATION candidate already exists and studies post-stop reclaim, retest, then M5 confirmation; it has an isolated historical diagnostic and a frozen prospective observer. This chart review is not evidence to create or alter that rule. Its prior positive historical result was concentrated in a few trades, so preserve its separate prospective evidence contract rather than retuning it here. For the baseline TR3 entry, no new candidate is promoted from this chart review. Any further test must use a separately predeclared rule and an allowed, strictly later sample; preserve the locked exam boundary and the already frozen observer contract.",
        "",
        "## Limitations",
        "",
        "- Historical M1 OHLC backtest only; no tick-level ordering, spread/slippage sensitivity, or live executions are added here.",
        "- The cohort label uses final RUNNER R; it is retrospective, not known at entry.",
        "- Matching and representative chart selection are for visualization only. They do not prove that any entry modification improves performance.",
        "- Pre-entry comparisons are exploratory/post-hoc, with five related features and no multiple-testing correction.",
        "- No change to TR1/TR3/TR4, any order path, or the forward-shadow contract.",
        "",
    ]
    (AUDIT / "CHART_CONTEXT_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"built {len(pairs)} same-side/session illustrative chart pairs")  # noqa: T201


if __name__ == "__main__":
    main()
