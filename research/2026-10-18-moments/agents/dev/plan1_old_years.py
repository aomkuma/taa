"""PLAN-1 through the bot on the old years (owner 2026-10-21 ~20:00 Thai): lane `plan1` (the London ORB, the NY
straddle, Asia B2 on M1 and M5; every journal rule in force, the regime switch D1 ATR(20) >= 60 on) backtested with
the tick path (--ticks) on 2021-09-01 .. 2025-09-30, one heavy run at a time, one year per run (one account each).

Data: the old M1 / H1 at data/history_old (to 2023-10-02), the newer at data/history (from 2023-09-01 M1, 2023-08-01
H1); the ticks at D:/taa-data/ticks. Nothing at / after 2025-10-01 is read (the history load and the tick store end
there; the learning parts and the exam are not in these runs).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_old_years.py run Y1   # Y1 .. Y4, one at a time
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_old_years.py report
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

END = pd.Timestamp("2025-10-01", tz="UTC")
TICKS = Path("D:/taa-data/ticks")
RUNS = {  # name: (store, start, end) - the store holds the warm-up before the start
    "Y1": ("data/history_old", "2021-09-01", "2022-09-01"),
    "Y2": ("data/history_old", "2022-09-01", "2023-09-25"),
    "Y3": ("data/history", "2023-09-25", "2024-09-01"),
    "Y4": ("data/history", "2024-09-01", "2025-10-01"),
}
PIECE = {"setup_plan1_orb": "London ORB", "setup_plan1_ny": "NY straddle", "setup_plan1_b2": "Asia B2",
         "setup_plan1_b2m5": "Asia B2"}


def run(name: str) -> None:
    from app.backtest.runner import load_history, run_backtest
    from app.config import load_settings
    from app.market_data.history_store import ParquetHistoryStore
    from app.market_data.tick_store import TickStore
    from app.news.releases import load_releases

    store_dir, a, b = RUNS[name]
    start, end = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
    if end > END:
        raise SystemExit("past 2025-09-30")
    settings = load_settings()
    full = settings.config
    cfg = full.for_lane(full.lane("plan1"))
    cfg = cfg.model_copy(update={
        "backtest": cfg.backtest.model_copy(update={"slippage_model": "none", "slippage_points": 0.0}),
        "risk": cfg.risk.model_copy(update={"max_risk_per_trade_percent": 0.25, "max_consecutive_losses": 50,
                                            "consecutive_loss_pause_hours": 0.0}),
    })
    loaded = load_history(ParquetHistoryStore(settings.path(store_dir)), "FBS-Demo", ["XAUUSD"], cfg.timeframes.enabled,
                          account_currency="USD", start=None, end=end.to_pydatetime())
    result, prov = run_backtest(cfg, loaded, config_hash=f"plan1-old-{name}", strategy_names=list(PIECE),
                                start=start.to_pydatetime(), end=(end - pd.Timedelta(minutes=1)).to_pydatetime(),
                                quotes=TickStore(TICKS, end=end.to_pydatetime()),
                                calendar=lambda f: load_releases(settings.path(f)))
    rows = [dict(piece=PIECE[t.strategy], strategy=t.strategy, t_in=pd.Timestamp(t.entry_time).value,
                 t_out=pd.Timestamp(t.exit_time).value, side=1 if t.side.value == "BUY" else -1, entry=t.entry_price,
                 stop=t.sl_initial, exit_px=t.exit_price, exit=t.exit_reason.value, net=t.net)
            for t in result.trades]
    A = pd.DataFrame(rows)
    if len(A):
        A["risk"] = (A.entry - A.stop) * A.side
        A["R"] = (A.exit_px - A.entry) * A.side / A.risk
    A.to_parquet(HERE / f"plan1_old_{name}.parquet")
    # the regime switch, each weekday at 06:00 UTC (the ORB's open): off when the D1 ATR(20) < 60 or unknown
    from app.core.enums import Timeframe
    from app.strategy.plan1 import d1_atr20

    h1 = ParquetHistoryStore(settings.path(store_dir)).load("FBS-Demo", "XAUUSD", Timeframe.H1, None, end.to_pydatetime())
    h1 = h1.set_index(pd.to_datetime(h1["open_time"], utc=True) + pd.Timedelta(hours=1))
    days = pd.bdate_range(start.tz_localize(None), end.tz_localize(None), inclusive="left", tz="UTC")
    vals = [d1_atr20(h1[h1.index <= d + pd.Timedelta(hours=6)].iloc[-3000:], d + pd.Timedelta(hours=6)) for d in days]
    pd.DataFrame({"day": days, "atr20": vals}).to_parquet(HERE / f"plan1_old_{name}_regime.parquet")
    print(f"{name} {a} .. {b}: {len(A)} trades, decisions {dict(result.decisions)}, rejections {dict(result.rejections)}, "
          f"tick minutes {result.tick_minutes}, data hash {prov.data_hash}", flush=True)


def report() -> None:
    lines = []
    for name, (_, a, b) in RUNS.items():
        f = HERE / f"plan1_old_{name}.parquet"
        if not f.exists():
            continue
        A = pd.read_parquet(f)
        Rg = pd.read_parquet(HERE / f"plan1_old_{name}_regime.parquet")
        off = int((~(Rg.atr20 >= 60)).sum())
        lines.append(f"\n{name} {a} .. {b}: {len(A)} trades; regime switch off on {off} of {len(Rg)} weekdays "
                     f"(D1 ATR(20) < 60 or unknown; median {Rg.atr20.median():.1f})")
        if not len(A):
            continue
        for pc, g in A.groupby("piece"):
            lines.append(f"  {pc:12s} {len(g):4d} trades  win {np.mean(g.R > 0):.2f}  R/trade {g.R.mean():+.3f}  "
                         f"sum R {g.R.sum():+.2f}")
        lines.append(f"  {'lane':12s} {len(A):4d} trades  win {np.mean(A.R > 0):.2f}  R/trade {A.R.mean():+.3f}  "
                     f"sum R {A.R.sum():+.2f}")
    text = "\n".join(lines)
    print(text)
    (HERE / "out_plan1_old_years.txt").write_text(text.lstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2])
    else:
        report()
