"""F1 CONF-72 + the 0.5 M15-ATR stop floor: the reference trades for the bot port (2026-10-18). Saves the window's
signals and trades (research costs, and the engine's backtest costs) and checks two engine questions: does the cap of
two trades per session-day ever bind, and how many trades have a target nearer than the stop (RR < 1)?

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_port_ref.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
from portfolio import family_signals  # noqa: E402

OUT = Path("research/2026-10-18-moments/shadow")
P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)
S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, "wtest").reset_index(drop=True)
S["a15"] = a15.reindex(pd.to_datetime(S.t, utc=True), method="ffill").to_numpy()
S["sl0"] = S.sl
S["sl"] = np.maximum(S.sl, 0.5 * S.a15)
S[["t", "side", "session", "e", "level", "level_kind", "atr1", "c_dec", "unit", "sl0", "a15", "sl", "tp"]].to_parquet(OUT / "f1_port_signals.parquet")
z = plib.run(S, P)
z["t"] = pd.to_datetime(z.t, utc=True)
print(f"research costs: {len(z)} trades, R {z.R.mean():+.3f}, {z.pnl.sum():+.1f} USD, win {100 * (z.exit == 'win').mean():.0f}%")
z.attrs = {}
z.to_parquet(OUT / "f1_port_trades.parquet")
z9 = plib.run(S, P, per_sess=99)
print(f"no session cap: {len(z9)} trades, {z9.pnl.sum():+.1f} USD (cap binds: {len(z9) != len(z) or not np.allclose(z9.pnl.sum(), z.pnl.sum())})")
print(f"RR < 1 (stop beyond the target): {(z.sl > z.tp).sum()} of {len(z)}; RR range {(z.tp / z.sl).min():.2f}..{(z.tp / z.sl).max():.2f}")
print(f"signals on the window: {len(S)} rows, {S.t.nunique()} minutes; sessions {z.session.value_counts().to_dict()}")
# the engine's backtest costs: the bar spread column as is, 1 point slippage (0.01) everywhere
P.sp = P.sp0.copy()
P.slip = P.stop_slip = P.stop_slip_ny = 0.01
ze = plib.run(S, P)
ze["t"] = pd.to_datetime(ze.t, utc=True)
print(f"engine costs: {len(ze)} trades, R {ze.R.mean():+.3f}, {ze.pnl.sum():+.1f} USD")
ze.attrs = {}
ze.to_parquet(OUT / "f1_port_trades_enginecost.parquet")
print(z[["t", "side", "sl", "tp", "exit", "pnl", "mins"]].to_string())
