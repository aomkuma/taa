from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import argparse

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TICK_DIR = ROOT / "data" / "ticks" / "XAUUSD"
HIST_DIR = ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD"
OUT_DIR = Path(__file__).resolve().parent
BIN = 0.10


def tick_day(day: pd.Timestamp, cache: OrderedDict) -> pd.DataFrame:
    key = day.strftime("%Y-%m-%d")
    if key not in cache:
        path = TICK_DIR / f"{key}.parquet"
        if path.exists():
            frame = pd.read_parquet(path, columns=["time_utc", "bid", "ask"])
            frame = frame.dropna().sort_values("time_utc")
        else:
            frame = pd.DataFrame(columns=["time_utc", "bid", "ask"])
        cache[key] = frame
        while len(cache) > 3:
            cache.popitem(last=False)
    else:
        cache.move_to_end(key)
    return cache[key]


def ticks_between(start: pd.Timestamp, end: pd.Timestamp, cache: OrderedDict) -> pd.DataFrame:
    days = pd.date_range(start.normalize(), (end - pd.Timedelta(milliseconds=1)).normalize(), freq="D", tz="UTC")
    parts = []
    for day in days:
        frame = tick_day(day, cache)
        if not frame.empty:
            part = frame.loc[(frame.time_utc >= start) & (frame.time_utc < end)]
            if not part.empty:
                parts.append(part)
    if not parts:
        return pd.DataFrame(columns=["time_utc", "bid", "ask"])
    return pd.concat(parts, ignore_index=True).sort_values("time_utc").reset_index(drop=True)


def profile(ticks: pd.DataFrame) -> tuple[float, float, float, float]:
    mid = (ticks.bid.to_numpy() + ticks.ask.to_numpy()) / 2
    bins = np.floor(mid / BIN + 0.5).astype(np.int64)
    observed_keys, observed_counts = np.unique(bins, return_counts=True)
    keys = np.arange(observed_keys[0], observed_keys[-1] + 1, dtype=np.int64)
    counts = np.zeros(len(keys), dtype=np.int64)
    counts[observed_keys - keys[0]] = observed_counts
    poc_pos = int(np.argmax(counts))
    left = right = poc_pos
    included = int(counts[poc_pos])
    required = int(np.ceil(counts.sum() * 0.70))
    while included < required and (left > 0 or right < len(keys) - 1):
        left_count = counts[left - 1] if left > 0 else -1
        right_count = counts[right + 1] if right < len(keys) - 1 else -1
        if left_count >= right_count:
            left -= 1
            included += int(counts[left])
        else:
            right += 1
            included += int(counts[right])
    spread = float(np.median(ticks.ask.to_numpy() - ticks.bid.to_numpy()))
    return keys[left] * BIN, keys[poc_pos] * BIN, keys[right] * BIN, spread


def simulate(ticks: pd.DataFrame, side: str, entry_i: int, stop: float, target: float, end_time: pd.Timestamp):
    is_long = side == "long"
    entry_row = ticks.iloc[entry_i]
    entry = float(entry_row.ask if is_long else entry_row.bid)
    entry_time = entry_row.time_utc
    if is_long and not (stop < entry < target):
        return None
    if not is_long and not (target < entry < stop):
        return None
    future = ticks.iloc[entry_i + 1:]
    future = future.loc[future.time_utc < end_time]
    for row in future.itertuples(index=False):
        if is_long:
            if row.bid <= stop:
                return {"entry_time": entry_time, "exit_time": row.time_utc, "entry": entry, "exit": float(row.bid), "exit_type": "stop", "pnl": float(row.bid) - entry, "risk": entry - stop}
            if row.bid >= target:
                return {"entry_time": entry_time, "exit_time": row.time_utc, "entry": entry, "exit": float(row.bid), "exit_type": "target", "pnl": float(row.bid) - entry, "risk": entry - stop}
        else:
            if row.ask >= stop:
                return {"entry_time": entry_time, "exit_time": row.time_utc, "entry": entry, "exit": float(row.ask), "exit_type": "stop", "pnl": entry - float(row.ask), "risk": stop - entry}
            if row.ask <= target:
                return {"entry_time": entry_time, "exit_time": row.time_utc, "entry": entry, "exit": float(row.ask), "exit_type": "target", "pnl": entry - float(row.ask), "risk": stop - entry}
    if future.empty:
        return None
    last = future.iloc[-1]
    exit_px = float(last.bid if is_long else last.ask)
    pnl = exit_px - entry if is_long else entry - exit_px
    return {"entry_time": entry_time, "exit_time": last.time_utc, "entry": entry, "exit": exit_px, "exit_type": "session_close", "pnl": pnl, "risk": entry - stop if is_long else stop - entry}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="First active-session UTC date, inclusive (YYYY-MM-DD)")
    parser.add_argument("--end", help="Last active-session UTC date, inclusive (YYYY-MM-DD)")
    parser.add_argument("--output-dir", help="Output directory (defaults to the study folder)")
    parser.add_argument("--edge-only", action="store_true", help="Test VAL/VAH edges only; omit direct POC-line entries")
    args = parser.parse_args()
    global OUT_DIR
    if args.output_dir:
        OUT_DIR = Path(args.output_dir)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
    d1 = pd.read_parquet(HIST_DIR / "D1.parquet").sort_values("open_time").reset_index(drop=True)
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("close_time").reset_index(drop=True)
    cache: OrderedDict = OrderedDict()
    trades, coverage, profiles = [], [], []
    daily_bars = [(m5.close_time > row.open_time) & (m5.close_time <= row.close_time) for row in d1.itertuples(index=False)]
    bar_counts = [int(mask.sum()) for mask in daily_bars if mask.sum() > 0]
    expected_bars = int(np.median(bar_counts)) if bar_counts else 0

    for i in range(1, len(d1)):
        prev, cur = d1.iloc[i - 1], d1.iloc[i]
        d1_day = cur.open_time.strftime("%Y-%m-%d")
        if args.start and d1_day < args.start:
            continue
        if args.end and d1_day > args.end:
            continue
        prev_bars = m5.loc[daily_bars[i - 1]]
        bars = m5.loc[daily_bars[i]].copy()
        if prev_bars.empty or bars.empty:
            coverage.append({"session_open_utc": cur.open_time, "session_close_utc": cur.close_time, "prior_ticks": 0, "session_ticks": 0, "m5_bars": len(bars), "expected_m5_bars": expected_bars, "prior_first_gap_s": np.inf, "prior_last_gap_s": np.inf, "current_first_gap_s": np.inf, "current_last_gap_s": np.inf, "included": False})
            continue
        prior_start, prior_end = prev_bars.open_time.iloc[0], prev_bars.close_time.iloc[-1]
        start, end = bars.open_time.iloc[0], bars.close_time.iloc[-1]
        session_day = start.strftime("%Y-%m-%d")
        if args.start and session_day < args.start:
            continue
        if args.end and session_day > args.end:
            continue
        prev_ticks = ticks_between(prior_start, prior_end, cache)
        curr_ticks = ticks_between(start, end, cache)
        first_gap = (prev_ticks.time_utc.iloc[0] - prior_start).total_seconds() if len(prev_ticks) else np.inf
        prev_last_gap = (prior_end - prev_ticks.time_utc.iloc[-1]).total_seconds() if len(prev_ticks) else np.inf
        cur_first_gap = (curr_ticks.time_utc.iloc[0] - start).total_seconds() if len(curr_ticks) else np.inf
        cur_last_gap = (end - curr_ticks.time_utc.iloc[-1]).total_seconds() if len(curr_ticks) else np.inf
        ok = (len(prev_ticks) > 0 and len(curr_ticks) > 0 and first_gap <= 300 and prev_last_gap <= 300
              and cur_first_gap <= 300 and cur_last_gap <= 300 and len(bars) >= 0.90 * expected_bars)
        coverage.append({"session_open_utc": start, "session_close_utc": end, "prior_ticks": len(prev_ticks), "session_ticks": len(curr_ticks), "m5_bars": len(bars), "expected_m5_bars": expected_bars, "prior_first_gap_s": first_gap, "prior_last_gap_s": prev_last_gap, "current_first_gap_s": cur_first_gap, "current_last_gap_s": cur_last_gap, "included": bool(ok)})
        if not ok:
            continue

        val, poc, vah, median_spread = profile(prev_ticks)
        profiles.append({"session_open_utc": start, "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(), "prior_quote_ticks": len(prev_ticks), "VAL": val, "POC": poc, "VAH": vah, "median_spread": median_spread})
        zone = max(0.05, 2 * median_spread)
        stop_pad = max(0.05, median_spread)
        used = set()
        occupied_until = start
        tick_times = curr_ticks.time_utc
        for bar in bars.itertuples(index=False):
            if bar.close_time <= occupied_until:
                continue
            candidates = []
            if bar.low <= val + zone and bar.close > val:
                candidates.append(("edge", "VAL", "long", poc, float(bar.low) - stop_pad))
            if bar.high >= vah - zone and bar.close < vah:
                candidates.append(("edge", "VAH", "short", poc, float(bar.high) + stop_pad))
            if not args.edge_only:
                if bar.low <= poc + zone and bar.close > poc:
                    candidates.append(("poc", "POC", "long", vah, float(bar.low) - stop_pad))
                if bar.high >= poc - zone and bar.close < poc:
                    candidates.append(("poc", "POC", "short", val, float(bar.high) + stop_pad))
            for group, level_name, side, target, stop in candidates:
                key = (level_name, side)
                if key in used:
                    continue
                idx = int(tick_times.searchsorted(bar.close_time, side="right"))
                if idx >= len(curr_ticks):
                    continue
                result = simulate(curr_ticks, side, idx, stop, target, end)
                if result is None:
                    continue
                used.add(key)
                occupied_until = result["exit_time"]
                trades.append({"session_open_utc": start, "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(), "group": group, "level": level_name, "side": side, "signal_close_utc": bar.close_time, "level_value": {"VAL": val, "POC": poc, "VAH": vah}[level_name], "val": val, "poc": poc, "vah": vah, "zone": zone, **result, "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan})
                break

    cov = pd.DataFrame(coverage)
    tr = pd.DataFrame(trades)
    cov.to_csv(OUT_DIR / "session_coverage.csv", index=False)
    pd.DataFrame(profiles).to_csv(OUT_DIR / "daily_levels.csv", index=False)
    tr.to_csv(OUT_DIR / "trades.csv", index=False)
    if tr.empty:
        print("No trades. Coverage included:", int(cov.included.sum()), "/", len(cov))
        return
    summaries = []
    for group, frame in [("edge", tr[tr.group == "edge"]), ("poc", tr[tr.group == "poc"]), ("all", tr)]:
        wins = frame.loc[frame.pnl > 0, "pnl"].sum()
        losses = -frame.loc[frame.pnl < 0, "pnl"].sum()
        summaries.append({"group": group, "trades": len(frame), "win_rate_pct": 100 * (frame.pnl > 0).mean() if len(frame) else np.nan, "net_points_per_oz": frame.pnl.sum(), "mean_points": frame.pnl.mean(), "median_points": frame.pnl.median(), "mean_R": frame.r_multiple.mean(), "median_R": frame.r_multiple.median(), "profit_factor": wins / losses if losses else np.inf, "targets": int((frame.exit_type == "target").sum()), "stops": int((frame.exit_type == "stop").sum()), "session_closes": int((frame.exit_type == "session_close").sum())})
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT_DIR / "summary.csv", index=False)
    monthly = tr.assign(month=pd.to_datetime(tr.session_date_bkk).dt.strftime("%Y-%m")).groupby(["month", "group"], as_index=False).agg(trades=("pnl", "size"), win_rate_pct=("pnl", lambda x: 100 * (x > 0).mean()), net_points_per_oz=("pnl", "sum"), mean_R=("r_multiple", "mean"))
    monthly.to_csv(OUT_DIR / "monthly.csv", index=False)
    by_level = tr.groupby(["group", "level", "side"], as_index=False).agg(trades=("pnl", "size"), win_rate_pct=("pnl", lambda x: 100 * (x > 0).mean()), net_points_per_oz=("pnl", "sum"), mean_R=("r_multiple", "mean"), median_R=("r_multiple", "median"), targets=("exit_type", lambda x: int((x == "target").sum())), stops=("exit_type", lambda x: int((x == "stop").sum())))
    by_level.to_csv(OUT_DIR / "by_level.csv", index=False)
    print("Included sessions", int(cov.included.sum()), "/", len(cov))
    print("Excluded sessions", int((~cov.included).sum()))
    print(summary.to_string(index=False))
    print("By level/direction:")
    print(by_level.to_string(index=False))
    print("Monthly rows:", len(monthly))
    print("Data end BKK:", tr.exit_time.max().tz_convert("Asia/Bangkok"))


if __name__ == "__main__":
    main()
