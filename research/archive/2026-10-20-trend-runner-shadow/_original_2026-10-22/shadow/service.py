"""Cold-start scoring service; it records decisions and cannot place orders."""

from __future__ import annotations

import json

import pandas as pd

from .journal import ShadowJournal
from .model import MINIMUM_TRAIN, WINDOW_DAYS, RidgeModel, fit_ridge, policy_action, predict
from .schema import FEATURE_COLUMNS, Opportunity, canonical_hash

POLICIES = {
    "CHAMPION_R3": {"threshold": 0.05, "penalty": 0.5, "buy_only": False},
    "CHALLENGER_T010": {"threshold": 0.10, "penalty": 0.5, "buy_only": False},
    "CHALLENGER_BUY_ONLY": {"threshold": 0.05, "penalty": 0.5, "buy_only": True},
}


def _joined_history(journal: ShadowJournal) -> pd.DataFrame:
    opportunities = journal.opportunities()
    outcomes = journal.outcomes()
    if opportunities.empty or outcomes.empty:
        return pd.DataFrame()
    feature_frame = pd.json_normalize(opportunities["features"])
    opportunities = pd.concat([opportunities.drop(columns="features"), feature_frame], axis=1)
    history = opportunities.merge(outcomes, on="trade_key", validate="one_to_one", suffixes=("", "_outcome"))
    history["entry_time"] = pd.to_datetime(history["entry_time"], utc=True)
    history["outcome_available"] = pd.to_datetime(history["outcome_available"], utc=True)
    return history


def _month(timestamp: pd.Timestamp) -> tuple[str, pd.Timestamp]:
    period = timestamp.tz_localize(None).to_period("M")
    return str(period), period.start_time.tz_localize("UTC")


def _snapshots_for(
    journal: ShadowJournal, opportunity: Opportunity
) -> tuple[list[RidgeModel], list[str]] | None:
    month, month_start = _month(opportunity.entry_time)
    existing = [journal.snapshot(month, days) for days in WINDOW_DAYS]
    if all(snapshot is not None for snapshot in existing):
        if any(snapshot["status"] == "WARMUP" for snapshot in existing if snapshot is not None):
            return None
        models = [RidgeModel.from_payload(snapshot["model"]) for snapshot in existing if snapshot is not None]
        hashes = [canonical_hash(snapshot) for snapshot in existing if snapshot is not None]
        return models, hashes

    history = _joined_history(journal)
    snapshots: list[dict[str, object]] = []
    for window_days in WINDOW_DAYS:
        start = month_start - pd.Timedelta(days=window_days)
        train = (
            history.loc[
                (history["entry_time"] >= start)
                & (history["entry_time"] < month_start)
                & (history["outcome_available"] < month_start)
            ]
            if not history.empty
            else history
        )
        if len(train) < MINIMUM_TRAIN:
            snapshots.append(
                {
                    "status": "WARMUP",
                    "model_month": month,
                    "window_days": window_days,
                    "train_count": len(train),
                    "train_keys": [] if train.empty else sorted(train["trade_key"].tolist()),
                }
            )
        else:
            model = fit_ridge(train.loc[:, list(FEATURE_COLUMNS)], train["runner_r"])
            snapshots.append(
                {
                    "status": "READY",
                    "model_month": month,
                    "window_days": window_days,
                    "train_count": len(train),
                    "train_keys": sorted(train["trade_key"].tolist()),
                    "features": list(FEATURE_COLUMNS),
                    "model": model.payload(),
                }
            )
    for snapshot in snapshots:
        journal.record_snapshot(month, int(snapshot["window_days"]), snapshot)
    if any(snapshot["status"] == "WARMUP" for snapshot in snapshots):
        return None
    return (
        [RidgeModel.from_payload(snapshot["model"]) for snapshot in snapshots],
        [canonical_hash(snapshot) for snapshot in snapshots],
    )


def score_opportunity(journal: ShadowJournal, trade_key: str) -> int:
    raw = journal.opportunity(trade_key)
    if raw is None:
        raise ValueError(f"unknown trade_key: {trade_key}")
    opportunity = Opportunity.from_dict(raw)
    month, _ = _month(opportunity.entry_time)
    snapshots = _snapshots_for(journal, opportunity)
    written = 0
    if snapshots is None:
        for policy in POLICIES:
            written += int(
                journal.record_decision(
                    {
                        "policy": policy,
                        "trade_key": trade_key,
                        "status": "WARMUP",
                        "action": None,
                        "reason": "all_component_windows_require_60_completed_forward_rows",
                        "model_month": month,
                        "model_hash": None,
                        "predictions": {},
                    }
                )
            )
        return written

    models, hashes = snapshots
    predictions = [predict(model, opportunity.features) for model in models]
    model_hash = canonical_hash({"component_hashes": hashes})
    prediction_payload = {f"w{days}": value for days, value in zip(WINDOW_DAYS, predictions, strict=True)}
    for policy, settings in POLICIES.items():
        result = policy_action(
            predictions,
            threshold=float(settings["threshold"]),
            penalty=float(settings["penalty"]),
        )
        if settings["buy_only"] and opportunity.side < 0:
            result["action"] = "SKIP"
            result["reason"] = "challenger_buy_only"
        written += int(
            journal.record_decision(
                {
                    "policy": policy,
                    "trade_key": trade_key,
                    "status": "SCORED",
                    "action": result["action"],
                    "reason": result["reason"],
                    "model_month": month,
                    "model_hash": model_hash,
                    "predictions": {**prediction_payload, **result},
                }
            )
        )
    return written


def score_pending(journal: ShadowJournal) -> int:
    opportunities = journal.opportunities()
    if opportunities.empty:
        return 0
    decisions = journal.decisions()
    completed = (
        set()
        if decisions.empty
        else set(decisions.loc[decisions["policy"] == "CHAMPION_R3", "trade_key"])
    )
    total = 0
    for trade_key in opportunities.loc[~opportunities["trade_key"].isin(completed), "trade_key"]:
        total += score_opportunity(journal, str(trade_key))
    return total


def policy_manifest() -> str:
    return json.dumps(POLICIES, sort_keys=True, indent=2)
