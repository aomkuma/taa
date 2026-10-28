"""Setup OWN V2, Task A1: the owner's two-way sweep at the news, detected on the real ticks (learning parts only).

The owner (2026-10-19), on the 2026-01-09 US jobs report: "to really buy, wait for the fake drop in the first minute -
then it sweeps up, and then it comes down"; "that is the case of the fake break upward". The sequence coded here:

1. the first leg: in the first minute after the release, price moves LEG USD or more away from p0 (the last mid
   before the release); its side is the way of the first minute's larger move (what its M1 candle shows; the
   researcher's rule, the way of the first LEG-USD move, is the variant side_rule='first'), its size the first
   minute's extreme that way;
2. the sweep: after the first minute, price goes RUN USD past p0 the OTHER way before it makes a new extreme
   CONT_EXTRA USD beyond the first minute's - 'faked'; that new extreme first is 'continued'; neither within WIN_MIN
   minutes of the release is 'neither'; no first leg is 'quiet';
3. the third leg: for a faked one, how far price comes back from the sweep's extreme within BACK_MIN minutes after it;
   'came_down' = back >= CAME_DOWN x the sweep; 'third' = back through p0.

Prices are the tick mid ((bid + ask) / 2), so the release's wide spread does not move them. The first minute's
readings (`first_minute`) use only ticks before the decision (the release + FIRST_S seconds); the label (`race`) reads
what came after by design - it is the description, not a decision. Start: `news_sweep.sweep()` by the researcher,
re-written so the decision-time readings and the label are separate functions (the no-look-ahead check needs that)
and with the pre-release range, the first minute's other side and the third leg's time added.

The exam (2026-04-18 onward) is never loaded: `learning_ticks` refuses those days and the event lists end before it.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/sweep_detector.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENTS = HERE.parent
sys.path.insert(0, str(AGENTS / "precursors"))
sys.path.insert(0, str(AGENTS / "journal"))
sys.path.insert(0, str(AGENTS.parent))

LEARN_START = pd.Timestamp("2025-10-18", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
NY = "America/New_York"
FIXED_NY = ((8, 30), (10, 0))  # the US data and the 10:00 releases, New York time
NS_S = 10**9
NS_MIN = 60 * NS_S
LEG = 3.0  # the first leg: a LEG-USD move from p0 within the first minute
FIRST_S = 60  # the first minute (the decision is at the release + FIRST_S seconds)
RUN = 10.0  # the sweep: RUN USD past p0 the other way
WIN_MIN = 15  # the race window, minutes from the release
BACK_MIN = 15  # the third leg is measured within BACK_MIN minutes after the sweep's extreme
PRE_MIN = 30  # the pre-release range: the PRE_MIN minutes before the release
CAME_DOWN = 0.5  # 'came_down': back at least this share of the sweep (past p0)
CONT_EXTRA = 3.0  # 'continued' needs a new extreme this many USD (one LEG) beyond the first minute's; the
# researcher's news_sweep used 0 (any new extreme, by a cent) - kept as a variant
EXTRA_CSV = AGENTS / "news" / "extra_releases.csv"


class ExamPeriodError(RuntimeError):
    """Raised when anything would load a day of the exam period."""


def learning_ticks(day: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """The day's ticks (t ns, bid, ask), sorted; refuses any UTC day at / after the exam start."""
    from tick_straddle import day_ticks  # noqa: PLC0415

    d = pd.Timestamp(day)
    d = (d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")).normalize()
    if d >= EXAM_START:
        raise ExamPeriodError(f"{d:%Y-%m-%d} is in the exam period (from {EXAM_START:%Y-%m-%d})")
    return day_ticks(d)


def first_minute(t: np.ndarray, mid: np.ndarray, t_rel: int, leg: float = LEG, first_s: int = FIRST_S,
                 pre_min: int = PRE_MIN, side_rule: str = "larger") -> dict | None:
    """Everything known at the decision (t_rel + first_s), from ticks before it only. None without a tick before the
    release. USD signed by the first leg: + = its way.

    p0 = the last mid before t_rel; pre_hi / pre_lo = the mid's range over [t_rel - pre_min, t_rel); up1 / dn1 = the
    first minute's largest move up / down from p0; c1 = the first minute's last mid. No move of LEG USD either way:
    first = 0 (quiet). Else the first leg's side: side_rule 'larger' = the way of the first minute's larger move (a tie:
    the one that reached LEG first) - what the first minute's M1 candle shows; 'first' = the way of the first LEG-USD
    move (the researcher's `news_sweep.sweep`). leg1 = the first minute's extreme that way; t_leg = the time of the
    first LEG-USD tick that way, t_ext = of the extreme; give_back = how far c1 sits back from the extreme toward p0;
    two_sided = the first minute moved LEG both ways; swept_pre = the first leg went beyond the pre-release range on
    its side."""
    if side_rule not in ("larger", "first"):
        raise ValueError(f"side_rule {side_rule!r}")
    k0 = int(np.searchsorted(t, t_rel, side="left")) - 1
    if k0 < 0:
        return None
    p0 = float(mid[k0])
    pa = int(np.searchsorted(t, t_rel - pre_min * NS_MIN, side="left"))
    pre = mid[min(pa, k0):k0 + 1]  # at least p0 itself
    a = k0 + 1
    b1 = int(np.searchsorted(t, t_rel + first_s * NS_S, side="left"))
    d = mid[a:b1] - p0
    up1 = float(max(d.max(), 0.0)) if len(d) else 0.0
    dn1 = float(max(-d.min(), 0.0)) if len(d) else 0.0
    out = dict(p0=p0, pre_hi=float(pre.max()), pre_lo=float(pre.min()), up1=up1, dn1=dn1,
               c1=float(mid[b1 - 1]) if b1 > a else p0, first=0)
    hit = np.nonzero(np.abs(d) >= leg)[0]
    if not len(hit):
        return out
    s_first = int(np.sign(d[hit[0]]))
    s1 = s_first if side_rule == "first" or up1 == dn1 else (1 if up1 > dn1 else -1)
    sd = s1 * d
    x = int(np.argmax(sd))
    leg1 = float(sd[x])
    h1 = int(np.nonzero(sd >= leg)[0][0])
    out.update(first=s1, leg1=leg1, t_leg=int(t[a + h1]), t_ext=int(t[a + x]),
               give_back=float(leg1 - s1 * (out["c1"] - p0)), two_sided=bool(min(up1, dn1) >= leg),
               swept_pre=bool(p0 + leg1 > out["pre_hi"]) if s1 > 0 else bool(p0 - leg1 < out["pre_lo"]))
    return out


def race(t: np.ndarray, mid: np.ndarray, t_rel: int, fm: dict, run: float = RUN, first_s: int = FIRST_S,
         win_min: int = WIN_MIN, back_min: int = BACK_MIN, cont_extra: float = CONT_EXTRA,
         came_down: float = CAME_DOWN) -> dict:
    """What came after the first minute (the label - it reads the future by design). fm = first_minute(...).

    Within [t_rel + first_s, t_rel + win_min): the first leg's way beyond leg1 + cont_extra first -> 'continued'
    (cont = the window's extreme that way beyond leg1, t_cont its time); run USD past p0 the other way first ->
    'faked'; else 'neither'. A faked one: sweep = the window's extreme the other way past p0 (t_sweep, sweep_min);
    back = the most it comes back from there within back_min minutes after the sweep's extreme (t_back its time);
    came_down = back >= came_down x sweep; third = back through p0; swept_other = the sweep went beyond the pre-release
    range on its side."""
    if fm is None:
        return {}
    if fm["first"] == 0:
        return dict(outcome="quiet")
    s1, p0, leg1 = fm["first"], fm["p0"], fm["leg1"]
    b1 = int(np.searchsorted(t, t_rel + first_s * NS_S, side="left"))
    end = int(np.searchsorted(t, t_rel + win_min * NS_MIN, side="left"))
    e = s1 * (mid[b1:end] - p0)
    c, f = np.nonzero(e > leg1 + cont_extra)[0], np.nonzero(e <= -run)[0]
    ci, fi = (int(c[0]) if len(c) else len(e)), (int(f[0]) if len(f) else len(e))
    outcome = "continued" if ci < fi else "faked" if fi < ci else "neither"
    out = dict(outcome=outcome)
    if outcome == "continued":
        j = b1 + int(np.argmax(e))
        out.update(t_decided=int(t[b1 + ci]), cont=float(e[j - b1] - leg1), t_cont=int(t[j]))
    if outcome != "faked":
        return out
    j = b1 + int(np.argmin(e))
    sweep = float(-e[j - b1])
    back_end = int(np.searchsorted(t, t[j] + back_min * NS_MIN, side="left"))
    after = s1 * (mid[j + 1:back_end] - p0)
    k = int(np.argmax(after)) if len(after) else -1
    back = float(after[k] + sweep) if len(after) else 0.0
    out.update(t_decided=int(t[b1 + fi]), sweep=sweep, t_sweep=int(t[j]), sweep_min=(int(t[j]) - t_rel) / NS_MIN,
               back=back, t_back=int(t[j + 1 + k]) if len(after) else int(t[j]),
               came_down=bool(back >= came_down * sweep), third=bool(len(after) and after[k] >= 0),
               swept_other=bool(p0 - s1 * sweep > fm["pre_hi"]) if s1 < 0 else bool(p0 - s1 * sweep < fm["pre_lo"]))
    return out


def detect(t: np.ndarray, mid: np.ndarray, t_rel: int, side_rule: str = "larger", **kw: float) -> dict | None:
    """first_minute + race for one release; kw goes to race (run, cont_extra, ...)."""
    fm = first_minute(t, mid, t_rel, side_rule=side_rule)
    if fm is None:
        return None
    return {**fm, **race(t, mid, t_rel, fm, **kw)}


def fixed_events(start: pd.Timestamp = LEARN_START, end: pd.Timestamp = EXAM_START) -> pd.DataFrame:
    """Every weekday's 08:30 and 10:00 New York minute in [start, end), in UTC (summer and winter time)."""
    if end > EXAM_START:
        raise ExamPeriodError("the event list may not reach the exam period")
    rows = []
    for d in pd.date_range(start.tz_convert(NY).date(), end.tz_convert(NY).date(), freq="D"):
        if d.weekday() >= 5:
            continue
        for hh, mm in FIXED_NY:
            t = pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hh, minute=mm, tz=NY).tz_convert("UTC")
            if start <= t < end:
                rows.append(dict(t=t, ny=f"{hh:02d}:{mm:02d}"))
    return pd.DataFrame(rows)


def calendar_events(start: pd.Timestamp = LEARN_START, end: pd.Timestamp = EXAM_START) -> pd.DataFrame:
    """The release minutes of the calendar (gold.releases(): CPI, NFP, PPI, PCE, GDP, FOMC; extra_releases.csv: RET,
    JOL, CLM, MIN, PC) in [start, end), one row a minute: t (UTC), ny ('HH:MM' New York), names ('CLM+NFP'), check
    (a release the calendar marks 'check' / 'schedule')."""
    import gold  # noqa: PLC0415

    if end > EXAM_START:
        raise ExamPeriodError("the event list may not reach the exam period")
    a = gold.releases()
    a = pd.DataFrame(dict(t=a["t"], name=a["event"], check=a["note"].isin(["check", "schedule"])))
    x = pd.read_csv(EXTRA_CSV, dtype=str, keep_default_na=False)
    tx = pd.to_datetime(x["date"] + " " + x["time_et"]).dt.tz_localize(NY).dt.tz_convert("UTC")
    b = pd.DataFrame(dict(t=tx, name=x["event"], check=False))
    c = pd.concat([a, b], ignore_index=True)
    c = c[(c.t >= start) & (c.t < end)]
    g = c.groupby("t", sort=True)
    out = pd.DataFrame(dict(names=g["name"].agg(lambda s: "+".join(sorted(set(s)))), check=g["check"].any())).reset_index()
    out["ny"] = out.t.dt.tz_convert(NY).dt.strftime("%H:%M")
    return out[["t", "ny", "names", "check"]]


def scan(ev: pd.DataFrame, **kw: float) -> pd.DataFrame:
    """detect() at every event (t, ny, ...), one day's ticks at a time; the event columns are kept."""
    rows = []
    for day, D in ev.groupby(pd.DatetimeIndex(ev.t).normalize(), sort=True):
        tk = learning_ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        mid = (bid + ask) / 2
        for r in D.itertuples(index=False):
            x = detect(t, mid, pd.Timestamp(r.t).value, **kw)
            if x is not None:
                rows.append({**r._asdict(), **x})
    return pd.DataFrame(rows)


def m1_from_ticks(t: np.ndarray, mid: np.ndarray, a: int, b: int) -> pd.DataFrame:
    """M1 candles of the mid over [a, b) (ns, whole minutes), indexed by each minute's open (UTC); a minute without a
    tick is left out."""
    s = slice(int(np.searchsorted(t, a, side="left")), int(np.searchsorted(t, b, side="left")))
    m = (t[s] // NS_MIN) * NS_MIN
    df = pd.DataFrame(dict(m=m, p=mid[s]))
    g = df.groupby("m", sort=True)["p"]
    o = pd.DataFrame(dict(open=g.first(), high=g.max(), low=g.min(), close=g.last(), n=g.size()))
    o.index = pd.to_datetime(o.index, utc=True)
    return o


def thai(t_ns: int) -> str:
    """A UTC epoch (ns) as Thai time (UTC+7), 'HH:MM'."""
    return pd.Timestamp(t_ns, tz="UTC").tz_convert("Asia/Bangkok").strftime("%H:%M")


def summary(T: pd.DataFrame) -> pd.DataFrame:
    """Per part x ny minute: days, the outcomes' counts, and for the faked ones the median sweep / its minute / back,
    the share that came down and that crossed p0 again."""
    rows = []
    for (p, ny), D in T.groupby(["part", "ny"], sort=True):
        F = D[D.outcome == "faked"]
        oc = D.outcome.value_counts()
        rows.append(dict(part=p, ny=ny, days=len(D), faked=int(oc.get("faked", 0)), continued=int(oc.get("continued", 0)),
                         neither=int(oc.get("neither", 0)), quiet=int(oc.get("quiet", 0)),
                         sweep_med=F.sweep.median() if len(F) else np.nan, min_med=F.sweep_min.median() if len(F) else np.nan,
                         back_med=F.back.median() if len(F) else np.nan,
                         came_down=float(F.came_down.mean()) if len(F) else np.nan,
                         third=float(F.third.mean()) if len(F) else np.nan))
    return pd.DataFrame(rows)


def main() -> None:
    from m15_trades import part_of  # noqa: PLC0415

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    cal = calendar_events()
    fixed = fixed_events().merge(cal[["t", "names"]], on="t", how="left")
    fixed["names"] = fixed["names"].fillna("")
    out = []
    variants = [("larger", CONT_EXTRA), ("first", CONT_EXTRA), ("larger", 0.0), ("first", 0.0)]
    for name, ev in (("fixed", fixed), ("calendar", cal)):
        for rule, extra in variants:
            T = scan(ev, side_rule=rule, cont_extra=extra)
            T["part"] = part_of(pd.DatetimeIndex(T.t))
            T["set"], T["side_rule"], T["cont_extra"] = name, rule, extra
            if not (pd.DatetimeIndex(T.t) < EXAM_START).all():
                raise ExamPeriodError("an exam minute was scanned")
            out.append(T)
    A = pd.concat(out, ignore_index=True)
    A.to_parquet(HERE / "a1_detections.parquet")
    main_v = (A.side_rule == "larger") & (A.cont_extra == CONT_EXTRA)
    for name in ("fixed", "calendar"):
        T = A[main_v & (A.set == name)]
        print(f"\n== {name} minutes ({len(T)} with ticks); the detector: the first leg = the first minute's larger "
              f"move, continued = a new extreme {CONT_EXTRA:.0f} USD beyond it, faked = {RUN:.0f} USD past p0 the "
              f"other way first")
        print(summary(T).round(2).to_string(index=False))
    print("\n== faked counts by variant (side: larger / first 3-USD move; continued needs a new extreme + 0 / 3 USD)")
    V = (A[A.outcome == "faked"].groupby(["set", "part", "ny", "side_rule", "cont_extra"]).size()
         .unstack(["side_rule", "cont_extra"]).fillna(0).astype(int))
    print(V.to_string())
    F = A[main_v & (A.outcome == "faked")]
    cols = ["set", "part", "ny", "names", "first", "leg1", "up1", "dn1", "two_sided", "swept_pre", "sweep",
            "sweep_min", "back", "came_down", "third", "swept_other"]
    print("\nthe faked minutes (the detector):")
    print(F.assign(t=pd.DatetimeIndex(F.t).strftime("%Y-%m-%d %H:%M"))[["t", *cols]].round(2).to_string(index=False))
    key = ["set", "t"]
    W = A.pivot_table(index=key, columns=["side_rule", "cont_extra"], values="outcome", aggfunc="first")
    W.columns = [f"{r}_{e:.0f}" for r, e in W.columns]
    d = W[W.nunique(axis=1) > 1].reset_index()
    print(f"\nthe minutes whose label differs between the variants ({len(d)}):")
    print(d.assign(t=pd.DatetimeIndex(d.t).strftime("%Y-%m-%d %H:%M")).to_string(index=False))


if __name__ == "__main__":
    main()
