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


def main() -> None:
    d1 = pd.read_parquet(HIST_DIR / "D1.parquet").sort_values("open_time").reset_index(drop=True)
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("close_time").reset_index(drop=True)
    counts = [int(((m5.close_time > row.open_time) & (m5.close_time <= row.close_time)).sum()) for row in d1.itertuples(index=False)]
    expected_bars = int(np.median([n for n in counts if n]))
    cache: OrderedDict = OrderedDict()
    sessions = []
    for i, row in enumerate(d1.itertuples(index=False)):
        bars = m5.loc[(m5.close_time > row.open_time) & (m5.close_time <= row.close_time)].copy().reset_index(drop=True)
        if bars.empty:
            continue
        start, end = bars.open_time.iloc[0], bars.close_time.iloc[-1]
        ticks = ticks_between(start, end, cache)
        gaps = [
            (ticks.time_utc.iloc[0] - start).total_seconds() if len(ticks) else np.inf,
            (end - ticks.time_utc.iloc[-1]).total_seconds() if len(ticks) else np.inf,
        ]
        ok = bool(len(ticks) and max(gaps) <= 300 and len(bars) >= .90 * expected_bars)
        levels = profile(ticks) if ok else None
        sessions.append({
            "d1_index": i, "start": start, "end": end, "bars": bars,
            "tick_count": len(ticks), "first_gap_s": gaps[0], "last_gap_s": gaps[1],
            "m5_count": len(bars), "coverage_ok": ok, "levels": levels,
        })

    candidates, coverage = [], []
    for j in range(2, len(sessions)):
        current, prev, prev2 = sessions[j], sessions[j - 1], sessions[j - 2]
        all_ok = current["coverage_ok"] and prev["coverage_ok"] and prev2["coverage_ok"]
        ratio = np.nan
        if prev["levels"] is not None and prev2["levels"] is not None:
            val1, _, vah1, _ = prev["levels"]
            val2, _, vah2, _ = prev2["levels"]
            width = min(vah1 - val1, vah2 - val2)
            overlap = max(0.0, min(vah1, vah2) - max(val1, val2))
            ratio = overlap / width if width > 0 else 0.0
        cluster = bool(all_ok and ratio >= 0.50)
        coverage.append({
            "session_open_utc": current["start"], "session_date_bkk": current["start"].tz_convert("Asia/Bangkok").date().isoformat(),
            "current_coverage_ok": current["coverage_ok"], "prior_coverage_ok": prev["coverage_ok"],
            "two_back_coverage_ok": prev2["coverage_ok"], "common_sample": bool(all_ok),
            "va_overlap_ratio": ratio, "cluster_filter_pass": cluster,
        })
        if not all_ok:
            continue
        val, poc, vah, med_spread = prev["levels"]
        candidates.append({
            "session_open_utc": current["start"], "session_close_utc": current["end"],
            "session_date_bkk": current["start"].tz_convert("Asia/Bangkok").date().isoformat(),
            "bars": current["bars"], "val": val, "poc": poc, "vah": vah,
            "median_spread": med_spread, "zone": max(.05, 2 * med_spread),
            "stop_pad": max(.05, med_spread), "va_overlap_ratio": ratio,
            "cluster_filter_pass": cluster, "ticks": ticks_between(current["start"], current["end"], cache),
        })

    candidate_count = len(candidates)
    dev_count = int(candidate_count * .70)
    trades = []
    levels_out = []
    for session_rank, item in enumerate(candidates):
        levels_out.append({k: item[k] for k in ["session_open_utc", "session_date_bkk", "val", "poc", "vah", "median_spread", "zone", "va_overlap_ratio", "cluster_filter_pass"]})
        split = "development" if session_rank < dev_count else "validation"
        for strategy in ["baseline", "cluster_only"]:
            if strategy == "cluster_only" and not item["cluster_filter_pass"]:
                continue
            bars, ticks = item["bars"], item["ticks"]
            occupied_until, used = item["session_open_utc"], set()
            tick_times = ticks.time_utc
            for bar in bars.itertuples(index=False):
                if bar.close_time <= occupied_until:
                    continue
                candidate_signals = []
                if bar.low <= item["val"] + item["zone"] and bar.close > item["val"]:
                    candidate_signals.append(("VAL", "long", item["poc"], float(bar.low) - item["stop_pad"]))
                if bar.high >= item["vah"] - item["zone"] and bar.close < item["vah"]:
                    candidate_signals.append(("VAH", "short", item["poc"], float(bar.high) + item["stop_pad"]))
                for level, side, target, stop in candidate_signals:
                    if level in used:
                        continue
                    idx = int(tick_times.searchsorted(bar.close_time, side="right"))
                    if idx >= len(ticks):
                        continue
                    result = simulate(ticks, side, idx, stop, target, item["session_close_utc"])
                    if result is None:
                        continue
                    used.add(level)
                    occupied_until = result["exit_time"]
                    trades.append({
                        "strategy": strategy, "session_rank": session_rank, "split": split,
                        "session_open_utc": item["session_open_utc"], "session_date_bkk": item["session_date_bkk"],
                        "va_overlap_ratio": item["va_overlap_ratio"], "level": level, "side": side,
                        "signal_close_utc": bar.close_time, "level_value": item["val"] if level == "VAL" else item["vah"],
                        "val": item["val"], "poc": item["poc"], "vah": item["vah"], "zone": item["zone"],
                        **result, "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan,
                    })
                    break

    cov = pd.DataFrame(coverage)
    lev = pd.DataFrame(levels_out)
    tr = pd.DataFrame(trades)
    cov.to_csv(OUT / "cluster_eligibility.csv", index=False)
    lev.to_csv(OUT / "daily_levels_and_cluster.csv", index=False)
    tr.to_csv(OUT / "trades.csv", index=False)

    def metrics(frame: pd.DataFrame) -> dict:
        wins = frame.loc[frame.pnl > 0, "pnl"].sum()
        losses = -frame.loc[frame.pnl < 0, "pnl"].sum()
        r_wins = frame.loc[frame.r_multiple > 0, "r_multiple"].sum()
        r_losses = -frame.loc[frame.r_multiple < 0, "r_multiple"].sum()
        return {"trades": len(frame), "wins": int((frame.pnl > 0).sum()), "win_rate_pct": 100 * (frame.pnl > 0).mean() if len(frame) else np.nan,
                "net_points_per_oz": frame.pnl.sum(), "net_R": frame.r_multiple.sum(), "mean_R": frame.r_multiple.mean(),
                "profit_factor_points": wins / losses if losses else (np.inf if wins else 0),
                "profit_factor_R": r_wins / r_losses if r_losses else (np.inf if r_wins else 0),
                "targets": int((frame.exit_type == "target").sum()), "stops": int((frame.exit_type == "stop").sum())}

    rows = []
    for strategy in ["baseline", "cluster_only"]:
        for split in ["development", "validation", "all"]:
            frame = tr[(tr.strategy == strategy) & ((tr.split == split) if split != "all" else True)]
            rows.append({"strategy": strategy, "split": split, **metrics(frame)})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary.csv", index=False)
    print("M5 sessions", len(sessions), "common three-session sample", candidate_count, "development", dev_count, "validation", candidate_count-dev_count)
    print("Cluster-positive common sessions", int(sum(x["cluster_filter_pass"] for x in candidates)))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
