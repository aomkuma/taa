"""Normalize downloaded OANDA M1 candles and aggregate complete M5 bars."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV created by fetch_candles.py")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"input file not found: {args.input}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    existing = [name for name in ("M1.parquet", "M5.parquet", "coverage.json", "m5_coverage.csv") if (args.out_dir / name).exists()]
    if existing:
        parser.error(f"output files already exist; choose another directory: {', '.join(existing)}")

    raw = pd.read_csv(args.input, parse_dates=["time"])
    if raw.empty:
        parser.error("input has no complete candles")
    complete_mask = raw.complete.astype(str).str.lower().isin({"true", "1"})
    raw = raw.loc[complete_mask].copy()
    raw["time"] = pd.to_datetime(raw.time, utc=True)
    raw = raw.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    raw["open_time"] = raw.time
    raw["close_time"] = raw.time + pd.Timedelta(minutes=1)
    raw["tick_volume"] = pd.to_numeric(raw.volume, errors="coerce").fillna(0).astype("int64")

    m1 = pd.DataFrame({
        "open_time": raw.open_time,
        "close_time": raw.close_time,
        "open": raw.mid_o,
        "high": raw.mid_h,
        "low": raw.mid_l,
        "close": raw.mid_c,
        "tick_volume": raw.tick_volume,
        "bid_open": raw.bid_o,
        "bid_high": raw.bid_h,
        "bid_low": raw.bid_l,
        "bid_close": raw.bid_c,
        "ask_open": raw.ask_o,
        "ask_high": raw.ask_h,
        "ask_low": raw.ask_l,
        "ask_close": raw.ask_c,
    })
    m1 = m1.dropna(subset=[
        "open", "high", "low", "close",
        "bid_open", "bid_high", "bid_low", "bid_close",
        "ask_open", "ask_high", "ask_low", "ask_close",
    ])
    m1.to_parquet(args.out_dir / "M1.parquet", index=False)

    m1["m5_open_time"] = m1.open_time.dt.floor("5min")
    m1["minute_offset"] = ((m1.open_time - m1.m5_open_time).dt.total_seconds() / 60).astype(int)
    aggregations = {
        "m1_count": ("open_time", "size"),
        "first_offset": ("minute_offset", "min"),
        "last_offset": ("minute_offset", "max"),
        "open_time_first": ("open_time", "min"),
        "close_time_last": ("close_time", "max"),
        "open": ("open", "first"),
        "high": ("high", "max"),
        "low": ("low", "min"),
        "close": ("close", "last"),
        "tick_volume": ("tick_volume", "sum"),
        "bid_open": ("bid_open", "first"),
        "bid_high": ("bid_high", "max"),
        "bid_low": ("bid_low", "min"),
        "bid_close": ("bid_close", "last"),
        "ask_open": ("ask_open", "first"),
        "ask_high": ("ask_high", "max"),
        "ask_low": ("ask_low", "min"),
        "ask_close": ("ask_close", "last"),
    }
    grouped = m1.groupby("m5_open_time", sort=True).agg(**aggregations).reset_index()
    m5 = grouped.loc[
        (grouped.m1_count == 5)
        & (grouped.first_offset == 0)
        & (grouped.last_offset == 4)
        & (grouped.open_time_first == grouped.m5_open_time)
        & (grouped.close_time_last == grouped.m5_open_time + pd.Timedelta(minutes=5))
    ].copy()
    m5 = m5.rename(columns={"m5_open_time": "open_time", "close_time_last": "close_time"})
    m5 = m5[[
        "open_time", "close_time", "open", "high", "low", "close", "tick_volume",
        "bid_open", "bid_high", "bid_low", "bid_close",
        "ask_open", "ask_high", "ask_low", "ask_close",
    ]]
    m5.to_parquet(args.out_dir / "M5.parquet", index=False)

    gaps = m1.open_time.diff().dropna()
    audit = {
        "source_csv": args.input.name,
        "m1_complete_rows": int(len(m1)),
        "m5_complete_rows": int(len(m5)),
        "non_contiguous_m1_intervals": int((gaps > pd.Timedelta(minutes=1)).sum()),
        "largest_observed_m1_gap_minutes": float(gaps.max().total_seconds() / 60) if len(gaps) else 0.0,
        "first_m1_open_utc": m1.open_time.min().isoformat(),
        "last_m1_open_utc": m1.open_time.max().isoformat(),
        "m5_rule": "five complete consecutive M1 candles aligned to UTC 5-minute boundaries",
        "execution_limit": "M1 bid/ask OHLC only; intraminute ordering is unavailable",
    }
    (args.out_dir / "coverage.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    pd.DataFrame({
        "m5_open_time": grouped.m5_open_time,
        "m1_count": grouped.m1_count,
        "first_offset": grouped.first_offset,
        "last_offset": grouped.last_offset,
        "complete_m5": (grouped.m1_count == 5)
        & (grouped.first_offset == 0)
        & (grouped.last_offset == 4)
        & (grouped.open_time_first == grouped.m5_open_time)
        & (grouped.close_time_last == grouped.m5_open_time + pd.Timedelta(minutes=5)),
    }).to_csv(args.out_dir / "m5_coverage.csv", index=False)
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
