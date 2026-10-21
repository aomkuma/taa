"""Planted bugs for plan1_forward.py (the PLAN-1 forward recorder), each run against test_plan1_forward.py in a
temporary copy (the harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_plan1_forward.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

BUGS = [
    # the band
    ("band: 12.0 itself outside", [("return (a >= BAND_LO) & (a < BAND_HI)", "return (a > BAND_LO) & (a < BAND_HI)")]),
    ("band: 16.0 itself inside", [("return (a >= BAND_LO) & (a < BAND_HI)", "return (a >= BAND_LO) & (a <= BAND_HI)")]),
    ("band: a NaN ATR inside", [("return (a >= BAND_LO) & (a < BAND_HI)", "return ~((a < BAND_LO) | (a >= BAND_HI))")]),
    ("band: 11 .. 16", [("BAND_LO, BAND_HI = 12.0, 16.0", "BAND_LO, BAND_HI = 11.0, 16.0")]),
    # the H1 ATR
    ("atr: the forming H1 bar read", [('k = np.searchsorted(avail, t, side="right") - 1',
                                       'k = np.minimum(np.searchsorted(avail, t, side="right"), len(avail) - 1)')]),
    ("atr: a bar closing exactly at the decision not read", [('k = np.searchsorted(avail, t, side="right") - 1',
                                                             'k = np.searchsorted(avail, t, side="left") - 1')]),
    ("atr: an hour complete one minute after its open", [('return pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, P.atr14(b)',
                                                         'return pd.DatetimeIndex(b.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8, P.atr14(b)')]),
    ("atr: the bar before's ATR", [('return pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, P.atr14(b)',
                                    'return pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, pd.Series(P.atr14(b)).shift(1).to_numpy()')]),
    ("atr: read at the fill, not the decision", [('T["atr_h1"] = atr_at(av, a, T.t_dec.to_numpy(np.int64))',
                                                  'T["atr_h1"] = atr_at(av, a, T.t_in.to_numpy(np.int64))')]),
    ("atr: the re-derivation with 13 bars", [("a = tr.rolling(14).mean()", "a = tr.rolling(13).mean()")]),
    # the variants
    ("VOL-16b: London outside the band, not NY", [('"VOL-16b": band | (T.piece.to_numpy() == "NY straddle")',
                                                   '"VOL-16b": band | (T.piece.to_numpy() == "London ORB")')]),
    ("VOL-16b: no straddle outside the band", [('"VOL-16b": band | (T.piece.to_numpy() == "NY straddle")', '"VOL-16b": band')]),
    ("variants: one position before the filter", [("        kept = L.stream(T[k].assign(_row=np.flatnonzero(k)))",
                                                   "        kept = L.stream(T.assign(_row=np.arange(len(T))))\n"
                                                   "        kept = kept[k[kept._row.to_numpy()]]")]),
    ("variants: the row numbers of the filtered frame", [("kept = L.stream(T[k].assign(_row=np.flatnonzero(k)))",
                                                          "kept = L.stream(T[k].assign(_row=np.arange(int(k.sum()))))")]),
    # the period and what is read
    ("end: today's filling day included", [("end = min(max(tick_days) + DAY, today.normalize())", "end = max(tick_days) + DAY")]),
    ("end: the newest tick day left out", [("end = min(max(tick_days) + DAY, today.normalize())",
                                            "end = min(max(tick_days), today.normalize())")]),
    ("end: a period without a weekday accepted", [("if end <= FWD_START + DAY:", "if end <= FWD_START:")]),
    ("m1: one more day of the exam read", [('("open_time", ">=", lo)', '("open_time", ">=", lo - DAY)')]),
    ("m1: a leaked early row let through", [("if len(m) and (m.index.min() < lo or m.index.max() >= end):",
                                             "if len(m) and m.index.max() >= end:")]),
    ("m1: a learning read may reach the exam", [("elif end > EXAM_START:", "elif end > FWD_START:")]),
    ("m1: a forward start other than 2026-10-18", [("if start != FWD_START:", "if False:")]),
    ("m1: 21 days of warm-up", [("WARM_DAYS = 14  #", "WARM_DAYS = 21  #")]),
    ("ticks: a day before the start opened", [("if d < self.start:", "if False:")]),
    ("pieces: B2 decisions before the start kept", [("asia = asia[asia.t_dec.astype(np.int64) >= start.value]", "asia = asia")]),
    ("pieces: B2 located from the start only", [("asia = L.asia_b2(m, start - locate_back, end, ticks, slip)",
                                                 "asia = L.asia_b2(m, start, end, ticks, slip)")]),
    ("pieces: located one day back", [("LOCATE_BACK = pd.Timedelta(days=3)", "LOCATE_BACK = pd.Timedelta(days=1)")]),
    ("pieces: the end's weekday included", [('end.tz_localize(None), inclusive="left", tz="UTC")',
                                             'end.tz_localize(None), inclusive="both", tz="UTC")')]),
    ("pieces: the period guard off", [("if len(every) and ((every.t_in < start.value) | (every.t_in >= end.value) | "
                                       "(every.t_dec < start.value)).any():", "if False:")]),
    ("forward: the warm-up check with the full warm-up", [("m3 = m[m.index >= start - pd.Timedelta(days=WARM_DAYS - 3)]", "m3 = m")]),
    ("forward: a dry run without its end", [("if start != FWD_START and end is None:", "if False:")]),
    # the report
    ("weeks: UTC weeks", [('.tz_convert("Asia/Bangkok")\n    return (th.normalize()', '.tz_convert("UTC")\n    return (th.normalize()')]),
    ("weeks: the running USD not running", [('out[(v, "run")] = out[(v, "usd")].cumsum()', 'out[(v, "run")] = out[(v, "usd")]')]),
    ("weeks: a 0 counted as a win", [("(x > 0).mean()", "(x >= 0).mean()")]),
    ("summary: trades a day over one day more", [('s["per_day"] = s["n"] / n_days if n_days else np.nan',
                                                  's["per_day"] = s["n"] / (n_days + 1) if n_days else np.nan')]),
    ("table: a sell's exit price", [("(X.entry + X.side * X.pnl)", "(X.entry + X.pnl)")]),
    ("table: every variant named", [('if r[f"take_{v}"]) for _, r in X.iterrows()]', 'if True) for _, r in X.iterrows()]')]),
    ("table: only the unfiltered trades", [('X = T[T[[f"take_{v}" for v in VARIANTS]].any(axis=1)]', "X = T[T.take_unfiltered]")]),
    ("table: times in UTC", [('utc=True).tz_convert("Asia/Bangkok").strftime("%m-%d %H:%M:%S")',
                              'utc=True).strftime("%m-%d %H:%M:%S")')]),
    ("compare: equal by key only", [("eq = sum(tuple(ka[k]) == tuple(kb[k]) for k in both)", "eq = len(both)")]),
    ("switch: --end without --forward", [("    if a.end is not None:", "    if False:")]),
    ("switch: the forward warm-up changeable", [("        if a.warm_days != WARM_DAYS:", "        if False:")]),
]


def main() -> None:
    py = Path(sys.executable)
    mod, test = HERE / "plan1_forward.py", HERE / "test_plan1_forward.py"
    src = mod.read_text(encoding="utf-8")
    ok, line = run(src, mod, test, py)
    print(f"plan1_forward.py: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits), mod, test, py)
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
