"""Describe selected trades stopped before +1R without changing strategy rules."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "trade_journal.csv"
OUTPUT = ROOT / "early_stop_audit"
METRICS = [
    "runner_r",
    "h1_atr",
    "risk_h1_atr",
    "pullback_ratio",
    "open_space_atr",
    "h1_atr_percentile_120",
    "confidence_score",
    "runner_hold_minutes",
    "mfe_before_exit_r_including_exit_bar",
    "mae_before_exit_r_including_exit_bar",
    "mfe_8h_r",
    "post_exit_best_from_entry_r",
    "post_exit_favorable_from_exit_r",
    "post_exit_mfe_minutes",
]
TRADE_FIELDS = [
    "trade_key",
    "entry_time_utc",
    "side",
    "window",
    "runner_r",
    "runner_exit_time_utc",
    "runner_exit_reason",
    "runner_hold_minutes",
    "h1_atr",
    "risk_h1_atr",
    "pullback_ratio",
    "open_space_atr",
    "h1_atr_percentile_120",
    "confidence_score",
    "mfe_before_exit_r_including_exit_bar",
    "mae_before_exit_r_including_exit_bar",
    "mfe_8h_r",
    "post_exit_best_from_entry_r",
    "post_exit_favorable_from_exit_r",
    "post_exit_mfe_minutes",
    "path_class",
]


def _group_stats(group: pd.DataFrame) -> dict[str, object]:
    stats: dict[str, object] = {"trades": len(group)}
    for metric in METRICS:
        series = pd.to_numeric(group[metric], errors="coerce")
        stats[f"{metric}_median"] = None if series.notna().sum() == 0 else float(series.median())
        stats[f"{metric}_mean"] = None if series.notna().sum() == 0 else float(series.mean())
    for threshold in (1, 2, 3):
        values = pd.to_numeric(group["post_exit_best_from_entry_r"], errors="coerce")
        stats[f"post_exit_reached_{threshold}r_count"] = int(values.ge(threshold).sum())
        stats[f"post_exit_reached_{threshold}r_rate"] = float(values.ge(threshold).mean())
    return stats


def _comparison(frame: pd.DataFrame, group_col: str) -> dict[str, dict[str, object]]:
    return {
        str(label): _group_stats(group)
        for label, group in frame.groupby(group_col, sort=False, dropna=False)
    }


def _context_summary(early: pd.DataFrame, column: str) -> pd.DataFrame:
    rows = []
    for key, group in early.groupby(column, dropna=False, sort=True):
        rows.append(
            {
                column: key,
                "trades": len(group),
                "mean_runner_r": group["runner_r"].mean(),
                "median_runner_r": group["runner_r"].median(),
                "median_h1_atr": group["h1_atr"].median(),
                "median_mfe_before_exit_r": group["mfe_before_exit_r_including_exit_bar"].median(),
                "post_exit_ge_1r_count": group["post_exit_best_from_entry_r"].ge(1).sum(),
            }
        )
    return pd.DataFrame(rows)


def _md_table(frame: pd.DataFrame) -> list[str]:
    headers = list(frame.columns)
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in frame.itertuples(index=False, name=None):
        cells = []
        for value in row:
            if pd.isna(value):
                cells.append("-")
            elif isinstance(value, (float, int)):
                cells.append(f"{value:.3f}" if isinstance(value, float) else str(value))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def main() -> None:
    journal = pd.read_csv(SOURCE)
    selected = journal.loc[journal["action"].eq("RUNNER")].copy()
    selected["audit_group"] = "OTHER_SELECTED"
    selected.loc[selected["runner_r"].gt(0), "audit_group"] = "SELECTED_WIN"
    selected.loc[
        selected["runner_r"].lt(0) & selected["path_class"].ne("STOP_BEFORE_1R"), "audit_group"
    ] = "OTHER_SELECTED_LOSS"
    selected.loc[
        selected["runner_r"].lt(0) & selected["path_class"].eq("STOP_BEFORE_1R"), "audit_group"
    ] = "STOP_BEFORE_1R_LOSS"

    early = selected.loc[selected["audit_group"].eq("STOP_BEFORE_1R_LOSS")].copy()
    if len(selected) != 313 or len(early) != 146:
        raise AssertionError(
            f"unexpected sample sizes: selected={len(selected)}, exact early stop={len(early)}"
        )
    if early["trade_key"].duplicated().any():
        raise AssertionError("duplicate trade key in early-stop audit")

    summary = {
        "source": SOURCE.name,
        "sample_scope": "Historical M1 OHLC 3-year walk-forward journal; frozen RUNNER-selected trades only.",
        "groups": _comparison(selected, "audit_group"),
        "early_stop_mfe_buckets": {
            "<0.25R": int(early["mfe_before_exit_r_including_exit_bar"].lt(0.25).sum()),
            "0.25-<0.5R": int(
                early["mfe_before_exit_r_including_exit_bar"].ge(0.25)
                .mul(early["mfe_before_exit_r_including_exit_bar"].lt(0.5)).sum()
            ),
            "0.5-<1R": int(
                early["mfe_before_exit_r_including_exit_bar"].ge(0.5)
                .mul(early["mfe_before_exit_r_including_exit_bar"].lt(1)).sum()
            ),
        },
        "early_stop_by_side": _context_summary(early, "side").to_dict(orient="records"),
        "early_stop_by_window": _context_summary(early, "window").to_dict(orient="records"),
        "limitations": [
            "Descriptive, post-hoc analysis of a frozen historical sample; not independent validation.",
            "M1 OHLC cannot establish exact intrabar price ordering; ambiguous paths are separate.",
            "Post-exit favorable movement is hindsight and does not prove the stop was avoidable.",
            "No strategy, entry, exit, or risk rule is changed by this audit.",
        ],
    }

    OUTPUT.mkdir(exist_ok=True)
    early[TRADE_FIELDS].to_csv(OUTPUT / "stop_before_1r_trades.csv", index=False, float_format="%.6f")
    _context_summary(early, "side").to_csv(OUTPUT / "by_side.csv", index=False, float_format="%.6f")
    _context_summary(early, "window").to_csv(OUTPUT / "by_window.csv", index=False, float_format="%.6f")
    (OUTPUT / "audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    comparison = pd.DataFrame(
        [
            {
                "Group": name,
                "N": stats["trades"],
                "Mean R": stats["runner_r_mean"],
                "Median R": stats["runner_r_median"],
                "Median pre-exit MFE R": stats["mfe_before_exit_r_including_exit_bar_median"],
                "Median H1 ATR": stats["h1_atr_median"],
                "Median risk/H1 ATR": stats["risk_h1_atr_median"],
                "Post-exit >=1R": (
                    f"{stats['post_exit_reached_1r_count']}/{stats['trades']} "
                    f"({stats['post_exit_reached_1r_rate']:.1%})"
                ),
                "Post-exit >=2R": (
                    f"{stats['post_exit_reached_2r_count']}/{stats['trades']} "
                    f"({stats['post_exit_reached_2r_rate']:.1%})"
                ),
            }
            for name, stats in summary["groups"].items()
        ]
    )
    buckets = pd.DataFrame(
        [
            {"Pre-exit MFE bucket": key, "Trades": value}
            for key, value in summary["early_stop_mfe_buckets"].items()
        ]
    )
    lines = [
        "# Early-stop trade audit",
        "",
        f"Source: `{SOURCE.name}`. {len(early)} of {len(selected)} selected RUNNER trades "
        "were stopped before +1R.",
        "Historical M1 OHLC only; no strategy rules changed.",
        "",
        "## Comparison",
        "",
        *_md_table(comparison),
        "",
        "Post-exit >=1R/2R means the later path moved that far from original entry after exit. "
        "This is hindsight, not a recoverable-trade rate.",
        "",
        "## Progress made before stop",
        "",
        *_md_table(buckets),
        "",
        "A large share with very small pre-exit MFE points more toward weak/failed follow-through "
        "than exits cutting off substantial progress. It does not establish whether entry timing or "
        "stop placement was at fault.",
        "",
        "## Early-stop losses by side",
        "",
        *_md_table(pd.read_csv(OUTPUT / "by_side.csv")),
        "",
        "## Early-stop losses by session",
        "",
        *_md_table(pd.read_csv(OUTPUT / "by_window.csv")),
        "",
        "## Reading and next test",
        "",
        "The exact STOP_BEFORE_1R group is separated from 54 STOP_AFTER_1R_PARTIAL losses and "
        "18 STOP_BEFORE_1R_OR_AMBIGUOUS losses. The matched chart and pre-entry context comparison "
        "is in `CHART_CONTEXT_REVIEW.md`. Session/side results are exploratory and post-hoc; any "
        "candidate needs a predeclared rule and an allowed chronologically later holdout before promotion.",
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in summary["limitations"]],
        "",
    ]
    (OUTPUT / "EARLY_STOP_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"audited {len(early)} exact pre-1R stopouts across {len(selected)} selected trades")  # noqa: T201


if __name__ == "__main__":
    main()
