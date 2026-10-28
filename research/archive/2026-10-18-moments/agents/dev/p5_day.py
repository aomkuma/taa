"""Task P5, the shape check on 2026-10-19 (after the data end, outside every part - shapes only, no outcome, no setting):
the detector on that day's M1 bars (the live file read with a filter from 2026-10-18, so the exam's bars are never
read), H from the day's own completed H1 bars, then found / missed / extra against the owner's 11 formations by the
matching rule written in DEV_LOG.md before this ran.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p5_day.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p5_patterns as F5  # noqa: E402

LIVE = Path(r"C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\07b81cb7-c5a7-49f9-8f44-3946d6d64c77\scratchpad\m1_live.parquet")
DAY0 = pd.Timestamp("2026-10-18", tz="UTC")  # nothing earlier is read (the exam ends 2026-10-17)
# the owner's formations (Thai clock on 2026-10-19): (number, start, end, the families that match, what)
OWNER = [
    (1, "06:30", "07:05", {"double top"}, "M 4185 / 4187.6"),
    (2, "05:00", "08:26", {"double bottom"}, "a wide W 4166 / 4165.6"),
    (3, "09:10", "09:32", {"double top", "double bottom"}, "a small M, then a W"),
    (4, "11:30", "12:30", {"double top"}, "M at about 4184.7"),
    (5, "12:29", "13:32", {"double bottom", "triple bottom", "break up, retest"}, "W / higher low 4174 / 4171"),
    (6, "12:57", "14:33", {"triple top"}, "triple top 4186.2 / 4186.5 / 4190.25 (the last swept)"),
    (7, "14:45", "17:20", {"channel break up", "channel break down"}, "descending channel, broken at 17:20"),
    (8, "17:46", "18:30", {"break down, retest"}, "V, then a failed retest at 4177"),
    (9, "19:03", "19:20", {"double bottom", "break down, retest"}, "a small W, then a lower high"),
    (10, "20:30", "21:30", {"open: fake up, then down"}, "the NY-open fake leg up to 4167, then the drop"),
    (11, "20:47", "22:00", {"base break up", "base break down", "double bottom"}, "a base / W at the bottom"),
]


def load_day() -> pd.DataFrame:
    import pyarrow.parquet as pq  # noqa: PLC0415

    x = pq.read_table(LIVE, columns=["open_time", "open", "high", "low", "close"],
                      filters=[("open_time", ">=", DAY0)]).to_pandas()
    m = x.set_index("open_time").sort_index() if "open_time" in x else x.sort_index()
    m.index = pd.DatetimeIndex(m.index).tz_convert("UTC")
    m.index.name = None
    if m.index.min() < DAY0:
        raise RuntimeError("a bar before 2026-10-18 was read")
    return m[["open", "high", "low", "close"]].astype(float)


def thai_span(start: str, end: str, minutes_after: int = 30) -> tuple[int, int]:
    a = pd.Timestamp(f"2026-10-19 {start}", tz="Asia/Bangkok").tz_convert("UTC").value
    b = pd.Timestamp(f"2026-10-19 {end}", tz="Asia/Bangkok").tz_convert("UTC").value + minutes_after * 60 * 10**9
    return a, b


def match(C: pd.DataFrame) -> tuple[list[dict], pd.DataFrame]:
    """Found / missed per formation; the catches inside no span are extra."""
    rows, used = [], np.zeros(len(C), bool)
    for n, s, e, fams, what in OWNER:
        a, b = thai_span(s, e)
        inside = (C.t_dec >= a) & (C.t_dec <= b)
        hit = C[inside & C["name"].isin(fams)]
        used |= inside.to_numpy()
        rows.append(dict(n=n, span=f"{s} - {e}", what=what, found=len(hit) > 0,
                         by=", ".join(f"{r['name']} {pd.Timestamp(r.t_dec, tz='UTC').tz_convert('Asia/Bangkok'):%H:%M}"
                                      for _, r in hit.iterrows()),
                         others=int(inside.sum() - len(hit))))
    return rows, C[~used]


def main() -> None:
    m = load_day()
    ch = F5.Chart(m, F5.day_h1_atr(m))
    opens = F5.window_opens(DAY0, pd.Timestamp("2026-10-20", tz="UTC"))
    C, Fm = ch.scan(1, len(ch.c), opens)
    th = lambda t: pd.Timestamp(int(t), tz="UTC").tz_convert("Asia/Bangkok").strftime("%H:%M")  # noqa: E731
    pd.to_pickle(dict(m=m, C=C, F=Fm, H=ch.H, piv=ch.piv), HERE / "p5_day.pkl")
    print(f"2026-10-19: {len(m)} M1 bars {th(m.index[0].value)} - {th(m.index[-1].value)} Thai; H (the day's H1 ATR) "
          f"from {np.nanmin(ch.H):.1f} to {np.nanmax(ch.H):.1f} USD -> the main swing {0.6 * np.nanmin(ch.H):.1f} - "
          f"{0.6 * np.nanmax(ch.H):.1f}")
    pb, pp, pk, pc = ch.piv
    print("the inner ZigZag's pivots: " + ", ".join(f"{th(ch.t_open[b])} {'H' if k > 0 else 'L'} {p:.2f}" for b, p, k in zip(pb, pp, pk, strict=True)))
    rows, extra = match(C)
    print("\nthe owner's formations:")
    for r in rows:
        print(f"  #{r['n']:<2} {r['span']:<13} {'FOUND ' if r['found'] else 'MISSED'} {r['what']}" + (f" - by {r['by']}" if r["by"] else "")
              + (f" (+{r['others']} other catches in the span)" if r["others"] else ""))
    print(f"\nfound {sum(r['found'] for r in rows)} of {len(rows)}; catches {len(C)}, extra (inside no span) {len(extra)}:")
    for _, r in extra.sort_values("t_dec").iterrows():
        print(f"  {th(r.t_dec)} {r['name']} ({r.variant}) trigger {r.trigger:.2f} extreme {r.extreme:.2f} height {r.height:.1f}")
    print(f"\npictures in formation: {len(Fm)}")
    for _, f in Fm.sort_values("t_dec").iterrows():
        print(f"  {th(f.t_dec)} {f['kind']}: tops / bottoms {f['pa'][1]:.2f} ({th(ch.t_open[f['pa'][0]])}) and {f['pb'][1]:.2f} "
              f"({th(ch.t_open[f['pb'][0]])}), between {f['t'][1]:.2f}; A {'SELL' if f['a']['side'] < 0 else 'BUY'} past "
              f"{f['a']['trigger']:.2f} stop {f['a']['stop']:.2f} target {f['a']['target']:.2f}; B {'BUY' if f['b']['side'] > 0 else 'SELL'} past "
              f"{f['b']['trigger']:.2f} stop {f['b']['stop']:.2f} target {f['b']['target']:.2f}")


if __name__ == "__main__":
    main()
