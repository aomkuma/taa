"""Rule 14's stability check of the M30 state on the stored bars (eye/BOT_RULES.md rule 14, "The state's
stability"; a reading, no trading).

For every M30 close of the period the closed bars at that ``now`` give the state from a 1,500-bar frame and
from a 2,500-bar frame, and:

  (a) the two states are equal (compared by times, not positions);
  (b) every change of the 1,500-bar state from the previous close falls at a close where a pivot was fixed, a
      close broke, or a look's start passed the range's E (range look) or the last break (trend look);
  (c) lo / hi never change while the same E / B stand.

Usage: state11_check.py [first last]       Thai dates, default 2026-07-01 2026-10-28
Writes eye/research/state11_check/<first>_<last>.csv (the full per-close table).
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app.indicators.price_action import Swing  # noqa: E402
from eye import bot2e, state11  # noqa: E402

TH = "Asia/Bangkok"
BIG_FRAME = 2500
RANGE_BARS = state11.look_bars("M30", 4)
TREND_BARS = state11.look_bars("M30", 7)


@dataclass(frozen=True)
class Sig:
    """A state compared by times (positions differ between frames)."""

    kind: str
    case: int
    e: pd.Timestamp | None
    b: pd.Timestamp | None
    lo: float | None
    hi: float | None
    legs: int | None
    last_touch: str | None
    brk_time: pd.Timestamp | None
    brk_way: str | None


def sig(st: state11.M30State) -> Sig:
    r, br = st.walk.range, st.walk.last_break
    return Sig(
        st.kind,
        st.case,
        st.e_time,
        st.b_time,
        r.lo if r else None,
        r.hi if r else None,
        r.legs if r else None,
        r.last_touch if r else None,
        st.break_time,
        br.way if br else None,
    )


def differing_fields(a: Sig, b: Sig) -> list[str]:
    """(a): the names of the fields in which two states differ (empty: equal)."""
    return [f for f in Sig.__dataclass_fields__ if getattr(a, f) != getattr(b, f)]


def change_causes(
    prev: Sig,
    cur: Sig,
    pivot_fixed: bool,
    bar_time: pd.Timestamp,
    prev_starts: tuple[pd.Timestamp, pd.Timestamp],
    cur_starts: tuple[pd.Timestamp, pd.Timestamp],
) -> list[str]:
    """(b): the causes of a change of state (empty if ``prev == cur`` or if it has none).

    ``*_starts`` = (range look's first bar time, trend look's first bar time) at the previous / this close.
    """
    if prev == cur:
        return []
    causes = []
    if pivot_fixed:
        causes.append("pivot")
    if cur.brk_time is not None and cur.brk_time == bar_time:
        causes.append("break")
    if prev.e is not None and prev_starts[0] <= prev.e < cur_starts[0]:
        causes.append("range_look")
    if prev.brk_time is not None and prev_starts[1] <= prev.brk_time < cur_starts[1]:
        causes.append("trend_look")
    return causes


def edge_violations(sigs: list[Sig]) -> list[int]:
    """(c): the indices ``i`` where E and B equal those of ``i - 1`` but lo or hi differ."""
    out = []
    for i in range(1, len(sigs)):
        a, b = sigs[i - 1], sigs[i]
        if a.e is not None and (a.e, a.b) == (b.e, b.b) and (a.lo, a.hi) != (b.lo, b.hi):
            out.append(i)
    return out


def _th(t: pd.Timestamp | None) -> str:
    return "" if t is None else t.tz_convert(TH).strftime("%Y-%m-%d %H:%M")


def _look_starts(index: pd.DatetimeIndex, i: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    return index[max(0, i - RANGE_BARS + 1)], index[max(0, i - TREND_BARS + 1)]


def select_closes(idx: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> list[int]:
    """The positions of the M30 bars whose close (open + 30 min) lies in ``(start, end]``."""
    return [i for i in range(len(idx)) if start < idx[i] + pd.Timedelta(minutes=30) <= end]


def pivot_fixed_at(pivots: list[Swing], bar_time: pd.Timestamp) -> bool:
    """A pivot is fixed at a close exactly when its confirm bar is that bar."""
    return any(p.confirm_at == bar_time for p in pivots)


def main(first: str, last: str) -> None:
    m30 = state11.m30_from_m15(bot2e.load_frames()["M15"])
    start = pd.Timestamp(first, tz=TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=TH).tz_convert("UTC") + pd.Timedelta(days=1)
    idx = m30.index
    # the bars whose close (open + 30 min) lies in [start, end)
    todo = select_closes(idx, start, end)
    if not todo:
        raise SystemExit("no M30 close in the period")

    def read(i: int) -> tuple[Sig, Sig, bool]:
        closed = m30.iloc[: i + 1]
        small = state11.state_at(closed)
        big = state11.state_at(closed, frame_bars=BIG_FRAME)
        piv = state11._zigzag(closed.iloc[-state11.FRAME_BARS :])
        return sig(small), sig(big), pivot_fixed_at(piv, idx[i])

    prev, _, _ = read(todo[0] - 1)
    prev_i = todo[0] - 1
    rows, sigs = [], []
    diffs_a, no_cause, counts = [], [], {"pivot": 0, "break": 0, "range_look": 0, "trend_look": 0}
    n_changes = 0
    for i in todo:
        cur, big, fixed = read(i)
        now = idx[i] + pd.Timedelta(minutes=30)
        d = differing_fields(cur, big)
        if d:
            diffs_a.append((now, d))
        causes = change_causes(prev, cur, fixed, idx[i], _look_starts(idx, prev_i), _look_starts(idx, i))
        if prev != cur:
            n_changes += 1
            for c in causes:
                counts[c] += 1
            if not causes:
                no_cause.append((now, differing_fields(prev, cur)))
        sigs.append(cur)
        rows.append(
            [
                *(_th(now), cur.kind, cur.case, cur.lo, cur.hi, cur.legs, cur.last_touch),
                *(_th(cur.e), _th(cur.b), _th(cur.brk_time), "+".join(causes), ",".join(d)),
            ]
        )
        prev, prev_i = cur, i
    viol = edge_violations(sigs)

    out = HERE / "state11_check" / f"{first}_{last}.csv"
    out.parent.mkdir(exist_ok=True)
    cols = [
        "thai_time",
        "kind",
        "case",
        "lo",
        "hi",
        "legs",
        "last_touch",
        "E",
        "B",
        "break",
        "causes",
        "diff_a",
    ]
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)

    print(f"M30 closes checked: {len(todo)}  ({first} .. {last} Thai; frames 1500 vs {BIG_FRAME})")
    print(f"(a) 1,500 vs {BIG_FRAME} differences: {len(diffs_a)}")
    for now, d in diffs_a[:20]:
        print(f"    {_th(now)}  {','.join(d)}")
    print(f"(b) changes of state: {n_changes}; by cause (a change may have several): {counts}")
    print(f"    changes with no cause: {len(no_cause)}")
    for now, d in no_cause:
        print(f"    {_th(now)}  changed: {','.join(d)}")
    print(f"(c) lo/hi changed under the same E/B: {len(viol)}")
    for i in viol:
        print(f"    {rows[i][0]}")
    print(f"table: {out}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0] if a else "2026-07-01", a[1] if len(a) > 1 else "2026-10-28")
