"""The journal agent's rules (each written in notes.md before it was run). Sizes are in units U: for gold
1 U = price / 4100 USD (1 USD at 4100, as ny_lab's price scaling); for an FX pair 1 U = the pair's gold-equivalent
(see ``unit``). The stop is the confluence stop (beyond the level by one M1 ATR) unless a rule says otherwise."""

from __future__ import annotations

import numpy as np
import pandas as pd

import jlib

# gold's median M1 ATR in U over the design years (set from the design table, see notes.md); an FX pair's 1 U is
# its own median M1 ATR (trailing 20 trading days) / this number, so targets sit at the same multiple of the M1 ATR
GOLD_ATR_U = 1.63


def unit(D: pd.DataFrame, P: jlib.Instr) -> np.ndarray:
    if P.sym == "XAUUSD":
        return (D.close / jlib.REF).to_numpy()
    med = D.drop_duplicates("t").set_index("t").atr1.rolling("28D").median()
    return (med.reindex(D.t).to_numpy() / GOLD_ATR_U)


def augment(D: pd.DataFrame, P: jlib.Instr) -> pd.DataFrame:
    """Context added after round 1: the M5 EMA20 (last closed M5 bar), the last 15 minutes' extreme."""
    if "m5_c_e20" in D:
        return D
    m = P.m
    b = m.resample("5min", label="left", closed="left").agg({"close": "last"}).dropna()
    e20 = b.close.ewm(span=20, adjust=False).mean()
    ends = b.index + pd.Timedelta(minutes=5)
    k = ends.searchsorted(pd.DatetimeIndex(D.t), side="right") - 1
    side = D.side.to_numpy()
    c5, e5, e5p = b.close.to_numpy()[k], e20.to_numpy()[k], e20.to_numpy()[k - 1]
    atr = D.atr1.to_numpy()
    p = D.e.to_numpy() - 1
    from numpy.lib.stride_tricks import sliding_window_view as win
    def ext(n: int, end: np.ndarray) -> np.ndarray:  # the side's extreme of the n bars ending at *end*
        lo_, hi_ = win(P.lo, n).min(1)[end - n + 1], win(P.h, n).max(1)[end - n + 1]
        return np.where(side > 0, lo_, hi_)

    def brk(n: int, end: np.ndarray) -> np.ndarray:  # the opposite extreme (the break level) of n bars ending at end
        lo_, hi_ = win(P.lo, n).min(1)[end - n + 1], win(P.h, n).max(1)[end - n + 1]
        return np.where(side > 0, hi_, lo_)

    # the 72-hour extreme of bars i-4320 .. i-16 for decision bar i (rolling 4305 ending at i-16)
    hi72 = pd.Series(P.h).rolling(4305).max().to_numpy()
    lo72 = pd.Series(P.lo).rolling(4305).min().to_numpy()
    front72 = np.where(side > 0, hi72[p - 16], lo72[p - 16])
    return D.assign(m5_c_e20=(c5 - e5) * side / atr, m5_e20_d=(e5 - e5p) * side / atr, front72=front72,
                    ext15=ext(15, p), ext30=ext(30, p), ext5=ext(5, p), brk10=brk(10, p - 1), c_dec=P.c[p])


def base_mask(D: pd.DataFrame) -> pd.Series:
    pa = D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim
    ind = (D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2
    return D.tide & D.at_level & pa & ind


def m5_with(D):
    return (D.m5_c_e20 > 0) & (D.m5_e20_d >= 0)


def h1_struct_ok(D):
    return (D.cr_H1_struct >= 0) & (D.cr_H1_now >= 0)


def no_knife(D):
    return (D.ret15.abs() <= 4) & (D.atr_ratio <= 2)


def no_news(D):
    return (D.since_rel > 15) & (D.until_rel > 15)


def sweep_stop(D):
    side = D.side.to_numpy()
    a = D.level.to_numpy() - side * D.atr1.to_numpy()
    b = D.ext15.to_numpy() - side * 0.5 * D.atr1.to_numpy()
    return np.where(side > 0, np.minimum(a, b), np.maximum(a, b))


def k_mask(D):
    s, a, lv = D.side, D.atr1, D.level
    test = ((D.ext30 - lv) * s <= a) & ((lv - D.ext30) * s <= 2 * a)
    higher_low = (D.ext5 - D.ext30) * s >= 0.3 * a
    trigger = ((D.c_dec - D.brk10) * s > 0) & ((D.c_dec - lv) * s > 0)
    return D.tide & m5_with(D) & test & higher_low & trigger


def k_stop(D):
    return D.ext30.to_numpy() - D.side.to_numpy() * 0.5 * D.atr1.to_numpy()


def not_flat(D):
    return D.h1_c_e50 >= 0.85


def w_mask(D, pos):
    return (D.cr_H1_leg_dir >= 0) & (D.h1_c_e50.abs() >= 0.85) & (D.pos240 >= pos)


def room72_ok(D, k=0.5, tp=8.0):
    return (D.front72 - D.c_dec) * D.side < k * tp * D.unit


def protect(D):
    """V2's protection: H1 leg not against, H1 not flat, pos240 >= .5, the 72-h extreme close in front, no fast tape."""
    return w_mask(D, 0.5) & room72_ok(D) & (D.atr_ratio < 2)


def e_mask(D):
    return D.tide & D.at_level & m5_with(D) & protect(D)


def quality(D):
    """Round 5: just under the 72-h extreme (not through it), not late in the window, no US release within 15 min."""
    under = (D.front72 - D.c_dec) * D.side > 0
    late = ((D.session == 2) & (D.min_in >= 120)) | ((D.session == 0) & (D.min_in >= 100))
    return under & ~late & no_news(D)


B = dict(tp=8.0, be=0.6, hz=60, rmin=3.0, rmax=10.0)
RULES: dict[str, dict] = {
    "B0": dict(doc="baseline: confluence.py as tested (H1 tide + level + price action + 2/3 M5), stop 3-10 U",
               mask=base_mask, **B),
    "J1": dict(doc="B0 + M5 with the trade", mask=lambda D: base_mask(D) & m5_with(D), **B),
    "J2": dict(doc="B0 + H1 structure not against", mask=lambda D: base_mask(D) & h1_struct_ok(D), **B),
    "J3": dict(doc="B0 + no knife (|ret15| <= 4 ATR, ATR <= 2x median)", mask=lambda D: base_mask(D) & no_knife(D), **B),
    "J4": dict(doc="B0 + no release +-15 min", mask=lambda D: base_mask(D) & no_news(D), **B),
    "J5": dict(doc="B0 + stop beyond the 15-min extreme", mask=base_mask, stop=sweep_stop, **B),
    "J6": dict(doc="B0 + J1..J5", mask=lambda D: base_mask(D) & m5_with(D) & h1_struct_ok(D) & no_knife(D) & no_news(D),
               stop=sweep_stop, **B),
    "J7": dict(doc="B0 + J1 + J5", mask=lambda D: base_mask(D) & m5_with(D), stop=sweep_stop, **B),
    "J8": dict(doc="B0 + J1 + J3 + J5", mask=lambda D: base_mask(D) & m5_with(D) & no_knife(D), stop=sweep_stop, **B),
    "J9": dict(doc="B0 + J1 + J2 + J5", mask=lambda D: base_mask(D) & m5_with(D) & h1_struct_ok(D), stop=sweep_stop, **B),
    "J10": dict(doc="B0 + J1 + J4 + J5", mask=lambda D: base_mask(D) & m5_with(D) & no_news(D), stop=sweep_stop, **B),
    "K": dict(doc="tide + M5 with + test of the level, higher low, break of the 10-bar high; stop beyond the test",
              mask=k_mask, stop=k_stop, **B),
    "K2": dict(doc="K + no news + not a flat H1", mask=lambda D: k_mask(D) & no_news(D) & not_flat(D), stop=k_stop, **B),
    # the lead's round 11 (docs/OWN_SETUP_ROUNDS.md): B0's losers were dips bought in weak structure
    "W2": dict(doc="B0 + H1 leg not against + not a flat H1 + pos240 >= 0.5",
               mask=lambda D: base_mask(D) & w_mask(D, 0.5), **B),
    "W3": dict(doc="B0 + H1 leg not against + not a flat H1 + pos240 >= 0.75",
               mask=lambda D: base_mask(D) & w_mask(D, 0.75), **B),
    "V1": dict(doc="W2 + the 72-h extreme in front closer than 0.5 target (or behind)",
               mask=lambda D: base_mask(D) & w_mask(D, 0.5) & room72_ok(D), **B),
    "V2": dict(doc="V1 + not a fast tape (ATR < 2x day median)",
               mask=lambda D: base_mask(D) & w_mask(D, 0.5) & room72_ok(D) & (D.atr_ratio < 2), **B),
    "E1": dict(doc="the 72-h extreme setup alone: tide + H1 leg with + not flat + pos240 >= .5 + room72 < .5 tp + M5 with + at a level",
               mask=lambda D: D.tide & D.at_level & w_mask(D, 0.5) & room72_ok(D) & m5_with(D), **B),
    "E2": dict(doc="tide + level + M5 with + V2 protection (no PA / 2-of-3)", mask=lambda D: e_mask(D), **B),
    "E3": dict(doc="E2 + one attempt per 72-h extreme a day", mask=lambda D: e_mask(D), once=True, **B),
    "E4": dict(doc="E3 + H1 not stretched (h1_c_e50 <= 4.5)", mask=lambda D: e_mask(D) & (D.h1_c_e50 <= 4.5), once=True, **B),
    "E4s1": dict(doc="E4, one trade a session", mask=lambda D: e_mask(D) & (D.h1_c_e50 <= 4.5), once=True, per_sess=1, **B),
    "V3": dict(doc="V2 + once + H1 not stretched",
               mask=lambda D: base_mask(D) & protect(D) & (D.h1_c_e50 <= 4.5), once=True, **B),
    "E5": dict(doc="E2 + just under the 72-h extreme + not late + no news", mask=lambda D: e_mask(D) & quality(D), **B),
    "E5s1": dict(doc="E5, one trade a session", mask=lambda D: e_mask(D) & quality(D), per_sess=1, **B),
    "V4": dict(doc="V2 + just under the 72-h extreme + not late + no news",
               mask=lambda D: base_mask(D) & protect(D) & quality(D), **B),
    # FX: the same logic in pips (1 U = 1 pip): target 20 (or 15) pips, stop level - 1 ATR within 7.5-25 pips
    "FB0": dict(doc="B0 in pips: tp 20, stop 7.5-25, BE 0.6, 120 min", mask=base_mask,
                tp=20.0, be=0.6, hz=120, rmin=7.5, rmax=25.0, upip=True),
    "FW3": dict(doc="W3 logic in pips: tp 20, stop 7.5-25, BE 0.6, 120 min", mask=lambda D: base_mask(D) & w_mask(D, 0.75),
                tp=20.0, be=0.6, hz=120, rmin=7.5, rmax=25.0, upip=True),
    "FW3s": dict(doc="W3 logic in pips: tp 15, stop 6-19, BE 0.6, 120 min", mask=lambda D: base_mask(D) & w_mask(D, 0.75),
                 tp=15.0, be=0.6, hz=120, rmin=6.0, rmax=19.0, upip=True),
    "FV1": dict(doc="V1 logic in pips: tp 20, stop 7.5-25, BE 0.6, 120 min",
                mask=lambda D: base_mask(D) & w_mask(D, 0.5) & room72_ok(D, 0.5, 20.0),
                tp=20.0, be=0.6, hz=120, rmin=7.5, rmax=25.0, upip=True),
}


def signals(D: pd.DataFrame, rule: dict, P: jlib.Instr) -> pd.DataFrame:
    u = np.full(len(D), P.pip) if rule.get("upip") else unit(D, P)
    D = augment(D, P).assign(unit=u)
    m = rule["mask"](D).to_numpy(bool)
    D = D[m]
    side = D.side.to_numpy()
    stop_px = D.level.to_numpy() - side * D.atr1.to_numpy() if "stop" not in rule else rule["stop"](D)
    D = D.assign(sl=(P.fill(D.e.to_numpy(), side) - stop_px) * side, stop_px=stop_px)
    m = np.ones(len(D), dtype=bool)
    ok = m & (D.sl >= rule["rmin"] * D.unit).to_numpy() & (D.sl <= rule["rmax"] * D.unit).to_numpy()
    return D[ok]
