"""V3-2's acceptance on 2026-10-19 (rule R11; the live bars, shape only: the entries are listed with their decision,
the M1 close at the decision, the stop and the target candidates - no outcome is computed, no tick is read).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/shape_v32.py > research/2026-10-18-moments/agents/dev2/out_shape_v32.txt
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402
import v32  # noqa: E402

TH = "Asia/Bangkok"
DAY0, DAY1 = pd.Timestamp("2026-10-19 05:00", tz=TH), pd.Timestamp("2026-10-20 05:00", tz=TH)


def th(t_ns) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(np.asarray(t_ns, np.int64), tz="UTC").tz_convert(TH)


def main() -> None:
    with open(HERE / "v32_specs.pkl", "rb") as f:
        q1, q2 = pickle.load(f)["q"]
    m = W.load_live()
    assert m.index.min() >= W.LIVE_FROM
    mk = v32.market(m)
    sp = v32.build(mk, learning=False)
    c1 = m.close.to_numpy(float)
    rows = []
    for key, df in sp.items():
        if key in ("rec", "tur", "levels") or not len(df):
            continue
        t = th(df.t_dec)
        df = df[(t >= DAY0) & (t < DAY1)].copy()
        if not len(df):
            continue
        k = mk.k1(df.t_dec.to_numpy(np.int64))
        df["close_dec"] = c1[k]
        df["vol_tf"] = v32.choose_tf(df.H.to_numpy(float), q1, q2)
        df["key"] = key
        rows.append(df)
    A = pd.concat(rows, ignore_index=True)
    A["th"] = th(A.t_dec).strftime("%H:%M")
    print(f"live bars {m.index.min()} .. {m.index.max()} UTC; terciles q1 {q1:.3f} q2 {q2:.3f}")
    show = ["key", "th", "side", "close_dec", "stop", "stop_ext", "window", "vol_tf", "S", "H", "tag", "lvl", "ev", "kind3",
            "first", "line", "al_label", "al_bias", "al_label_bar", "al_bias_bar", "open", "p0", "ext", "piv", "top", "bot"]
    show = [c for c in show if c in A.columns]
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    for key in sorted(A.key.unique()):
        x = A[A.key == key]
        print(f"\n---- {key}: {len(x)} entries on 2026-10-19 (Thai 05:00 .. next 05:00)")
        print(x[[c for c in show if x[c].notna().any()]].to_string(index=False))

    def found(name, sel):
        x = A[sel]
        print(f"\n{name}: {'FOUND' if len(x) else 'MISSED'}")
        if len(x):
            print(x[[c for c in ("key", "th", "side", "close_dec", "stop", "stop_ext", "window", "vol_tf") if c in x]].to_string(index=False))

    t = th(A.t_dec)
    tt = lambda a, b: (t >= pd.Timestamp(f"2026-10-19 {a}", tz=TH)) & (t <= pd.Timestamp(f"2026-10-19 {b}", tz=TH))  # noqa: E731
    e = A.key.str[:2]
    found("Trade 4 (entry 1 sell, 18:25-19:00, close 4167.0-4172.5, stop 4177.06-4182.0)",
          (e == "e1") & (A.side == -1) & tt("18:25", "19:00") & A.close_dec.between(4167.0, 4172.5) & A.stop.between(4177.06, 4182.0))
    found("The base (entry 2 sell, 21:15-23:00, close 4142-4150, stop 4155.3-4165.0)",
          (e == "e2") & (A.side == -1) & tt("21:15", "23:00") & A.close_dec.between(4142.0, 4150.0) & A.stop.between(4155.3, 4165.0))
    found("The triple-top sell (any entry, 14:33-15:30, close 4176.0-4186.5)",
          (A.side == -1) & tt("14:33", "15:30") & A.close_dec.between(4176.0, 4186.5))
    found("The NY-open fake leg then the sell (entry 4, 20:30-20:50, close >= 4150)",
          (e == "e4") & (A.side == -1) & tt("20:30", "20:50") & (A.close_dec >= 4150.0))

    # the side / trend readings at the moments that matter (path = rule 18, bar = the TF's bars)
    moments = ["14:33", "16:00", "17:20", "18:30", "18:58", "19:00", "20:30", "21:30", "22:30"]
    tn = W._ns(pd.DatetimeIndex([pd.Timestamp(f"2026-10-19 {x}", tz=TH) for x in moments]).tz_convert("UTC"))
    for mode in ("path", "bar"):
        rd = W.readings_at(mk.R, tn, mode=mode)
        rd.index = moments
        print(f"\nreadings ({mode}):")
        print(rd.to_string())
    p = mk.R["H1@M1"].struct
    tl = th(W._ns(mk.R["H1@M1"].bars.avail))
    after = np.asarray(tl >= pd.Timestamp("2026-10-19 14:33", tz=TH))
    dn = np.nonzero(after & (p.label.to_numpy() == -1))[0]
    print(f"\nH1 on the M1 path: label down first at {tl[dn[0]]:%H:%M} (known)" if len(dn) else "\nH1 on the M1 path: never down")
    # rule 19 on the day (the M5 box 4165.61-4190.25 from 05:05)
    k = (m.index.tz_convert(TH) >= pd.Timestamp("2026-10-19 05:05", tz=TH)) & (m.index.tz_convert(TH) < pd.Timestamp("2026-10-19 17:50", tz=TH))
    v = W.edge_visits(m.high.to_numpy()[k], m.low.to_numpy()[k], W.swing_size(m)[k], 4190.25, 4165.61, 1)
    print(f"rule 19, the top's tests 05:05-17:50: {len(v)} at {[f'{x:%H:%M}' for x in m.index[k][v].tz_convert(TH)]}")


if __name__ == "__main__":
    main()
