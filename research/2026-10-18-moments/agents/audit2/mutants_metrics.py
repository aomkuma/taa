"""Planted bugs for audit 8: wf.longest_run / weekly and a summary's drawdown, against audit2/test_metrics.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_metrics
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PRE = ROOT / "research" / "2026-10-18-moments" / "agents" / "precursors"
TESTS = ["research/2026-10-18-moments/agents/audit2/test_metrics.py"]
WF = [
    ("the streak never resets", "cur = cur + 1 if x else 0", "cur = cur + 1 if x else cur"),
    ("the streak is the last run, not the longest", "best = max(best, cur)", "best = cur"),
    ("the week on the UTC clock", 'th = pd.DatetimeIndex(T.t).tz_convert("Asia/Bangkok")', 'th = pd.DatetimeIndex(T.t).tz_convert("UTC")'),
    ("the running USD not cumulative", "W.usd.cumsum().round(2)", "W.usd.round(2)"),
    ("the worst trade is the best", '"worst": g.pnl.min().round(2)', '"worst": g.pnl.max().round(2)'),
    ("the week's R is the mean", '"R": g.R.sum().round(2)', '"R": g.R.mean().round(2)'),
]
SR_BREAK = [
    ("the drawdown without the start again", "(eq.cummax().clip(lower=0) - eq).max()", "(eq.cummax() - eq).max()"),
    ("the drawdown as the lowest running total", "(eq.cummax().clip(lower=0) - eq).max()", "(-eq.min())"),
]
TARGETS = [("wf", PRE / "wf.py", TESTS, WF), ("sr_break", PRE / "sr_break.py", TESTS, SR_BREAK)]
