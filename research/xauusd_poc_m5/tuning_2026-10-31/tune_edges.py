from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from run_poc_test import HIST_DIR, profile, simulate, ticks_between  # noqa: E402

OUT = Path(__file__).resolve().parent
CONFIGS = [
    (confirm, acceptance)
    for acceptance in ["none", "permanent_2", "temporary_2"]
    for confirm in [0, 1]
]


def disabled_masks(closes: np.ndarray, val: float, vah: float, mode: str) -> tuple[np.ndarray, np.ndarray]:
    val_mask = np.zeros(len(closes), dtype=bool)
    vah_mask = np.zeros(len(closes), dtype=bool)
    if mode == "none":
        return val_mask, vah_mask
    permanent = mode == "permanent_2"
    for edge, boundary, mask, outside_test, inside_test in [
        ("VAL", val, val_mask, lambda x: x < val, lambda x: x > val),
        ("VAH", vah, vah_mask, lambda x: x > vah, lambda x: x < vah),
    ]:
        del edge, boundary
        state = False
        outside_run = inside_run = 0
        for j, close in enumerate(closes):
            outside_run = outside_run + 1 if outside_test(close) else 0
            if outside_run >= 2:
                state = True
            if state and not permanent:
                inside_run = inside_run + 1 if inside_test(close) else 0
                if inside_run >= 2:
                    state = False
                    outside_run = 0
                    inside_run = 0
            mask[j] = state
    return val_mask, vah_mask


def main() -> None:
    d1 = pd.read_parquet(HIST_DIR / "D1.parquet").sort_values("open_time").reset_index(drop=True)
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("close_time").reset_index(drop=True)
    counts = [int(((m5.close_time > row.open_time) & (m5.close_time <= row.close_time)).sum()) for row in d1.itertuples(index=False)]
    expected_bars = int(np.median([n for n in counts if n]))
    cache: OrderedDict = OrderedDict()
    coverage, levels, all_trades = [], [], []
    for i in range(1, len(d1)):
        prev, cur = d1.iloc[i - 1], d1.iloc[i]
        prev_bars = m5.loc[(m5.close_time > prev.open_time) & (m5.close_time <= prev.close_time)]
        bars = m5.loc[(m5.close_time > cur.open_time) & (m5.close_time <= cur.close_time)].copy().reset_index(drop=True)
        if prev_bars.empty or bars.empty:
            continue
        prior_start, prior_end = prev_bars.open_time.iloc[0], prev_bars.close_time.iloc[-1]
        start, end = bars.open_time.iloc[0], bars.close_time.iloc[-1]
        prev_ticks = ticks_between(prior_start, prior_end, cache)
        curr_ticks = ticks_between(start, end, cache)
        gaps = [
            (prev_ticks.time_utc.iloc[0] - prior_start).total_seconds() if len(prev_ticks) else np.inf,
            (prior_end - prev_ticks.time_utc.iloc[-1]).total_seconds() if len(prev_ticks) else np.inf,
            (curr_ticks.time_utc.iloc[0] - start).total_seconds() if len(curr_ticks) else np.inf,
            (end - curr_ticks.time_utc.iloc[-1]).total_seconds() if len(curr_ticks) else np.inf,
        ]
        ok = bool(len(prev_ticks) and len(curr_ticks) and max(gaps) <= 300 and len(bars) >= 0.90 * expected_bars)
        coverage.append({"session_open_utc": start, "session_close_utc": end, "prior_ticks": len(prev_ticks), "session_ticks": len(curr_ticks), "m5_bars": len(bars), "expected_m5_bars": expected_bars, "prior_first_gap_s": gaps[0], "prior_last_gap_s": gaps[1], "current_first_gap_s": gaps[2], "current_last_gap_s": gaps[3], "included": ok})
        if not ok:
            continue

        val, poc, vah, med_spread = profile(prev_ticks)
        zone, stop_pad = max(0.05, 2 * med_spread), max(0.05, med_spread)
        levels.append({"session_open_utc": start, "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(), "prior_quote_ticks": len(prev_ticks), "VAL": val, "POC": poc, "VAH": vah, "median_spread": med_spread, "touch_zone": zone})
        close_arr = bars.close.to_numpy()
        tick_times = curr_ticks.time_utc
        for confirm_n, acceptance in CONFIGS:
            val_disabled, vah_disabled = disabled_masks(close_arr, val, vah, acceptance)
            occupied_until, used = start, set()
            config = f"confirm_{confirm_n}__{acceptance}"
            for j in range(len(bars) - confirm_n):
                signal = bars.iloc[j]
                confirm = bars.iloc[j + confirm_n]
                if signal.close_time <= occupied_until or confirm.close_time <= occupied_until:
                    continue
                candidates = []
                if not val_disabled[j] and signal.low <= val + zone and signal.close > val:
                    if confirm_n == 0 or confirm.close > val:
                        candidates.append(("VAL", "long", poc, float(confirm.low) - stop_pad))
                if not vah_disabled[j] and signal.high >= vah - zone and signal.close < vah:
                    if confirm_n == 0 or confirm.close < vah:
                        candidates.append(("VAH", "short", poc, float(confirm.high) + stop_pad))
                for level, side, target, stop in candidates:
                    if level in used:
                        continue
                    entry_i = int(tick_times.searchsorted(confirm.close_time, side="right"))
                    if entry_i >= len(curr_ticks):
                        continue
                    result = simulate(curr_ticks, side, entry_i, stop, target, end)
                    if result is None:
                        continue
                    used.add(level)
                    occupied_until = result["exit_time"]
                    all_trades.append({
                        "config": config, "confirm_bars": confirm_n, "acceptance": acceptance,
                        "session_open_utc": start, "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(),
                        "level": level, "side": side, "signal_close_utc": signal.close_time,
                        "entry_confirm_close_utc": confirm.close_time,
                        "level_value": val if level == "VAL" else vah, "val": val, "poc": poc, "vah": vah,
                        "zone": zone, **result,
                        "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan,
                    })
                    break

    cov = pd.DataFrame(coverage).sort_values("session_open_utc").reset_index(drop=True)
    tr = pd.DataFrame(all_trades)
    cov["session_rank"] = -1
    cov.loc[cov.included, "session_rank"] = np.arange(int(cov.included.sum()))
    n_sessions = int(cov.included.sum())
    n_dev = int(n_sessions * 0.70)
    rank_map = dict(zip(cov.loc[cov.included, "session_open_utc"], cov.loc[cov.included, "session_rank"]))
    if not tr.empty:
        tr["session_rank"] = tr.session_open_utc.map(rank_map)
        tr["split"] = np.where(tr.session_rank < n_dev, "development", "validation")
        tr["fold"] = np.where(tr.session_rank < n_dev, np.minimum((tr.session_rank * 3 // max(n_dev, 1)).astype(int) + 1, 3).astype(str), "validation")
    lev = pd.DataFrame(levels)
    cov.to_csv(OUT / "session_coverage.csv", index=False)
    lev.to_csv(OUT / "daily_levels.csv", index=False)
    tr.to_csv(OUT / "trades_all_configs.csv", index=False)

    def metrics(frame: pd.DataFrame) -> dict:
        gains = frame.loc[frame.r_multiple > 0, "r_multiple"].sum()
        losses = -frame.loc[frame.r_multiple < 0, "r_multiple"].sum()
        return {"trades": len(frame), "wins": int((frame.pnl > 0).sum()), "win_rate_pct": 100 * (frame.pnl > 0).mean() if len(frame) else np.nan,
                "net_points_per_oz": frame.pnl.sum(), "net_R": frame.r_multiple.sum(), "mean_R": frame.r_multiple.mean(),
                "profit_factor_R": gains / losses if losses else (np.inf if gains else 0), "targets": int((frame.exit_type == "target").sum()), "stops": int((frame.exit_type == "stop").sum())}

    summary_rows = []
    for config, full in tr.groupby("config"):
        for split in ["development", "validation"]:
            frame = full[full.split == split]
            summary_rows.append({"config": config, "split": split, **metrics(frame)})
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "summary.csv", index=False)

    dev = tr[tr.split == "development"]
    fold_rows = []
    for config in [f"confirm_{c}__{a}" for a in ["none", "permanent_2", "temporary_2"] for c in [0, 1]]:
        for fold in ["1", "2", "3"]:
            frame = dev[(dev.config == config) & (dev.fold == fold)]
            fold_rows.append({"config": config, "fold": fold, **metrics(frame)})
    folds = pd.DataFrame(fold_rows)
    folds.to_csv(OUT / "development_folds.csv", index=False)
    selection = []
    for config in folds.config.unique():
        f = folds[folds.config == config]
        positives = int((f.net_R > 0).sum())
        trades = int(f.trades.sum())
        eligible = trades >= 20 and positives >= 2
        score = float(f.mean_R.median())
        selection.append({"config": config, "development_trades": trades, "positive_folds": positives, "median_fold_mean_R": score, "eligible": eligible})
    sel = pd.DataFrame(selection).sort_values(["eligible", "median_fold_mean_R"], ascending=[False, False])
    sel.to_csv(OUT / "selection.csv", index=False)
    winner = sel.loc[sel.eligible, "config"].iloc[0] if sel.eligible.any() else "NONE"
    (OUT / "selected_config.txt").write_bytes(winner.encode("utf-8"))
    print("Covered sessions", n_sessions, "development", n_dev, "validation", n_sessions - n_dev)
    print("Selected config by preregistered rule:", winner)
    print(summary.to_string(index=False))
    print("Development folds:")
    print(folds.to_string(index=False))


if __name__ == "__main__":
    main()
