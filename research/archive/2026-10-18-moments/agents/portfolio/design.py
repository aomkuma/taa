"""Per family on the DESIGN data (2023-11 .. 2026-02): the baseline, each protective condition counted on the family's
own trades (pass vs fail R overall and by half-year, the share of stopped losers vs winners that fail it), the kept
layer by the selection rule in notes.md, the step table, the coin on the final rule, the account.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/portfolio/design.py [--build] [FAM ...]

--build writes sig_<fam>_wdesign.parquet (the family's signal rows with their features)."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plib

HERE = plib.HERE
DAYS = pd.bdate_range("2023-11-01", "2026-03-01", inclusive="left").size


def fam_key(name: str) -> str:
    return name.split()[0]


def build(part: str, names: list[str]) -> None:
    P, D = plib.load(part)
    print(part, "candidate rows", len(D), flush=True)
    for name in names:
        f = plib.FAMILIES[name]
        variants = {"": f} if name != "F2 NYB" else {"a": lambda D, P: f(D, P, "a"), "": lambda D, P: f(D, P, "b")}
        for v, fn in variants.items():
            S = fn(D, P).reset_index(drop=True)
            S["fam"] = fam_key(name) + v
            S.drop(columns=[c for c in S.columns if S[c].dtype == object and c not in ("fam", "level_kind")]).to_parquet(
                HERE / f"sig_{fam_key(name)}{v}_{part}.parquet")
            print(f"{name}{v}: {len(S)} signal rows, {S.t.dt.normalize().nunique()} days", flush=True)


def sig(fk: str, part: str = "wdesign") -> pd.DataFrame:
    S = pd.read_parquet(HERE / f"sig_{fk}_{part}.parquet")
    S["t"] = pd.to_datetime(S.t, utc=True)
    return S


def evaluate(z: pd.DataFrame, menu: dict) -> dict:
    """Each condition on trades z: (diff, meets the rule, printable line). The rule (notes.md): R(pass) - R(fail) >= 0.10
    and pass > fail in >= 4 of the halves where both sides have >= 5 trades (all if fewer than 5 such halves, >= 2)."""
    z = z.reset_index(drop=True)
    h = plib.half_of(z.t)
    lost = (z.exit == "stop").to_numpy()
    won = (z.exit == "win").to_numpy()
    out = {}
    for cname, fn in menu.items():
        ok = fn(z).to_numpy(bool)
        if ok.all() or (~ok).all():
            out[cname] = (-9.0, False, f"    {cname:30} {'(all pass)' if ok.all() else '(all fail)'}")
            continue
        rp, rf = z.R[ok].mean(), z.R[~ok].mean()
        cmp, n_ok = 0, 0
        for hn, _, _ in plib.HALVES:
            m = (h == hn).to_numpy()
            a, b = ok & m, ~ok & m
            if a.sum() >= 5 and b.sum() >= 5:
                n_ok += 1
                cmp += z.R[a].mean() > z.R[b].mean()
        need = 4 if n_ok >= 5 else n_ok
        meets = (rp - rf >= 0.10) and n_ok >= 2 and cmp >= need and ok.sum() >= 30
        line = (f"    {cname:30} {100 * (~ok & lost).sum() / max(lost.sum(), 1):4.0f} / {100 * (~ok & won).sum() / max(won.sum(), 1):4.0f}"
                f"  | {rp:+.3f} ({ok.sum():4}) / {rf:+.3f} ({(~ok).sum():4}) | {cmp}/{n_ok} | {'meets' if meets else '-'}")
        out[cname] = (rp - rf, meets, line)
    return out


def causes(z: pd.DataFrame) -> None:
    """The family's stopped losers (kind 1 wrong way / kind 3 too early) vs its winners, at the entry: medians."""
    z = z.assign(stop_atr=z.sl / z.atr1, room72_tp=(z.front72 - z.c_dec) * z.side / (8 * z.unit),
                 asia=(z.session == 0).astype(float), ny=(z.session == 2).astype(float))
    cols = ["stop_atr", "ret15", "ret60", "atr_ratio", "room72_tp", "pos240", "h1_c_e50", "cr_H1_leg_dir", "min_in", "asia", "ny"]
    g = {"winners": z[z.exit == "win"], "kind 1 (wrong way)": z[z.kind == "1"], "kind 3 (too early)": z[z.kind == "3"]}
    print("  losers vs winners (median; asia/ny = share):  " + " ".join(f"{c:>10}" for c in cols))
    for k, x in g.items():
        vals = [x[c].mean() if c in ("asia", "ny") else x[c].median() for c in cols]
        print(f"    {k:20} n {len(x):4}         " + " ".join(f"{v:10.2f}" for v in vals))


def report_family(P, fk: str, menu: dict, out: list) -> None:
    S = sig(fk)
    print(f"\n==== {fk}: {len(S)} signal rows", flush=True)
    z = plib.run(S, P)
    if not len(z):
        print("  no trades")
        return
    z = plib.with_features(z)
    c = plib.coin(S, P)
    print(plib.summary(z, DAYS, "baseline") + f"  coin R {c['R']:+.3f} (win {100 * c['win']:.0f}%)")
    print("  " + plib.by_half(z) + f"  kinds {plib.kinds(z)} (coin {c['kinds']})")
    use = {k: v for k, v in menu.items() if not (k.startswith("C8") and fk in ("F1", "F2", "F2a", "F5", "F6", "F7"))
           and not (k.startswith("C9") and fk == "F6")}
    kept, m, step = [], np.ones(len(S), bool), 0
    rows = [plib.summary(z, DAYS, "0 baseline") + "  " + plib.by_half(z)]
    while True:
        ev = evaluate(z, {k: v for k, v in use.items() if k not in kept})
        print(f"  step {step}: conditions on the current {len(z)} trades - fail %: stopped losers / winners | R pass (n) / fail (n) | halves | rule")
        for _, _, line in ev.values():
            print(line)
        cand = [(d, k) for k, (d, ok, _) in ev.items() if ok]
        if not cand:
            break
        d, best = max(cand)
        kept.append(best)
        m &= use[best](S).to_numpy(bool)
        z = plib.with_features(plib.run(S[m], P))
        step += 1
        rows.append(plib.summary(z, DAYS, f"{step} + {best}") + "  " + plib.by_half(z))
    causes(z)
    print("  STEP TABLE:")
    for r in rows:
        print(r)
    if kept:
        c = plib.coin(S[m], P)
        print(f"  final {fk}: coin R {c['R']:+.3f} (win {100 * c['win']:.0f}%), kinds ours {plib.kinds(z)} / coin {c['kinds']};"
              f" sessions " + ", ".join(f"{plib.jlib.SESS[s]} {len(g)} {g.R.mean():+.3f}" for s, g in z.groupby("session")))
    z.attrs = {}
    z.to_parquet(HERE / f"trades_{fk}_design.parquet")
    out.append((fk, kept))


def main() -> None:
    plib.jlib.gold.below_normal_priority()
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--build" in sys.argv:
        build("wdesign", [n for n in plib.FAMILIES if not names or plib.FAMILIES and fam_key(n) in names])
        return
    P = plib.jlib.Instr("XAUUSD")
    out = []
    for fk in names or ["F1", "F2", "F2a", "F3", "F4", "F5", "F6", "F7"]:
        report_family(P, fk, plib.MENU, out)
    print("\nkept:", out)


if __name__ == "__main__":
    main()
