"""Planted bugs for audit 3: foundation.py's ATR / RSI / MACD / EMA against the earlier tests and the hand values.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_foundation
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PRE = ROOT / "research" / "2026-10-18-moments" / "agents" / "precursors"
TESTS = [
    "research/2026-10-18-moments/agents/audit2/test_foundation_hand.py",
    "research/2026-10-18-moments/agents/precursors/test_foundation.py",
]
FOUNDATION = [
    ("TR without the previous close against the low", "np.maximum(h, pc) - np.minimum(lo, pc)", "np.maximum(h, pc) - lo"),
    ("TR without the previous close against the high", "np.maximum(h, pc) - np.minimum(lo, pc)", "h - np.minimum(lo, pc)"),
    ("ATR as Wilder's smoothing", "return pd.Series(true_range(h, lo, c)).rolling(n).mean().to_numpy()",
     "return pd.Series(true_range(h, lo, c)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()"),
    ("ATR over n - 1 bars", "return pd.Series(true_range(h, lo, c)).rolling(n).mean().to_numpy()",
     "return pd.Series(true_range(h, lo, c)).rolling(n - 1).mean().to_numpy()"),
    ("RSI smoothing by n instead of n - 1", "pos = (pos * (n - 1) + gain[i - 1]) / n", "pos = (pos * n + gain[i - 1]) / (n + 1)"),
    ("RSI seed over n + 1 changes", "pos, neg = gain[:n].mean(), loss[:n].mean()", "pos, neg = gain[:n + 1].mean(), loss[:n + 1].mean()"),
    ("RSI 100 on a flat market", "np.where(p != 0, 100.0, 50.0)", "100.0"),
    ("MACD signal as an EMA", "return line, sma(line, signal)", "return line, ema(line, signal)"),
    ("MACD line reversed", "line = ema(c, fast) - ema(c, slow)", "line = ema(c, slow) - ema(c, fast)"),
    ("EMA with adjust=True", "ewm(span=n, adjust=False)", "ewm(span=n, adjust=True)"),
    ("EMA factor 1/n", "ewm(span=n, adjust=False)", "ewm(alpha=1 / n, adjust=False)"),
]
TARGETS = [("foundation", PRE / "foundation.py", TESTS, FOUNDATION)]
