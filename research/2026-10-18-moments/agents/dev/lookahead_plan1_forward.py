"""The no-look-ahead check of the forward recorder's new reading (plan1_forward.py): the H1 ATR at each decision, on
every learning trade of the self-test (plan1_forward_selftest_w14.parquet; the pieces themselves are plan1.py's, whose
check passed: out_lookahead_plan1.txt).

(a) every M1 bar opening at / after the start of the decision's hour (the forming H1 bar and everything later)
    replaced by other prices (x 1.07): the ATR at the decision and the band must be unchanged;
(b) the H1 bar it reads must close at / before the decision and the forming bar must not be complete;
(c) power: the read H1 bar's own M1 bars replaced (x 1.07): the ATR must change on every trade.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_plan1_forward.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan1 as L  # noqa: E402
import plan1_forward as F  # noqa: E402

OHLC = ["open", "high", "low", "close"]
H = 3600 * 10**9


def atr_now(m: pd.DataFrame, t: int) -> float:
    av, a = F.h1_atr(m)
    return float(F.atr_at(av, a, [t])[0])


def main() -> None:
    T = pd.read_parquet(HERE / "plan1_forward_selftest_w14.parquet")
    m_all = L.load_m1(F.EXAM_START, False)
    t_m = m_all.index.as_unit("ns").asi8
    same = order = power = 0
    bad = []
    for r in T.itertuples(index=False):
        t = int(r.t_dec)
        w = (t_m >= t - 5 * 86400 * 10**9) & (t_m < t + 86400 * 10**9)  # 5 days back: >= 15 H1 bars; the SMA needs 15
        m = m_all[w]
        a0 = atr_now(m, t)
        hour = t - t % H  # the start of the decision's (forming) hour, UTC
        m2 = m.copy()
        k = m2.index.as_unit("ns").asi8 >= hour
        m2.loc[k, OHLC] = m.loc[k, OHLC].to_numpy() * 1.07
        a1 = atr_now(m2, t)
        ok = a0 == a1 and bool(F.in_band([a0])[0]) == bool(r.band) and a0 == r.atr_h1
        same += ok
        if not ok:
            bad.append((r.piece, pd.Timestamp(t, tz="UTC"), a0, a1, r.atr_h1))
        av, _ = F.h1_atr(m)
        i = int(np.searchsorted(av, t, side="right")) - 1
        order += av[i] <= t and (i + 1 == len(av) or av[i + 1] > t)
        m3 = m.copy()
        k3 = (m3.index.as_unit("ns").asi8 >= av[i] - H) & (m3.index.as_unit("ns").asi8 < av[i])
        m3.loc[k3, OHLC] = m.loc[k3, OHLC].to_numpy() * 1.07
        power += atr_now(m3, t) != a0
    n = len(T)
    print(f"(a) the ATR and the band unchanged with the forming hour and every later M1 bar replaced: {same} of {n}")
    for b in bad:
        print(f"    differs: {b}")
    print(f"(b) the read H1 bar closes at / before the decision and the next one after it: {order} of {n}")
    print(f"(c) power - the read H1 bar's M1 bars replaced changes the ATR: {power} of {n}")
    print(f"\nLOOK-AHEAD CHECK {'PASSED' if same == n and order == n and power == n else 'FAILED'}")


if __name__ == "__main__":
    main()
