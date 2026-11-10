"""ADVISORY ONLY. The gate of the replay is ``zone_replay_compare.gate_failures`` (zero raw differences, no ERROR
log line); nothing in this module can pass a run (eye/ZONE_LIVE.md L11.2, "the gate is strict"). It lists each
difference with the path's facts and *suggests* an admitted cause for a human to check by hand.

The explanations of the differences between the replayed runner and the simulation (eye/ZONE_LIVE.md L11.2).

Every difference is listed with the bar that explains it and classified as one of the causes L11.2 admits:
the order of touches inside one bar, the bar boundary, a P2 re-placed after its P1 filled in the same bar, a missed
touch (polling mode), tick rounding. Each cause comes with a check that the bar really has that property (the
checks read the stored bars, the quote path the replay walked, the broker's event log and the cycles that ran).
A difference no check explains is a fault. After an admitted difference the setups must agree again once the
reservation of the differing setup has ended: a later difference inside that reservation is a ``cascade``."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.zone.core import Bars, plan_setup
from app.zone.live import be_stop_sent, closed_hour_cancel, entry_blocked, sent_prices
from tests.zone_replay import CENT, bar_path
from tests.zone_replay_compare import (
    EPS,
    TICK,
    Diff,
    Key,
    Record,
    RunSetup,
    SimSetup,
    SpanPlan,
    gate_failures,
    key_of,
    raw_diffs,
)

PER = {"M5": 12, "M15": 4}
CAUSES = ("tick rounding", "bar boundary", "P2 after P1", "missed touch", "in-bar order", "cascade")


@dataclass
class Why:
    cause: str
    text: str


class Explainer:
    def __init__(self, plan: SpanPlan, rec: Record, full: Bars) -> None:
        self.plan, self.rec = plan, rec
        fr = full.frame(plan.tf)
        self.ex_open = fr["open_time"]
        self.open_ns = fr["open_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
        self.close_ns = fr["close_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
        self.o, self.h, self.lo, self.c = (fr[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.spread = fr["spread"].to_numpy(int)
        self.visit_of: dict[Key, Any] = {
            key_of(o.visit.time, o.visit.side, o.visit.line): o.visit for o in plan.sim.outcomes
        }
        self.W = rec.preclose
        self.C = rec.cycle_seconds if rec.mode == "poll" else 0.0
        self._paths: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self.ids = self._ids()

    # --- helpers ---
    def path(self, j: int) -> tuple[np.ndarray, np.ndarray]:
        if j not in self._paths:
            self._paths[j] = bar_path(
                self.o[j],
                self.h[j],
                self.lo[j],
                self.c[j],
                self.open_ns[j] / 1e9,
                self.close_ns[j] / 1e9,
                self.W,
            )
        return self._paths[j]

    def bar_of_time(self, t_s: float) -> int:
        return int(np.searchsorted(self.close_ns, round(t_s * 1e9), side="right"))

    def bar_of_ts(self, t: pd.Timestamp) -> int:
        return int(np.searchsorted(self.close_ns, t.value, side="right"))

    def when(self, j: int | None) -> str:
        return "-" if j is None else f"bar {j} ({self.ex_open.iloc[j]:%m-%d %H:%M})"

    def _ids(self) -> dict[int, Key]:
        """Setup id -> key: the first request of each id was placed in its own hour, on its own side."""
        out: dict[int, Key] = {}
        by_hour_side: dict[tuple[pd.Timestamp, str], list[Key]] = {}
        for k in self.rec.run_setups:
            by_hour_side.setdefault((k[0], k[1]), []).append(k)
        seen: set[int] = set()
        for t, req, _rc in self.rec.requests:
            cm = str(req.get("comment", ""))
            if not cm.startswith("Z") or req.get("action") not in (1, 5):
                continue
            sid = int(cm[1:].split("-")[0])
            if sid in seen:
                continue
            seen.add(sid)
            side = "BUY" if req.get("type") in (0, 2) else "SELL"
            hour = pd.Timestamp(int(t // 3600) * 3600, unit="s", tz="UTC")
            ks = by_hour_side.get((hour, side))
            if ks:
                out[sid] = ks[0]
        return out

    def events_of(self, key: Key) -> list[Any]:
        sids = {sid for sid, k in self.ids.items() if k == key}
        out = []
        for e in self.rec.events:
            cm = e.comment
            if cm.startswith("Z") and cm[1:].split("-")[0].isdigit() and int(cm[1:].split("-")[0]) in sids:
                out.append(e)
        return out

    def plan_of(self, key: Key) -> Any:
        return plan_setup(self.visit_of[key], self.plan.params)

    # --- the simulation's comparisons, evaluated on the walked path ---
    def levels(self, key: Key) -> dict[str, tuple[str, float]]:
        v, pl = self.visit_of[key], self.plan_of(key)
        buy = v.sgn > 0
        lv: dict[str, tuple[str, float]] = {}
        for n, px in (("P1", pl.p1), ("P2", pl.p2)):
            lv[n] = ("ask_le", px) if buy else ("bid_ge", px)
        lv["SL"] = ("bid_le", pl.sl) if buy else ("ask_ge", pl.sl)
        lv["TP"] = ("bid_ge", pl.tp) if buy else ("ask_le", pl.tp)
        lv["withdraw"] = ("bid_ge", v.line + pl.away) if buy else ("bid_le", v.line - pl.away)
        lv["near"] = ("bid_le", v.line + v.z) if buy else ("bid_ge", v.line - v.z)
        s = self.rec.sim_setups.get(key)
        if s is not None and s.fills:
            avg = float(np.mean([f[1] for f in s.fills.values()]))
            mid = avg + pl.be_frac * (pl.tp - avg)
            lv["BE"] = ("bid_ge", mid) if buy else ("ask_le", mid)
        return lv

    def touch_time(self, j: int, cond: str, price: float) -> float | None:
        bids, times = self.path(j)
        sp = int(self.spread[j])
        lvl = round(price * CENT)
        if cond == "ask_le":
            m = bids + sp <= lvl
        elif cond == "ask_ge":
            m = bids + sp >= lvl
        elif cond == "bid_le":
            m = bids <= lvl
        else:
            m = bids >= lvl
        idx = np.flatnonzero(m)
        return float(times[idx[0]]) if len(idx) else None

    def extreme_gap(self, j: int, cond: str, price: float) -> float:
        sp = int(self.spread[j]) * 0.01
        ext = {
            "ask_le": self.lo[j] + sp,
            "ask_ge": self.h[j] + sp,
            "bid_le": self.lo[j],
            "bid_ge": self.h[j],
        }[cond]
        return abs(ext - price)

    # --- the bar of a difference ---
    def diff_bar(self, d: Diff, s: SimSetup | None, r: RunSetup | None) -> int | None:
        f = d.field
        cand: list[int] = []
        if f.startswith("fill"):
            name = f.split()[1]
            for x in (s.fills.get(name) if s else None, r.fills.get(name) if r else None):
                if x is not None:
                    cand.append(int(x[0]))
        elif f.startswith("be"):
            cand += [x for x in (s.be_j if s else None, r.be_j if r else None) if x is not None]
        elif f.startswith("exit"):
            cand += [x for x in (s.exit_j if s else None, r.exit_j if r else None) if x is not None]
        if not cand:
            for t in (s.end_time if s else None, r.end_time if r else None):
                if t is not None:
                    cand.append(self.bar_of_ts(t) - 1)
        if not cand:
            v = self.visit_of.get(d.key)
            if v is not None:
                cand.append(int(v.j0))
        return min(cand) if cand else None

    # --- the checks: each is tied to the field it can explain, and proves the property ---
    def sent_levels(self, key: Key) -> dict[str, float]:
        sp = sent_prices(self.plan_of(key), 0.01)
        out = {"P1": sp.p1, "P2": sp.p2, "SL": sp.sl, "TP": sp.tp}
        s = self.rec.sim_setups.get(key)
        if s is not None and s.be_sl is not None:
            out["BE"] = be_stop_sent(s.be_sl, self.visit_of[key].sgn, 0.01)
        return out

    def _bars_of(self, d: Diff) -> list[int]:
        """The bars the two sides name for the field (the bar of a fill, the break-even or the exit)."""
        s, r = self.rec.sim_setups.get(d.key), self.rec.run_setups.get(d.key)
        out: list[int] = []
        if d.field.startswith("fill"):
            name = d.field.split()[1]
            for x in (s.fills.get(name) if s else None, r.fills.get(name) if r else None):
                if x is not None:
                    out.append(int(x[0]))
        elif d.field.startswith("be"):
            out += [x for x in (s.be_j if s else None, r.be_j if r else None) if x is not None]
        elif d.field.startswith("exit"):
            out += [x for x in (s.exit_j if s else None, r.exit_j if r else None) if x is not None]
        return sorted(set(out))

    def _own_levels(self, key: Key, d: Diff) -> list[str]:
        """The level names the field is decided by."""
        f = d.field
        if f.startswith("fill"):
            return [f.split()[1]]
        if f.startswith("be"):
            return ["BE"]
        if f.startswith("exit"):
            s, r = self.rec.sim_setups.get(key), self.rec.run_setups.get(key)
            hows = {h for h in (s.how if s else None, r.how if r else None) if h}
            names = {"SL" if h in ("SL", "BE") else "TP" for h in hows}
            return sorted(names or {"SL", "TP"})
        return []

    @staticmethod
    def _hit(ext: float, cond: str, level: float) -> bool:
        return ext <= level + EPS if cond.endswith("_le") else ext >= level - EPS

    def _extreme(self, j: int, cond: str) -> float:
        sp = int(self.spread[j]) * 0.01
        return {
            "ask_le": float(self.lo[j]) + sp,
            "ask_ge": float(self.h[j]) + sp,
            "bid_le": float(self.lo[j]),
            "bid_ge": float(self.h[j]),
        }[cond]

    def p_tick(self, key: Key, d: Diff) -> Why | None:
        """Tick rounding: for a fill / exit / BE bar, the field's OWN price level, as the simulation has it and as
        it was sent, are within one tick of the bar's extreme AND the bar touches one but not the other. A price
        that differs is never rounding."""
        if d.field in ("exit price", "be stop", "be stop (logic)") or d.field.startswith("plan"):
            return None
        lv, sent = self.levels(key), self.sent_levels(key)
        for j in self._bars_of(d):
            for name in self._own_levels(key, d):
                if name not in lv or name not in sent:
                    continue
                cond, logic = lv[name]
                ext = self._extreme(j, cond)
                if abs(ext - logic) <= TICK + EPS and self._hit(ext, cond, logic) != self._hit(
                    ext, cond, sent[name]
                ):
                    return Why(
                        "tick rounding",
                        f"{self.when(j)}: {name} logic {logic:.4f}, sent {sent[name]}, extreme {ext:.2f}",
                    )
        return None

    def _last_quote(self, before_s: float) -> float | None:
        """The bid (dollars) of the last cycle at or before a time: what the pre-close judgment had."""
        i = int(np.searchsorted(self.rec.cycle_t, before_s, side="right")) - 1
        return None if i < 0 else float(self.rec.cycle_b[i]) / CENT

    def judgment_differs(self, key: Key, m: int) -> bool:
        """Whether the runner's pre-close judgment for bar ``m`` (the closed-hour cancel from the last recorded
        quote before the bar's open) differs from the judgment with the true close of bar ``m - 1``."""
        pl = self.plan_of(key)
        if m - pl.per_h < 0 or m < 1:
            return False
        bid = self._last_quote(self.open_ns[m] / 1e9 - 1e-6)
        if bid is None:
            return False
        ohm = float(self.o[m - pl.per_h])
        return closed_hour_cancel(pl, m, bid, ohm) != closed_hour_cancel(pl, m, float(self.c[m - 1]), ohm)

    def p_boundary(self, key: Key, d: Diff) -> Why | None:
        """The bar boundary: the pre-close judgment differs from the true-close one AND the field's own touch (or
        the runner's own fill / exit) falls in that boundary's window (the last ``preclose`` seconds before the
        open of bar ``m``, or its first ``cycle_seconds``)."""
        if not (d.field.startswith("fill") or d.field in ("exit bar", "exit how", "outcome")):
            return None
        lv = self.levels(key)
        times: list[tuple[int, float, str]] = []
        for j in self._bars_of(d):
            for name in self._own_levels(key, d):
                if name in lv:
                    t = self.touch_time(j, *lv[name])
                    if t is not None:
                        times.append((j, t, f"path touch of {name}"))
        for e in self.events_of(key):
            if e.kind in ("fill", "exit", "market"):
                times.append((self.bar_of_time(e.t), e.t, f"runner {e.kind} {e.comment}"))
        for j, t, what in times:
            for m in (j, j + 1):
                if not 0 < m < len(self.open_ns):
                    continue
                b = self.open_ns[m] / 1e9
                if b - self.W - 1e-6 <= t <= b + max(self.C, 1e-3) + 1e-6 and self.judgment_differs(key, m):
                    return Why(
                        "bar boundary",
                        f"{what} {t - b:+.1f} s from the open of {self.when(m)}; the pre-close judgment differs",
                    )
        return None

    def p_p2(self, key: Key, d: Diff) -> Why | None:
        """P2 re-placed after its P1 filled in the same bar: the recorded sequence shows P1 filled in the bar, P2
        blocked there, and the P2 touch after the P1 fill and before the P2 was placed again."""
        if not d.field.startswith("fill P2"):
            return None
        s = self.rec.sim_setups.get(key)
        if s is None or "P1" not in s.fills or "P2" not in s.fills or s.fills["P1"][0] != s.fills["P2"][0]:
            return None
        jj = s.fills["P1"][0]
        pl = self.plan_of(key)
        if jj - pl.per_h < 0 or not entry_blocked(pl, pl.p2, float(self.o[jj - pl.per_h])):
            return None
        ev = self.events_of(key)
        p1 = [e.t for e in ev if e.kind == "fill" and e.comment.split("-")[1:2] == ["P1"]]
        if not p1 or self.bar_of_time(p1[0]) != jj:
            return None
        cond, px = self.levels(key)["P2"]
        bids, times = self.path(jj)
        sp = int(self.spread[jj])
        lvl = round(px * CENT)
        hit = (bids + sp <= lvl) if cond == "ask_le" else (bids >= lvl)
        idx = np.flatnonzero(hit & (times >= p1[0] - 1e-9))
        if not len(idx):
            return None
        t2 = float(times[idx[0]])
        placed = [
            e.t
            for e in ev
            if e.kind == "place" and e.comment.split("-")[1:2] == ["P2"] and e.t >= p1[0] - 1e-9
        ]
        if placed and placed[0] <= t2:
            return None
        return Why(
            "P2 after P1",
            f"{self.when(jj)}: P1 filled at {p1[0]:.1f}, P2 blocked, touched at {t2:.1f}, re-placed {placed[:1]}",
        )

    def p_missed(self, key: Key, d: Diff) -> Why | None:
        if self.rec.mode != "poll" or d.field not in ("setup", "visit", "class"):
            return None
        if "setup" not in (d.sim, d.run) and d.sim != "present":
            return None
        v = self.visit_of.get(key)
        if v is None:
            return None
        t0 = v.time.value / 1e9
        band = round((v.line + v.z) * CENT) if v.sgn > 0 else round((v.line - v.z) * CENT)
        m = (self.rec.cycle_t >= t0) & (self.rec.cycle_t < t0 + 3600)
        b = self.rec.cycle_b[m]
        if bool(((b <= band) if v.sgn > 0 else (b >= band)).any()):
            return None
        cond, px = self.levels(key)["near"]
        for jj in range(v.j0, min(v.j0 + PER[self.plan.tf], len(self.open_ns))):
            t = self.touch_time(jj, cond, px)
            if t is not None and t0 <= t < t0 + 3600:
                return Why(
                    "missed touch", f"the path reached the band in {self.when(jj)}; no cycle's bid was in it"
                )
        return None

    def p_inbar(self, key: Key, d: Diff) -> Why | None:
        """In-bar order: in the field's bar the path touches the field's own level and another level of the setup
        in the opposite order to the simulation's fixed one (P1, P2, SL, TP, BE)."""
        if d.field.startswith("plan") or d.field in ("exit price", "be stop", "be stop (logic)"):
            return None
        own = self._own_levels(key, d)
        lv = self.levels(key)
        for j in self._bars_of(d):
            touched = {
                n: t
                for n, (cond, px) in lv.items()
                if n not in ("withdraw", "near") and (t := self.touch_time(j, cond, px)) is not None
            }
            order = [n for n in ("P1", "P2", "SL", "TP", "BE") if n in touched]
            for a in range(len(order)):
                for b in range(a + 1, len(order)):
                    u, w = order[a], order[b]
                    if touched[u] > touched[w] and (u in own or w in own):
                        return Why(
                            "in-bar order",
                            f"{self.when(j)}: the path touches {w} before {u}; the simulation tests {u} first",
                        )
        return None

    def p_two_candidates(self, key: Key, d: Diff) -> Why | None:
        """Both candidates of the hour touched in one bar and the path's first touch is the other one."""
        if d.field not in ("setup", "visit", "class"):
            return None
        v = self.visit_of.get(key)
        if v is None:
            return None
        for k2, o2 in self.visit_of.items():
            if k2[0] == key[0] and k2 != key and o2.touch_j == v.touch_j and v.touch_j < len(self.open_ns):
                t1 = self.touch_time(v.touch_j, *self.levels(key)["near"])
                t2 = self.touch_time(v.touch_j, *self.levels(k2)["near"])
                sim_first = (v.from_open, v.line) < (o2.from_open, o2.line)
                if t1 is not None and t2 is not None and (t1 < t2) != sim_first:
                    return Why(
                        "in-bar order", f"{self.when(v.touch_j)}: the path reaches the other candidate first"
                    )
        return None

    def facts(self, d: Diff) -> list[str]:
        """The path's facts around a difference: the bar(s), the setup's levels and when the path touches them, the
        runner's recorded decisions near the bar, and the simulation's own record of the setup."""
        out: list[str] = []
        key = d.key
        bars = sorted({b for b in [d.bar, *self._bars_of(d)] if b is not None})
        s, r = self.rec.sim_setups.get(key), self.rec.run_setups.get(key)
        for j in bars:
            if not 0 <= j < len(self.open_ns):
                continue
            o0, c0 = self.open_ns[j] / 1e9, self.close_ns[j] / 1e9
            out.append(
                f"{self.when(j)}: O {self.o[j]:.2f} H {self.h[j]:.2f} L {self.lo[j]:.2f} C {self.c[j]:.2f} "
                f"spread {int(self.spread[j])} pts, {len(self.path(j)[0])} ticks, last tick {self.W / 2:.1f} s before close"
            )
            if key in self.visit_of:
                for name, (cond, px) in self.levels(key).items():
                    t = self.touch_time(j, cond, px)
                    if t is not None:
                        out.append(
                            f"  path touches {name} ({cond} {px:.4f}) at {t - o0:+.1f} s from the open ({t - c0:+.1f} s from the close)"
                        )
            for e in self.events_of(key):
                if o0 - self.W <= e.t <= c0 + self.W:
                    out.append(
                        f"  runner/broker {e.kind} {e.comment} @ {e.price} at {e.t - o0:+.1f} s from the open {e.detail}"
                    )
        if s is not None:
            out.append(
                f"  simulation: outcome {s.outcome}, fills {s.fills}, be {s.be_j}/{s.be_sl}, exit {s.exit_j} {s.how} {s.exit_price}, ends {s.end_time}"
            )
        if r is not None:
            out.append(
                f"  runner: outcome {r.outcome}, fills {r.fills}, be {r.be_j}/{r.be_sent}, exit {r.exit_j} {r.how} {r.exit_price}/{r.exit_broker}, ends {r.end_time}"
            )
        return out

    def explain(self, key: Key, d: Diff) -> Why | None:
        for fn in (
            self.p_tick,
            self.p_boundary,
            self.p_p2,
            self.p_missed,
            self.p_inbar,
            self.p_two_candidates,
        ):
            w = fn(key, d)
            if w is not None:
                return w
        return None


# --- what an admitted difference may excuse ------------------------------------------------------------------------


def stage_of(field: str) -> int:
    if field.startswith("fill P1"):
        return 0
    if field.startswith("fill P2"):
        return 1
    if field.startswith("be"):
        return 2
    if field.startswith("exit"):
        return 3
    if field == "outcome":
        return 4
    if field == "reservation end":
        return 5
    return -1


def dependent(first: Diff, other: Diff, fields: set[str]) -> bool:
    """Whether ``other`` can be a consequence of the admitted ``first`` on the same setup: a LATER stage of the
    setup's life. A price is never a consequence on its own: an exit price follows only a different exit (bar or
    how), a break-even stop only a different break-even bar or a different fill; plan prices and fill prices are
    independent of everything."""
    a, b = stage_of(first.field), stage_of(other.field)
    if a < 0 or b <= a or other.field.startswith("plan") or other.field == "duplicate record":
        return False
    if other.field.startswith("fill") and "price" in other.field:
        return False
    if other.field == "exit price":
        return bool(fields & {"exit bar", "exit how"})
    if other.field.startswith("be stop"):
        return "be bar" in fields or any(f.startswith("fill") and "price" not in f for f in fields)
    return True


def explain_all(plan: SpanPlan, rec: Record, full: Bars) -> tuple[list[Diff], Explainer]:
    """Every difference with its bar and cause (empty cause = a fault). A cause is admitted only when its check
    proves it for the field. The cascade excuses only (a) the same setup's dependent fields and (b) later
    busy / not-busy visits inside the SIMULATION's reservation of an admitted differing setup."""
    ex = Explainer(plan, rec, full)
    diffs = raw_diffs(rec)
    by_key: dict[Key, list[Diff]] = {}
    for d in diffs:
        by_key.setdefault(d.key, []).append(d)
    windows: list[
        tuple[pd.Timestamp, pd.Timestamp]
    ] = []  # (the differing setup's hour, the SIMULATION's end)
    for key in sorted(by_key):
        ds = by_key[key]
        s, r = rec.sim_setups.get(key), rec.run_setups.get(key)
        for d in ds:
            d.bar = ex.diff_bar(d, s, r)
        ds.sort(key=lambda d: (d.bar is None, d.bar if d.bar is not None else 0, stage_of(d.field)))
        if key not in ex.visit_of:
            continue
        fields = {d.field for d in ds}
        first = ds[0]
        why = ex.explain(key, first)
        if why is None and first.field in ("class", "visit", "setup"):
            sim_cls, run_cls = rec.sim_classes.get(key), (rec.run_classes.get(key) or (None,))[0]
            if "busy" in (sim_cls, run_cls) and any(h < key[0] <= e for h, e in windows):
                why = Why(
                    "cascade", "busy / not busy inside the simulation's reservation of an admitted difference"
                )
        if why is None:
            continue
        first.cause, first.why = why.cause, why.text
        for d in ds[1:]:
            if why.cause == "cascade":
                if d.field in ("setup", "class", "visit"):
                    d.cause, d.why = "cascade", why.text
            elif dependent(first, d, fields):
                d.cause, d.why = f"follows {why.cause}", why.text
        if why.cause != "cascade":
            end = s.end_time if s is not None else key[0] + pd.Timedelta(hours=1)
            windows.append((key[0], end))
    return diffs, ex


def table(plan: SpanPlan, rec: Record, diffs: list[Diff]) -> str:
    keys = set(rec.sim_classes) | set(rec.run_classes)
    both = [k for k in keys if k in rec.sim_classes and k in rec.run_classes]
    same = sum(1 for k in both if rec.sim_classes[k] == rec.run_classes[k][0])
    missing = len(keys) - len(both)
    diff_keys = {d.key for d in diffs}
    setup_keys = set(rec.sim_setups) | set(rec.run_setups)
    matched_setups = sum(1 for k in setup_keys if k not in diff_keys)
    cause_of: dict[Key, str] = {}
    for d in diffs:
        cause_of.setdefault(d.key, d.cause or "no suggestion")
    by_cause = Counter(cause_of.values())
    failures = gate_failures(rec)
    return "\n".join(
        [
            f"{plan.name} / {rec.mode}: replay {plan.start:%Y-%m-%d %H:%M} .. {rec.end:%Y-%m-%d %H:%M}, compared "
            f"to {plan.cmp_end:%Y-%m-%d}; {rec.cycles} cycles ({rec.skipped} gated out), {rec.seconds:.0f} s",
            f"  visits : simulation {len(rec.sim_classes)}, runner {len(rec.run_classes)}; same classification "
            f"{same}, class differs {len(both) - same}, present on one side only {missing}",
            f"  setups : simulation {len(rec.sim_setups)}, runner {len(rec.run_setups)}; matched in every field "
            f"{matched_setups}, with a difference {len(setup_keys) - matched_setups}",
            "  suggested causes (advisory, one per setup / visit, its first): "
            + (", ".join(f"{c} {n}" for c, n in sorted(by_cause.items())) or "none"),
            f"  runner log lines WARNING or above: {len(rec.log_lines)}",
            f"  GATE: {'PASS' if not failures else f'FAIL ({len(failures)} reasons)'}",
        ]
    )


def detail(diffs: list[Diff], ex: Explainer) -> str:
    out: list[str] = []
    for d in diffs:
        out.append("    " + d.line(ex.ex_open))
        out += ["        " + f for f in ex.facts(d)]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    from app.zone.core import load_bars
    from tests.zone_replay_compare import load

    ap = argparse.ArgumentParser(description="Explain and tabulate saved replay records")
    ap.add_argument("records", nargs="+", type=Path)
    args = ap.parse_args(argv)
    full = load_bars("XAUUSD")
    failed = False
    for path in args.records:
        plan, rec = load(path)
        diffs, ex = explain_all(plan, rec, full)
        print(table(plan, rec, diffs))
        if diffs:
            print(detail(diffs, ex))
        for lvl, msg in rec.log_lines[:60]:
            print(f"    runner {lvl}: {msg[:220]}")
        print()
        failed = failed or bool(gate_failures(rec))
    return 1 if failed else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
