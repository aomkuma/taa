"""The bot's engine backtest of setup_own_conf72 against the research's trades (shadow/f1_port_ref.py), trade by
trade: entry minute, side, exit kind, and the result at 0.01 lot (price move x 1 for gold).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/f1_engine_parity.py data/backtests/own_window [ref.parquet]
"""

import sys

import pandas as pd

run = sys.argv[1]
ref_path = sys.argv[2] if len(sys.argv) > 2 else "research/2026-10-18-moments/shadow/f1_port_trades_enginecost.parquet"
e = pd.read_csv(f"{run}/trades.csv", parse_dates=["entry_time", "exit_time"])
e["side_n"] = e.side.map({"BUY": 1, "SELL": -1})
e["usd"] = (e.exit_price - e.entry_price) * e.side_n
e["t"] = pd.to_datetime(e.entry_time, utc=True)
r = pd.read_parquet(ref_path)
r["t"] = pd.to_datetime(r.t, utc=True)
m = e[["t", "side_n", "exit_reason", "usd", "r_multiple"]].merge(
    r[["t", "side", "exit", "pnl", "R"]], on="t", how="outer", indicator=True)
pd.set_option("display.width", 200)
print(m.round(2).to_string(index=False))
both = m[m._merge == "both"]
print(f"\nengine {len(e)} trades {e.usd.sum():+.1f} USD (0.01 lot) R {e.r_multiple.mean():+.3f} | research {len(r)} trades"
      f" {r.pnl.sum():+.1f} USD R {r.R.mean():+.3f} | matched {len(both)}, engine only {(m._merge == 'left_only').sum()},"
      f" research only {(m._merge == 'right_only').sum()}; matched |usd diff| median {(both.usd - both.pnl).abs().median():.2f},"
      f" max {(both.usd - both.pnl).abs().max():.2f}")
