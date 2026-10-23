"""The weekly review (PROTOCOL.md decision rules), on the ledger up to week N and the learning weeks; nothing after
week N's end is read. Prints the evidence for each decision; `--apply k=v ...` writes the decided changes to
state.json (effective from week N+1):

    solo_review.py 3
    solo_review.py 3 --apply delete=near shadow=m1_only exit=noband piece=retest:stop
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import solo_lib as S

LEARN_FWD = {"near": 1.86, "news": 0.75, "vol": -1.05}  # the learning journal's forward record of the start rules


def b2_all(n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    L = S.ledger()
    E = L[(L.week <= n) & (L.piece == "B2")].copy()
    A = pd.concat([S.learning().assign(week=0), E], ignore_index=True)
    A["r_cur"] = A.r_cur.fillna(A.r_real)
    return E, A


def review(n: int) -> None:
    st = S.load_state()
    L = S.ledger()
    L = L[L.week <= n]
    E, A = b2_all(n)
    print(f"== review after exam week {n}; state {st['exit']} rules {st['rules']} shadows {st['shadows']} pieces {st['pieces']}")
    print("-- skip rules in force: the skipped trades' R (under the exit at the time), from the week the rule took effect")
    for k, w0 in st["rules"].items():
        m = S.RULES[k](E) & (E.week >= w0)
        v = E.r_cur[m].sum()
        extra = f" | with the learning forward {v + LEARN_FWD[k]:+.2f}" if k in LEARN_FWD else ""
        print(f"  {k:12s} from wk {w0}: {v:+.2f} on {m.sum()}{extra} -> {'DELETE' if v > 1.0 else 'keep'}")
    print("-- shadows: R the shadow would have saved (positive = saved) since it started")
    for k, w0 in st["shadows"].items():
        m = S.RULES[k](E) & (E.week >= w0)
        saved, weeks = -E.r_cur[m].sum(), n - w0 + 1
        bef = S.RULES[k](A[A.week < w0])
        print(f"  {k:12s} from wk {w0} ({weeks} wk): saved {saved:+.2f} on {m.sum()} | before it: {A[A.week < w0].r_cur[bef].sum():+.2f} on {bef.sum()}"
              f" -> {'APPLY' if weeks >= 4 and saved >= 1.0 else 'wait'}")
    print("-- exits over all B2 trades (unfiltered): the last 8 exam weeks / all trades before the week's end")
    last8 = E[E.week > n - 8]
    cur = st["exit"]
    for k in S.EXITS:
        d8 = last8[f"r_{k}"].sum() - last8[f"r_{cur}"].sum()
        da = A[f"r_{k}"].sum() - A[f"r_{cur}"].sum()
        print(f"  {k:7s} last 8 wk {last8[f'r_{k}'].sum():+.2f} ({d8:+.2f}) | all {A[f'r_{k}'].sum():+.2f} ({da:+.2f})"
              f"{'  -> SWITCH' if k != cur and d8 >= 1.5 and da >= 0 else ''}")
    print("-- pieces: forward realized R (exam weeks) and the record while stopped")
    for p in sorted(set(L.piece)):
        P = L[L.piece == p]
        w0 = st["pieces"].get(p, st["stopped"].get(p, 1))
        f = P[P.week >= (w0 if p not in ("B2",) else 1)] if p in st["pieces"] else P
        print(f"  {p:10s} {len(f)} signals, realized {np.nansum(f.r_realized):+.2f} on {f.r_realized.notna().sum()}, the piece's own exit {f.r_cur.sum():+.2f}"
              f"{'  -> STOP' if p in st['pieces'] and np.nansum(f.r_realized) < -3 else ''}")
        if p in st["stopped"]:
            g = P[P.week >= st["stopped"][p]]
            print(f"  {'':10s} since stopped (wk {st['stopped'][p]}): {len(g)} signals {g.r_cur.sum():+.2f} under its exit, "
                  f"{np.nansum(np.where(g.skipped_by.fillna('').str.replace('stopped', '').str.strip() == '', g.r_cur, np.nan)):+.2f} with the skip rules")
    if "B2" in st["stopped"]:  # its return: gate 1 on its whole record (learning + exam), the rules in force applied
        keep = np.ones(len(A), bool)
        for k in st["rules"]:
            keep &= ~S.RULES[k](A).values
        r = A[f"r_{st['exit']}"][keep].reset_index(drop=True)
        h = len(r) // 2
        print(f"-- B2 return, gate 1 (rules in force, current exit): half 1 {r[:h].mean():+.3f} on {h}, half 2 {r[h:].mean():+.3f} on {len(r) - h}"
              f" -> {'PASS' if r[:h].mean() >= 0.1 and r[h:].mean() >= 0.1 else 'fail'}; gate 2 not measurable (no B2 trades before 2025-10)")
    print("-- B2 splits (r_cur unfiltered): learning | exam so far | last 4 exam weeks")
    A["zbin"] = pd.cut(A.zone_step_pos, [-0.01, 0.1, 0.25, 0.4, 0.51])
    A["vbin"] = pd.cut(A.vol, [0, 0.8, 1.1, 1.5, 9])
    A["pbin"] = pd.cut(A.push3d, [-9, -1, 0, 1, 9])
    A["hour"] = A.t.dt.tz_convert("Asia/Bangkok").dt.hour
    A["sbin"] = pd.cut(A.score, [-20, -1, 3, 20])
    A["drbin"] = pd.cut(A.day_run, [-9, -0.5, 0, 0.5, 9])
    for c in ("tf", "side", "zbin", "vbin", "pbin", "hour", "sbin", "run3", "drbin"):
        g = A.groupby([c, A.week.gt(0).map({False: "learn", True: "exam"})], observed=True).r_cur.agg(["size", "sum"]).unstack()
        print(f"  {c}:\n" + g.round(2).to_string().replace("\n", "\n    "))


def apply(n: int, args: list[str]) -> None:
    st = S.load_state()
    for a in args:
        k, v = a.split("=", 1)
        if k == "delete":
            st["deleted"][v] = n + 1
            st["rules"].pop(v)
        elif k == "shadow":
            st["shadows"][v] = n + 1
        elif k == "drop_shadow":
            st["shadows"].pop(v)
        elif k == "rule":  # a shadow applied
            st["shadows"].pop(v, None)
            st["rules"][v] = n + 1
            assert len(st["rules"]) <= 2, "at most 2 skip rules in force"
        elif k == "exit":
            st["exit"] = v
        elif k == "piece":
            p, how = v.split(":")
            if how == "stop":
                st["stopped"][p] = n + 1
                st["pieces"].pop(p)
            else:
                st["pieces"][p] = n + 1
                st["stopped"].pop(p, None)
        st["log"].append(f"after week {n}: {a}")
    S.save_state(st)
    print(st)


if __name__ == "__main__":
    n = int(sys.argv[1])
    if "--apply" in sys.argv:
        apply(n, sys.argv[sys.argv.index("--apply") + 1 :])
    else:
        review(n)
