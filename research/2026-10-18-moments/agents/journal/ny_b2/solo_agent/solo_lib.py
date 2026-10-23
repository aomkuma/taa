"""The solo exam of the NY-B2 journal (PROTOCOL.md): shared loaders, the state, the exit variants and the skip rules.

Nothing after a week's end is read: the exam trades are filtered on their entry time before anything else, bars and
ticks go through week.py / retest_week.py, which use closed bars before each decision and the trade's own ticks.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SOLO = Path(__file__).resolve().parent
NYB2 = SOLO.parent
sys.path.insert(0, str(NYB2))
import retest_week as RT  # noqa: E402
import week as W  # noqa: E402

W.C.EXAM = pd.Timestamp("2026-10-23", tz="UTC")  # the owner allowed reading the exam period
EXAM_RAW = NYB2 / "exam_raw"
WEEK1 = pd.Timestamp("2026-04-18", tz="UTC")  # Saturday before exam week 1; a week = Sat 00:00 .. Sat 00:00 UTC
LEDGER = SOLO / "ledger.csv"
STATE = SOLO / "state.json"
LEARN = SOLO / "learning_b2.csv"

# the exit variants (PROTOCOL: the current exit + the candidates); band 1e-9 = aim at the line itself
EXITS = {"real": dict(be=True, band=0.1, hold=120), "nobe": dict(be=False, band=0.1, hold=120),
         "noband": dict(be=True, band=1e-9, hold=120), "hold90": dict(be=True, band=0.1, hold=90)}

# the skip rules, start rules and shadows: name -> mask over the enriched B2 frame
RULES = {
    "vol": lambda X: X.vol > 1.1,  # H1 ATR(14) > 1.1x its 20-day median
    "near": lambda X: X.zone_line_dist < 10.0,  # within 10 USD of a zone line
    "news": lambda X: (X.min_to_10et > 0) & (X.min_to_10et <= 30),  # 10:00-10:30 New York
}

START_STATE = {"exit": "real", "rules": {"vol": 1, "near": 1, "news": 1}, "shadows": {}, "pieces": {"B2": 1, "retest": 1},
               "stopped": {}, "deleted": {}, "log": []}


def bounds(n: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    s = WEEK1 + pd.Timedelta(days=7 * (n - 1))
    return s, s + pd.Timedelta(days=7)


def week_of(t: pd.Series) -> pd.Series:
    return ((t - WEEK1) // pd.Timedelta(days=7) + 1).astype(int)


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else json.loads(json.dumps(START_STATE))


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=1))


def load_b2(folder: Path, end: pd.Timestamp) -> pd.DataFrame:
    """week.load(), but the rows at / after `end` are dropped before anything else is read or computed."""
    T = pd.read_csv(folder / "trades.csv")
    T = T[pd.to_datetime(T.entry_time, utc=True) < end].copy()
    ids = set(T.signal_id)
    J = [json.loads(x) for x in open(folder / "journal.jsonl", encoding="utf-8")]
    J = pd.DataFrame([j for j in J if j["signal_id"] in ids])
    if not len(T):
        return T.assign(t=pd.Series(dtype="datetime64[ns, UTC]"))
    J = pd.concat([J.drop(columns=["conditions"]), pd.json_normalize(J.conditions)], axis=1)
    X = T.merge(J[["signal_id", "level", "pattern", "rule", "agreement", "h1_atr", "stop_distance"]], on="signal_id", how="left")
    X["t"] = pd.to_datetime(X.entry_time, utc=True)
    g = W.Z.daily_grid(W.Z.bars("D1"))
    k = g.index.searchsorted(X.t, side="right") - 1
    anc, stp = g.anchor.values[k], g.step.values[k]
    pos = (X.entry_price - anc) / stp
    X["zone_pos"] = pos - np.floor(pos)
    X["zone_line_dist"] = np.minimum(X.zone_pos, 1 - X.zone_pos) * stp
    X["zone_step_pos"] = np.minimum(X.zone_pos, 1 - X.zone_pos)
    return X.reset_index(drop=True)


def enrich(X: pd.DataFrame) -> pd.DataFrame:
    """Every exit variant, the pressure and context fields, the minutes from 10:00 New York, the 3-day run."""
    if not len(X):
        return X
    for k, p in EXITS.items():
        X[f"r_{k}"] = W.realistic(X, **p)
    X = X.join(W.pressure(X)).join(W.context(X))
    ny = X.t.dt.tz_convert("America/New_York")
    X["min_to_10et"] = ny.dt.hour * 60 + ny.dt.minute - 600
    X["run3"] = [W.run3(t) for t in X.t]
    X["tf"] = np.where(X.strategy.str.endswith("m5"), "M5", "M1")
    X["thai"] = X.t.dt.tz_convert("Asia/Bangkok").dt.strftime("%a %d %H:%M")
    X["risk"] = (X.entry_price - X.sl_initial).abs()
    return X


def learning() -> pd.DataFrame:
    """The 98 learning-week B2 trades (2025-10-20 .. 2026-04-17), enriched once and cached."""
    if LEARN.exists():
        L = pd.read_csv(LEARN)
        L["t"] = pd.to_datetime(L.t, utc=True)
        return L
    L = enrich(load_b2(NYB2, WEEK1))
    L["week"] = 0
    L["piece"] = "B2"
    L.drop(columns=["bounces"]).to_csv(LEARN, index=False)
    return L


def ledger() -> pd.DataFrame:
    if not LEDGER.exists():
        return pd.DataFrame()
    L = pd.read_csv(LEDGER)
    L["t"] = pd.to_datetime(L.t, utc=True)
    return L


def replay(L: pd.DataFrame, col: str) -> pd.DataFrame:
    """Both accounts over the ledger rows in time order on column `col` (NaN = not traded)."""
    A = L[["t", "entry_price", "sl_initial", col]].rename(columns={col: "rr"}).sort_values("t").copy()
    for eq0, pct in W.ACCOUNTS:  # week.accounts(), except that an account at or below 0 stops trading (blown)
        eq, bal = eq0, []
        for r in A.itertuples():
            risk = abs(r.entry_price - r.sl_initial)
            if np.isfinite(r.rr) and eq > 0:
                lots = max(0.01, np.floor(eq * pct / 100 / (risk * 100) * 100) / 100)
                eq += r.rr * risk * lots * 100
            bal.append(eq)
        A[f"balx_{eq0:.0f}"] = bal
    return A


def balances(L: pd.DataFrame, col: str, upto_week: int) -> tuple[float, float, float, float]:
    """(100 acct, 300 acct) after `upto_week`, and their worst drawdowns in USD so far."""
    A = replay(L[L.week <= upto_week], col)
    out = []
    for eq0 in (100, 300):
        b = np.r_[eq0, A[f"balx_{eq0}"].values]
        out += [b[-1], float((np.maximum.accumulate(b) - b).max())]
    return out[0], out[2], out[1], out[3]
