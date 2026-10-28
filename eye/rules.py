"""Put the rules themselves on trial (owner, 2026-10-28).

*"The rules need something that proves them too - which ones actually work, and which ones are always in
conflict with another rule, so that they push you into bad trades."*

So every decision now records, at the moment it is made, which of the nine trading rules held and which did
not, and which pair of rules pointed opposite ways. That turns two questions into counting:

- **Does a rule help?** Compare the trades where it held against the trades where it was broken.
- **Does a rule fight the others?** Count how often it is on the losing side of a conflict, and what the
  trades chosen that way returned.

The ledger carries two extra columns:

- ``rules`` - nine characters, one per rule in METHOD's order, each ``+`` (held), ``-`` (broken) or ``?``
  (not judged; only the trades taken before the rules existed).
- ``conflict`` - ``"3 vs 5"`` when two rules pointed opposite ways, with the one that was followed first.
  Empty when nothing conflicted.

    python eye/rules.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = {
    1: "two frames, upper first",
    2: "levels from the left",
    3: "price has run into a level",
    4: "legs complete, trade the fifth with it",
    5: "structure at the level (HH+HL / LH+LL)",
    6: "enter and exit on one timeframe",
    7: "the entry is reachable from here",
    8: "the order fills while the idea is intact",
    9: "stop beyond the structure, target a leg away",
}


def rows() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for name in ("ledger.csv", "ledger_control.csv"):
        p = HERE / name
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("why") in ("", "no trade", "open"):  # "open": held, not yet a result
                continue
            r["source"] = "live" if name == "ledger.csv" else "control"
            out.append(r)
    return out


def main() -> None:
    data = rows()
    judged = [r for r in data if r.get("rules") and "?" not in r["rules"]]
    # A plan that never filled earned nothing, and averaging its 0.00 into a rule's column would
    # read as the rule being neutral when it never got a trade at all. Only fills are averaged; the
    # no-fills are counted beside them, because never filling is itself a result (METHOD rule 7).
    scored = [r for r in judged if r["why"] != "no fill"]
    unfilled = [r for r in judged if r["why"] == "no fill"]
    print(
        f"{len(data)} trades in the ledgers, {len(judged)} with every rule judged at decision time, "
        f"of which {len(scored)} filled and {len(unfilled)} never did\n"
    )

    if scored:
        print("| rule | held: n, R a trade | broken: n, R a trade | what breaking it cost |")
        print("|---|---:|---:|---:|")
        for i in range(1, 10):
            held = [float(r["r_net"]) for r in scored if r["rules"][i - 1] == "+"]
            broke = [float(r["r_net"]) for r in scored if r["rules"][i - 1] == "-"]
            h = f"{len(held)}, {sum(held) / len(held):+.2f}" if held else "-"
            b = f"{len(broke)}, {sum(broke) / len(broke):+.2f}" if broke else "-"
            gap = f"{sum(held) / len(held) - sum(broke) / len(broke):+.2f}" if held and broke else "-"
            print(f"| {i} {NAMES[i]} | {h} | {b} | {gap} |")

        pairs: dict[str, list[float]] = defaultdict(list)
        for r in scored:
            if r.get("conflict"):
                pairs[r["conflict"]].append(float(r["r_net"]))
        print("\n## Where the rules fought each other\n")
        if pairs:
            print("| the conflict | times | R a trade when it was resolved this way |")
            print("|---|---:|---:|")
            for k, v in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
                print(f"| {k} | {len(v)} | {sum(v) / len(v):+.2f} |")
        else:
            print("No conflict recorded yet.")
    else:
        print(
            f"No filled trade has been judged against the rules yet "
            f"({len(unfilled)} judged plan(s) never filled) - the first fill will be the first row."
        )

    print("\n## The trades taken before the rules existed\n")
    old = [r for r in data if not r.get("rules") or "?" in r.get("rules", "?")]
    if old:
        rs = [float(r["r_net"]) for r in old]
        print(
            f"{len(old)} trades, {sum(rs):+.2f} R, {sum(rs) / len(rs):+.3f} a trade. "
            "They are the control and are never mixed with the judged ones."
        )


if __name__ == "__main__":
    main()
