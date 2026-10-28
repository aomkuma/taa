"""Round 4: the measurer's new research code (precursors/ns1.py, ns1_ticks.py, ns2.py, sw20_plan1.py, check_plan1.py),
read only. Nothing here reads market data: the readers are replaced by stubs, the ticks are written here.

- One trade per release day: the calendar holds two 08:30 releases on 2025-04-30 (GDP and PCE), and
  `ns1_ticks.main` / `ns2.main` iterate `sorted(...date)` without removing the repeat, so that day is traded twice.
  FAILS on the current code (ns1.run_days and fetch_release_ticks use a set and are right).
- The three straddle copies agree: `ns1_ticks.straddle` = `ns2.straddle_k(k=1)` = `check_plan1.ny`'s rule.
- `sw20_plan1.switch` against a brute-force reading of its definition.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_measurer_r4.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PRE = Path(__file__).resolve().parents[1] / "precursors"
sys.path.insert(0, str(PRE))
import check_plan1 as C  # noqa: E402
import ns1_ticks as N  # noqa: E402
import ns2  # noqa: E402
from sw20_plan1 import switch  # noqa: E402

MIN, S = 60 * 10**9, 10**9
TWICE = "2025-04-30"  # GDP and PCE, both 08:30 ET, in app/news/us_releases.csv


def _calendar_has_the_repeat() -> None:
    cal = pd.read_csv(N.ROOT / "app/news/us_releases.csv")
    assert (cal[(cal.time_et == "08:30")].date == TWICE).sum() == 2


def _capture(monkeypatch) -> list[pd.DataFrame]:
    saved: list[pd.DataFrame] = []
    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, *a, **k: saved.append(self.copy()))
    return saved


def _trade(*a, **k) -> dict:
    return dict(side=1, k=1.0, entry=100.0, exit_px=101.0, pnl=1.0, R=0.125, exit="time", spread=0.3)


def test_ns1_ticks_trades_each_release_day_once(monkeypatch) -> None:
    _calendar_has_the_repeat()
    saved = _capture(monkeypatch)
    tk = (np.array([0], np.int64), np.array([1.0]), np.array([1.2]))
    monkeypatch.setattr(N, "load", lambda d: tk if d in (TWICE, "2025-04-29") else None)
    monkeypatch.setattr(N, "straddle", lambda *a, **k: {key: v for key, v in _trade().items() if key not in ("k", "spread")})
    N.main()
    T = saved[-1]
    assert not T.day.duplicated().any(), T.day.tolist()


def test_ns2_trades_each_release_day_once(monkeypatch) -> None:
    _calendar_has_the_repeat()
    saved = _capture(monkeypatch)
    monkeypatch.setattr(C, "EXAM", C.EXAM)  # restored after the test (ns2.main moves it)
    monkeypatch.setattr(C, "day_ticks", lambda *a, **k: None)  # no day from 2025-10-18 on is read
    tk = (np.array([0], np.int64), np.array([1.0]), np.array([1.2]))
    monkeypatch.setattr(N, "load", lambda d: tk if d == TWICE else None)
    monkeypatch.setattr(ns2, "h1_atr", lambda: pd.Series([16.33], index=pd.DatetimeIndex(["2021-01-01"], tz="UTC")))
    monkeypatch.setattr(ns2, "straddle_k", _trade)
    ns2.main()
    T = saved[-1]
    assert not T.day.duplicated().any(), T.day.tolist()


# ---------------------------------------------------------------- the three straddle copies
def _ticks(rng: np.random.Generator, t0: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = 7000  # about 55 min of ticks from t0 - 10 min
    t = t0 - 10 * MIN + np.cumsum(rng.integers(50, 900, n)).astype(np.int64) * 10**6  # 0.05 .. 0.9 s apart
    size = rng.choice([-1.0, 1.0]) * rng.uniform(1.5, 12.0) * (rng.random() < 0.8)  # a release jump, sometimes none
    bid = 2000 + np.cumsum(rng.normal(0, 0.15, n)) + size * (t >= t0 + int(rng.integers(0, 70)) * S)
    ask = bid + rng.uniform(0.1, 0.5, n)
    return t, bid, ask


def test_the_straddle_copies_agree() -> None:
    rng = np.random.default_rng(4)
    t0 = pd.Timestamp("2024-05-15 12:30", tz="UTC").value
    traded = 0
    for _ in range(300):
        t, bid, ask = _ticks(rng, t0)
        if t[-1] < t0 + 30 * MIN:
            continue
        a = N.straddle(t, bid, ask, t0)
        b = ns2.straddle_k(t, bid, ask, t0, 1.0)
        assert (a is None) == (b is None)
        if a is None:
            continue
        traded += 1
        assert (a["side"], a["entry"], a["exit"]) == (b["side"], b["entry"], b["exit"])
        assert a["pnl"] == pytest.approx(b["pnl"]) and a["R"] == pytest.approx(b["R"])
    assert traded > 50  # power: most series trade


def test_ns2_scales_the_trigger_and_the_stop() -> None:
    t0 = pd.Timestamp("2024-05-15 12:30", tz="UTC").value
    t = t0 + np.array([-5, 2, 10, 31 * 60], np.int64) * S
    bid = np.array([100.0, 100.9, 99.5, 99.0])
    ask = bid + 0.2
    # k 0.5: buy stop 100.2 + 1.0 = 101.2 (the ask 101.1 at +2 s is short), sell stop 100 - 1.0 = 99.0 (the bid 99.5
    # at +10 s is short; the 99.0 tick comes after the 60 s): no trade. k 0.4: buy stop 100.2 + 0.8 = 101.0 -> 101.1
    assert ns2.straddle_k(t, bid, ask, t0, 0.5) is None
    x = ns2.straddle_k(t, bid, ask, t0, 0.4)
    assert (x["side"], x["entry"]) == (1, pytest.approx(101.1))
    # the stop 8 k = 3.2 below the fill: 97.9, never reached; out at the time (the bid 99.0 at +31 min)
    assert x["exit"] == "time" and x["R"] == pytest.approx((99.0 - 101.1) / 3.2)


# ---------------------------------------------------------------- SW-20
def _brute(g: pd.DataFrame, n: int) -> list[bool]:
    out = []
    for r in g.itertuples():
        seen = g[g.t_out < r.t_in].sort_values("t_out", kind="stable")
        out.append(len(seen) >= n and seen.R.iloc[-n:].mean() > 0)
    return out


def test_sw20_switch_against_its_definition() -> None:
    rng = np.random.default_rng(8)
    for _ in range(150):
        k = int(rng.integers(1, 60))
        t_in = np.sort(rng.integers(0, 5000, k))
        g = pd.DataFrame({"t_in": t_in.astype(np.int64), "t_out": (t_in + rng.integers(1, 400, k)).astype(np.int64),
                          "R": rng.choice([-1.0, -0.5, 0.0, 0.5, 2.0], k)})
        n = int(rng.integers(1, 6))
        assert switch(g, n=n).tolist() == _brute(g, n)
