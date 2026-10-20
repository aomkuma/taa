"""The real trade result of every snap (owner, 2026-10-19: "the library learns the real trade result"): a buy and a
sell with V2's trade from each snap of the three-year library - entry at the next M1 open within 5 minutes, the entry
TF the smallest of M1 / M5 / M15 / M30 whose ATR covers 5 USD, the stop one entry-TF ATR >= 5 USD, the target 10 U,
out after 12 entry-TF bars, the auditor's costs (v2s.py's trade, verified 723 / 723 by check_v2s.py). Asserted equal
to v2s's walk-forward trades for the same snap and side.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/trade_labels.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))


def trade(mk: dict, j0: int, side: int, atrs: dict[str, float]) -> dict:
    """V2's trade from bar j0 (the first M1 bar opening at or after the snap) the given way."""
    from lvl2 import MINS, NS_MIN, manage  # noqa: PLC0415
    from v2b import plan  # noqa: PLC0415

    o, h, lo, c, sp, ot_ns, ny = (mk[k] for k in ("o", "h", "lo", "c", "sp", "ot_ns", "ny"))
    etf, sl, tp = plan(atrs, c[j0 - 1])
    ss = 0.20 if ny[j0] else 0.15
    entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
    t_end = int(ot_ns[j0] + 12 * MINS[etf] * NS_MIN)
    empty = (np.array([], np.int64), np.array([], float))
    x = manage(o, h, lo, c, sp, ot_ns, j0, side, entry, sl, tp, 0.0, *empty, 99.0, t_end, 0.07, ss)
    return dict(etf=etf, sl=sl, tp=tp, exit=x["exit"], pnl=x["pnl"], R=x["pnl"] / (sl + ss), xj=x["xj"])


def market() -> tuple[pd.DataFrame, dict]:
    """The M1 bars the trades walk (jlib's store, the same as the pictures'), as arrays."""
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415

    m = jlib.m1_frame("XAUUSD")
    mk = dict(o=m.open.to_numpy(float), h=m.high.to_numpy(float), lo=m.low.to_numpy(float), c=m.close.to_numpy(float),
              sp=m.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=m.index.tz_convert("UTC").as_unit("ns").asi8,
              ny=plib.ny_mask(m.index))
    return m, mk


def trades_at(m: pd.DataFrame, mk: dict, s_ns: np.ndarray) -> pd.DataFrame:
    """V2's buy and sell from every decision time (UTC ns): the entry bar j0 and each side's plan and result (no trade
    when no M1 bar opens within 5 minutes of the decision)."""
    import foundation as F  # noqa: PLC0415
    import plib  # noqa: PLC0415
    from lvl2 import NS_MIN  # noqa: PLC0415

    atr_at = {}
    for tf, rule in (("M1", None), ("M5", "5min"), ("M15", "15min"), ("M30", "30min")):
        if rule is None:
            hh, ll, cc, av = mk["h"], mk["lo"], mk["c"], mk["ot_ns"] + NS_MIN
        else:
            b = plib.tf_bars(m, rule)
            hh, ll, cc = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
            av = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
        a = F.atr(hh, ll, cc, 14)
        k = np.searchsorted(av, s_ns, side="right") - 1
        atr_at[tf] = np.where(k >= 0, a[np.maximum(k, 0)], np.nan)
    j0s = np.searchsorted(mk["ot_ns"], s_ns)
    rows = []
    for i in range(len(s_ns)):
        j0 = int(j0s[i])
        rec = dict(j0=j0)
        if j0 < len(mk["o"]) and mk["ot_ns"][j0] - s_ns[i] <= 5 * 60 * 10**9:
            atrs = {tf: atr_at[tf][i] for tf in atr_at}
            for side, nm in ((1, "buy"), (-1, "sell")):
                x = trade(mk, j0, side, atrs)
                rec |= {f"{nm}_{k}": v for k, v in x.items()}
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    snaps = np.nonzero((T.kind == "snap").to_numpy())[0]
    m, mk = market()
    s_ns = pd.DatetimeIndex(T.t_dec.to_numpy()[snaps]).as_unit("ns").asi8
    L = trades_at(m, mk, s_ns)
    L.insert(0, "row", snaps)
    # the same trade as v2s's walk-forward trades (verified independently 723 / 723)
    W = pd.read_parquet(HERE / "v2s_wf_trades.parquet").merge(L, on="row")
    for side, nm in ((1, "buy"), (-1, "sell")):
        w = W[W.side == side]
        assert len(w) and (w.j0_x == w.j0_y).all() and np.allclose(w.pnl, w[f"{nm}_pnl"], atol=1e-9), nm
        assert (w.exit == w[f"{nm}_exit"]).all() and (w.xj == w[f"{nm}_xj"]).all(), nm
    print(f"labels: {len(L)} snaps, {int(L.buy_R.notna().sum())} with a trade; equal to v2s's {len(W)} trades", flush=True)
    L.to_parquet(HERE / "snap_trade_labels.parquet")
    t = pd.DatetimeIndex(T.t_dec.to_numpy()[L.row])
    for name, k in (("learning", np.asarray(t < plib.EXAM_START)), ("exam", np.asarray(t >= plib.EXAM_START))):
        P = L[k]
        print(f"{name}: buy R {P.buy_R.mean():+.3f} (win {(P.buy_R > 0).mean():.3f}), sell R {P.sell_R.mean():+.3f} "
              f"(win {(P.sell_R > 0).mean():.3f}), a coin's side {((P.buy_R + P.sell_R) / 2).mean():+.3f}")


if __name__ == "__main__":
    main()
