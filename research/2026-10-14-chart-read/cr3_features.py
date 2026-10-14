"""CR-3 (docs/CHART_READ.md §8 M1): a proven setup's year of trades with the chart read features, walk-forward.

The trades: breakout F1 (``f1``: data/backtests/inv/setup_breakout_f1_2025-10 .. _2026-09) or harmonic V1
(``v1``: data/backtests/inv/setup_harmonic_prz_v11y). For each trade the market map at its entry is rebuilt
with the engine's own code (``MapBook.from_config`` on the setup's research config with the context
timeframes H1, H4, D1, full context history as in a backtest) and its ``ctx:`` features are computed relative
to the trade (``signal_features``: side, entry, initial stop and target).

Two stages, so the rules are written down before the data that judges them is looked at:

- ``choose``: the first half (entries before 2026-04-09) without the hold-out symbols (AUDUSD, XAUUSD); every
  candidate filter of §7 that a taken trade can be judged by (structure_gate, mixed_rule, level_gate,
  room_min_r on H1 / H4);
- ``judge RULE [RULE ...]``: the named rules on the second half (without the hold-outs) and on the hold-out
  symbols (whole year), next to the first half.

``structure_stop`` and ``screen_source: swings`` change which trades exist or how they end; they need the
backtest ladder (CR-6), not this filter view.

    .venv/Scripts/python research/2026-10-14-chart-read/cr3_features.py f1 choose
    .venv/Scripts/python research/2026-10-14-chart-read/cr3_features.py f1 judge h4_not_against h1_room_2
"""

from __future__ import annotations

import glob
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.backtest.runner import load_context  # noqa: E402
from app.config import AppConfig, load_app_config  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.indicators.market_map import signal_features  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.market_maps import MapBook  # noqa: E402

B = "data/backtests/inv/"
SETUPS = {
    "f1": (B + "setup_breakout_f1_20*/trades.csv", "data/research/config_bo_f1.yaml"),
    # config_h_v1.yaml predates risk.fade; the map reads only indicators / context_map, as in config.yaml
    "v1": (B + "setup_harmonic_prz_v11y/trades.csv", "config.yaml"),
}
CONTEXT = ["H1", "H4", "D1"]
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")
HOLDOUT = {"AUDUSD", "XAUUSD"}
TOL = 0.25  # the read's tol_atr: "at a level"

Rule = Callable[[pd.DataFrame], pd.Series]


def _f(df: pd.DataFrame, key: str) -> pd.Series:
    return df[key] if key in df else pd.Series(np.nan, index=df.index)


def rules() -> dict[str, Rule]:
    out: dict[str, Rule] = {}
    for tf in ("h1", "h4"):
        k = f"ctx:{tf}_"
        out[f"{tf}_not_against"] = lambda d, k=k: _f(d, k + "sw_trend") >= 0
        out[f"{tf}_with"] = lambda d, k=k: _f(d, k + "sw_trend") == 1
        out[f"{tf}_skip_mixed"] = lambda d, k=k: _f(d, k + "sw_phase") == 0
        out[f"{tf}_at_level"] = lambda d, k=k: (_f(d, k + "lvl_with_atr") <= TOL) | (_f(d, k + "lvl_flipped") == 1)
        for r in (1.0, 1.5, 2.0):
            out[f"{tf}_room_{r:g}"] = lambda d, k=k, r=r: _f(d, k + "lvl_against_r") >= r
    higher = {"h1": "h4", "h4": "d1"}
    for tf, up in higher.items():
        k, u = f"ctx:{tf}_", f"ctx:{up}_"

        def surest(d: pd.DataFrame, k: str = k, u: str = u) -> pd.Series:
            mixed = _f(d, k + "sw_phase") > 0
            sure = (_f(d, u + "sw_trend") == 1) & (
                (_f(d, k + "lvl_with_atr") <= TOL) | (_f(d, k + "lvl_flipped") == 1)
            )
            return ~mixed | sure

        out[f"{tf}_surest_mixed"] = surest
    return out


def features(setup: str) -> pd.DataFrame:
    cache = Path(B) / f"cr3_{setup}_features.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    pattern, config = SETUPS[setup]
    t = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(pattern))], ignore_index=True)
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    raw = load_app_config(config).model_dump(mode="json")
    raw["timeframes"]["context"] = CONTEXT  # features only: the trades are given
    cfg = AppConfig.model_validate(raw)
    book = MapBook.from_config(cfg)
    if book is None:
        raise SystemExit("the F1 config has no context timeframes")
    store = ParquetHistoryStore(Path("data/history"))
    tfs = list(cfg.timeframes.context)
    ctx = load_context(store, "FBS-Demo", sorted(t.symbol.unique()), tfs)
    rows = []
    for _, r in t.iterrows():
        spec = store.spec("FBS-Demo", r.symbol)
        point = float(spec["spec"]["point"])  # type: ignore[index]
        mm = book.at(r.symbol, ctx[r.symbol], r.entry_time.to_pydatetime(), point)
        f = (
            {}
            if mm is None
            else signal_features(
                mm, buy=r.side == "BUY", entry=r.entry_price, stop=r.sl_initial, target=r.tp_initial
            )
        )
        rows.append({**{k: r[k] for k in ("symbol", "side", "entry_time", "r_multiple")}, **f})
    out = pd.DataFrame(rows)
    out.to_parquet(cache)
    return out


RNG = np.random.default_rng(42)


def ci(v: pd.Series) -> str:
    a = v.to_numpy()
    if len(a) < 3:
        return "      -        "
    b = RNG.choice(a, (4000, len(a))).mean(axis=1)
    return f"[{np.quantile(b, 0.05):+.3f}, {np.quantile(b, 0.95):+.3f}]"


def line(name: str, d: pd.DataFrame, keep: pd.Series) -> str:
    k, x = d[keep], d[~keep]
    removed = f"{x.r_multiple.mean():+.3f} R (n {len(x)})" if len(x) else "-"
    return (
        f"  {name:20} kept n {len(k):3}  {k.r_multiple.mean():+.3f} R  CI90 {ci(k.r_multiple)}  "
        f"total {k.r_multiple.sum():+6.2f} R   removed {removed}"
    )


def main() -> None:
    setup = sys.argv[1] if len(sys.argv) > 1 else "f1"
    stage = sys.argv[2] if len(sys.argv) > 2 else "choose"
    d = features(setup)
    first = d.entry_time < SPLIT
    hold = d.symbol.isin(HOLDOUT)
    sets = {
        "choose (1st half, no hold-outs)": d[first & ~hold],
        "2nd half (no hold-outs)": d[~first & ~hold],
        "hold-outs AUDUSD+XAUUSD (year)": d[hold],
    }
    rs = rules()
    if stage == "choose":
        c = sets["choose (1st half, no hold-outs)"]
        print(f"{setup} trades {len(d)}; choose set {len(c)}: {c.r_multiple.mean():+.3f} R, total {c.r_multiple.sum():+.2f} R")
        cov = {k: int(c[k].notna().sum()) for k in c.columns if k.startswith("ctx:") and "_sw_trend" in k}
        print(f"features present (sw_trend): {cov}\n")
        print(line("baseline", c, pd.Series(True, index=c.index)))
        for name, rule in rs.items():
            print(line(name, c, rule(c).fillna(False).astype(bool)))
        return
    chosen = sys.argv[3:]
    unknown = [n for n in chosen if n not in rs]
    if unknown or not chosen:
        raise SystemExit(f"name 1-3 rules from: {', '.join(rs)} (unknown: {unknown})")
    for title, s in sets.items():
        print(f"\n== {title}: {len(s)} trades")
        print(line("baseline", s, pd.Series(True, index=s.index)))
        for name in chosen:
            print(line(name, s, rs[name](s).fillna(False).astype(bool)))
        if len(chosen) > 1:
            keep = pd.Series(True, index=s.index)
            for name in chosen:
                keep &= rs[name](s).fillna(False).astype(bool)
            print(line("all chosen", s, keep))


if __name__ == "__main__":
    main()
