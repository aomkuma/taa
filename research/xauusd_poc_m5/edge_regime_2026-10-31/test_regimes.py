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
CONFIGS = ["baseline", "cluster_fade", "trend_pullback", "hybrid"]


def main() -> None:
    profile_path = BASE / "rolling_6h_m5" / "rolling_profiles.csv"
    coverage_path = BASE / "rolling_6h_m5" / "session_coverage.csv"
    profiles = pd.read_csv(profile_path, parse_dates=["signal_bar_open_utc"])
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("close_time").reset_index(drop=True)
    closes = m5.close_time
    cov = pd.read_csv(coverage_path, parse_dates=["session_open_utc", "session_close_utc"])
    valid = cov[cov.included].sort_values("session_open_utc").reset_index(drop=True)
    rank_by_open = dict(zip(valid.session_open_utc, range(len(valid))))
    valid["session_rank"] = np.arange(len(valid))
    end_by_rank = dict(zip(valid.session_rank, valid.session_close_utc))
    start_by_rank = dict(zip(valid.session_rank, valid.session_open_utc))
    profiles["session_rank"] = profiles.session_rank.astype(int)
    bars = m5.set_index("open_time")

    # Features use only completed M5 bars strictly before the candidate bar opens.
    feature_rows = []
    for row in profiles.itertuples(index=False):
        t = row.signal_bar_open_utc
        right = int(closes.searchsorted(t, side="right"))
        mid = int(closes.searchsorted(t - pd.Timedelta(hours=3), side="right"))
        left = int(closes.searchsorted(t - pd.Timedelta(hours=6), side="right"))
        old = m5.iloc[left:mid]
        recent = m5.iloc[mid:right]
        both = m5.iloc[left:right]
        overlap_ratio = 0.0
        if len(old) and len(recent):
            old_lo, old_hi = float(old.low.min()), float(old.high.max())
            recent_lo, recent_hi = float(recent.low.min()), float(recent.high.max())
            narrower = min(old_hi - old_lo, recent_hi - recent_lo)
            overlap = max(0.0, min(old_hi, recent_hi) - max(old_lo, recent_lo))
            overlap_ratio = overlap / narrower if narrower > 0 else 0.0
        if len(both):
            first_open = float(both.open.iloc[0])
            last_close = float(both.close.iloc[-1])
            net = last_close - first_open
            path = float(np.abs(np.diff(np.r_[first_open, both.close.to_numpy()])).sum())
            efficiency = abs(net) / path if path else 0.0
        else:
            net, efficiency = 0.0, 0.0
        cluster_ok = bool(len(old) >= 24 and len(recent) >= 24 and overlap_ratio >= .50)
        trend_ok = bool(efficiency >= .35)
        feature_rows.append({
            "signal_bar_open_utc": t, "old_3h_bars": len(old), "recent_3h_bars": len(recent),
            "range_overlap_ratio": overlap_ratio, "six_hour_net": net,
            "six_hour_efficiency": efficiency, "cluster_ok": cluster_ok, "trend_ok": trend_ok,
        })
    features = pd.DataFrame(feature_rows)
    profiles = profiles.merge(features, on="signal_bar_open_utc", how="left", validate="one_to_one")
    profiles = profiles.merge(m5[["open_time", "close_time", "open", "high", "low", "close"]],
                              left_on="signal_bar_open_utc", right_on="open_time", how="left", validate="one_to_one")
    profiles["session_close_utc"] = profiles.session_rank.map(end_by_rank)
    profiles["session_start_utc"] = profiles.session_rank.map(start_by_rank)
    profiles.to_csv(OUT / "signal_features.csv", index=False)

    cache: OrderedDict = OrderedDict()
    trades = []
    dev_n = int(len(valid) * .70)
    for session_rank, frame in profiles.groupby("session_rank", sort=True):
        frame = frame.sort_values("signal_bar_open_utc").reset_index(drop=True)
        start, end = start_by_rank[int(session_rank)], end_by_rank[int(session_rank)]
        trade_ticks = ticks_between(start, end, cache)
        tick_times = trade_ticks.time_utc
        split = "development" if int(session_rank) < dev_n else "validation"
        for config in CONFIGS:
            occupied_until, used = start, set()
            for row in frame.itertuples(index=False):
                if row.close_time <= occupied_until:
                    continue
                signals = []
                if row.low <= row.VAL + row.touch_zone and row.close > row.VAL:
                    signals.append(("VAL", "long", row.POC, float(row.low) - max(.05, row.spread_median_of_bar_medians)))
                if row.high >= row.VAH - row.touch_zone and row.close < row.VAH:
                    signals.append(("VAH", "short", row.POC, float(row.high) + max(.05, row.spread_median_of_bar_medians)))
                if len(signals) != 1:
                    continue
                for level, side, target, stop in signals:
                    allowed = True
                    if config == "cluster_fade":
                        allowed = bool(row.cluster_ok)
                    elif config == "trend_pullback":
                        allowed = bool(row.trend_ok and ((level == "VAL" and row.six_hour_net > 0) or (level == "VAH" and row.six_hour_net < 0)))
                    elif config == "hybrid":
                        allowed = bool(row.cluster_ok or (row.trend_ok and ((level == "VAL" and row.six_hour_net > 0) or (level == "VAH" and row.six_hour_net < 0))))
                    if not allowed or level in used:
                        continue
                    entry_i = int(tick_times.searchsorted(row.close_time, side="right"))
                    if entry_i >= len(trade_ticks):
                        continue
                    result = simulate(trade_ticks, side, entry_i, stop, target, end)
                    if result is None:
                        continue
                    used.add(level)
                    occupied_until = result["exit_time"]
                    trades.append({
                        "config": config, "session_rank": int(session_rank), "split": split,
                        "session_date_bkk": row.session_date_bkk, "signal_close_utc": row.close_time,
                        "level": level, "side": side, "cluster_ok": row.cluster_ok,
                        "range_overlap_ratio": row.range_overlap_ratio, "six_hour_net": row.six_hour_net,
                        "six_hour_efficiency": row.six_hour_efficiency,
                        "VAL": row.VAL, "POC": row.POC, "VAH": row.VAH,
                        "entry_time": result["entry_time"], "exit_time": result["exit_time"],
                        "entry": result["entry"], "exit": result["exit"], "exit_type": result["exit_type"],
                        "pnl": result["pnl"], "risk": result["risk"], "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan,
                    })
                    break

    tr = pd.DataFrame(trades)
    tr.to_csv(OUT / "trades.csv", index=False)

    def metrics(frame: pd.DataFrame) -> dict:
        pg, pl = frame.loc[frame.pnl > 0, "pnl"].sum(), -frame.loc[frame.pnl < 0, "pnl"].sum()
        rg, rl = frame.loc[frame.r_multiple > 0, "r_multiple"].sum(), -frame.loc[frame.r_multiple < 0, "r_multiple"].sum()
        return {"trades": len(frame), "wins": int((frame.pnl > 0).sum()), "win_rate_pct": 100 * (frame.pnl > 0).mean() if len(frame) else np.nan,
                "net_points_per_oz": frame.pnl.sum(), "net_R": frame.r_multiple.sum(), "mean_R": frame.r_multiple.mean(),
                "profit_factor_points": pg / pl if pl else (np.inf if pg else 0), "profit_factor_R": rg / rl if rl else (np.inf if rg else 0),
                "targets": int((frame.exit_type == "target").sum()), "stops": int((frame.exit_type == "stop").sum())}
    summary_rows = []
    for config in CONFIGS:
        frame = tr[tr.config == config]
        for split in ["development", "validation", "all"]:
            part = frame[frame.split == split] if split != "all" else frame
            summary_rows.append({"config": config, "split": split, **metrics(part)})
    pd.DataFrame(summary_rows).to_csv(OUT / "summary.csv", index=False)

    folds = []
    dev = tr[tr.split == "development"]
    for config in CONFIGS:
        for fold in [0, 1, 2]:
            lo, hi = fold * dev_n // 3, (fold + 1) * dev_n // 3
            part = dev[(dev.config == config) & (dev.session_rank >= lo) & (dev.session_rank < hi)]
            folds.append({"config": config, "fold": fold + 1, **metrics(part)})
    fold_df = pd.DataFrame(folds)
    fold_df.to_csv(OUT / "development_folds.csv", index=False)
    select_rows = []
    for config in CONFIGS:
        f = fold_df[fold_df.config == config]
        dev_trades = int(f.trades.sum())
        positive_folds = int((f.net_R > 0).sum())
        val_r = float(tr[(tr.config == config) & (tr.split == "validation")].r_multiple.sum())
        candidate = dev_trades >= 20 and positive_folds >= 2 and val_r > 0
        select_rows.append({"config": config, "development_trades": dev_trades, "positive_development_folds": positive_folds,
                            "validation_net_R": val_r, "candidate": candidate})
    selection = pd.DataFrame(select_rows)
    selection.to_csv(OUT / "selection.csv", index=False)
    selected = selection.loc[selection.candidate, "config"].iloc[0] if selection.candidate.any() else "NONE"
    (OUT / "selected_config.txt").write_bytes(selected.encode("utf-8"))
    print("Sessions", len(valid), "development", dev_n, "validation", len(valid) - dev_n)
    print("Selected:", selected)
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print("Folds:")
    print(fold_df.to_string(index=False))


if __name__ == "__main__":
    main()
