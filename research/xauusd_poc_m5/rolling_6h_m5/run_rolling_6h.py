from __future__ import annotations

from collections import OrderedDict, deque
from pathlib import Path
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from run_poc_test import HIST_DIR, simulate, ticks_between  # noqa: E402

OUT = Path(__file__).resolve().parent
BIN = 0.10
LOOKBACK = pd.Timedelta(hours=6)


def profile_from_counts(hist: dict[int, int]) -> tuple[float, float, float, int] | None:
    if not hist:
        return None
    low_bin, high_bin = min(hist), max(hist)
    counts = np.zeros(high_bin - low_bin + 1, dtype=np.int64)
    for price_bin, count in hist.items():
        counts[price_bin - low_bin] = count
    total = int(counts.sum())
    if total == 0:
        return None
    poc_i = int(np.argmax(counts))
    left = right = poc_i
    included = int(counts[poc_i])
    target = int(np.ceil(total * 0.70))
    while included < target and (left > 0 or right < len(counts) - 1):
        left_count = int(counts[left - 1]) if left > 0 else -1
        right_count = int(counts[right + 1]) if right < len(counts) - 1 else -1
        if left_count >= right_count:
            left -= 1
            included += int(counts[left])
        else:
            right += 1
            included += int(counts[right])
    return (low_bin + left) * BIN, (low_bin + poc_i) * BIN, (low_bin + right) * BIN, total


def main() -> None:
    d1 = pd.read_parquet(HIST_DIR / "D1.parquet").sort_values("open_time").reset_index(drop=True)
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("open_time").reset_index(drop=True)
    nonempty_counts = [int(((m5.close_time > row.open_time) & (m5.close_time <= row.close_time)).sum()) for row in d1.itertuples(index=False)]
    expected_bars = int(np.median([n for n in nonempty_counts if n]))
    cache: OrderedDict = OrderedDict()
    sessions = []
    for row in d1.itertuples(index=False):
        bars = m5.loc[(m5.close_time > row.open_time) & (m5.close_time <= row.close_time)].copy().reset_index(drop=True)
        if bars.empty:
            continue
        start, end = bars.open_time.iloc[0], bars.close_time.iloc[-1]
        current_ticks = ticks_between(start, end, cache)
        first_gap = (current_ticks.time_utc.iloc[0] - start).total_seconds() if len(current_ticks) else np.inf
        last_gap = (end - current_ticks.time_utc.iloc[-1]).total_seconds() if len(current_ticks) else np.inf
        good = bool(len(current_ticks) and first_gap <= 300 and last_gap <= 300 and len(bars) >= .90 * expected_bars)
        sessions.append({"start": start, "end": end, "bars": bars, "ticks": current_ticks,
                         "tick_count": len(current_ticks), "first_gap_s": first_gap,
                         "last_gap_s": last_gap, "coverage_ok": good})

    eligible = []
    coverage = []
    for i in range(1, len(sessions)):
        current, previous = sessions[i], sessions[i - 1]
        good = current["coverage_ok"] and previous["coverage_ok"]
        coverage.append({"session_open_utc": current["start"], "session_close_utc": current["end"],
                         "session_date_bkk": current["start"].tz_convert("Asia/Bangkok").date().isoformat(),
                         "current_ticks": current["tick_count"], "previous_ticks": previous["tick_count"],
                         "current_first_gap_s": current["first_gap_s"], "current_last_gap_s": current["last_gap_s"],
                         "current_m5_bars": len(current["bars"]), "included": bool(good)})
        if good:
            eligible.append(current)

    trades, profiles = [], []
    dev_n = int(len(eligible) * .70)
    for session_rank, session in enumerate(eligible):
        split = "development" if session_rank < dev_n else "validation"
        start, end, bars, trade_ticks = session["start"], session["end"], session["bars"], session["ticks"]
        look_start = start - LOOKBACK
        profile_bars = m5.loc[(m5.close_time > look_start) & (m5.open_time < end)].copy().reset_index(drop=True)
        window_ticks = ticks_between(look_start, end, cache)
        tick_times = window_ticks.time_utc
        tick_mids = ((window_ticks.bid.to_numpy() + window_ticks.ask.to_numpy()) / 2) if len(window_ticks) else np.array([])
        tick_spreads = (window_ticks.ask.to_numpy() - window_ticks.bid.to_numpy()) if len(window_ticks) else np.array([])

        bar_hists: list[tuple[np.ndarray, np.ndarray]] = []
        bar_spreads: list[float] = []
        for bar in profile_bars.itertuples(index=False):
            lo = max(bar.open_time, look_start)
            a = int(tick_times.searchsorted(lo, side="left"))
            b = int(tick_times.searchsorted(bar.close_time, side="left"))
            if b > a:
                bins = np.floor(tick_mids[a:b] / BIN + .5).astype(np.int64)
                keys, counts = np.unique(bins, return_counts=True)
                bar_hists.append((keys, counts.astype(np.int64)))
                bar_spreads.append(float(np.median(tick_spreads[a:b])))
            else:
                bar_hists.append((np.array([], dtype=np.int64), np.array([], dtype=np.int64)))
                bar_spreads.append(np.nan)

        running: dict[int, int] = {}
        active: deque[int] = deque()
        ptr = 0
        context_closes = profile_bars.close_time
        used, occupied_until = set(), start
        trade_times = trade_ticks.time_utc
        for bar in bars.itertuples(index=False):
            cutoff = bar.open_time - LOOKBACK
            while active and context_closes.iloc[active[0]] <= cutoff:
                old = active.popleft()
                keys, counts = bar_hists[old]
                for k, value in zip(keys, counts):
                    new_value = running.get(int(k), 0) - int(value)
                    if new_value <= 0:
                        running.pop(int(k), None)
                    else:
                        running[int(k)] = new_value
            while ptr < len(profile_bars) and context_closes.iloc[ptr] <= bar.open_time:
                if context_closes.iloc[ptr] > cutoff:
                    active.append(ptr)
                    keys, counts = bar_hists[ptr]
                    for k, value in zip(keys, counts):
                        running[int(k)] = running.get(int(k), 0) + int(value)
                ptr += 1
            # A newly added bar can already be outside the trailing six-hour window.
            while active and context_closes.iloc[active[0]] <= cutoff:
                old = active.popleft()
                keys, counts = bar_hists[old]
                for k, value in zip(keys, counts):
                    new_value = running.get(int(k), 0) - int(value)
                    if new_value <= 0:
                        running.pop(int(k), None)
                    else:
                        running[int(k)] = new_value
            if bar.close_time <= occupied_until:
                continue
            result_profile = profile_from_counts(running)
            active_spreads = [bar_spreads[k] for k in active if np.isfinite(bar_spreads[k])]
            if result_profile is None or not active_spreads:
                continue
            val, poc, vah, window_ticks_n = result_profile
            spread = float(np.median(active_spreads))
            zone, stop_pad = max(.05, 2 * spread), max(.05, spread)
            profiles.append({"session_rank": session_rank, "split": split,
                             "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(),
                             "signal_bar_open_utc": bar.open_time, "profile_ticks": window_ticks_n,
                             "profile_m5_bars": len(active), "VAL": val, "POC": poc, "VAH": vah,
                             "spread_median_of_bar_medians": spread, "touch_zone": zone})

            signals = []
            if bar.low <= val + zone and bar.close > val:
                signals.append(("VAL", "long", poc, float(bar.low) - stop_pad))
            if bar.high >= vah - zone and bar.close < vah:
                signals.append(("VAH", "short", poc, float(bar.high) + stop_pad))
            if len(signals) != 1:
                continue
            level, side, target, stop = signals[0]
            if level in used:
                continue
            entry_i = int(trade_times.searchsorted(bar.close_time, side="right"))
            if entry_i >= len(trade_ticks):
                continue
            result = simulate(trade_ticks, side, entry_i, stop, target, end)
            if result is None:
                continue
            used.add(level)
            occupied_until = result["exit_time"]
            trades.append({"session_rank": session_rank, "split": split,
                           "session_open_utc": start, "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(),
                           "signal_close_utc": bar.close_time, "level": level, "side": side,
                           "level_value": val if level == "VAL" else vah, "val": val, "poc": poc, "vah": vah,
                           "profile_ticks": window_ticks_n, "profile_m5_bars": len(active), "zone": zone,
                           **result, "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan})

    cov, prof, tr = pd.DataFrame(coverage), pd.DataFrame(profiles), pd.DataFrame(trades)
    cov.to_csv(OUT / "session_coverage.csv", index=False)
    prof.to_csv(OUT / "rolling_profiles.csv", index=False)
    tr.to_csv(OUT / "trades.csv", index=False)
    rows = []
    for split in ["development", "validation", "all"]:
        frame = tr[tr.split == split] if split != "all" else tr
        gains, losses = frame.loc[frame.pnl > 0, "pnl"].sum(), -frame.loc[frame.pnl < 0, "pnl"].sum()
        rg, rl = frame.loc[frame.r_multiple > 0, "r_multiple"].sum(), -frame.loc[frame.r_multiple < 0, "r_multiple"].sum()
        rows.append({"split": split, "trades": len(frame), "wins": int((frame.pnl > 0).sum()),
                     "win_rate_pct": 100 * (frame.pnl > 0).mean() if len(frame) else np.nan,
                     "net_points_per_oz": frame.pnl.sum(), "net_R": frame.r_multiple.sum(),
                     "mean_R": frame.r_multiple.mean(), "profit_factor_points": gains / losses if losses else (np.inf if gains else 0),
                     "profit_factor_R": rg / rl if rl else (np.inf if rg else 0),
                     "targets": int((frame.exit_type == "target").sum()), "stops": int((frame.exit_type == "stop").sum()),
                     "session_closes": int((frame.exit_type == "session_close").sum())})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary.csv", index=False)
    print("Eligible sessions", len(eligible), "development", dev_n, "validation", len(eligible)-dev_n)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
