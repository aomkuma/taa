"""Audit 3: foundation.py's ATR / RSI / MACD on values worked by hand (fractions written out below).

The existing precursors/test_foundation.py compares against literal ports of the MQL5 loops; these add the cases it
does not hand-check: a gap bar whose true range is |previous close - low|, an RSI whose seed has a loss, and MACD.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import foundation as F  # noqa: E402


def test_true_range_on_gaps_uses_the_previous_close() -> None:
    # bar1 gaps down: high 15, low 14 after a close of 20 -> TR = 20 - 14 = 6 (high - low is only 1)
    # bar2 gaps up: high 21, low 20 after a close of 14.5 -> TR = 21 - 14.5 = 6.5
    h, lo, c = np.array([21.0, 15, 21]), np.array([19.0, 14, 20]), np.array([20.0, 14.5, 20.5])
    tr = F.true_range(h, lo, c)
    assert np.isnan(tr[0]) and tr[1:].tolist() == [6.0, 6.5]
    a = F.atr(h, lo, c, 2)
    assert np.isnan(a[1]) and a[2] == pytest.approx((6 + 6.5) / 2)


def test_rsi_with_a_loss_in_the_seed() -> None:
    # closes 10, 12, 11, 14, 13 -> changes +2, -1, +3, -1; n = 2
    # seed (bars 1-2): gain (2 + 0) / 2 = 1, loss (0 + 1) / 2 = 0.5 -> RSI 100 - 100 / 3 = 66.667
    # bar 3: gain (1 * 1 + 3) / 2 = 2, loss (0.5 * 1 + 0) / 2 = 0.25 -> RS 8 -> RSI 100 - 100 / 9
    # bar 4: gain (2 * 1 + 0) / 2 = 1, loss (0.25 * 1 + 1) / 2 = 0.625 -> RS 1.6 -> RSI 100 - 100 / 2.6
    r = F.rsi(np.array([10.0, 12, 11, 14, 13]), 2)
    assert np.isnan(r[:2]).all()
    assert r[2:].tolist() == pytest.approx([100 - 100 / 3, 100 - 100 / 9, 100 - 100 / 2.6])


def test_macd_by_hand() -> None:
    # closes 10, 12, 11, 13; fast 2 (factor 2/3), slow 3 (factor 1/2), signal 2 (a simple average)
    # EMA2: 10, 34/3, 100/9, 334/27; EMA3: 10, 11, 11, 12
    # line: 0, 1/3, 1/9, 10/27; signal: -, 1/6, 2/9, 13/54
    line, sig = F.macd(np.array([10.0, 12, 11, 13]), 2, 3, 2)
    assert line.tolist() == pytest.approx([0, 1 / 3, 1 / 9, 10 / 27])
    assert np.isnan(sig[0]) and sig[1:].tolist() == pytest.approx([1 / 6, 2 / 9, 13 / 54])


def test_ema_seeded_with_the_first_price() -> None:
    # n = 3 (factor 1/2): 4, then 8 -> 6, then 2 -> 4
    assert F.ema(np.array([4.0, 8, 2]), 3).tolist() == pytest.approx([4, 6, 4])
