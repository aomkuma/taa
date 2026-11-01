"""Backtest OCO value-area edge entries using OANDA M1 bid/ask OHLC candles.

Intraminute event order is unavailable in candle history. When stop and target
are both reachable in one M1 candle, this engine assumes the stop happened first.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict, deque
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
BIN = 0.10

OUT = None
LOOKBACK = pd.Timedelta(hours=6)
HALF = pd.Timedelta(hours=3)


def make_hist(low: float, high: float, volume: float) -> dict[int, float]:
    if volume <= 0:
        return {}
    if high <= low:
        return {int(np.floor(((low + high) / 2) / BIN)): float(volume)}
    first, last = int(np.floor(low / BIN)), int(np.floor(high / BIN))
    widths: dict[int, float] = {}
    total_width = 0.0
    for key in range(first, last + 1):
        width = max(0.0, min(high, (key + 1) * BIN) - max(low, key * BIN))
        if width > 0:
            widths[key] = width
            total_width += width
    if total_width <= 0:
        return {int(np.floor(((low + high) / 2) / BIN)): float(volume)}
    return {key: float(volume) * width / total_width for key, width in widths.items()}


def add_hist(dst: dict[int, float], src: dict[int, float], sign: int) -> None:
    for key, value in src.items():
        updated = dst.get(key, 0.0) + sign * value
        if updated <= 1e-9:
            dst.pop(key, None)
        else:
            dst[key] = updated


def profile(hist: dict[int, float]):
    if not hist:
        return None
    lo, hi = min(hist), max(hist)
    counts = np.zeros(hi - lo + 1, dtype=float)
    for key, value in hist.items():
        counts[key - lo] = value
    total = float(counts.sum())
    if total <= 0:
        return None
    poc = int(np.argmax(counts))
    left = right = poc
    included = float(counts[poc])
    target = 0.70 * total
    while included + 1e-9 < target and (left > 0 or right < len(counts) - 1):
        left_value = float(counts[left - 1]) if left > 0 else -1.0
        right_value = float(counts[right + 1]) if right < len(counts) - 1 else -1.0
        if left_value > right_value:
            side = "left"
        elif right_value > left_value:
            side = "right"
        else:
            left_distance = abs((left - 1) - poc) if left > 0 else 10**9
            right_distance = abs((right + 1) - poc) if right < len(counts) - 1 else 10**9
            side = "left" if left_distance < right_distance else "right"
        value = left_value if side == "left" else right_value
        if value < 0 or included + value > target + 1e-9:
            break
        if side == "left":
            left -= 1
        else:
            right += 1
        included += value
    return (lo + left) * BIN, (lo + poc) * BIN, (lo + right) * BIN, total


def simulate_m1(m1: pd.DataFrame, entry_i: int, side: str, limit: float, stop: float, target: float, session_end: pd.Timestamp):
    is_long = side == "long"
    planned_risk = limit - stop if is_long else stop - limit
    if planned_risk <= 0:
        return None
    future = m1.iloc[entry_i:].loc[lambda x: x.open_time < session_end]
    if future.empty:
        return None
    first = future.iloc[0]
    entry = float(limit)  # no assumed price improvement or queue priority
    for offset, row in enumerate(future.itertuples(index=False)):
        if is_long:
            stop_hit = float(row.bid_low) <= stop
            target_hit = float(row.bid_high) >= target
            if stop_hit:
                fill = min(stop, float(row.bid_open))
                return {"entry_time": first.open_time, "exit_time": row.open_time, "entry": entry,
                        "exit": fill, "exit_type": "stop_at_fill" if offset == 0 else "stop",
                        "pnl": fill - entry, "risk": planned_risk}
            if target_hit:
                fill = max(target, float(row.bid_open))
                return {"entry_time": first.open_time, "exit_time": row.open_time, "entry": entry,
                        "exit": fill, "exit_type": "target", "pnl": fill - entry, "risk": planned_risk}
        else:
            stop_hit = float(row.ask_high) >= stop
            target_hit = float(row.ask_low) <= target
            if stop_hit:
                fill = max(stop, float(row.ask_open))
                return {"entry_time": first.open_time, "exit_time": row.open_time, "entry": entry,
                        "exit": fill, "exit_type": "stop_at_fill" if offset == 0 else "stop",
                        "pnl": entry - fill, "risk": planned_risk}
            if target_hit:
                fill = min(target, float(row.ask_open))
                return {"entry_time": first.open_time, "exit_time": row.open_time, "entry": entry,
                        "exit": fill, "exit_type": "target", "pnl": entry - fill, "risk": planned_risk}
    last = future.iloc[-1]
    exit_price = float(last.bid_close if is_long else last.ask_close)
    pnl = exit_price - entry if is_long else entry - exit_price
    return {"entry_time": first.open_time, "exit_time": last.close_time, "entry": entry,
            "exit": exit_price, "exit_type": "session_close", "pnl": pnl, "risk": planned_risk}


def build_rows(m1: pd.DataFrame, m5: pd.DataFrame, session_start: pd.Timestamp, session_end: pd.Timestamp) -> pd.DataFrame:
    bars = m5.loc[(m5.close_time > session_start) & (m5.close_time <= session_end)].copy().reset_index(drop=True)
    if bars.empty:
        return pd.DataFrame()
    context_m1 = m1.loc[(m1.open_time >= session_start - LOOKBACK) & (m1.open_time < session_end)
                        & (m1.close_time <= session_end)].copy().reset_index(drop=True)
    context_m5 = m5.loc[(m5.close_time > session_start - LOOKBACK) & (m5.open_time < session_end)].copy().reset_index(drop=True)
    c1, c5 = context_m1.close_time, context_m5.close_time
    hist6: dict[int, float] = {}
    hist3: dict[int, float] = {}
    queue6: deque[int] = deque()
    queue3: deque[int] = deque()
    hist_rows = [make_hist(float(x.low), float(x.high), float(x.tick_volume)) for x in context_m1.itertuples(index=False)]
    ptr = 0
    profile_rows = []
    for bar in bars.itertuples(index=False):
        t = bar.open_time
        cut6, cut3 = t - LOOKBACK, t - HALF
        while queue6 and c1.iloc[queue6[0]] <= cut6:
            add_hist(hist6, hist_rows[queue6.popleft()], -1)
        while queue3 and c1.iloc[queue3[0]] <= cut3:
            add_hist(hist3, hist_rows[queue3.popleft()], -1)
        while ptr < len(context_m1) and c1.iloc[ptr] <= t:
            if c1.iloc[ptr] > cut6:
                queue6.append(ptr)
                add_hist(hist6, hist_rows[ptr], 1)
                if c1.iloc[ptr] > cut3:
                    queue3.append(ptr)
                    add_hist(hist3, hist_rows[ptr], 1)
            ptr += 1
        while queue6 and c1.iloc[queue6[0]] <= cut6:
            add_hist(hist6, hist_rows[queue6.popleft()], -1)
        while queue3 and c1.iloc[queue3[0]] <= cut3:
            add_hist(hist3, hist_rows[queue3.popleft()], -1)
        older = {key: value - hist3.get(key, 0.0) for key, value in hist6.items()
                 if value - hist3.get(key, 0.0) > 1e-9}
        p6, po, pn = profile(hist6), profile(older), profile(hist3)
        if p6 is None:
            continue
        val, poc, vah, total = p6
        overlap = 0.0
        poc_shift = float("nan")
        if po is not None and pn is not None:
            oval, opoc, ovah, _ = po
            nval, npoc, nvah, _ = pn
            poc_shift = abs(opoc - npoc)
            narrow = min(ovah - oval, nvah - nval)
            overlap = max(0.0, min(ovah, nvah) - max(oval, nval)) / narrow if narrow > 0 else 0.0
        n6 = int(((context_m5.open_time >= cut6) & (context_m5.close_time <= t)).sum())
        n_old = int(((context_m5.open_time >= cut6) & (context_m5.close_time <= cut3)).sum())
        n_recent = int(((context_m5.open_time >= cut3) & (context_m5.close_time <= t)).sum())
        prior_i = int(c5.searchsorted(t, side="right")) - 1
        prior_close = float(context_m5.close.iloc[prior_i]) if prior_i >= 0 else float("nan")
        efficiency_window = context_m5.loc[(context_m5.open_time >= cut6) & (context_m5.close_time <= t)]
        if len(efficiency_window) >= 2:
            path = efficiency_window.close.to_numpy()
            denominator = float(np.abs(np.diff(path)).sum())
            efficiency = abs(float(path[-1] - path[0])) / denominator if denominator > 0 else 0.0
        else:
            efficiency = float("nan")
        spread_window = context_m1.loc[(context_m1.open_time >= cut6) & (context_m1.close_time <= t)]
        median_spread = float((spread_window.ask_close - spread_window.bid_close).median()) if not spread_window.empty else float("nan")
        qualified = bool(n6 >= 48 and n_old >= 24 and n_recent >= 24 and overlap >= 0.50)
        profile_rows.append({
            "open_time": t, "close_time": bar.close_time, "open": bar.open, "high": bar.high,
            "low": bar.low, "close": bar.close, "VAL": val, "POC": poc, "VAH": vah,
            "profile_volume": total, "half_va_overlap": overlap, "poc_shift": poc_shift,
            "poc_stability_ratio": poc_shift / max(vah - val, 0.10), "prior_close": prior_close,
            "efficiency_6h": efficiency, "median_spread": median_spread,
            "stop_pad": max(0.10, 2 * median_spread + 0.10) if np.isfinite(median_spread) else float("nan"),
            "qualifies": qualified,
        })
    return pd.DataFrame(profile_rows)


def metrics(frame: pd.DataFrame) -> dict:
    wins = frame.loc[frame.pnl > 0, "pnl"].sum()
    losses = -frame.loc[frame.pnl < 0, "pnl"].sum()
    gain_r = frame.loc[frame.r_multiple > 0, "r_multiple"].sum()
    loss_r = -frame.loc[frame.r_multiple < 0, "r_multiple"].sum()
    return {
        "trades": int(len(frame)), "wins": int((frame.pnl > 0).sum()),
        "win_rate_pct": 100 * float((frame.pnl > 0).mean()) if len(frame) else np.nan,
        "net_points_per_oz": float(frame.pnl.sum()), "net_R": float(frame.r_multiple.sum()),
        "mean_R": float(frame.r_multiple.mean()) if len(frame) else np.nan,
        "profit_factor_points": wins / losses if losses else (float("inf") if wins else 0.0),
        "profit_factor_R": gain_r / loss_r if loss_r else (float("inf") if gain_r else 0.0),
        "targets": int((frame.exit_type == "target").sum()),
        "stops": int(frame.exit_type.str.startswith("stop").sum()),
    }


def main() -> int:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True, help="Directory produced by prepare_candles.py")
    parser.add_argument("--sessions", type=Path, default=BASE / "rolling_6h_m5" / "session_coverage.csv")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if not (args.data_dir / "M1.parquet").is_file() or not (args.data_dir / "M5.parquet").is_file():
        parser.error("data-dir must contain M1.parquet and M5.parquet")
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        parser.error("out-dir must be empty; choose a new output directory")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    OUT = args.out_dir
    m1 = pd.read_parquet(args.data_dir / "M1.parquet").sort_values("open_time").reset_index(drop=True)
    m5 = pd.read_parquet(args.data_dir / "M5.parquet").sort_values("open_time").reset_index(drop=True)
    coverage = pd.read_csv(args.sessions, parse_dates=["session_open_utc", "session_close_utc"])
    sessions = coverage.sort_values("session_open_utc").reset_index(drop=True)
    if sessions.empty:
        parser.error("no included reference sessions")

    reference_counts = pd.to_numeric(coverage.loc[coverage.included, "current_m5_bars"], errors="coerce").dropna()
    expected_bars = float(reference_counts.median()) if len(reference_counts) else 0.0
    session_rows, eligible_sessions, trades, audit_rows = [], [], [], []
    for _, session in sessions.iterrows():
        start, end = session.session_open_utc, session.session_close_utc
        bars = m5.loc[(m5.close_time > start) & (m5.close_time <= end)]
        included = len(bars) >= 0.90 * expected_bars
        coverage_row = {"session_date_bkk": session.session_date_bkk, "session_open_utc": start,
                        "session_close_utc": end, "oanda_m5_bars": len(bars),
                        "reference_expected_m5": expected_bars, "included": included}
        session_rows.append(coverage_row)
        if included:
            eligible_sessions.append(session)
    dev_count = max(1, int(len(eligible_sessions) * 0.70))
    for rank, session in enumerate(eligible_sessions):
        start, end = session.session_open_utc, session.session_close_utc
        prof = build_rows(m1, m5, start, end)
        if prof.empty:
            continue
        m1s = m1.loc[(m1.open_time >= start) & (m1.open_time < end)].copy().reset_index(drop=True)
        if m1s.empty:
            continue
        m1s["m5_open_time"] = m1s.open_time.dt.floor("5min")
        m1_groups = {}
        for key, positions in m1s.groupby("m5_open_time", sort=True).indices.items():
            first_position = int(positions[0])
            m1_groups[key] = (m1s.iloc[first_position:first_position + len(positions)].reset_index(drop=True), first_position)
        split = "development" if rank < dev_count else "validation"
        for variant, stable_poc_limit in (("base_oco", None), ("stable_poc_050", 0.50), ("stable_poc_100", 1.00)):
            active = None
            created = False
            trade_taken = False
            for i, row in prof.iterrows():
                audit_rows.append({"variant": variant, "session_rank": rank,
                                   "session_date_bkk": session.session_date_bkk, **row.to_dict()})
                formation_ok = row.qualifies and active is None and not created
                if stable_poc_limit is not None:
                    formation_ok = bool(formation_ok and row.prior_close >= row.VAL and row.prior_close <= row.VAH
                                        and np.isfinite(row.efficiency_6h) and row.efficiency_6h <= 0.25
                                        and np.isfinite(row.poc_shift) and row.poc_shift <= stable_poc_limit)
                if formation_ok:
                    active = {"start_i": i, "val": row.VAL, "poc": row.POC, "vah": row.VAH,
                              "pad": row.stop_pad, "outside_up": 0, "outside_down": 0}
                    created = True
                if active is None:
                    continue
                if i - active["start_i"] >= 72:
                    active = None
                    continue
                can_trade = not trade_taken and row.close_time > start
                if stable_poc_limit is not None:
                    can_trade = bool(can_trade and row.prior_close >= active["val"] and row.prior_close <= active["vah"]
                                     and np.isfinite(row.efficiency_6h) and row.efficiency_6h <= 0.25
                                     and np.isfinite(row.poc_shift) and row.poc_shift <= stable_poc_limit)
                group_info = m1_groups.get(row.open_time)
                if can_trade and group_info is not None:
                    group, group_start = group_info
                    long_hit = np.flatnonzero(group.ask_low.to_numpy(dtype=float) <= active["val"])
                    short_hit = np.flatnonzero(group.bid_high.to_numpy(dtype=float) >= active["vah"])
                    candidates = []
                    if len(long_hit):
                        candidates.append((int(long_hit[0]), "long", "VAL", active["val"], active["val"] - active["pad"]))
                    if len(short_hit):
                        candidates.append((int(short_hit[0]), "short", "VAH", active["vah"], active["vah"] + active["pad"]))
                    if candidates:
                        candidates.sort(key=lambda item: item[0])
                        if not (len(candidates) > 1 and candidates[0][0] == candidates[1][0]):
                            m1_i, side, level, limit, stop = candidates[0]
                            result = simulate_m1(m1s, group_start + m1_i, side, limit, stop, active["poc"], end)
                            if result is not None:
                                trade_taken = True
                                trades.append({"variant": variant, "split": split, "session_rank": rank,
                                               "session_date_bkk": session.session_date_bkk,
                                               "order_bar_open_utc": row.open_time, "level": level, "side": side,
                                               "limit": limit, "stop": stop, "target": active["poc"],
                                               "cluster_val": active["val"], "cluster_poc": active["poc"],
                                               "cluster_vah": active["vah"], **result,
                                               "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan})
                if not trade_taken:
                    active["outside_up"] = active["outside_up"] + 1 if row.close > active["vah"] else 0
                    active["outside_down"] = active["outside_down"] + 1 if row.close < active["val"] else 0
                    if active["outside_up"] >= 2 or active["outside_down"] >= 2:
                        active = None

    trade_frame = pd.DataFrame(trades)
    if trade_frame.empty:
        trade_frame = pd.DataFrame(columns=["variant", "split", "session_rank", "pnl", "r_multiple", "exit_type"])
    trade_frame.to_csv(OUT / "trades.csv", index=False)
    pd.DataFrame(session_rows).to_csv(OUT / "session_coverage.csv", index=False)
    pd.DataFrame(audit_rows).to_csv(OUT / "profile_audit.csv", index=False)
    summary, folds, decisions = [], [], []
    for variant in ("base_oco", "stable_poc_050", "stable_poc_100"):
        subset = trade_frame.loc[trade_frame.variant == variant]
        for split in ("development", "validation", "all"):
            frame = subset if split == "all" else subset.loc[subset.split == split]
            summary.append({"variant": variant, "split": split, **metrics(frame)})
        fold_r = []
        for fold in range(3):
            lo = fold * dev_count // 3
            hi = (fold + 1) * dev_count // 3
            frame = subset.loc[(subset.session_rank >= lo) & (subset.session_rank < hi)]
            row = metrics(frame)
            fold_r.append(row["net_R"])
            folds.append({"variant": variant, "fold": fold + 1, **row})
        dev_n = int((subset.split == "development").sum())
        val_r = float(subset.loc[subset.split == "validation", "r_multiple"].sum())
        decisions.append({"variant": variant, "development_trades": dev_n,
                          "positive_folds": int(sum(value > 0 for value in fold_r)),
                          "validation_net_R": val_r,
                          "candidate": bool(dev_n >= 20 and sum(value > 0 for value in fold_r) >= 2 and val_r > 0)})
    pd.DataFrame(summary).to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(folds).to_csv(OUT / "development_folds.csv", index=False)
    pd.DataFrame(decisions).to_csv(OUT / "selection.csv", index=False)
    print("OANDA-covered sessions", sum(row["included"] for row in session_rows), "/", len(session_rows))
    print(pd.DataFrame(summary).to_string(index=False))
    print(pd.DataFrame(folds).to_string(index=False))
    print(pd.DataFrame(decisions).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
