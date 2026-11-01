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
START = pd.Timestamp("2026-09-24", tz="UTC")
END = pd.Timestamp("2026-10-07", tz="UTC")


def main() -> None:
    d1 = pd.read_parquet(HIST_DIR / "D1.parquet").sort_values("open_time").reset_index(drop=True)
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("close_time").reset_index(drop=True)
    nonempty_counts = [
        int(((m5.close_time > row.open_time) & (m5.close_time <= row.close_time)).sum())
        for row in d1.itertuples(index=False)
    ]
    expected_bars = int(np.median([n for n in nonempty_counts if n]))
    cache: OrderedDict = OrderedDict()
    coverage, levels, trades = [], [], []

    for i in range(1, len(d1)):
        prev, cur = d1.iloc[i - 1], d1.iloc[i]
        if cur.open_time < START or cur.open_time >= END:
            continue
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
        coverage.append({
            "session_open_utc": start, "session_close_utc": end,
            "prior_ticks": len(prev_ticks), "session_ticks": len(curr_ticks),
            "m5_bars": len(bars), "expected_m5_bars": expected_bars,
            "prior_first_gap_s": gaps[0], "prior_last_gap_s": gaps[1],
            "current_first_gap_s": gaps[2], "current_last_gap_s": gaps[3], "included": ok,
        })
        if not ok:
            continue

        val, poc, vah, med_spread = profile(prev_ticks)
        zone, stop_pad = max(0.05, 2 * med_spread), max(0.05, med_spread)
        levels.append({
            "session_open_utc": start,
            "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(),
            "prior_quote_ticks": len(prev_ticks), "VAL": val, "POC": poc, "VAH": vah,
            "median_spread": med_spread, "touch_zone": zone,
        })

        closes = bars.close.to_numpy()
        val_disabled = np.zeros(len(bars), dtype=bool)
        vah_disabled = np.zeros(len(bars), dtype=bool)
        val_run = vah_run = 0
        val_broken = vah_broken = False
        for j, close in enumerate(closes):
            if j > 0 and closes[j - 1] < val and close < val:
                val_broken = True
            if j > 0 and closes[j - 1] > vah and close > vah:
                vah_broken = True
            val_disabled[j], vah_disabled[j] = val_broken, vah_broken

        tick_times = curr_ticks.time_utc
        occupied_until = start
        used = set()
        for j in range(len(bars) - 1):
            signal = bars.iloc[j]
            confirm = bars.iloc[j + 1]
            if confirm.close_time <= occupied_until:
                continue
            candidates = []
            if (not val_disabled[j] and signal.low <= val + zone and signal.close > val
                    and confirm.close > val):
                candidates.append(("VAL", "long", poc, float(confirm.low) - stop_pad))
            if (not vah_disabled[j] and signal.high >= vah - zone and signal.close < vah
                    and confirm.close < vah):
                candidates.append(("VAH", "short", poc, float(confirm.high) + stop_pad))
            if len(candidates) != 1:
                continue
            level, side, target, stop = candidates[0]
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
            trades.append({
                "session_open_utc": start,
                "session_date_bkk": start.tz_convert("Asia/Bangkok").date().isoformat(),
                "level": level, "side": side, "signal_close_utc": signal.close_time,
                "confirmation_close_utc": confirm.close_time,
                "level_value": val if level == "VAL" else vah, "val": val, "poc": poc, "vah": vah,
                "zone": zone, **result,
                "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan,
            })

    cov, lev, tr = pd.DataFrame(coverage), pd.DataFrame(levels), pd.DataFrame(trades)
    cov.to_csv(OUT / "session_coverage.csv", index=False)
    lev.to_csv(OUT / "daily_levels.csv", index=False)
    tr.to_csv(OUT / "trades.csv", index=False)
    if tr.empty:
        print(f"Included {int(cov.included.sum())}/{len(cov)} sessions; no trades")
        return
    rows = []
    for group, frame in [("edge", tr), ("VAL_long", tr[tr.level == "VAL"]), ("VAH_short", tr[tr.level == "VAH"])]:
        gains, losses = frame.loc[frame.pnl > 0, "pnl"].sum(), -frame.loc[frame.pnl < 0, "pnl"].sum()
        rows.append({
            "setup": group, "trades": len(frame), "wins": int((frame.pnl > 0).sum()),
            "win_rate_pct": 100 * (frame.pnl > 0).mean(), "net_points_per_oz": frame.pnl.sum(),
            "mean_R": frame.r_multiple.mean(), "profit_factor": gains / losses if losses else np.inf,
            "targets": int((frame.exit_type == "target").sum()), "stops": int((frame.exit_type == "stop").sum()),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary.csv", index=False)
    print(f"Included {int(cov.included.sum())}/{len(cov)} sessions")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
