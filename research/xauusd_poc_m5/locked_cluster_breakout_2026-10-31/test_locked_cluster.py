from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from run_poc_test import HIST_DIR, simulate, ticks_between  # noqa: E402

OUT = Path(__file__).resolve().parent
VARIANTS = ["locked_rotation", "rotation_plus_breakout"]


def main() -> None:
    source = BASE / "edge_regime_2026-10-31" / "signal_features.csv"
    frame = pd.read_csv(source, parse_dates=["signal_bar_open_utc", "close_time", "session_start_utc", "session_close_utc"])
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("open_time").reset_index(drop=True)
    coverage = pd.read_csv(BASE / "rolling_6h_m5" / "session_coverage.csv", parse_dates=["session_open_utc", "session_close_utc"])
    valid = coverage[coverage.included].sort_values("session_open_utc").reset_index(drop=True)
    start_by_rank = dict(zip(range(len(valid)), valid.session_open_utc))
    end_by_rank = dict(zip(range(len(valid)), valid.session_close_utc))
    dev_n = int(len(valid) * .70)
    cache: OrderedDict = OrderedDict()
    trades, cluster_logs = [], []

    for rank, day in frame.groupby("session_rank", sort=True):
        day = day.sort_values("signal_bar_open_utc").reset_index(drop=True)
        start, end = start_by_rank[int(rank)], end_by_rank[int(rank)]
        ticks = ticks_between(start, end, cache)
        tick_times = ticks.time_utc
        split = "development" if int(rank) < dev_n else "validation"
        for variant in VARIANTS:
            active = None
            cooldown_until = -1
            occupied_until = start
            clusters_started = clusters_broken = 0
            for i, row in enumerate(day.itertuples(index=False)):
                # Form and freeze a cluster using information available before this bar opened.
                if active is None and i >= cooldown_until and bool(row.cluster_ok):
                    active = {
                        "start_i": i, "val": float(row.VAL), "poc": float(row.POC), "vah": float(row.VAH),
                        "zone": float(row.touch_zone), "pad": max(.05, float(row.spread_median_of_bar_medians)),
                        "width": float(row.VAH - row.VAL), "used": set(), "up_run": 0, "down_run": 0,
                        "phase": "rotation", "break_dir": None, "break_i": None, "retest_deadline": None,
                    }
                    clusters_started += 1
                    cluster_logs.append({"variant": variant, "session_rank": int(rank), "session_date_bkk": row.session_date_bkk,
                                         "cluster_start_utc": row.signal_bar_open_utc, "val": active["val"], "poc": active["poc"],
                                         "vah": active["vah"], "width": active["width"], "formation_overlap": row.range_overlap_ratio})
                if active is None:
                    continue
                age = i - active["start_i"]
                if age >= 72:
                    active = None
                    cooldown_until = i + 6
                    continue

                if active["phase"] == "rotation":
                    active["up_run"] = active["up_run"] + 1 if row.close > active["vah"] else 0
                    active["down_run"] = active["down_run"] + 1 if row.close < active["val"] else 0
                    breakout = "up" if active["up_run"] >= 2 else ("down" if active["down_run"] >= 2 else None)
                    if breakout:
                        clusters_broken += 1
                        if variant == "locked_rotation":
                            active = None
                            cooldown_until = i + 6
                            continue
                        active["phase"] = "breakout_pending"
                        active["break_dir"] = breakout
                        active["break_i"] = i
                        active["retest_deadline"] = i + 6
                        continue

                candidate_signals = []
                if active["phase"] == "rotation":
                    if row.low <= active["val"] + active["zone"] and row.close > active["val"]:
                        candidate_signals.append(("VAL", "long", active["poc"], float(row.low) - active["pad"], "rotation"))
                    if row.high >= active["vah"] - active["zone"] and row.close < active["vah"]:
                        candidate_signals.append(("VAH", "short", active["poc"], float(row.high) + active["pad"], "rotation"))
                elif active["phase"] == "breakout_pending":
                    if i > active["break_i"] and i <= active["retest_deadline"]:
                        if active["break_dir"] == "up" and row.low <= active["vah"] + active["zone"] and row.close > active["vah"]:
                            candidate_signals.append(("VAH_break", "long", active["vah"] + active["width"], float(row.low) - active["pad"], "breakout"))
                        if active["break_dir"] == "down" and row.high >= active["val"] - active["zone"] and row.close < active["val"]:
                            candidate_signals.append(("VAL_break", "short", active["val"] - active["width"], float(row.high) + active["pad"], "breakout"))
                    elif i > active["retest_deadline"]:
                        active = None
                        cooldown_until = i + 6
                        continue

                if len(candidate_signals) != 1 or row.close_time <= occupied_until:
                    continue
                level, side, target, stop, mode = candidate_signals[0]
                used_key = level
                if used_key in active["used"]:
                    continue
                entry_i = int(tick_times.searchsorted(row.close_time, side="right"))
                if entry_i >= len(ticks):
                    continue
                result = simulate(ticks, side, entry_i, stop, target, end)
                if result is None:
                    continue
                active["used"].add(used_key)
                occupied_until = result["exit_time"]
                trades.append({
                    "variant": variant, "session_rank": int(rank), "split": split,
                    "session_date_bkk": row.session_date_bkk, "cluster_start_utc": day.iloc[active["start_i"]].signal_bar_open_utc,
                    "signal_close_utc": row.close_time, "mode": mode, "level": level, "side": side,
                    "cluster_val": active["val"], "cluster_poc": active["poc"], "cluster_vah": active["vah"],
                    "target": target, "stop": stop, "entry_time": result["entry_time"], "exit_time": result["exit_time"],
                    "entry": result["entry"], "exit": result["exit"], "exit_type": result["exit_type"],
                    "pnl": result["pnl"], "risk": result["risk"],
                    "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan,
                })
            # Per-day state summary for audit.
            cluster_logs.append({"variant": variant, "session_rank": int(rank), "session_date_bkk": day.session_date_bkk.iloc[0],
                                 "cluster_start_utc": pd.NaT, "val": np.nan, "poc": np.nan, "vah": np.nan,
                                 "width": np.nan, "formation_overlap": np.nan,
                                 "clusters_started_in_session": clusters_started, "clusters_broken_in_session": clusters_broken})

    tr = pd.DataFrame(trades)
    logs = pd.DataFrame(cluster_logs)
    tr.to_csv(OUT / "trades.csv", index=False)
    logs.to_csv(OUT / "cluster_lifecycle.csv", index=False)

    def metrics(part: pd.DataFrame) -> dict:
        pg, pl = part.loc[part.pnl > 0, "pnl"].sum(), -part.loc[part.pnl < 0, "pnl"].sum()
        rg, rl = part.loc[part.r_multiple > 0, "r_multiple"].sum(), -part.loc[part.r_multiple < 0, "r_multiple"].sum()
        return {"trades": len(part), "wins": int((part.pnl > 0).sum()), "win_rate_pct": 100 * (part.pnl > 0).mean() if len(part) else np.nan,
                "net_points_per_oz": part.pnl.sum(), "net_R": part.r_multiple.sum(), "mean_R": part.r_multiple.mean(),
                "profit_factor_points": pg / pl if pl else (np.inf if pg else 0), "profit_factor_R": rg / rl if rl else (np.inf if rg else 0),
                "targets": int((part.exit_type == "target").sum()), "stops": int((part.exit_type == "stop").sum())}

    rows, fold_rows, candidate_rows = [], [], []
    for variant in VARIANTS:
        part = tr[tr.variant == variant]
        for split_name in ["development", "validation", "all"]:
            split_part = part[part.split == split_name] if split_name != "all" else part
            rows.append({"variant": variant, "split": split_name, **metrics(split_part)})
        vals = []
        for fold in range(3):
            lo, hi = fold * dev_n // 3, (fold + 1) * dev_n // 3
            ff = part[(part.session_rank >= lo) & (part.session_rank < hi)]
            met = metrics(ff)
            fold_rows.append({"variant": variant, "fold": fold + 1, **met})
            vals.append(met["net_R"])
        dev_trades = int(len(part[part.split == "development"]))
        validation_r = float(part.loc[part.split == "validation", "r_multiple"].sum())
        candidate_rows.append({"variant": variant, "development_trades": dev_trades,
                               "positive_folds": int(sum(v > 0 for v in vals)), "validation_net_R": validation_r,
                               "candidate": bool(dev_trades >= 20 and sum(v > 0 for v in vals) >= 2 and validation_r > 0)})
    summary = pd.DataFrame(rows)
    folds = pd.DataFrame(fold_rows)
    selection = pd.DataFrame(candidate_rows)
    summary.to_csv(OUT / "summary.csv", index=False)
    folds.to_csv(OUT / "development_folds.csv", index=False)
    selection.to_csv(OUT / "selection.csv", index=False)
    selected = selection.loc[selection.candidate, "variant"].iloc[0] if selection.candidate.any() else "NONE"
    (OUT / "selected_variant.txt").write_bytes(selected.encode("utf-8"))
    print("Covered sessions", len(valid), "development", dev_n, "validation", len(valid)-dev_n, "selected", selected)
    print(summary.to_string(index=False))
    print(folds.to_string(index=False))


if __name__ == "__main__":
    main()
