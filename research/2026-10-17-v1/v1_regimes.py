"""V1 (harmonic + room) by market condition, two years (owner, 2026-10-17: every setup profitable in every market
condition, one setup at a time; V1 first, it fails the out-of-sample year, docs/OUT_OF_SAMPLE.md).

Year A: the out-of-sample monthly runs (``data/backtests/oos/v1_YYYY-MM``, 2024-10 ..), year B: the in-sample
monthly runs with the same rules (``data/backtests/inv/v1cr_room_YYYY-MM``). For each trade the market map at its
entry is rebuilt with the engine's code (``MapBook`` on ``config.yaml``'s context map, H1/H4/D1, as
``research/2026-10-14-chart-read/cr3_features.py``) plus each timeframe's volatility (ATR percentile), ADX and
efficiency. The tables put a condition's R per trade in year A next to year B: a condition that loses in both is
where V1 needs stricter rules (trade less, not never: CLAUDE.md, regime fit).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-v1/v1_regimes.py
"""

from __future__ import annotations

import ctypes
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.backtest.runner import load_context  # noqa: E402
from app.config import AppConfig, load_app_config  # noqa: E402
from app.indicators.market_map import signal_features  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.market_maps import MapBook  # noqa: E402

YEARS = {"A": "data/backtests/oos/v1_20*/trades.csv", "B": "data/backtests/inv/v1cr_room_20*/trades.csv"}
CACHE = Path("data/research/v1_regime_features.parquet")
CONTEXT = ["H1", "H4", "D1"]


def below_normal_priority() -> None:
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def trades() -> pd.DataFrame:
    out = []
    for year, pattern in YEARS.items():
        for path in sorted(glob.glob(pattern)):
            if not Path(path).with_name("summary.json").exists():
                continue  # a month still running
            t = pd.read_csv(path)
            t["year"], t["month"] = year, Path(path).parent.name[-7:]
            out.append(t)
    t = pd.concat(out, ignore_index=True)
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    return t


def features(t: pd.DataFrame) -> pd.DataFrame:
    """The map features of every trade (cached by symbol and entry time; new trades are added)."""
    done = pd.read_parquet(CACHE) if CACHE.exists() else pd.DataFrame(columns=["symbol", "entry_time"])
    key = ["symbol", "entry_time"]
    todo = t.merge(done[key], on=key, how="left", indicator=True)
    todo = todo[todo["_merge"] == "left_only"].drop(columns="_merge")
    if len(todo):
        raw = load_app_config("config.yaml").model_dump(mode="json")
        raw["timeframes"]["context"] = CONTEXT
        cfg = AppConfig.model_validate(raw)
        book = MapBook.from_config(cfg)
        assert book is not None
        store = ParquetHistoryStore(Path("data/history"))
        ctx = load_context(store, "FBS-Demo", sorted(todo.symbol.unique()), list(cfg.timeframes.context))
        rows = []
        for _, r in todo.iterrows():
            point = float(store.spec("FBS-Demo", r.symbol)["spec"]["point"])  # type: ignore[index]
            mm = book.at(r.symbol, ctx[r.symbol], r.entry_time.to_pydatetime(), point)
            f: dict[str, float] = {}
            if mm is not None:
                f = signal_features(mm, buy=r.side == "BUY", entry=r.entry_price, stop=r.sl_initial, target=r.tp_initial)
                for tf, m in mm.frames.items():
                    k = f"ctx:{tf.lower()}_"
                    f[k + "atr_pct"] = np.nan if m.atr_pct is None else m.atr_pct
                    f[k + "adx"] = np.nan if m.adx is None else m.adx
                    f[k + "er"] = np.nan if m.efficiency is None else m.efficiency
            rows.append({"symbol": r.symbol, "entry_time": r.entry_time, **f})
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
        done["entry_time"] = pd.to_datetime(done["entry_time"], utc=True)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        done.to_parquet(CACHE)
    done["entry_time"] = pd.to_datetime(done["entry_time"], utc=True)
    return t.merge(done, on=key, how="left")


def bands(s: pd.Series, edges: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(s, edges, labels=labels).astype(str).replace("nan", "unknown")


def trend_name(s: pd.Series) -> pd.Series:
    return s.map({1.0: "with", -1.0: "against", 0.0: "range/transition"}).fillna("unknown")


def table(d: pd.DataFrame, col: str) -> str:
    g = d.groupby([col, "year"]).r_multiple.agg(["count", "mean"]).unstack("year")
    lines = [f"\n{col}", f"  {'bucket':22} {'A n':>5} {'A R/t':>7}   {'B n':>5} {'B R/t':>7}"]
    for bucket, row in g.iterrows():
        n_a, m_a = np.nan_to_num(row.get(("count", "A"), 0)), row.get(("mean", "A"), np.nan)
        n_b, m_b = np.nan_to_num(row.get(("count", "B"), 0)), row.get(("mean", "B"), np.nan)
        flag = "  <- loses in both" if (m_a < 0 and m_b < 0 and n_a >= 8 and n_b >= 8) else ""
        lines.append(f"  {str(bucket):22} {int(n_a or 0):5} {m_a:+7.3f}   {int(n_b or 0):5} {m_b:+7.3f}{flag}")
    return "\n".join(lines)


def main() -> None:
    below_normal_priority()
    d = features(trades())
    d["hour"] = d["entry_time"].dt.hour
    d["session"] = pd.cut(d["hour"], [-1, 6, 11, 16, 23], labels=["asia 0-7", "london 7-12", "ny 12-17", "late 17-24"]).astype(str)
    d["rr"] = ((d["tp_initial"] - d["entry_price"]).abs() / (d["entry_price"] - d["sl_initial"]).abs()).round(1)
    d["rr_band"] = bands(d["rr"], [0, 1.5, 2.25, 10], ["<1.5", "1.5-2.25", ">2.25"])
    for tf in ("h1", "h4", "d1"):
        d[f"{tf}_map"] = trend_name(d.get(f"ctx:{tf}_trend", pd.Series(np.nan, index=d.index)))
        d[f"{tf}_swings"] = trend_name(d.get(f"ctx:{tf}_sw_trend", pd.Series(np.nan, index=d.index)))
        d[f"{tf}_vol"] = bands(d.get(f"ctx:{tf}_atr_pct"), [-1, 25, 75, 101], ["low <25", "mid", "high >75"])
    d["h4_room"] = bands(d.get("ctx:h4_lvl_against_r"), [-1, 2, 3, 5, 1e9], ["<2", "2-3", "3-5", ">5"])
    d["h1_room"] = bands(d.get("ctx:h1_lvl_against_r"), [-1, 1, 2, 3, 1e9], ["<1", "1-2", "2-3", ">3"])
    d["h1_zone_with"] = d.get("ctx:h1_zone_with").map({1.0: "in a zone", 0.0: "no zone"}).fillna("unknown")
    d["h4_zone_with"] = d.get("ctx:h4_zone_with").map({1.0: "in a zone", 0.0: "no zone"}).fillna("unknown")
    d["h4_box_pos"] = bands(d.get("ctx:h4_range_pos"), [-10, 0.33, 0.66, 10], ["low third", "middle", "high third"])
    for year in ("A", "B"):
        y = d[d.year == year]
        print(f"year {year}: {len(y)} trades, {y.r_multiple.mean():+.3f} R/trade, months {sorted(y.month.unique())}")
    for col in ("symbol", "side", "session", "rr_band", "h4_map", "h1_map", "d1_map", "h4_swings", "h1_swings",
                "d1_swings", "h4_vol", "h1_vol", "d1_vol", "h4_room", "h1_room", "h1_zone_with", "h4_zone_with",
                "h4_box_pos"):
        print(table(d, col))
    d.to_parquet("data/research/v1_regimes.parquet")


if __name__ == "__main__":
    main()
