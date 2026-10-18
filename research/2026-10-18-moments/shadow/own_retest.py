"""Round 13 (docs/OWN_SETUP.md): OWN-RT - the owner's own setup, the retest after the break, with the void rule
("if it has run very far, the setup is void - find a new one"). Gold, M1 entries, the journal's real costs.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/own_retest.py [--charts]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "journal"))
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
import jlib  # noqa: E402


def _m1(sym: str) -> pd.DataFrame:
    m = gold.bars("M1")
    m = m[(m.index >= pd.Timestamp("2023-08-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-17", tz="UTC"))]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


jlib.m1_frame = _m1  # the store now reaches 2026-10-16

REF, LOOK, VOID_M15, VOID_MIN, ZONE, FAIL, PAD = 4100.0, 24, 2.5, 120, 0.25, 0.5, 0.5
BE, HZ = 0.6, 180
V2 = "--v2" in sys.argv


def ohlc(m: pd.DataFrame, mins: int) -> pd.DataFrame:
    b = m.resample(f"{mins}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b["atr"] = (b.high - b.low).rolling(14).mean()
    b["end"] = b.index + pd.Timedelta(minutes=mins)
    return b


def signals(P: jlib.Instr) -> pd.DataFrame:
    m = P.m
    m5, m15, h1 = ohlc(m, 5), ohlc(m, 15), ohlc(m, 60)
    e20, e50 = h1.close.ewm(span=20, adjust=False).mean(), h1.close.ewm(span=50, adjust=False).mean()
    tide = np.where((e20 > e20.shift(3)) & (h1.close > e50), 1, np.where((e20 < e20.shift(3)) & (h1.close < e50), -1, 0))
    tide = pd.Series(tide, index=h1.end)
    a15 = pd.Series(m15.atr.to_numpy(), index=m15.end)
    hi24 = m5.high.rolling(LOOK).max().shift(1)
    lo24 = m5.low.rolling(LOOK).min().shift(1)
    ot = P.ot
    pos = pd.Series(np.arange(len(ot)), index=ot)
    rows = []
    busy_until = pd.Timestamp(0, tz="UTC")
    m5c, m5a, m5end = m5.close.to_numpy(), m5.atr.to_numpy(), pd.DatetimeIndex(m5.end)
    for k in range(LOOK + 14, len(m5)):
        t_close = m5end[k]  # the break is known at this bar's close
        if t_close.hour >= 20 or t_close < busy_until:
            continue
        ti = tide.iloc[tide.index.searchsorted(t_close, side="right") - 1] if t_close >= tide.index[0] else 0
        if ti == 0:
            continue
        s = int(ti)
        L = hi24.iloc[k] if s > 0 else lo24.iloc[k]
        if not np.isfinite(L) or (m5c[k] - L) * s <= 0:
            continue
        atr5 = m5a[k]
        atr15 = a15.iloc[a15.index.searchsorted(t_close, side="right") - 1]
        i = pos.get(t_close)
        if i is None or not np.isfinite(atr5) or not np.isfinite(atr15):
            continue
        # walk M1 from the break: void if too far / failed / too long; else the retest, then the trigger
        imp = P.h[i - 1] if s > 0 else P.lo[i - 1]
        touched, low_since, status = False, None, "none"
        end = min(i + VOID_MIN, len(P.o) - 2)
        j = i
        while j < end:
            hj, lj, cj = P.h[j], P.lo[j], P.c[j]
            if not touched:
                imp = max(imp, hj) if s > 0 else min(imp, lj)
                if (imp - L) * s > VOID_M15 * atr15:
                    status = "void_far"
                    break
                near = (lj - (L + s * ZONE * atr5)) * s <= 0
                if near:
                    touched, low_since, low_bar, quiet = True, (lj if s > 0 else hj), j, 0
            else:
                if V2 and (cj - (L - s * 0.25 * atr5)) * s < 0:  # a close back beyond the level: the break failed
                    status = "void_failed"
                    break
                if V2:
                    if (lj - low_since) * s < 0:  # a new pullback extreme: the count restarts
                        low_since, low_bar, quiet = (lj if s > 0 else hj), j, 0
                    else:
                        quiet += 1
                    turn = P.h[low_bar] if s > 0 else P.lo[low_bar]
                    if quiet >= 3 and (cj - turn) * s > 0:
                        status = "entry"
                        break
                else:
                    low_since = min(low_since, lj) if s > 0 else max(low_since, hj)
                    prev_ext = P.h[j - 1] if s > 0 else P.lo[j - 1]
                    if (cj - prev_ext) * s > 0 and (cj - (L - s * 0.25 * atr5)) * s > 0:
                        status = "entry"
                        break
            # a failed break: an M5 close beyond L - 0.5 ATR (checked on the M5 bar ending at this minute)
            if (ot[j] + pd.Timedelta(minutes=1)).minute % 5 == 0:
                c5 = cj
                if (c5 - (L - s * FAIL * atr5)) * s < 0:
                    status = "void_failed"
                    break
            j += 1
        else:
            status = "void_time"
        if status != "entry":
            rows.append(dict(t=t_close, side=s, status=status))
            continue
        e = j + 1
        fill = float(P.fill(np.array([e]), np.array([s]))[0])
        stop_px = low_since - s * PAD * atr5
        sl = (fill - stop_px) * s
        u = fill / REF
        tp = (imp - s * 0.1 * atr5 - fill) * s
        st = "entry"
        if not (3 * u <= sl <= 10 * u):
            st = "skip_stop"
        elif tp < sl:
            st = "skip_room"
        rows.append(dict(t=t_close, side=s, status=st, e=e, t_entry=ot[e], L=L, imp=imp, sl=sl, tp=tp, atr5=atr5, u=u,
                         session=0 if ot[e].hour < 7 else (1 if ot[e].hour < 12 else 2)))
        if st == "entry":
            busy_until = ot[e] + pd.Timedelta(minutes=HZ)
    return pd.DataFrame(rows)


def run(S: pd.DataFrame, P: jlib.Instr, coin: np.random.Generator | None = None) -> pd.DataFrame:
    out, free = [], pd.Timestamp(0, tz="UTC")
    for r in S[S.status == "entry"].sort_values("t_entry").itertuples():
        if r.t_entry < free:
            continue
        s = int(r.side) if coin is None else int(coin.choice([-1, 1]))
        ss = P.stop_slip_ny if r.session == 2 else P.stop_slip
        x = P.trade(int(r.e), s, float(r.tp), float(r.sl), BE, HZ, ss)
        x |= dict(t=r.t_entry, side=s, sl=float(r.sl), tp=float(r.tp), R=x["pnl"] / (float(r.sl) + ss), session=r.session,
                  L=r.L, imp=r.imp, e=int(r.e))
        out.append(x)
        free = r.t_entry + pd.Timedelta(minutes=int(x["mins"]))
    return pd.DataFrame(out)


def report(name: str, z: pd.DataFrame, by: str) -> None:
    if not len(z):
        print(f"  {name}: 0 trades")
        return
    eq = z.pnl.cumsum()
    streak = mx = 0
    for v in z.pnl:
        streak = streak + 1 if v < 0 else 0
        mx = max(mx, streak)
    g = z.groupby(z.t.dt.strftime("%Y-%m") if by == "month" else pd.cut(
        z.t, pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01"], utc=True), right=False), observed=True)
    per = " ".join(f"{(str(k)[5:7] if by == 'month' else str(k.left)[:7])} {v.R.mean():+.2f}({len(v)})" for k, v in g)
    los = z[z.exit == "stop"]
    kinds = los.kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    print(f"  {name}: {len(z)} trades, win {100 * (z.exit == 'win').mean():.0f}%, R {z.R.mean():+.3f}, {z.pnl.sum():+.1f} USD at 0.01 lot,"
          f" worst {z.pnl.min():.2f}, streak {mx}, max DD {(eq.cummax() - eq).max():.1f}; losers 1/2/3 "
          f"{100 * kinds['1']:.0f}/{100 * kinds['2']:.0f}/{100 * kinds['3']:.0f}% | {per}")


def main() -> None:
    gold.below_normal_priority()
    P = jlib.Instr("XAUUSD")
    S = signals(P)
    S["t"] = pd.to_datetime(S.t, utc=True)
    tag = "rt2" if V2 else "rt"
    S.to_parquet(f"data/research/own_{tag}_signals.parquet")
    for part, a, b, by in (("DESIGN 2023-11 .. 2026-02", "2023-11-01", "2026-03-01", "half"),
                           ("2026-03-01 .. 10-16 (new rule)", "2026-03-01", "2026-10-17", "month")):
        x = S[(S.t >= pd.Timestamp(a, tz="UTC")) & (S.t < pd.Timestamp(b, tz="UTC"))]
        print(f"\n== {part}: breaks {len(x)}; outcomes {x.status.value_counts().to_dict()}")
        z = run(x, P)
        report("OWN-RT2" if V2 else "OWN-RT", z, by)
        zc = run(x, P, np.random.default_rng(5))
        report("coin side", zc, by)
        z.to_parquet(f"data/research/own_{tag}_{'design' if by == 'half' else 'test'}.parquet")


if __name__ == "__main__":
    main()
