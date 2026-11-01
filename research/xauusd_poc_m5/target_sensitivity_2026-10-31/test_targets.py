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
HALF = pd.Timedelta(hours=3)
VARIANTS = ["target_poc", "target_opposite_va"]


def profile_from_counts(hist: dict[int, int]) -> tuple[float, float, float, int] | None:
    if not hist:
        return None
    low, high = min(hist), max(hist)
    counts = np.zeros(high - low + 1, dtype=np.int64)
    for key, value in hist.items():
        counts[key - low] = value
    total = int(counts.sum())
    if total <= 0:
        return None
    poc_i = int(np.argmax(counts))
    left = right = poc_i
    included = int(counts[poc_i])
    target = int(np.ceil(total * .70))
    while included < target and (left > 0 or right < len(counts) - 1):
        left_count = int(counts[left - 1]) if left > 0 else -1
        right_count = int(counts[right + 1]) if right < len(counts) - 1 else -1
        if left_count >= right_count:
            left -= 1
            included += int(counts[left])
        else:
            right += 1
            included += int(counts[right])
    return (low + left) * BIN, (low + poc_i) * BIN, (low + right) * BIN, total


def add_hist(dst: dict[int, int], keys: np.ndarray, counts: np.ndarray, sign: int) -> None:
    for key, value in zip(keys, counts):
        k = int(key)
        v = dst.get(k, 0) + sign * int(value)
        if v <= 0:
            dst.pop(k, None)
        else:
            dst[k] = v


def main() -> None:
    m5 = pd.read_parquet(HIST_DIR / "M5.parquet").sort_values("open_time").reset_index(drop=True)
    cov = pd.read_csv(BASE / "rolling_6h_m5" / "session_coverage.csv", parse_dates=["session_open_utc", "session_close_utc"])
    valid = cov[cov.included].sort_values("session_open_utc").reset_index(drop=True)
    dev_n = int(len(valid) * .70)
    cache: OrderedDict = OrderedDict()
    trades, qualifying_rows, session_log, cluster_logs = [], [], [], []

    for rank, session in valid.iterrows():
        start, end = session.session_open_utc, session.session_close_utc
        split = "development" if rank < dev_n else "validation"
        current_bars = m5.loc[(m5.close_time > start) & (m5.close_time <= end)].copy().reset_index(drop=True)
        context_bars = m5.loc[(m5.close_time > start - LOOKBACK) & (m5.open_time < end)].copy().reset_index(drop=True)
        window_ticks = ticks_between(start - LOOKBACK, end, cache)
        current_ticks = ticks_between(start, end, cache)
        times = window_ticks.time_utc
        mids = (window_ticks.bid.to_numpy() + window_ticks.ask.to_numpy()) / 2 if len(window_ticks) else np.array([])
        spreads = window_ticks.ask.to_numpy() - window_ticks.bid.to_numpy() if len(window_ticks) else np.array([])

        bar_hists: list[tuple[np.ndarray, np.ndarray]] = []
        bar_spreads: list[float] = []
        for bar in context_bars.itertuples(index=False):
            lo = max(bar.open_time, start - LOOKBACK)
            a = int(times.searchsorted(lo, side="left"))
            b = int(times.searchsorted(bar.close_time, side="left"))
            if b > a:
                bins = np.floor(mids[a:b] / BIN + .5).astype(np.int64)
                keys, counts = np.unique(bins, return_counts=True)
                bar_hists.append((keys, counts.astype(np.int64)))
                bar_spreads.append(float(np.median(spreads[a:b])))
            else:
                bar_hists.append((np.array([], dtype=np.int64), np.array([], dtype=np.int64)))
                bar_spreads.append(np.nan)

        h6: dict[int, int] = {}
        h3: dict[int, int] = {}
        q6: deque[int] = deque()
        q3: deque[int] = deque()
        ptr = 0
        context_close = context_bars.close_time
        rows = []
        for bar in current_bars.itertuples(index=False):
            t = bar.open_time
            cutoff6, cutoff3 = t - LOOKBACK, t - HALF
            while q6 and context_close.iloc[q6[0]] <= cutoff6:
                old = q6.popleft()
                add_hist(h6, *bar_hists[old], -1)
            while q3 and context_close.iloc[q3[0]] <= cutoff3:
                old = q3.popleft()
                add_hist(h3, *bar_hists[old], -1)
            while ptr < len(context_bars) and context_close.iloc[ptr] <= t:
                if context_close.iloc[ptr] > cutoff6:
                    q6.append(ptr)
                    add_hist(h6, *bar_hists[ptr], 1)
                    if context_close.iloc[ptr] > cutoff3:
                        q3.append(ptr)
                        add_hist(h3, *bar_hists[ptr], 1)
                ptr += 1
            # Remove bars that entered after an interval rollover but are already stale.
            while q6 and context_close.iloc[q6[0]] <= cutoff6:
                old = q6.popleft()
                add_hist(h6, *bar_hists[old], -1)
            while q3 and context_close.iloc[q3[0]] <= cutoff3:
                old = q3.popleft()
                add_hist(h3, *bar_hists[old], -1)

            old_hist = {k: v - h3.get(k, 0) for k, v in h6.items() if v - h3.get(k, 0) > 0}
            p6, p_old, p_recent = profile_from_counts(h6), profile_from_counts(old_hist), profile_from_counts(h3)
            if p6 is None:
                rows.append(None)
                continue
            val, poc, vah, total_ticks = p6
            overlap_ratio = 0.0
            if p_old and p_recent:
                old_val, _, old_vah, _ = p_old
                new_val, _, new_vah, _ = p_recent
                narrow = min(old_vah - old_val, new_vah - new_val)
                overlap = max(0.0, min(old_vah, new_vah) - max(old_val, new_val))
                overlap_ratio = overlap / narrow if narrow > 0 else 0.0
            enough = len(q6) >= 48 and len(q6) <= 72 and len(q6) - len(q3) >= 24 and len(q3) >= 24
            spread_values = [bar_spreads[idx] for idx in q6 if np.isfinite(bar_spreads[idx])]
            if not spread_values:
                rows.append(None)
                continue
            spread = float(np.median(spread_values))
            row = {"signal_bar_open_utc": t, "close_time": bar.close_time, "open": bar.open, "high": bar.high,
                   "low": bar.low, "close": bar.close, "VAL": val, "POC": poc, "VAH": vah,
                   "touch_zone": max(.05, 2 * spread), "stop_pad": max(.05, spread), "profile_ticks": total_ticks,
                   "profile_m5_bars": len(q6), "older_half_bars": len(q6)-len(q3), "recent_half_bars": len(q3),
                   "half_va_overlap_ratio": overlap_ratio, "cluster_qualifies": bool(enough and overlap_ratio >= .50)}
            rows.append(row)
            if row["cluster_qualifies"]:
                qualifying_rows.append({"session_rank": rank, "split": split, "session_date_bkk": session.session_date_bkk,
                                        **row})

        day_profiles = pd.DataFrame([r for r in rows if r is not None])
        day_clusters = 0
        for variant in VARIANTS:
            active = None
            occupied_until = start
            created = False
            logs = []
            for i, row in day_profiles.reset_index(drop=True).iterrows():
                if active is None and not created and row.cluster_qualifies:
                    active = {"start_i": i, "val": row.VAL, "poc": row.POC, "vah": row.VAH,
                              "zone": row.touch_zone, "pad": row.stop_pad, "width": row.VAH-row.VAL,
                              "used": set(), "up_run": 0, "down_run": 0, "phase": "rotation",
                              "break_dir": None, "break_i": None, "deadline": None}
                    created = True
                    day_clusters += 1
                    logs.append({"variant": variant, "session_rank": rank, "session_date_bkk": session.session_date_bkk,
                                 "cluster_start_utc": row.signal_bar_open_utc, "VAL": active["val"], "POC": active["poc"],
                                 "VAH": active["vah"], "width": active["width"], "half_va_overlap_ratio": row.half_va_overlap_ratio})
                if active is None:
                    continue
                age = i - active["start_i"]
                if age >= 72:
                    active = None
                    continue
                if active["phase"] == "rotation":
                    active["up_run"] = active["up_run"] + 1 if row.close > active["vah"] else 0
                    active["down_run"] = active["down_run"] + 1 if row.close < active["val"] else 0
                    direction = "up" if active["up_run"] >= 2 else ("down" if active["down_run"] >= 2 else None)
                    if direction:
                        active = None
                        continue

                signals = []
                if active["phase"] == "rotation":
                    if row.low <= active["val"] + active["zone"] and row.close > active["val"]:
                        signals.append(("VAL", "long", active["poc"], float(row.low)-active["pad"], "rotation"))
                    if row.high >= active["vah"] - active["zone"] and row.close < active["vah"]:
                        signals.append(("VAH", "short", active["poc"], float(row.high)+active["pad"], "rotation"))
                elif active["phase"] == "pending" and i > active["break_i"] and i <= active["deadline"]:
                    if active["break_dir"] == "up" and row.low <= active["vah"] + active["zone"] and row.close > active["vah"]:
                        signals.append(("VAH_break", "long", active["vah"]+active["width"], float(row.low)-active["pad"], "breakout"))
                    if active["break_dir"] == "down" and row.high >= active["val"] - active["zone"] and row.close < active["val"]:
                        signals.append(("VAL_break", "short", active["val"]-active["width"], float(row.high)+active["pad"], "breakout"))
                elif active["phase"] == "pending" and i > active["deadline"]:
                    active = None
                    continue
                if len(signals) != 1 or row.close_time <= occupied_until:
                    continue
                level, side, target, stop, mode = signals[0]
                target = active["poc"] if variant == "target_poc" else (active["vah"] if side == "long" else active["val"])
                if level in active["used"]:
                    continue
                tick_times = current_ticks.time_utc
                entry_i = int(tick_times.searchsorted(row.close_time, side="right"))
                if entry_i >= len(current_ticks):
                    continue
                result = simulate(current_ticks, side, entry_i, stop, target, end)
                if result is None:
                    continue
                active["used"].add(level)
                occupied_until = result["exit_time"]
                trades.append({"variant": variant, "session_rank": rank, "split": split,
                               "session_date_bkk": session.session_date_bkk, "cluster_start_utc": day_profiles.iloc[active["start_i"]].signal_bar_open_utc,
                               "signal_close_utc": row.close_time, "mode": mode, "level": level, "side": side,
                               "cluster_val": active["val"], "cluster_poc": active["poc"], "cluster_vah": active["vah"],
                               "half_va_overlap_ratio": day_profiles.iloc[active["start_i"]].half_va_overlap_ratio,
                               "target": target, "stop": stop, **result,
                               "r_multiple": result["pnl"] / result["risk"] if result["risk"] > 0 else np.nan})
            cluster_logs.extend(logs)
        session_log.append({"session_rank": rank, "session_date_bkk": session.session_date_bkk,
                            "qualifying_profile_bars": int(day_profiles.cluster_qualifies.sum()),
                            "clusters_started": day_clusters})

    tr, qf = pd.DataFrame(trades), pd.DataFrame(qualifying_rows)
    tr.to_csv(OUT / "trades.csv", index=False)
    qf.to_csv(OUT / "qualifying_profile_windows.csv", index=False)
    pd.DataFrame(session_log).to_csv(OUT / "session_cluster_counts.csv", index=False)
    pd.DataFrame(cluster_logs).to_csv(OUT / "cluster_starts.csv", index=False)

    def metrics(part: pd.DataFrame) -> dict:
        pg, pl = part.loc[part.pnl > 0, "pnl"].sum(), -part.loc[part.pnl < 0, "pnl"].sum()
        rg, rl = part.loc[part.r_multiple > 0, "r_multiple"].sum(), -part.loc[part.r_multiple < 0, "r_multiple"].sum()
        return {"trades": len(part), "wins": int((part.pnl > 0).sum()), "win_rate_pct": 100*(part.pnl>0).mean() if len(part) else np.nan,
                "net_points_per_oz": part.pnl.sum(), "net_R": part.r_multiple.sum(), "mean_R": part.r_multiple.mean(),
                "profit_factor_points": pg/pl if pl else (np.inf if pg else 0), "profit_factor_R": rg/rl if rl else (np.inf if rg else 0),
                "targets": int((part.exit_type=="target").sum()), "stops": int((part.exit_type=="stop").sum())}
    summaries, folds, decisions = [], [], []
    for variant in VARIANTS:
        part = tr[tr.variant == variant]
        for split_name in ["development", "validation", "all"]:
            sub = part[part.split == split_name] if split_name != "all" else part
            summaries.append({"variant":variant,"split":split_name,**metrics(sub)})
        fold_r=[]
        for f in range(3):
            lo,hi=f*dev_n//3,(f+1)*dev_n//3
            sub=part[(part.session_rank>=lo)&(part.session_rank<hi)]
            fold_r.append(metrics(sub)["net_R"])
            folds.append({"variant":variant,"fold":f+1,**metrics(sub)})
        devtr=len(part[part.split=="development"])
        valr=float(part.loc[part.split=="validation","r_multiple"].sum())
        decisions.append({"variant":variant,"development_trades":devtr,"positive_folds":sum(v>0 for v in fold_r),"validation_net_R":valr,
                          "candidate":bool(devtr>=20 and sum(v>0 for v in fold_r)>=2 and valr>0)})
    summary=pd.DataFrame(summaries); folddf=pd.DataFrame(folds); selection=pd.DataFrame(decisions)
    summary.to_csv(OUT/"summary.csv",index=False); folddf.to_csv(OUT/"development_folds.csv",index=False); selection.to_csv(OUT/"selection.csv",index=False)
    selected=selection.loc[selection.candidate,"variant"].iloc[0] if selection.candidate.any() else "NONE"
    (OUT/"selected_variant.txt").write_bytes(selected.encode())
    print("Covered sessions",len(valid),"development",dev_n,"validation",len(valid)-dev_n,"selected",selected)
    print("Qualifying cluster starts",len(pd.DataFrame(cluster_logs)))
    print(summary.to_string(index=False)); print(folddf.to_string(index=False))


if __name__ == "__main__":
    main()
