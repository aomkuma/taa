"""Drift, performance and forward-readiness reporting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .journal import ShadowJournal
from .robustness import analyze_champion, policy_comparison
from .schema import FEATURE_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT.parent / "2026-10-20-trend-runner-r2/feature_panel.parquet"
REFERENCE_HASH = "cee56de79682d4a113517354402d524413cfc25159cc5f5051e1508023a72a0b"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _drawdown(values: np.ndarray) -> float:
    equity = np.r_[0.0, np.cumsum(values)]
    return float(np.max(np.maximum.accumulate(equity) - equity))


def _psi(reference: np.ndarray, current: np.ndarray) -> float:
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, 11)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    expected = np.histogram(reference, bins=edges)[0] / len(reference)
    actual = np.histogram(current, bins=edges)[0] / len(current)
    expected = np.clip(expected, 1e-6, None)
    actual = np.clip(actual, 1e-6, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def build_report(journal: ShadowJournal) -> dict[str, object]:
    opportunities = journal.opportunities()
    outcomes = journal.outcomes()
    decisions = journal.decisions()
    snapshots = journal.snapshots()
    adapter_anchors = journal.adapter_anchors()
    champion = (
        pd.DataFrame()
        if decisions.empty
        else decisions.loc[decisions["policy"] == "CHAMPION_R3"].copy()
    )
    scored = champion.loc[champion["status"] == "SCORED"] if not champion.empty else champion
    scored_days = 0
    joined = pd.DataFrame()
    if not scored.empty:
        scored = scored.merge(
            opportunities[["trade_key", "entry_time", "side", "window"]],
            on="trade_key",
            validate="one_to_one",
        )
        scored["entry_time"] = pd.to_datetime(scored["entry_time"], utc=True)
        scored_days = scored["entry_time"].dt.date.nunique()
        if not outcomes.empty:
            joined = (
                scored.merge(outcomes, on="trade_key", how="inner", validate="one_to_one")
                .sort_values("entry_time")
                .reset_index(drop=True)
            )

    performance: dict[str, object] = {"completed_scored": len(joined)}
    if not joined.empty:
        selected = joined.loc[joined["action"] == "RUNNER", "runner_r"].to_numpy(dtype=float)
        all_runner = joined["runner_r"].to_numpy(dtype=float)
        performance.update(
            {
                "selected_completed": len(selected),
                "selected_total_r": float(selected.sum()),
                "selected_mean_r": float(selected.mean()) if len(selected) else None,
                "selected_drawdown_r": _drawdown(selected) if len(selected) else 0.0,
                "always_runner_total_r": float(all_runner.sum()),
                "always_runner_mean_r": float(all_runner.mean()),
                "rolling_20_mean_r": float(pd.Series(selected).rolling(20).mean().iloc[-1])
                if len(selected) >= 20
                else None,
                "rolling_40_mean_r": float(pd.Series(selected).rolling(40).mean().iloc[-1])
                if len(selected) >= 40
                else None,
            }
        )

    drift: dict[str, object] = {"status": "INSUFFICIENT", "rows": len(opportunities)}
    if len(opportunities) >= 20:
        if _hash(REFERENCE) != REFERENCE_HASH:
            raise ValueError("drift reference hash mismatch")
        reference = pd.read_parquet(REFERENCE, columns=list(FEATURE_COLUMNS))
        current = pd.json_normalize(opportunities["features"])
        features: dict[str, object] = {}
        for name in FEATURE_COLUMNS:
            base = reference[name].to_numpy(dtype=float)
            recent = current[name].to_numpy(dtype=float)
            scale = float(np.std(base, ddof=0)) or 1.0
            features[name] = {
                "standardized_mean_shift": float((np.mean(recent) - np.mean(base)) / scale),
                "psi": _psi(base, recent),
            }
        maximum_psi = max(float(value["psi"]) for value in features.values())
        drift = {
            "status": "ALERT" if maximum_psi >= 0.25 else "WATCH" if maximum_psi >= 0.10 else "OK",
            "rows": len(opportunities),
            "maximum_psi": maximum_psi,
            "features": features,
        }

    action_counts = (
        {}
        if scored.empty
        else {str(key): int(value) for key, value in scored["action"].value_counts(dropna=False).items()}
    )
    evaluation_ready = len(scored) >= 100 and scored_days >= 60
    selected_frame = (
        pd.DataFrame()
        if joined.empty
        else joined.loc[joined["action"] == "RUNNER"].copy()
    )
    robustness = analyze_champion(selected_frame, evaluation_ready=evaluation_ready)
    return {
        "mode": "SHADOW_ONLY_NO_ORDER_CAPABILITY",
        "opportunities": len(opportunities),
        "outcomes": len(outcomes),
        "decisions": len(decisions),
        "snapshots": len(snapshots),
        "adapter_anchors": len(adapter_anchors),
        "adapter_status_counts": {}
        if adapter_anchors.empty
        else {
            str(key): int(value)
            for key, value in adapter_anchors["status"].value_counts().items()
        },
        "champion_scored_opportunities": len(scored),
        "champion_scored_trading_days": scored_days,
        "action_counts": action_counts,
        "evaluation_ready": evaluation_ready,
        "performance": performance,
        "robustness": robustness,
        "policy_comparison": policy_comparison(decisions, outcomes),
        "drift": drift,
    }


def write_report(journal: ShadowJournal, output: Path) -> dict[str, object]:
    report = build_report(journal)
    output.mkdir(parents=True, exist_ok=True)
    (output / "shadow_status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# TREND-RUNNER shadow status",
        "",
        f"Mode: **{report['mode']}**",
        "",
        f"Opportunities {report['opportunities']}; outcomes {report['outcomes']}; decisions "
        f"{report['decisions']}; snapshots {report['snapshots']}.",
        f"Finalized adapter anchors {report['adapter_anchors']}: {report['adapter_status_counts']}.",
        f"Champion scored opportunities {report['champion_scored_opportunities']}; scored trading days "
        f"{report['champion_scored_trading_days']}.",
        f"Formal evaluation ready: **{report['evaluation_ready']}**.",
        f"Forward robustness: **{report['robustness']['status']}** — "
        f"{report['robustness']['reason']}.",
        "",
        f"Drift status: **{report['drift']['status']}** with {report['drift']['rows']} rows.",
        "",
        "This report is observational. It cannot place or authorize an order.",
        "",
    ]
    (output / "shadow_status.md").write_text("\n".join(lines), encoding="utf-8")
    return report
