"""The broker side of the replay gate (eye/ZONE_LIVE.md L11.2, "the gate is strict").

``gate_failures`` first checks the runner's stored summaries against the simulation. This module checks the replay
double's OWN ledger - the requests it received, the orders' lives, the deals, positions and orders it holds -
independently of what the runner wrote in its rows, and in BOTH directions: everything the broker did must be
something the simulation did, and everything the simulation did must have its broker deal / event. The simulation
side here runs to the replay's END (``rec.sim_all_setups``), the same window as the broker's ledger. Every finding is
a failure of the gate; nothing is excused (a bar-boundary difference is listed, not passed)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import numpy as np

from app.broker import mt5_constants as c
from app.zone.live import be_stop_sent

if TYPE_CHECKING:
    from tests.zone_replay_compare import Record

TICK = 0.01
CENT = 100
EPS = 1e-6
LOT = 0.01
MAGIC = 7_310_100
SYMBOL = "XAUUSD"
COMMENT = re.compile(r"^Z(\d+)-(P1|P2)-(\d+)$")
ENTRY_ACTIONS = (c.TRADE_ACTION_PENDING, c.TRADE_ACTION_DEAL)
OK_CODES = (10008, 10009, 10010, 10025)


def _near(a: float, b: float, tol: float = TICK) -> bool:
    return abs(a - b) <= tol + EPS


def bar_of(rec: Record, t_s: float) -> int | None:
    """The exec row of the bar a time falls in (a bar's close belongs to the next bar, as for the runner)."""
    if rec.bar_close_ns is None:
        return None
    return rec.bar0 + int(np.searchsorted(rec.bar_close_ns, round(t_s * 1e9), side="right"))


def parse(comment: str) -> tuple[int, str, int] | None:
    m = COMMENT.match(comment)
    return None if m is None else (int(m.group(1)), m.group(2), int(m.group(3)))


class Ledger:
    """The broker's record, indexed once."""

    def __init__(self, rec: Record) -> None:
        self.rec = rec
        self.rows = rec.setup_rows
        self.sim = rec.sim_all_setups
        self.requests = sorted(rec.requests, key=lambda x: x[0])
        self.deals = sorted((d for d in rec.deals if d["magic"] == MAGIC), key=lambda d: d["t"])
        self.events = sorted(rec.events, key=lambda e: e.t)
        self.order_comment: dict[int, str] = {}  # order ticket -> comment (from the place requests' results)
        self.place_req: dict[str, dict[str, Any]] = {}
        for _t, req, _rc in self.requests:
            if req.get("action") == c.TRADE_ACTION_PENDING and req.get("_order"):
                self.order_comment[int(req["_order"])] = str(req.get("comment", ""))
            if req.get("action") in ENTRY_ACTIONS and not req.get("position"):
                self.place_req.setdefault(str(req.get("comment", "")), req)
        self.pos_in: dict[int, dict[str, Any]] = {}
        self.pos_out: dict[int, list[dict[str, Any]]] = {}
        for d in self.deals:
            if d["entry"] == c.DEAL_ENTRY_IN:
                self.pos_in.setdefault(d["position"], d)
            elif d["entry"] == c.DEAL_ENTRY_OUT:
                self.pos_out.setdefault(d["position"], []).append(d)
        self.end_bar = rec.bar0 + (0 if rec.bar_close_ns is None else len(rec.bar_close_ns))
        self.end_s = rec.end.value / 1e9
        self.sids_of_key: dict[Any, list[int]] = {}
        self.pos_buy = {p: d.get("type") == c.DEAL_TYPE_BUY for p, d in self.pos_in.items()}
        for sid, row in self.rows.items():
            self.sids_of_key.setdefault(row["key"], []).append(sid)

    def pin_buy(self, pos: int) -> bool:
        return self.pos_buy.get(pos, True)

    def sim_of(self, sid: int) -> Any:
        row = self.rows.get(sid)
        return None if row is None else self.sim.get(row["key"])


def broker_failures(rec: Record) -> list[str]:
    led = Ledger(rec)
    out: list[str] = []
    _entries(led, out)
    _fills(led, out)
    _exits(led, out)
    _reasons(led, out)
    _stops(led, out)
    _closes(led, out)
    _lifetimes(led, out)
    _end(led, out)
    return out


# --- 5, entries: every request that can open exposure --------------------------------------------------------------


def _entries(led: Ledger, out: list[str]) -> None:
    seen: dict[str, int] = {}
    for t, req, rc in led.requests:
        if req.get("action") not in ENTRY_ACTIONS or req.get("position"):
            continue
        cm = str(req.get("comment", ""))
        where = f"request at {t:.1f} ({cm!r}, retcode {rc})"
        key = parse(cm)
        if key is None:
            out.append(f"{where}: the comment is not Z<id>-<P1|P2>-<n>")
            continue
        seen[cm] = seen.get(cm, 0) + 1
        if seen[cm] == 2:
            out.append(f"{where}: the comment was sent twice")
        sl, tp = float(req.get("sl", 0.0)), float(req.get("tp", 0.0))
        if sl <= 0:
            out.append(f"{where}: an entry without a stop-loss")
        if tp <= 0:
            out.append(f"{where}: an entry without a take-profit")
        if abs(float(req.get("volume", 0.0)) - LOT) > EPS:
            out.append(f"{where}: volume {req.get('volume')} is not {LOT}")
        if int(req.get("magic", -1)) != MAGIC:
            out.append(f"{where}: magic {req.get('magic')} is not the zone magic")
        if req.get("symbol") != SYMBOL:
            out.append(f"{where}: symbol {req.get('symbol')!r} is not {SYMBOL}")
        row = led.rows.get(key[0])
        if row is None:
            out.append(f"{where}: no setup row {key[0]}")
            continue
        buy = row["side"] == "BUY"
        px = float(req.get("price", 0.0))
        sent = row[key[1].lower() + "_sent"]
        _protected(buy, px, sl, tp, where, out)
        if sl > 0 and not _near(sl, row["sl_sent"]):
            out.append(f"{where}: SL {sl} is not the setup's {row['sl_sent']}")
        if not _near(tp, row["tp_sent"]):
            out.append(f"{where}: TP {tp} is not the setup's {row['tp_sent']}")
        typ = req.get("type")
        if req["action"] == c.TRADE_ACTION_PENDING:
            if req.get("type_time") != c.ORDER_TIME_SPECIFIED:
                out.append(f"{where}: a limit without a specified expiry (type_time {req.get('type_time')})")
            else:
                want_exp = (t // 3600) * 3600 + 3660  # the close of the current H1 bar + 1 minute (L3)
                if abs(float(req.get("_exp_s", 0.0)) - want_exp) > 1.0:
                    out.append(
                        f"{where}: expiry {req.get('_exp_s')} is not the H1 close + 1 minute ({want_exp})"
                    )
            want = c.ORDER_TYPE_BUY_LIMIT if buy else c.ORDER_TYPE_SELL_LIMIT
            if typ != want:
                out.append(f"{where}: order type {typ}, a {row['side']} limit is {want}")
            if not _near(px, sent):
                out.append(f"{where}: price {px} is not the setup's {sent}")
        else:  # a market entry: only the already marketable case, with its price check
            want = c.ORDER_TYPE_BUY if buy else c.ORDER_TYPE_SELL
            if typ != want:
                out.append(f"{where}: market order type {typ}, a {row['side']} entry is {want}")
            if (buy and px > sent + TICK + EPS) or (not buy and px < sent - TICK - EPS):
                out.append(f"{where}: a market entry at {px} is not marketable for the setup's {sent}")


def _protected(buy: bool, px: float, sl: float, tp: float, where: str, out: list[str]) -> None:
    """SL and TP both set and on the correct side of the price (BUY: TP > price > SL; SELL: TP < price < SL)."""
    if sl <= 0 or tp <= 0:
        return  # reported as missing by the caller
    ok = (tp > px > sl) if buy else (tp < px < sl)
    if not ok:
        out.append(f"{where}: SL {sl} / TP {tp} not on the correct sides of the price {px}")


# --- 2, fills: both ways -----------------------------------------------------------------------------------------------


def _fills(led: Ledger, out: list[str]) -> None:
    rec = led.rec
    count: dict[tuple[int, str], int] = {}
    open_sids: dict[int, int] = {}
    for d in led.deals:
        if d["entry"] != c.DEAL_ENTRY_IN:
            if d["entry"] == c.DEAL_ENTRY_OUT:
                open_sids.pop(d["position"], None)
            continue
        key = parse(d["comment"])
        where = f"broker fill at {d['t']:.1f} @ {d['price']} ({d['comment']!r})"
        if key is None:
            out.append(f"{where}: the comment maps to no setup")
            continue
        sid, name, _n = key
        if abs(d["volume"] - LOT) > EPS:
            out.append(f"{where}: volume {d['volume']} is not {LOT}")
        count[(sid, name)] = count.get((sid, name), 0) + 1
        if count[(sid, name)] == 2:
            out.append(f"setup {sid}: {name} filled twice at the broker")
        open_sids[d["position"]] = sid
        if len(set(open_sids.values())) > 1:
            out.append(f"{where}: entries of two setups are open at once {sorted(set(open_sids.values()))}")
        sim = led.sim_of(sid)
        if sim is None or name not in sim.fills:
            out.append(f"{where}: the simulation has no such fill")
            continue
        j, price = sim.fills[name]
        if bar_of(rec, d["t"]) != j:
            out.append(f"{where}: bar {bar_of(rec, d['t'])}, the simulation's {j}")
        if not _near(d["price"], price):
            out.append(f"{where}: price differs from the simulation's {price}")
    for key, sim in led.sim.items():  # every simulated fill has its broker deal
        for name, (j, price) in sim.fills.items():
            if j >= led.end_bar:
                continue  # after the replay's end: not demanded
            hits = [
                d
                for sid in led.sids_of_key.get(key, [])
                for d in led.deals
                if d["entry"] == c.DEAL_ENTRY_IN
                and parse(d["comment"]) is not None
                and parse(d["comment"])[:2] == (sid, name)  # type: ignore[index]
            ]
            if not hits:
                out.append(
                    f"simulated fill {name} of {key[0]:%m-%d %H} {key[1]} {key[2]} (bar {j}, {price:.2f}): no broker deal"
                )


# --- 2, 6: exits, volumes ------------------------------------------------------------------------------------------


def _exits(led: Ledger, out: list[str]) -> None:
    rec = led.rec
    for pos, d_in in led.pos_in.items():
        key = parse(d_in["comment"])
        sid = None if key is None else key[0]
        sim = None if sid is None else led.sim_of(sid)
        outs = led.pos_out.get(pos, [])
        total = sum(o["volume"] for o in outs)
        where = f"position {pos} ({d_in['comment']!r})"
        if total > d_in["volume"] + EPS:
            out.append(f"{where}: exit deals sum to {total}, the position is {d_in['volume']}")
        if len(outs) > 1:
            out.append(f"{where}: {len(outs)} exit deals")
        for o in outs:
            if sim is None or sim.exit_j is None or sim.exit_price is None:
                out.append(f"{where}: exit at {o['t']:.1f} but the simulation has none")
                continue
            if bar_of(rec, o["t"]) != sim.exit_j:
                out.append(f"{where}: exit in bar {bar_of(rec, o['t'])}, the simulation's {sim.exit_j}")
            if not _near(o["price"], sim.exit_price):
                out.append(f"{where}: exit price {o['price']} differs from the simulation's {sim.exit_price}")
        closed_by_sim = sim is not None and sim.exit_j is not None and sim.exit_j < _end_bar(rec)
        if closed_by_sim and abs(total - d_in["volume"]) > EPS:
            out.append(f"{where}: exit deals sum to {total}, the simulation closed it ({d_in['volume']})")


def _reasons(led: Ledger, out: list[str]) -> None:
    """Every deal of the ledger, each judged: an exit needs its entry (a position nobody opened is a
    failure before any reason); every deal's reason is the kind of the event that made it: an entry is
    the runner's own order
    (EXPERT); an exit is the broker's SL (the original SL, or the BE stop) or TP as the simulation's exit
    kind says, or the runner's own close (EXPERT) of a position it sent a close request for - never a hand
    (CLIENT, MOBILE, WEB) or a stop-out (L8 cause 7)."""
    closed = {
        int(req["position"])
        for _t, req, _rc in led.requests
        if req.get("action") == c.TRADE_ACTION_DEAL and req.get("position")
    }
    for d in led.deals:
        if d["entry"] != c.DEAL_ENTRY_IN and d["position"] not in led.pos_in:
            out.append(
                f"exit deal at {d['t']:.1f} of position {d['position']} (reason {d.get('reason')}): "
                "no entry deal opened that position"
            )
    for pos, d_in in led.pos_in.items():
        where = f"position {pos} ({d_in['comment']!r})"
        if d_in.get("reason") != c.DEAL_REASON_EXPERT:
            out.append(f"{where}: entry deal reason {d_in.get('reason')}, not the runner's own (EXPERT)")
        key = parse(d_in["comment"])
        sim = None if key is None else led.sim_of(key[0])
        if sim is None:
            continue  # an exit with no simulated setup is a failure of `_exits` already
        want = {"SL": {c.DEAL_REASON_SL}, "BE": {c.DEAL_REASON_SL}, "TP": {c.DEAL_REASON_TP}}.get(
            str(sim.how), set()
        )
        if pos in closed:
            want = want | {c.DEAL_REASON_EXPERT}  # the runner's own close (L5's BE fallback)
        for o in led.pos_out.get(pos, []):
            if o.get("reason") not in want:
                out.append(
                    f"{where}: exit deal reason {o.get('reason')} is not the simulation's exit {sim.how}"
                    + (" or the runner's own close" if pos in closed else "")
                )


def _end_bar(rec: Record) -> int:
    return rec.bar0 + (0 if rec.bar_close_ns is None else len(rec.bar_close_ns))


# --- 4, 2: stops and orders modified ---------------------------------------------------------------------------------


def _stops(led: Ledger, out: list[str]) -> None:
    rec = led.rec
    entry = {cm: float(r.get("sl", 0.0)) for cm, r in led.place_req.items()}
    # every position stop change (the events), toward profit, to the simulation's BE stop, in the bar after its bar
    current: dict[str, float] = {}
    moved: dict[str, float] = {}  # comment -> time of its (first) stop move
    for e in led.events:
        if e.kind == "fill" or e.kind == "market":
            current.setdefault(e.comment, entry.get(e.comment, 0.0))
        if e.kind != "sltp":
            continue
        key = parse(e.comment)
        where = f"stop change of {e.comment} at {e.t:.1f} to {e.price}"
        if key is None or key[0] not in led.rows:
            out.append(f"{where}: maps to no setup")
            continue
        buy = led.rows[key[0]]["side"] == "BUY"
        old = current.get(e.comment, entry.get(e.comment))
        if old is not None and ((buy and not e.price > old) or (not buy and not e.price < old)):
            out.append(f"{where}: from {old}, not toward profit")
        sim = led.sim_of(key[0])
        if sim is None or sim.be_j is None or sim.be_sl is None:
            out.append(f"{where}: the simulation has no break-even")
        else:
            if not _near(e.price, sim.be_sl):
                out.append(f"{where}: the simulation's break-even stop is {sim.be_sl}")
            if bar_of(rec, e.t) != sim.be_j + 1:
                out.append(f"{where}: bar {bar_of(rec, e.t)}, the simulation's break-even bar is {sim.be_j}")
        current[e.comment] = e.price
        moved.setdefault(e.comment, e.t)
    # ... and the other way: EVERY simulated break-even (up to the replay's end) has its stop move on every position,
    # before any later exit, whatever bar that exit is in
    for key, sim in led.sim.items():
        if sim.be_j is None or sim.be_j >= led.end_bar:
            continue
        for name in sim.fills:
            cms = {
                d["comment"]
                for sid in led.sids_of_key.get(key, [])
                for d in led.pos_in.values()
                if (parse(d["comment"]) or (0, ""))[:2] == (sid, name)
            }
            if not cms:
                continue  # the missing fill is reported by _fills
            what = f"simulated break-even of {key[0]:%m-%d %H} {key[1]} {key[2]} ({name}, bar {sim.be_j})"
            for cm in cms:
                if cm not in moved:
                    if _be_fallback_close(led, cm, sim):
                        continue
                    out.append(f"{what}: no stop move on {cm}")
                    continue
                pos = next(p for p, d in led.pos_in.items() if d["comment"] == cm)
                exits = [o["t"] for o in led.pos_out.get(pos, [])]
                if exits and min(exits) < moved[cm]:
                    out.append(
                        f"{what}: the position {cm} exited at {min(exits):.1f}, before its stop move {moved[cm]:.1f}"
                    )
    # requests: a modify keeps the order's price / SL / TP and moves the expiry an hour on from 10 minutes before
    # it; an SLTP keeps the TP and sets the SL to the BE stop
    grace = max(rec.cycle_seconds if rec.mode == "poll" else 0.0, 1e-3) + 1e-6
    cur_exp: dict[int, float] = {}
    for _t, req, _rc in led.requests:
        if req.get("action") == c.TRADE_ACTION_PENDING and req.get("_order"):
            cur_exp[int(req["_order"])] = float(req.get("_exp_s", 0.0))
    ok_sltp: dict[int, int] = {}
    for t, req, rc in led.requests:
        action = req.get("action")
        if action == c.TRADE_ACTION_MODIFY:
            ticket = int(req.get("order", 0))
            cm = led.order_comment.get(ticket)
            base = None if cm is None else led.place_req.get(cm)
            where = f"modify of order {ticket} at {t:.1f}"
            if base is None:
                out.append(f"{where}: an order the ledger does not know")
                continue
            m_sl, m_tp = float(req.get("sl", 0.0)), float(req.get("tp", 0.0))
            if m_sl <= 0 or m_tp <= 0:
                out.append(f"{where}: the modify leaves SL {m_sl} / TP {m_tp} unset")
            else:
                mrow = led.rows.get((parse(cm) or (0,))[0])
                if mrow is not None:
                    _protected(mrow["side"] == "BUY", float(req.get("price", 0.0)), m_sl, m_tp, where, out)
            for field_ in ("price", "sl", "tp"):
                if not _near(float(req.get(field_, 0.0)), float(base.get(field_, 0.0)), EPS):
                    out.append(f"{where}: {field_} {req.get(field_)} is not the order's {base.get(field_)}")
            new_exp = float(req.get("_exp_s", 0.0))
            old_exp = cur_exp.get(ticket, 0.0)
            if req.get("type_time") != c.ORDER_TIME_SPECIFIED or not new_exp:
                out.append(f"{where}: the modify removes the expiry")
            else:
                if abs(new_exp - (old_exp + 3600)) > 1.0:
                    out.append(f"{where}: expiry {new_exp} is not the old {old_exp} + 1 hour")
                if t < old_exp - 600 - grace:
                    out.append(
                        f"{where}: extended {old_exp - t:.0f} s before the expiry, earlier than 10 minutes"
                    )
                if rc in OK_CODES[:3]:
                    cur_exp[ticket] = new_exp
        elif action == c.TRADE_ACTION_SLTP:
            pos = int(req.get("position", 0))
            d_in = led.pos_in.get(pos)
            where = f"stops request on position {pos} at {t:.1f}"
            if d_in is None:
                out.append(f"{where}: a position nobody opened")
                continue
            key = parse(d_in["comment"])
            base = led.place_req.get(d_in["comment"])
            sim = None if key is None else led.sim_of(key[0])
            r_sl, r_tp = float(req.get("sl", 0.0)), float(req.get("tp", 0.0))
            if r_sl <= 0 or r_tp <= 0:
                out.append(f"{where}: the stops request leaves SL {r_sl} / TP {r_tp} unset")
            elif not (r_tp > r_sl if led.pin_buy(pos) else r_tp < r_sl):
                out.append(f"{where}: TP {r_tp} is on the wrong side of SL {r_sl}")
            if base is not None and not _near(float(req.get("tp", 0.0)), float(base.get("tp", 0.0)), EPS):
                out.append(f"{where}: TP {req.get('tp')} is not the position's {base.get('tp')}")
            if sim is None or sim.be_sl is None or not _near(float(req.get("sl", 0.0)), sim.be_sl):
                out.append(f"{where}: SL {req.get('sl')} is not the simulation's break-even stop")
            if rc in OK_CODES[:3]:
                ok_sltp[pos] = ok_sltp.get(pos, 0) + 1
                if ok_sltp[pos] == 2:
                    out.append(f"{where}: the stops of the position were set twice")


# --- 6: closes by request --------------------------------------------------------------------------------------------


def _closes(led: Ledger, out: list[str]) -> None:
    per: dict[int, int] = {}
    for t, req, _rc in led.requests:
        if req.get("action") != c.TRADE_ACTION_DEAL or not req.get("position"):
            continue
        pos = int(req["position"])
        per[pos] = per.get(pos, 0) + 1
        d_in = led.pos_in.get(pos)
        key = None if d_in is None else parse(d_in["comment"])
        sim = None if key is None else led.sim_of(key[0])
        where = f"close request on position {pos} at {t:.1f}"
        # the simulation closes only by SL / TP / its BE stop: a close at market is justified only as the runner's
        # way of reaching the BE stop (exit BE), once per position
        if sim is None or sim.how != "BE":
            out.append(f"{where}: the simulation does not close this position at market")
        elif not _fallback_ok(led, pos, sim, t):
            # every market close must be justified by a spec rule; the only one a clean run can have is L5's BE
            # fallback (a disallowed fill, a both-filled later candidate, a missed-touch fault and an owed close are
            # faults the runner logs at ERROR, which fail the gate too)
            out.append(
                f"{where}: not L5's BE fallback (the first cycle after the BE bar, the quote beyond the stop)"
            )
        if per[pos] == 2:
            out.append(f"{where}: a second close of the same position")
        if d_in is None:
            out.append(f"{where}: a position nobody opened")
            continue
        if abs(float(req.get("volume", 0.0)) - d_in["volume"]) > EPS:
            out.append(f"{where}: volume {req.get('volume')} is not the position's {d_in['volume']}")
        want = c.ORDER_TYPE_SELL if d_in["type"] == c.DEAL_TYPE_BUY else c.ORDER_TYPE_BUY
        if req.get("type") != want:
            out.append(f"{where}: type {req.get('type')} is not the opposite side ({want})")
        if req.get("symbol") != SYMBOL:
            out.append(f"{where}: symbol {req.get('symbol')!r} is not {SYMBOL}")
        if int(req.get("magic", -1)) != MAGIC:
            out.append(f"{where}: magic {req.get('magic')} is not the zone magic")


# --- 3: orders' lives -------------------------------------------------------------------------------------------------


def _lifetimes(led: Ledger, out: list[str]) -> None:
    rec = led.rec
    grace = max(rec.cycle_seconds if rec.mode == "poll" else 0.0, 1e-3) + 1e-6
    alive: dict[tuple[int, str], str] = {}
    born: dict[str, float] = {}
    died: dict[str, float] = {}
    for e in led.events:
        key = parse(e.comment)
        if key is None:
            continue
        slot = (key[0], key[1])
        if e.kind == "place":
            if slot in alive:
                out.append(
                    f"order {e.comment} placed at {e.t:.1f} while {alive[slot]} of the same setup and name is alive"
                )
            alive[slot] = e.comment
            born[e.comment] = e.t
        elif e.kind in ("fill", "cancel", "expire"):
            if alive.get(slot) == e.comment:
                del alive[slot]
            died[e.comment] = e.t
    at_end = {o[0] for o in rec.end_orders}
    for cm, t0 in born.items():
        key = parse(cm)
        row = led.rows.get(key[0]) if key else None
        if row is None or key is None:
            continue
        if cm in died:
            t1 = died[cm]
        elif cm in at_end:
            t1 = led.end_s  # still resting at the end: alive until then, no longer
        else:
            continue
        sim = led.sim.get(row["key"])
        # no order rests after its setup's end (L5): the close of the bar that ended it, the bar boundary; an expiry
        # (rule 1) removes at the expiry bar's OPEN
        if row["chosen"] and sim is not None:
            limit, what = sim.end_time.value / 1e9, f"its setup's simulated end {sim.end_time:%m-%d %H:%M}"
            k_end = _bar_closing_at(rec, limit)
            if (
                sim.outcome == "no fill"
                and k_end is not None
                and rec.bar_open_ns is not None  # required evidence (validate_record)
                and rec.order_life_h is not None
                and k_end + rec.bar0 >= row["j_hour"] + rec.order_life_h * rec.per_h
            ):
                limit, what = rec.bar_open_ns[k_end] / 1e9, f"the open of its expiry bar {k_end + rec.bar0}"
            if t0 > limit + grace:
                out.append(f"order {cm} placed at {t0:.1f}, after {what}")
            elif t1 > limit + grace:
                out.append(f"order {cm} alive until {t1:.1f}, after {what}")
    _p2_needs_p1(led, out)


def _bar_closing_at(rec: Record, t: float) -> int | None:
    if rec.bar_close_ns is None:
        return None
    i = int(np.searchsorted(rec.bar_close_ns, round(t * 1e9), side="left"))
    if i < len(rec.bar_close_ns) and abs(rec.bar_close_ns[i] / 1e9 - t) < 1e-3:
        return i
    return None


def _p2_needs_p1(led: Ledger, out: list[str]) -> None:
    """P2 may be alive only while P1 of its setup is alive (placed and not yet ended) or filled: the whole life of
    every P2 order lies inside the merged lives of the setup's P1 orders (the events ledger)."""
    tol = 1e-3
    inf = float("inf")
    start: dict[str, float] = {}
    end: dict[str, float] = {}  # the last event that ended the order (a fill, cancel, expiry)
    filled: set[str] = set()
    for e in led.events:
        if e.kind in ("place", "market"):
            start.setdefault(e.comment, e.t)
        if e.kind in ("fill", "market"):
            filled.add(e.comment)
        if e.kind in ("fill", "cancel", "expire"):
            end[e.comment] = e.t
    at_end = {o[0] for o in led.rec.end_orders}
    p1: dict[int, list[tuple[float, float]]] = {}
    for cm, t0 in start.items():
        key = parse(cm)
        if key is not None and key[1] == "P1":
            t1 = inf if cm in filled or cm in at_end else end.get(cm, inf)
            p1.setdefault(key[0], []).append((t0, t1))
    for cm, t0 in start.items():
        key = parse(cm)
        if key is None or key[1] != "P2":
            continue
        t1 = end.get(cm, led.end_s if cm in at_end else None)
        if t1 is None:
            continue
        merged: list[list[float]] = []
        for a, b in sorted(p1.get(key[0], [])):
            if merged and a <= merged[-1][1] + tol:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        if not any(a - tol <= t0 and t1 <= b + tol for a, b in merged):
            out.append(
                f"P2 order {cm} alive {t0:.1f} .. {t1:.1f} while no P1 of the setup is alive or filled"
            )


def _first_cycle_at_or_after(rec: Record, t: float) -> int | None:
    i = int(np.searchsorted(rec.cycle_t, t - 1e-6, side="left"))
    return None if i >= len(rec.cycle_t) else i


def _fallback_ok(led: Ledger, pos: int, sim: Any, t_req: float) -> bool:
    """L5's BE fallback: a close of the position at market AT the first cycle after the BE bar's close, when the
    recorded quote was then already beyond the BE stop AS SENT (rounded toward the TP side): BUY bid <= stop; SELL ask
    >= stop (the cycle's recorded ask)."""
    rec = led.rec
    if sim is None or sim.be_j is None or sim.be_sl is None or rec.bar_close_ns is None:
        return False
    k = sim.be_j - rec.bar0
    if not 0 <= k < len(rec.bar_close_ns):
        return False
    i = _first_cycle_at_or_after(rec, rec.bar_close_ns[k] / 1e9)
    if i is None or abs(float(rec.cycle_t[i]) - t_req) > 1e-3:
        return False
    buy = led.pin_buy(pos)
    stop = be_stop_sent(sim.be_sl, 1 if buy else -1, TICK)
    bid = float(rec.cycle_b[i]) / CENT
    ask = float(rec.cycle_a[i]) / CENT
    return bid <= stop + EPS if buy else ask >= stop - EPS


def _be_fallback_close(led: Ledger, cm: str, sim: Any) -> bool:
    pos = next((p for p, d in led.pos_in.items() if d["comment"] == cm), None)
    if pos is None:
        return False
    return any(
        _fallback_ok(led, pos, sim, t)
        for t, req, _rc in led.requests
        if req.get("action") == c.TRADE_ACTION_DEAL and int(req.get("position", 0) or 0) == pos
    )


# --- the end of the span ---------------------------------------------------------------------------------------------


def _end(led: Ledger, out: list[str]) -> None:
    rec = led.rec
    for cm, price in rec.end_orders:
        key = parse(cm)
        row = None if key is None else led.rows.get(key[0])
        if row is None:
            out.append(f"resting order {cm!r} @ {price}: maps to no setup")
            continue
        sim = led.sim.get(row["key"])
        if row["state"] in ("ended", "dropped") or (sim is not None and sim.end_time <= rec.end):
            out.append(
                f"resting order {cm!r} @ {price} at the end of the span: its setup {key[0] if key else '?'} has ended"
            )
    held: dict[Any, int] = {}
    for cm, _price in rec.end_positions:
        key = parse(cm)
        row = None if key is None else led.rows.get(key[0])
        if row is None:
            out.append(f"open position {cm!r} at the end of the span maps to no setup")
        else:
            held[row["key"]] = held.get(row["key"], 0) + 1
    end_bar = _end_bar(rec)
    # the simulation's state AT THE END: positions filled before it and not yet exited
    expect = {}
    for k, s in led.sim.items():
        n = sum(1 for j, _p in s.fills.values() if j < end_bar)
        if n and (s.exit_j is None or s.exit_j >= end_bar):
            expect[k] = n
    if held != expect:
        out.append(f"open positions at the end {held} differ from the simulation's {expect}")
