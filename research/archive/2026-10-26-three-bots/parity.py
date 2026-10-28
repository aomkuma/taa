"""Compare research trades with the new strategies in the application backtest engine.

Run from the repository root with ``.venv\\Scripts\\python research\\2026-10-26-three-bots\\parity.py``.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import audit  # noqa: E402
import bots  # noqa: E402

from app.backtest.runner import load_history, run_backtest  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.engine.decision_engine import DecisionEngine  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.registry import StrategySet  # noqa: E402

NAMES = ("trend_box_down", "trend_box_up", "range_break")
BOT_NAMES = dict(zip(NAMES, ("DOWN", "UP", "RANGE"), strict=True))
START = datetime(2025, 10, 20, tzinfo=UTC)
END = datetime(2026, 10, 24, tzinfo=UTC)


def _decision_key(strategy: str, at: object, side: str) -> tuple[str, str, str]:
    stamp = pd.Timestamp(at)
    return strategy, stamp.tz_convert("UTC").isoformat(), side


def main() -> None:
    settings = load_settings()
    config = settings.config
    lane = config.lane("three_bots")
    enabled = lane.model_copy(
        update={
            "strategies": lane.strategies.model_copy(
                update={
                    "items": [item.model_copy(update={"enabled": True}) for item in lane.strategies.items]
                }
            )
        }
    )
    # Keep risk-book guards from ending a signal-parity sample before the reference window ends. These
    # overrides exist only on this in-memory backtest config; the app config and any account are untouched.
    parity_risk = config.risk.model_copy(
        update={
            "max_positions_per_symbol": 2,
            "max_daily_loss_percent": 35.0,
            "max_weekly_loss_percent": 35.0,
            "max_account_drawdown_percent": 60.0,
            "max_consecutive_losses": 50,
            "consecutive_loss_pause_hours": 0.0,
        }
    )
    run_config = config.model_copy(update={"lanes": [enabled], "risk": parity_risk})
    store = ParquetHistoryStore(ROOT / "data" / "history")
    reference_frames = audit.load()
    reference: dict[str, list[bots.Trade]] = {name: [] for name in NAMES}
    for bot_name, params in audit.BEST.items():
        strategy = next(name for name, bot in BOT_NAMES.items() if bot == bot_name)
        if bot_name in {"UP", "RANGE"}:
            params = replace(params, exit_mode="be", be_at=0.5)
        reference[strategy] = bots.run(reference_frames, params)
    observed_signals: dict[tuple[str, str], tuple[str, tuple[str, ...], str]] = {}
    observed_decisions: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {}
    original_evaluate, original_decide = StrategySet.evaluate, DecisionEngine.decide

    def capture_signals(strategy_set: StrategySet, ctx: object) -> list:
        signals = original_evaluate(strategy_set, ctx)  # type: ignore[arg-type]
        at = pd.Timestamp(ctx.decision_time_utc).tz_convert("UTC").isoformat()  # type: ignore[attr-defined]
        for signal in signals:
            key = signal.strategy, at
            if signal.strategy in NAMES:
                observed_signals[key] = (signal.action.value, signal.reason_codes, signal.explanation)
        return signals

    def capture_decisions(engine: DecisionEngine, request: object) -> object:
        record = original_decide(engine, request)  # type: ignore[arg-type]
        signal = request.signal  # type: ignore[attr-defined]
        key = signal.strategy, pd.Timestamp(signal.data_timestamp_utc).tz_convert("UTC").isoformat()
        if signal.strategy in NAMES:
            observed_decisions[key] = (record.decision.value, tuple(record.reason_codes))
        return record

    tfs = {"XAUUSD": (Timeframe.M1, Timeframe.M5, Timeframe.H1)}
    loaded = load_history(
        store,
        "FBS-Demo",
        ["XAUUSD"],
        tfs,
        account_currency=run_config.backtest.account_currency,
        start=START - timedelta(days=60),
        end=END,
    )
    StrategySet.evaluate = capture_signals  # type: ignore[method-assign]
    DecisionEngine.decide = capture_decisions  # type: ignore[method-assign]
    try:
        engine, _ = run_backtest(
            run_config,
            loaded,
            config_hash="three-bots-parity",
            strategy_names=NAMES,
            start=START,
            end=END,
            detectors=(),
            portfolio=True,
        )
    finally:
        StrategySet.evaluate = original_evaluate  # type: ignore[method-assign]
        DecisionEngine.decide = original_decide  # type: ignore[method-assign]

    engine_rows = {
        name: [
            row
            for row in engine.journal.values()
            if row["strategy"] == name and row["action"] in ("BUY", "SELL")
        ]
        for name in NAMES
    }
    sys.stdout.write(
        "| strategy | research trades | engine trades | research R/trade | research total R | "
        "engine R/trade | engine total R | decisions matched |\n"
    )
    sys.stdout.write("|---|---:|---:|---:|---:|---:|---:|---:|\n")
    reference_keys: dict[str, set[tuple[str, str, str]]] = {}
    engine_keys: dict[str, set[tuple[str, str, str]]] = {}
    for name in NAMES:
        ref = reference[name]
        rows = engine_rows[name]
        ref_r = [t.r for t in ref]
        eng_trades = [t for t in engine.trades if t.strategy == name]
        eng_r = [t.r_multiple or 0.0 for t in eng_trades]
        rkeys = {_decision_key(name, t.at, "SELL" if t.side == "SELL" else "BUY") for t in ref}
        ekeys = {_decision_key(name, row["decided_at"], row["action"]) for row in rows}
        reference_keys[name], engine_keys[name] = rkeys, ekeys
        matched = len(rkeys & ekeys)
        sys.stdout.write(
            f"| {name} | {len(ref)} | {len(eng_trades)} | "
            f"{(sum(ref_r) / len(ref_r)) if ref_r else 0:+.3f} | {sum(ref_r):+.1f} | "
            f"{(sum(eng_r) / len(eng_r)) if eng_r else 0:+.3f} | {sum(eng_r):+.1f} | "
            f"{matched}/{max(1, len(rkeys))} ({matched / max(1, len(rkeys)):.1%}) |\n"
        )
    sys.stdout.write("\n## Unmatched decisions\n")
    sys.stdout.write(
        f"Engine decision outcomes: {dict(engine.decisions)}; rejection codes: {dict(engine.rejections)}\n"
    )
    for name in NAMES:
        unmatched_ref = sorted(reference_keys[name] - engine_keys[name])
        unmatched_engine = sorted(engine_keys[name] - reference_keys[name])
        for _, at, side in unmatched_ref:
            key = name, at
            signal = observed_signals.get(key)
            decision = observed_decisions.get(key)
            siblings = {
                other: (observed_signals.get((other, at)), observed_decisions.get((other, at)))
                for other in NAMES
                if other != name
            }
            accepted_sibling = next(
                (
                    other
                    for other in NAMES
                    if other != name and any(k[1] == at for k in engine_keys.get(other, set()))
                ),
                None,
            )
            if signal is None:
                cause = "the engine has no strategy evaluation recorded at that M5 close"
            elif signal[0] == "HOLD":
                cause = f"engine strategy held with {signal[1]}"
            elif decision is not None and decision[0] != "ACCEPT":
                cause = f"engine decision rejected the signal with {decision[1]}"
            elif accepted_sibling is not None:
                cause = f"lane arbitration accepted {accepted_sibling} at the same close"
            elif any(sig is not None and sig[0] in ("BUY", "SELL") for sig, _ in siblings.values()):
                cause = f"lane arbitration selected a sibling signal; sibling results={siblings}"
            elif decision is not None:
                cause = f"engine decision was {decision[0]} with {decision[1]}"
            else:
                cause = f"engine signal was {signal[0]} ({signal[1]}); no accepted same-bar journal entry"
            sys.stdout.write(f"- research only: {name} XAUUSD {side} {at}; {cause}.\n")
        for _, at, side in unmatched_engine:
            signal = observed_signals.get((name, at))
            decision = observed_decisions.get((name, at))
            cause = (
                f"strategy signal={signal[0]} reason_codes={signal[1]}"
                if signal is not None
                else "no strategy evaluation was recorded at this engine decision time"
            )
            if decision is not None:
                cause += f"; engine decision={decision[0]} reason_codes={decision[1]}"
            sys.stdout.write(
                f"- engine only: {name} XAUUSD {side} {at}; no research entry at that M5 close. "
                f"{cause}. The executed fill uses the following quote.\n"
            )


if __name__ == "__main__":
    main()
