"""Independently replay frozen P2 entries and all four exits after the one validation run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from tr1.boundaries import P2, period_for
from tr1.data import TickStore, load_m1
from verify_exits import independent_events, independent_exit, read_path
from verify_opportunities import (
    aggregate_independently,
    atr_independently,
    pivot_indices,
    reconstruct_candidate,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
TICK_ROOT = REPO / "data" / "ticks" / "XAUUSD"


class VerificationError(AssertionError):
    """Independent P2 reconstruction differs from a frozen artifact."""


def equal(actual: object, expected: object) -> bool:
    if pd.isna(actual) and pd.isna(expected):
        return True
    if isinstance(actual, (float, np.floating)) or isinstance(expected, (float, np.floating)):
        return bool(np.isclose(float(actual), float(expected), rtol=1e-9, atol=1e-9))
    return bool(actual == expected)


def require(entry_id: int, scope: str, field: str, actual: object, expected: object) -> None:
    if not equal(actual, expected):
        raise VerificationError(
            f"entry {entry_id} {scope} {field}: reconstructed {actual!r}, saved {expected!r}"
        )


def main() -> None:
    period = period_for(P2.name, allow_validation=True, allow_exam=False)
    entries = pd.read_parquet(HERE / "frozen_entries_p2.parquet")
    results = pd.read_parquet(HERE / "frozen_results_p2.parquet")
    m1 = load_m1(BAR_PATH, period, warmup_start=period.start - pd.Timedelta(days=50))
    bars = {
        "M1": aggregate_independently(m1, 1),
        "M5": aggregate_independently(m1, 5),
        "M15": aggregate_independently(m1, 15),
    }
    atrs = {name: atr_independently(frame) for name, frame in bars.items()}
    pivots = {
        name: {kind: pivot_indices(frame, kind) for kind in ("low", "high")} for name, frame in bars.items()
    }
    h1 = aggregate_independently(m1, 60)
    h1_atr = atr_independently(h1)
    store = TickStore(TICK_ROOT, period, cache_days=4)
    entry_checks = 0
    exit_checks = 0
    candidate_mapping = {
        "reference": "reference",
        "h1_atr": "h1_atr",
        "side": "side",
        "impulse_decision": "impulse_decision",
        "pivot_time": "pivot_time",
        "pivot_price": "pivot_price",
        "pivot_available": "pivot_available",
        "pullback_ratio": "pullback_ratio",
        "decision_time": "decision_time",
        "entry_atr": "entry_atr",
    }
    exit_fields = [
        "complete",
        "exit_time",
        "exit_price",
        "reason",
        "r",
        "holding_minutes",
        "runner_activated",
        "partial_taken",
        "graduated",
        "final_stop",
    ]
    for entry_id, entry in entries.iterrows():
        descriptor = entry.copy()
        descriptor["threshold"] = 0.25
        descriptor["timeframe"] = "M1"
        candidate = reconstruct_candidate(
            descriptor,
            m1,
            h1,
            h1_atr,
            bars["M1"],
            atrs["M1"],
            pivots["M1"],
        )
        for candidate_field, saved_field in candidate_mapping.items():
            require(entry_id, "entry", saved_field, getattr(candidate, candidate_field), entry[saved_field])
            entry_checks += 1
        decision = pd.Timestamp(entry["decision_time"])
        fill_ticks = store.span(decision, min(decision + pd.Timedelta(minutes=5), period.end))
        if fill_ticks.empty:
            raise VerificationError(f"entry {entry_id} has no independent fill")
        quote = fill_ticks.iloc[0]
        side = int(entry["side"])
        fill = float(quote["ask"] if side > 0 else quote["bid"])
        spread = float(quote["ask"] - quote["bid"])
        buffer = max(spread, 0.10 * candidate.entry_atr)
        stop = candidate.pivot_price - buffer if side > 0 else candidate.pivot_price + buffer
        risk = (fill - stop) * side
        derived = {
            "entry_time": pd.Timestamp(quote["time_utc"]),
            "entry": fill,
            "spread": spread,
            "stop": stop,
            "risk": risk,
            "risk_h1": risk / candidate.h1_atr,
        }
        for field, actual in derived.items():
            require(entry_id, "entry", field, actual, entry[field])
            entry_checks += 1
        entry_time = pd.Timestamp(entry["entry_time"])
        end = entry_time + pd.Timedelta(hours=8)
        path = read_path(store, entry_time, end)
        events: list[dict[str, object]] = []
        for timeframe in ("M5", "M15"):
            events.extend(
                independent_events(
                    bars[timeframe],
                    atrs[timeframe],
                    pivots[timeframe],
                    timeframe,
                    side,
                    entry_time,
                    spread,
                    min(end, period.end),
                )
            )
        for family in ("FAST", "SWING", "SPLIT", "STATE"):
            expected = results.loc[(results["entry_id"] == entry_id) & (results["family"] == family)].iloc[0]
            actual = independent_exit(family, path, side, fill, stop, entry_time, events)
            for field in exit_fields:
                require(entry_id, family, field, actual[field], expected[field])
                exit_checks += 1
    if any(day >= period.end for day in store.opened):
        raise VerificationError("P2 verifier crossed into the exam period")
    report = "\n".join(
        [
            "TR1 independent frozen P2 replay",
            f"entries replayed: {len(entries)}",
            f"entry field checks: {entry_checks}",
            f"exit rows replayed: {len(results)}",
            f"exit field checks: {exit_checks}",
            f"latest tick day opened: {max(store.opened).date() if store.opened else None}",
            "result: PASS",
            "Producer opportunity/exit/structure modules were not imported by the verifier logic.",
            "The exam period was not opened.",
            "",
        ]
    )
    (HERE / "out_verify_frozen_p2.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
