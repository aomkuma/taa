# ruff: noqa: E501
"""Trend Runner journal for one short slice: TR1 SPLIT source trades and their RETEST-CONTINUATION V1 re-entries.

Fixed tick pipeline of 2026-10-22 (DEBUG_2026-10-22.md). Week-sized slices only (memory; the machine also runs the
DEMO engine); the reserved exam [2026-04-18, 2026-10-18) is refused before any read.

    .venv\\Scripts\\python research\\2026-10-21-trend-runner-retest-continuation\\pipeline.py 2025-11-03 2025-11-10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from candidate import simulate_historical_diagnostic
from journal_fields import Context, path_excursions, thai, thai_week
from source_ticks import source_trades
from ticks import EXAM_START, TickSource, refuse_exam

HERE = Path(__file__).resolve().parent
WINDOW_TH = {"ASIA": "Asia 07:00", "LONDON": "London 13:00", "NY0830": "NY 08:30"}


def _row(trade_id: str, setup: str, variant: str, window: str, side: int) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "setup": setup,
        "variant": variant,
        "window": WINDOW_TH.get(window, window),
        "side": "BUY" if side > 0 else "SELL",
    }


def run_slice(start: pd.Timestamp, end: pd.Timestamp, *, slippage: float = 0.0) -> pd.DataFrame:
    refuse_exam(start, end)
    entries, m1 = source_trades(start, end)
    quotes = TickSource()
    context = Context(start - pd.Timedelta(days=1), end + pd.Timedelta(days=3), m1)
    rows: list[dict[str, object]] = []
    for e in entries.itertuples(index=False):
        side = int(e.side)
        anchor = pd.Timestamp(e.anchor)
        tr1_id = f"TR1-{anchor.tz_convert('Asia/Bangkok').date().isoformat()}-{e.window}"
        entry_time = pd.Timestamp(e.entry_time)
        row = _row(tr1_id, "TREND-RUNNER", "TR1-SPLIT (source)", e.window, side)
        row.update(
            status="COMPLETE" if bool(e.split_complete) else "CENSORED",
            entry_time_utc=entry_time.isoformat(),
            entry_time_thai=thai(entry_time),
            week_thai=thai_week(entry_time),
            entry=float(e.entry),
            stop=float(e.stop),
            target=float(e.entry + side * e.risk),  # the +1R partial (1/3); the rest trails
            entry_spread=float(e.spread),
            initial_risk=float(e.risk),
            exit_time_utc=pd.Timestamp(e.split_exit_time).isoformat() if bool(e.split_complete) else "",
            exit_time_thai=thai(pd.Timestamp(e.split_exit_time)) if bool(e.split_complete) else "",
            exit=float(e.split_exit_price),
            r=float(e.split_r),
            exit_reason=str(e.split_reason) + ("+PARTIAL_1R" if bool(e.split_partial_taken) else ""),
            stopped_before_1r=bool(e.runner_stopped_before_plus1),
            h1_atr_anchor=float(e.h1_atr),
            decision_time_utc=pd.Timestamp(e.decision_time).isoformat(),
            pivot_time_utc=pd.Timestamp(e.pivot_time).isoformat(),
            pivot_price=float(e.pivot_price),
            entry_tf_atr=float(e.entry_atr),
        )
        if bool(e.split_complete):
            path = quotes.span(entry_time, pd.Timestamp(e.split_exit_time))
            row["mfe_r"], row["mae_r"] = path_excursions(
                path, side, float(e.entry), float(e.risk), pd.Timestamp(e.split_exit_time)
            )
        row.update(context.at(entry_time))
        rows.append(row)
        if not bool(e.runner_stopped_before_plus1):
            continue

        stop_time = pd.Timestamp(e.split_exit_time)
        event = {
            "trade_key": tr1_id,
            "stop_time_utc": stop_time,
            "side": side,
            "entry": float(e.entry),
            "stop": float(e.stop),
            "spread": float(e.spread),  # the original fill's tick spread (bug B7)
            "runner_stopped_before_plus1": True,
        }
        warm = (stop_time - pd.Timedelta(hours=3)).floor("5min")
        bars = m1.loc[m1.index >= warm]
        result = simulate_historical_diagnostic(
            event, bars, quotes, exam_start=EXAM_START, earliest_data=warm, slippage=slippage
        )
        v1 = _row(f"RC1-{tr1_id[4:]}", "TREND-RUNNER", "RETEST-CONTINUATION V1", e.window, side)
        v1.update(
            status=result["status"],
            source_trade_id=tr1_id,
            source_stop_time_utc=stop_time.isoformat(),
            source_stop_time_thai=thai(stop_time),
            reclaim_time_utc=str(result.get("reclaim_time_utc", "")),
            retest_time_utc=str(result.get("retest_time_utc", "")),
            confirmation_time_utc=str(result.get("confirmation_time_utc", "")),
        )
        if "entry_time_utc" in result:
            v_entry = pd.Timestamp(result["entry_time_utc"])
            v1.update(
                entry_time_utc=v_entry.isoformat(),
                entry_time_thai=thai(v_entry),
                week_thai=thai_week(v_entry),
                entry=result["entry"],
                stop=result["initial_stop"],
                target=np.nan,  # V1 has no profit target (PLAN.md step 7)
                entry_spread=result["entry_spread"],
                initial_risk=result["initial_risk"],
            )
            v1.update(context.at(v_entry))
        else:
            v1["week_thai"] = thai_week(stop_time)
        if result["status"] == "COMPLETE":
            v1.update(
                exit_time_utc=result["exit_time_utc"],
                exit_time_thai=thai(pd.Timestamp(result["exit_time_utc"])),
                exit=result["exit"],
                r=result["r"],
                exit_reason=result["reason"],
                retest_atr=result["retest_atr"],
                final_stop=result["final_stop"],
                mfe_r=result["mfe_r"],
                mae_r=result["mae_r"],
                holding_minutes=result["holding_minutes"],
            )
        rows.append(v1)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("start")
    parser.add_argument("end")
    parser.add_argument("--out", default=str(HERE / "smoke_2026-10-22"))
    args = parser.parse_args()
    start, end = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC")
    journal = run_slice(start, end)
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    name = f"journal_{start.date()}_{end.date()}.csv"
    journal.to_csv(out / name, index=False)
    print(f"{len(journal)} journal rows -> {out / name}")  # noqa: T201
    print(journal["variant"].value_counts().to_string())  # noqa: T201
    print(journal.groupby("variant")["status"].value_counts().to_string())  # noqa: T201


if __name__ == "__main__":
    main()
