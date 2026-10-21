"""Row 58 - five setups for the CALM gold (H1 ATR < 12), pre-registered at the top of PROPOSALS.md.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/calm58.py learn   # LEARN only; freezes the settings
    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/calm58.py test    # TEST once (needs the frozen file)
Run from the repo root. Ticks: D:/taa-data/ticks/XAUUSD; the costs are the tick spread only, slippage 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # gold.py
sys.path.insert(0, str(HERE.parent / "precursors"))
TICKS = Path("D:/taa-data/ticks/XAUUSD")
LEARN = (pd.Timestamp("2021-09-01", tz="UTC"), pd.Timestamp("2023-10-01", tz="UTC"))
TEST = (pd.Timestamp("2023-10-01", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC"))
FROZEN = HERE / "calm58_frozen.json"
MIN = 60 * 10**9
CALM = 12.0

# the settings per candidate: (name, side, stop multiple, target) for tsim.grid; ASIA_FADE's are the stop buffers b
SETTINGS = {
    "ORB_FADE": [("i stop d, target d", "opp", 1.0, "1R0"), ("ii stop d, target 0.5 d", "opp", 1.0, 0.25),
                 ("iii stop 1.5 d, target d", "opp", 1.5, "1R0")],
    "STR_FADE": [("i stop 8, no target, 30 min", "opp", 1.0, "orig"), ("ii stop 8, target 8", "opp", 1.0, "orig"),
                 ("iii stop 4, target 4", "opp", 0.5, 0.5)],
    "ASIA_FADE": [("b 0.10", "same", 1.0, "orig"), ("b 0.25", "same", 1.0, "orig"), ("b 0.50", "same", 1.0, "orig")],
    "RC_CALM": [("target 2 R (rule)", "same", 1.0, "orig"), ("target 1 R", "same", 1.0, 0.5),
                ("target 0.5 R", "same", 1.0, 0.25)],
    "RT_OPP_CALM": [("i stop d, target d", "opp", 1.0, "1R0"), ("ii stop d, target 0.5 d", "opp", 1.0, 0.25),
                    ("iii stop 1.5 d, target d", "opp", 1.5, "1R0")],
}
ASIA_B = (0.10, 0.25, 0.50)


def period_of(phase: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    if phase == "learn":
        return LEARN
    if phase == "test":
        if not FROZEN.exists():
            raise RuntimeError("TEST is read only after the LEARN run froze the settings")
        return TEST
    raise ValueError(phase)


def ticks(day: pd.Timestamp, end: pd.Timestamp):
    """A UTC day's ticks; never a day at / after `end` (the phase's end)."""
    if day >= end:
        return None
    f = TICKS / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f, columns=["time_utc", "bid", "ask"]).sort_values("time_utc", kind="stable")
    return (pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), x.bid.to_numpy(float),
            x.ask.to_numpy(float))


def span(t_ns: int, end: pd.Timestamp, cache: dict):
    d = pd.Timestamp(int(t_ns), tz="UTC").normalize()
    if d not in cache:
        cache.clear()
        a = ticks(d, end)
        b = ticks(d + pd.Timedelta(days=1), end) if a is not None else None
        cache[d] = a if b is None else tuple(np.concatenate([x, y]) for x, y in zip(a, b, strict=True))
    return cache[d]


# ---------------------------------------------------------------- ASIA_FADE's event (pure; tested)
def asia_event(o_ns, hi, lo, cl, ah: float, al: float, h0: int, h1: int):
    """In the M1 bars with open time in [h0, h1): after a bar trades beyond an Asia edge, the first M1 close back inside
    the range (the same bar counts) -> (decision ns = that bar's close, fade side, the excursion's extreme). The first
    edge to be traded beyond decides; None if no close back inside within the hour."""
    i0, i1 = int(np.searchsorted(o_ns, h0)), int(np.searchsorted(o_ns, h1))
    side, ext = 0, np.nan
    for k in range(i0, i1):
        if side == 0:
            if hi[k] > ah:
                side, ext = -1, hi[k]
            elif lo[k] < al:
                side, ext = 1, lo[k]
            else:
                continue
        else:
            ext = max(ext, hi[k]) if side < 0 else min(ext, lo[k])
        if (side < 0 and cl[k] < ah) or (side > 0 and cl[k] > al):
            return int(o_ns[k] + MIN), side, float(ext)
    return None


def events(phase: str) -> pd.DataFrame:
    """Every candidate's events in the phase, with the H1 ATR at the decision (vol16_old's ATR)."""
    import gold
    import ns1_ticks as N
    import streams

    a, b = period_of(phase)
    m = gold.bars("M1", before=b)
    m = m[m.index >= a - pd.Timedelta(days=40)]
    m = m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)
    m = m[~m.index.duplicated(keep="last")].sort_index()
    m.index = pd.DatetimeIndex(m.index).as_unit("ns")
    assert m.index.max() < b
    h = gold.bars("H1", before=b)[["high", "low", "close"]]
    pc = h.close.shift(1)
    atr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    a_t, a_v = (h.index + pd.Timedelta(hours=1)).as_unit("ns").asi8, atr.to_numpy()

    def atr_at(t_ns: int) -> float:
        i = int(np.searchsorted(a_t, t_ns, side="right")) - 1
        return float(a_v[i]) if i >= 0 else np.nan

    o = m.index.asi8
    hi_, lo_, cl_ = m.high.to_numpy(), m.low.to_numpy(), m.close.to_numpy()
    E = []
    for day in pd.bdate_range(a, b - pd.Timedelta(days=1), tz="UTC"):
        tk = ticks(day, b)
        if tk is None:
            continue
        t, bid, ask = tk
        # ORB (vol16_old's loop)
        t0 = day + pd.Timedelta(hours=6)
        i0, i15, i75 = (int(np.searchsorted(o, (t0 + pd.Timedelta(minutes=k)).value)) for k in (0, 15, 75))
        if i15 > i0 and o[i0] - t0.value <= 5 * MIN:
            rh, rl = hi_[i0:i15].max(), lo_[i0:i15].min()
            H = atr_at(t0.value)
            if np.isfinite(H) and rh - rl <= 1.5 * H:
                c = cl_[i15:i75]
                k = np.flatnonzero((c > rh) | (c < rl))
                if len(k):
                    side = 1 if c[k[0]] > rh else -1
                    t_dec = int(o[i15 + k[0]] + MIN)
                    E.append(dict(cand="ORB_FADE", t_in=t_dec, side0=side, stop_px=rl if side > 0 else rh, tgt_px=np.nan,
                                  stop_d=np.nan, tgt_r=2.0, t_out_min=60, atr=atr_at(t_dec)))
        # the straddle's trigger (ns1_ticks.straddle's rule)
        tn = pd.Timestamp(f"{day:%Y-%m-%d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value
        s = N.straddle(t, bid, ask, tn)
        if s is not None:
            j = int(np.searchsorted(t, tn, side="left"))
            while not ((ask[j] >= s["entry"] and s["side"] > 0) or (bid[j] <= s["entry"] and s["side"] < 0)):
                j += 1
            E.append(dict(cand="STR_FADE", t_in=int(t[j]), side0=s["side"], stop_px=np.nan, tgt_px=np.nan, stop_d=8.0,
                          tgt_r=np.nan, t_out=int(tn + 30 * MIN), atr=atr_at(tn), check_entry=s["entry"]))
        # ASIA_FADE
        a0 = (day - pd.Timedelta(hours=7)).value  # 00:00 Thai of this day = 17:00 UTC the day before
        ia, ib = int(np.searchsorted(o, a0)), int(np.searchsorted(o, day.value))
        if ib - ia >= 60:
            ah, al = hi_[ia:ib].max(), lo_[ia:ib].min()
            l0 = pd.Timestamp(f"{day:%Y-%m-%d} 08:00").tz_localize("Europe/London").tz_convert("UTC").value
            ev = asia_event(o, hi_, lo_, cl_, ah, al, l0, l0 + 60 * MIN)
            if ev is not None:
                td, side, ext = ev
                H = atr_at(td)
                for bb in ASIA_B:
                    E.append(dict(cand="ASIA_FADE", setting=f"b {bb:.2f}", t_in=td, side0=side,
                                  stop_px=ext - side * bb * H, tgt_px=(ah + al) / 2, stop_d=np.nan, tgt_r=np.nan,
                                  t_out_min=60, atr=H))
    # RC / RT from streams.build (the row-45 event loops)
    S = streams.build(m, f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}")
    for r in S[S.stream.isin(["RC", "RT_opp"])].itertuples():
        E.append(dict(cand="RC_CALM" if r.stream == "RC" else "RT_OPP_CALM", t_in=int(r.t_in), side0=int(r.side),
                      stop_px=float(r.stop), tgt_px=np.nan, stop_d=np.nan, tgt_r=2.0, t_out_min=120, atr=atr_at(int(r.t_in))))
    E = pd.DataFrame(E)
    E = E[(E.t_in >= a.value) & (E.t_in < b.value)].reset_index(drop=True)
    E["t_out"] = np.where(E.t_out_min.notna(), E.t_in + E.t_out_min.fillna(0) * MIN, E.get("t_out", np.nan))
    return E


def simulate(E: pd.DataFrame, end: pd.Timestamp, same_too: bool = True) -> pd.DataFrame:
    """Every setting of every event on the ticks (tsim.grid); plus the rule's own side for the parity check."""
    import tsim

    rows, cache = [], {}
    for r in E.sort_values("t_in").itertuples():
        sp = span(int(r.t_in), end, cache)
        if sp is None:
            continue
        sets = SETTINGS[r.cand]
        if r.cand == "ASIA_FADE":
            sets = [s for s in sets if s[0] == r.setting]
        if same_too and r.cand in ("ORB_FADE", "STR_FADE"):
            sets = [*sets, ("rule side", "same", 1.0, "orig")]
        for name, side, mult, tg in sets:
            tgt_r = 1.0 if (r.cand == "STR_FADE" and name.startswith(("ii", "iii"))) else r.tgt_r
            g = tsim.grid(*sp, int(r.t_in), int(r.side0), float(r.stop_px), float(r.tgt_px), int(r.t_out),
                          sides=(side,), stops=(mult,), targets=(tg,), stop_d=float(r.stop_d), tgt_r=float(tgt_r))
            if g:
                x = g[0]
                rows.append(dict(cand=r.cand, setting=name, t_in=int(r.t_in), atr=r.atr, entry=x["entry"], risk=x["risk"],
                                 exit=x["exit"], pnl=x["pnl"], R=x["R"]))
    return pd.DataFrame(rows)


def ci95(x: np.ndarray, n_boot: int = 4000, seed: int = 7) -> tuple[float, float]:
    if len(x) < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(1)
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def choose(T: pd.DataFrame) -> dict:
    """Per candidate, the setting with the best R on the calm trades (a tie -> the first listed)."""
    out = {}
    for cand, sets in SETTINGS.items():
        best = None
        for name, *_ in sets:
            x = T[(T.cand == cand) & (T.setting == name) & (T.atr < CALM)]
            r = x.R.mean() if len(x) else -np.inf
            if best is None or r > best[1] + 1e-12:
                best = (name, r)
        out[cand] = best[0]
    return out


def year_of(t_ns: pd.Series) -> pd.Series:
    t = pd.to_datetime(t_ns, utc=True)
    y = t.dt.year.where(t.dt.month >= 10, t.dt.year - 1)
    return y.astype(str) + "-" + ((y + 1) % 100).map(lambda v: f"{v:02d}")


def main() -> None:
    import tsim

    phase = sys.argv[1] if len(sys.argv) > 1 else "learn"
    a, b = period_of(phase)
    tsim.idle()
    E = events(phase)
    T = simulate(E, b)
    T.to_parquet(HERE / f"calm58_{phase}.parquet")
    T["year"] = year_of(T.t_in)
    lines = [f"=== {phase.upper()} {a:%Y-%m-%d} .. {b - pd.Timedelta(days=1):%Y-%m-%d}; calm = H1 ATR < {CALM:g}"]
    # parity of the ORB / straddle rule side with vol16_old (all ATR), per year
    V = pd.read_parquet(HERE.parent / "precursors/vol16_old.parquet")
    for cand, pc in (("ORB_FADE", "London ORB"), ("STR_FADE", "NY straddle")):
        x = T[(T.cand == cand) & (T.setting == "rule side")]
        for y, g in x.groupby("year"):
            v = V[(V.piece == pc) & (V.year == y)]
            lines.append(f"parity {pc} {y}: vol16_old {len(v)} R {v.R.mean():+.3f} | mine {len(g)} R {g.R.mean():+.3f}")
    frozen = json.loads(FROZEN.read_text()) if phase == "test" else None
    lines.append("\ncandidate / setting: calm trades, R (95 % range), win, USD at 0.01 lot | per year")
    for cand, sets in SETTINGS.items():
        for name, *_ in sets:
            if phase == "test" and name != frozen[cand]:
                continue
            x = T[(T.cand == cand) & (T.setting == name) & (T.atr < CALM)]
            lo, hi = ci95(x.R.to_numpy())
            yrs = " | ".join(f"{y} {len(g)} {g.R.mean():+.3f}" for y, g in x.groupby("year"))
            lines.append(f"{cand:12s} {name:28s} {len(x):4d}  {x.R.mean() if len(x) else np.nan:+.3f} ({lo:+.3f} .. {hi:+.3f})"
                         f"  win {(x.pnl > 0).mean() if len(x) else np.nan:.2f}  USD {x.pnl.sum():+8.1f} | {yrs}")
    if phase == "learn":
        ch = choose(T)
        FROZEN.write_text(json.dumps(ch, indent=1))
        lines.append(f"\nFROZEN (best LEARN R per candidate): {ch}")
    else:
        L = pd.read_parquet(HERE / "calm58_learn.parquet")
        lines.append("\nPASS (TEST R >= +0.10 on >= 100 calm trades, 95 % range above 0, LEARN >= +0.10):")
        for cand, name in frozen.items():
            x = T[(T.cand == cand) & (T.setting == name) & (T.atr < CALM)]
            lx = L[(L.cand == cand) & (L.setting == name) & (L.atr < CALM)]
            lo, _ = ci95(x.R.to_numpy())
            ok = len(x) >= 100 and x.R.mean() >= 0.10 and lo > 0 and lx.R.mean() >= 0.10
            lines.append(f"  {cand:12s} {name:28s} LEARN {lx.R.mean():+.3f} ({len(lx)}) TEST {x.R.mean():+.3f} ({len(x)}, low "
                         f"{lo:+.3f}) -> {'PASS' if ok else 'FAIL'}")
    txt = "\n".join(lines)
    (HERE / f"out_calm58_{phase}.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
