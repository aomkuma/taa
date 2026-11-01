"""The run-zone setup's parameters in a database (eye/ZONE_RULES.md, rule 1).

SQLite, ``data/bot_config.db`` by default (the *file* is shared with the Fibonacci bot; the table is not). A
*set* is a full set of every ``ZoneParams`` field, named by market and set name. The table
``zone_config_change`` is append-only: one row per value written; a set's current values are, per name,
the row with the highest ``id``, and its version is the highest ``id`` among its rows.

    python eye/zone_config.py seed --market XAUUSD --set default --by me
    python eye/zone_config.py set --market XAUUSD --set default --by me --note "why" abn_atr=2.5
    python eye/zone_config.py copy --market XAUUSD --set default --to-market XAUUSD --to-set alt --by me
    python eye/zone_config.py show|list|history ...   (every command takes --db PATH)

Reading never creates the file. Every write is one transaction opened with ``BEGIN IMMEDIATE``; the set as it
would be after the write is checked through ``ZoneParams`` inside that transaction, so an invalid write writes
nothing. The time of a write is an argument (read once in ``main``).

This module is independent of the Fibonacci bot (rule 0): it imports nothing from ``bot2e``, ``bot_config`` or
``bot_research`` and never touches the table ``config_change``.
"""

from __future__ import annotations

import argparse
import math
import re
import sqlite3
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_DB = ROOT / "data" / "bot_config.db"
SEED_NOTE = "seeded from the code defaults"
_NAME = re.compile(r"[A-Za-z0-9_-]+")
_RESERVED = re.compile(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])")
_STEP_MODES = ("watr", "fixed")
_EXEC_TFS = ("M5", "M15")
SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS zone_config_change (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    set_name TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    changed_at_utc TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
""",
    "CREATE INDEX IF NOT EXISTS zone_config_change_set ON zone_config_change (market, set_name, name, id)",
)
_CURRENT = """
SELECT c.name, c.value, c.id FROM zone_config_change c
WHERE c.market = ? AND c.set_name = ?
  AND c.id = (SELECT MAX(id) FROM zone_config_change
              WHERE market = c.market AND set_name = c.set_name AND name = c.name)
"""
_INSERT = (
    "INSERT INTO zone_config_change (market, set_name, name, value, changed_at_utc, changed_by, note)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)"
)


class ConfigError(ValueError):
    """A read or write the database refuses; the message says what to do."""


def _is_float(v: Any) -> bool:
    return isinstance(v, float) and math.isfinite(v)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


@dataclass(frozen=True)
class ZoneParams:
    """Every parameter of the run-zone setup (eye/ZONE_RULES.md, Parameters). Validated at construction."""

    step_mode: str = "watr"
    step_factor: float = 0.3333333333333333
    step_fixed: float = 76.0
    grid_ks: tuple[int, ...] = (1, 2, 3)
    grid_tol: float = 0.10
    shift_tol: float = 0.20
    step_remake: float = 0.20
    near_frac: float = 10 / 76  # 0.13157894736842105
    away_frac: float = 0.5
    p1_frac: float = 10 / 76  # 0.13157894736842105
    p2_frac: float = 15 / 76  # 0.19736842105263158
    sl_frac: float = 0.5
    tp_steps: int = 1
    order_life_h: int = 48
    cancel_frac: float = 0.3333333333333333
    mom_bars: int = 3
    mom_med_bars: int = 120
    run_bars: int = 6
    gate_w: tuple[float, float, float, float] = (0.4, 0.3, 0.2, 0.1)  # D1, H4, H1, M15
    gate_min: float = 0.25
    abn_atr: float = 3.0
    ema_len: int = 50
    atr_len: int = 14
    exec_tf: str = "M15"

    def __post_init__(self) -> None:
        def bad(name: str, why: str) -> ValueError:
            return ValueError(f"{name}={getattr(self, name)!r}: {why}")

        # every field's type first, so a cross-field comparison never meets a wrong type
        for n in _STR_FIELDS:
            if not isinstance(getattr(self, n), str):
                raise bad(n, "must be a string")
        for n in _INT_FIELDS:
            if not _is_int(getattr(self, n)):
                raise bad(n, "must be an int")
        for n in _FLOAT_FIELDS:
            if not _is_float(getattr(self, n)):
                raise bad(n, "must be a finite float")
        if not isinstance(self.grid_ks, tuple) or not all(_is_int(k) for k in self.grid_ks):
            raise bad("grid_ks", "must be a non-empty strictly increasing tuple of ints >= 1")
        if not isinstance(self.gate_w, tuple) or not all(_is_float(x) for x in self.gate_w):
            raise bad("gate_w", "must be a tuple of four floats >= 0 (D1, H4, H1, M15) summing to 1")

        if self.step_mode not in _STEP_MODES:
            raise bad("step_mode", f"must be one of {_STEP_MODES}")
        if self.exec_tf not in _EXEC_TFS:
            raise bad("exec_tf", f"must be one of {_EXEC_TFS}")
        for n in ("step_factor", "step_fixed", "near_frac", "away_frac", "p1_frac", "p2_frac", "sl_frac"):
            if not _is_float(getattr(self, n)) or not getattr(self, n) > 0:
                raise bad(n, "must be a finite float > 0")
        for n in ("cancel_frac", "abn_atr"):
            if not _is_float(getattr(self, n)) or not getattr(self, n) > 0:
                raise bad(n, "must be a finite float > 0")
        for n in ("grid_tol", "shift_tol", "step_remake"):
            v = getattr(self, n)
            if not _is_float(v) or not 0 < v < 1:
                raise bad(n, "must be a float in (0, 1)")
        if not _is_float(self.gate_min) or not 0 <= self.gate_min < 1:
            raise bad("gate_min", "must be a float in [0, 1)")
        if not self.p2_frac < self.sl_frac:
            raise bad("p2_frac", f"must be < sl_frac ({self.sl_frac!r}): P2 must lie before the SL")
        if not self.near_frac < self.away_frac:
            raise bad("near_frac", f"must be < away_frac ({self.away_frac!r})")
        if not self.p1_frac <= self.near_frac:
            raise bad("p1_frac", f"must be <= near_frac ({self.near_frac!r}): no fill without its visit")
        if not self.p1_frac < self.tp_steps:
            raise bad(
                "p1_frac", f"must be < tp_steps ({self.tp_steps!r}): P1's target lies on the profit side"
            )
        for n in ("tp_steps", "order_life_h", "mom_bars", "mom_med_bars", "run_bars", "ema_len", "atr_len"):
            if not _is_int(getattr(self, n)) or getattr(self, n) < 1:
                raise bad(n, "must be an int >= 1")
        ks = self.grid_ks
        if (
            not isinstance(ks, tuple)
            or not ks
            or not all(_is_int(k) and k >= 1 for k in ks)
            or any(b <= a for a, b in pairwise(ks))
        ):
            raise bad("grid_ks", "must be a non-empty strictly increasing tuple of ints >= 1")
        w = self.gate_w
        if (
            not isinstance(w, tuple)
            or len(w) != 4
            or not all(_is_float(x) and x >= 0 for x in w)
            or abs(sum(w) - 1.0) > 1e-9
        ):
            raise bad("gate_w", "must be a tuple of four floats >= 0 (D1, H4, H1, M15) summing to 1")

    def text(self) -> str:
        """Every field as ``name=value`` in field order."""
        return " ".join(f"{n}={param_to_text(n, getattr(self, n))}" for n in FIELD_NAMES)


FIELD_NAMES = tuple(f.name for f in fields(ZoneParams))
_INT_FIELDS = ("tp_steps", "order_life_h", "mom_bars", "mom_med_bars", "run_bars", "ema_len", "atr_len")
_STR_FIELDS = ("step_mode", "exec_tf")
_FLOAT_FIELDS = tuple(
    n for n in FIELD_NAMES if n not in _INT_FIELDS + _STR_FIELDS and n not in ("grid_ks", "gate_w")
)


def param_to_text(name: str, value: Any) -> str:
    """A value as text: float -> ``repr``, int -> digits, str -> itself, ``grid_ks`` -> ``1,2,3``,
    ``gate_w`` ->
    ``0.4,0.3,0.2,0.1``. ``param_from_text(name, param_to_text(name, v)) == v``."""
    if name not in FIELD_NAMES:
        raise ValueError(f"unknown parameter {name!r}")
    if name in ("grid_ks", "gate_w"):
        return ",".join(repr(x + 0.0) if name == "gate_w" else str(x) for x in value)
    if name in _STR_FIELDS:
        return str(value)
    if name in _INT_FIELDS:
        return str(int(value))
    return repr(float(value) + 0.0)  # -0.0 + 0.0 == 0.0: one text for both zeros


def param_from_text(name: str, text: str) -> Any:
    """The inverse of ``param_to_text``; a text that is not a value of the field's type is a ValueError naming
    the field."""
    if name not in FIELD_NAMES:
        raise ValueError(f"unknown parameter {name!r}")
    try:
        if name in _STR_FIELDS:
            return text
        if name in _INT_FIELDS:
            return int(text)
        if name == "grid_ks":
            return tuple(int(p) for p in text.split(","))
        if name == "gate_w":
            return tuple(float(p) for p in text.split(","))
        return float(text)
    except ValueError:
        raise ValueError(f"{name}={text!r}: not a valid value for this field") from None


def check_name(kind: str, text: str) -> str:
    """A market or set name: letters, digits, ``_`` and ``-`` only (they name folders)."""
    if not _NAME.fullmatch(text):
        raise ConfigError(f"{kind} {text!r} must be letters, digits, '_' and '-' only")
    if _RESERVED.fullmatch(text):
        raise ConfigError(f"{kind} {text!r} is a reserved Windows device name")
    return text


def seed_command(db: Path, market: str, set_name: str) -> str:
    return f"python eye/zone_config.py seed --market {market} --set {set_name} --by <who> --db {db}"


def _missing(db: Path, market: str, set_name: str, what: str) -> ConfigError:
    return ConfigError(
        f"{what} for {market}/{set_name}: create it with  {seed_command(db, market, set_name)}"
    )


def _now() -> datetime:
    """The wall clock; read only by ``main`` (the write functions take the time as an argument)."""
    return datetime.now(UTC)


def _utc_text(at: datetime) -> str:
    if at.tzinfo is None:
        raise ValueError("changed_at_utc must be timezone-aware")
    return at.astimezone(UTC).isoformat(timespec="seconds")


def build_params(values: dict[str, str]) -> ZoneParams:
    """The text values of one set as a ``ZoneParams``: every field present, no other name, each read by its
    type, the whole set checked by ``ZoneParams``. No value falls back to the code's default."""
    missing = [n for n in FIELD_NAMES if n not in values]
    unknown = sorted(n for n in values if n not in FIELD_NAMES)
    if missing or unknown:
        raise ConfigError(f"the set is not a full set of ZoneParams: missing {missing}, unknown {unknown}")
    typed = {}
    for n in FIELD_NAMES:
        try:
            typed[n] = param_from_text(n, values[n])
        except ValueError as e:
            raise ConfigError(str(e)) from None
    try:
        return ZoneParams(**typed)
    except ValueError as e:
        raise ConfigError(f"the set is refused by ZoneParams: {e}") from None


def _read_current(con: sqlite3.Connection, market: str, set_name: str) -> tuple[dict[str, str], int]:
    """(current values by name, version); one query, so one snapshot. Version 0 and no values: no such set."""
    try:
        rows = con.execute(_CURRENT, (market, set_name)).fetchall()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return {}, 0
        raise
    return {r[0]: r[1] for r in rows}, max((r[2] for r in rows), default=0)


def _open_ro(db: Path, market: str, set_name: str) -> sqlite3.Connection:
    """A read-only connection; a missing file is not created, it stops with the seed command."""
    if not db.exists():
        raise _missing(db, market, set_name, f"no config database {db}")
    return sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=30)


def load_params(db: Path | str, market: str, set_name: str) -> tuple[ZoneParams, int]:
    """The current ``ZoneParams`` of a set and its version. Never creates the file; a missing file or set
    stops
    with the seed command."""
    db = Path(db)
    check_name("market", market)
    check_name("set", set_name)
    con = _open_ro(db, market, set_name)
    try:
        values, version = _read_current(con, market, set_name)
    finally:
        con.close()
    if not values:
        raise _missing(db, market, set_name, "no such set")
    return build_params(values), version


def _write(
    db: Path | str,
    by: str,
    at: datetime,
    plan: Callable[[sqlite3.Connection, str], int],
    *,
    must_exist: tuple[str, str] | None = None,
) -> int:
    """Run ``plan(con, stamp)`` (inserts rows, returns the version) inside ``BEGIN IMMEDIATE``; commit,
    or roll back when it raises. The file is created if missing, except when ``must_exist`` is given."""
    db = Path(db)
    if not by.strip():
        raise ConfigError("--by must say who writes")
    stamp = _utc_text(at)
    if must_exist is not None and not db.exists():
        raise _missing(db, *must_exist, f"no config database {db}")
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db, timeout=30, isolation_level=None)
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            for statement in SCHEMA:  # DDL inside the transaction: a refused write leaves the file as it was
                con.execute(statement)
            version = plan(con, stamp)
        except BaseException:
            con.execute("ROLLBACK")
            raise
        con.execute("COMMIT")
        return version
    finally:
        con.close()


def _insert_all(
    con: sqlite3.Connection, market: str, set_name: str, rows: dict[str, str], stamp: str, by: str, note: str
) -> int:
    version = 0
    for name, text in rows.items():
        cur = con.execute(_INSERT, (market, set_name, name, text, stamp, by, note))
        version = cur.lastrowid or version
    return version


def seed(db: Path | str, market: str, set_name: str, by: str, at: datetime, note: str = SEED_NOTE) -> int:
    """A new set from the code's defaults; refused if the set exists. Returns the version."""
    check_name("market", market)
    check_name("set", set_name)

    def plan(con: sqlite3.Connection, stamp: str) -> int:
        if _read_current(con, market, set_name)[0]:
            raise ConfigError(f"{market}/{set_name} exists already; change it with  set")
        d = ZoneParams()
        rows = {n: param_to_text(n, getattr(d, n)) for n in FIELD_NAMES}
        build_params(rows)
        return _insert_all(con, market, set_name, rows, stamp, by, note)

    return _write(db, by, at, plan)


def copy_set(
    db: Path | str,
    market: str,
    set_name: str,
    to_market: str,
    to_set: str,
    by: str,
    at: datetime,
    note: str = "",
) -> int:
    """A new set with the values of an existing one; refused if the source is missing or the target exists.
    Returns the target's version."""
    for kind, text in (("market", market), ("set", set_name), ("market", to_market), ("set", to_set)):
        check_name(kind, text)

    def plan(con: sqlite3.Connection, stamp: str) -> int:
        src, _ = _read_current(con, market, set_name)
        if not src:
            raise _missing(Path(db), market, set_name, "no such set")
        if _read_current(con, to_market, to_set)[0]:
            raise ConfigError(f"{to_market}/{to_set} exists already; change it with  set")
        build_params(src)
        rows = {n: src[n] for n in FIELD_NAMES}
        return _insert_all(
            con, to_market, to_set, rows, stamp, by, note or f"copied from {market}/{set_name}"
        )

    return _write(db, by, at, plan, must_exist=(market, set_name))


def _differs(name: str, old_text: str, new_text: str) -> bool:
    """True when the new value differs from the stored one by typed value; a stored text that does not parse
    counts as different (so a ``set`` can repair it)."""
    try:
        old = param_from_text(name, old_text)
    except ValueError:
        return True
    return bool(old != param_from_text(name, new_text))


def set_values(
    db: Path | str,
    market: str,
    set_name: str,
    by: str,
    at: datetime,
    note: str,
    assignments: dict[str, str],
) -> int:
    """Write the values that change (``name`` -> text); a value equal to the current one writes no row. The
    whole resulting set is checked through ``ZoneParams`` first. Returns the version after the write."""
    check_name("market", market)
    check_name("set", set_name)

    def plan(con: sqlite3.Connection, stamp: str) -> int:
        current, version = _read_current(con, market, set_name)
        if not current:
            raise _missing(Path(db), market, set_name, "no such set")
        stored_missing = [n for n in FIELD_NAMES if n not in current]
        stored_unknown = sorted(n for n in current if n not in FIELD_NAMES)
        if stored_missing or stored_unknown:
            raise ConfigError(
                f"the set is not a full set of ZoneParams: missing {stored_missing}, unknown {stored_unknown}"
            )
        bad = sorted(n for n in assignments if n not in FIELD_NAMES)
        if bad:
            raise ConfigError(f"unknown parameter(s) {bad}")
        canonical: dict[str, str] = {}
        for n, text in assignments.items():
            try:
                canonical[n] = param_to_text(n, param_from_text(n, text))
            except ValueError as e:
                raise ConfigError(str(e)) from None
        build_params({**current, **canonical})
        changes = {
            n: t
            for n, t in canonical.items()
            if _differs(n, current[n], t)  # typed, not text, equality
        }
        return _insert_all(con, market, set_name, changes, stamp, by, note) or version

    return _write(db, by, at, plan, must_exist=(market, set_name))


# --- reading for the command line ---------------------------------------------------------------------------


def list_sets(db: Path | str) -> list[tuple[str, str, int]]:
    """Every (market, set name, version), in name order."""
    con = _open_ro(Path(db), "<market>", "<set>")
    try:
        try:
            rows = con.execute(
                "SELECT market, set_name, MAX(id) FROM zone_config_change"
                " GROUP BY market, set_name ORDER BY 1, 2"
            ).fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e):
                raise
            rows = []
    finally:
        con.close()
    for m, s, _ in rows:
        check_name("market", m)
        check_name("set", s)
    return [(m, s, v) for m, s, v in rows]


def history(db: Path | str, market: str, set_name: str, name: str = "") -> list[tuple[Any, ...]]:
    """The rows of a set (optionally one name), oldest first: (id, name, value, changed_at_utc, by, note)."""
    db = Path(db)
    check_name("market", market)
    check_name("set", set_name)
    con = _open_ro(db, market, set_name)
    try:
        sql = (
            "SELECT id, name, value, changed_at_utc, changed_by, note FROM zone_config_change"
            " WHERE market = ? AND set_name = ?"
        )
        args = [market, set_name]
        if name:
            sql += " AND name = ?"
            args.append(name)
        try:
            rows = con.execute(sql + " ORDER BY id", args).fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e):
                raise
            rows = []
    finally:
        con.close()
    if not rows:
        raise _missing(db, market, set_name, "no such set" if not name else f"no rows for {name!r}")
    return rows


# --- the command line ---------------------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--db", default=str(DEFAULT_DB), help="the config database (default data/bot_config.db)"
    )
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str, *, by: bool = False, target: bool = False) -> argparse.ArgumentParser:
        p = sub.add_parser(name, parents=[common])
        if name != "list":
            p.add_argument("--market", required=True)
            p.add_argument("--set", dest="set_name", required=True)
        if target:
            p.add_argument("--to-market", required=True)
            p.add_argument("--to-set", required=True)
        if by:
            p.add_argument("--by", required=True)
        return p

    add("seed", by=True)
    add("copy", by=True, target=True).add_argument("--note", default="")
    p = add("set", by=True)
    p.add_argument("--note", required=True)
    p.add_argument("assignments", nargs="+", metavar="name=value")
    add("show")
    add("list")
    add("history").add_argument("name", nargs="?", default="")
    return ap


def _version(db: Path | str, market: str, set_name: str) -> int:
    """The version of a set, 0 when there is no file or set (used only to word the ``set`` answer)."""
    try:
        return load_params(db, market, set_name)[1]
    except ConfigError:
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    now = _now()  # read once; the write functions take it as an argument
    try:
        if args.cmd == "seed":
            v = seed(args.db, args.market, args.set_name, args.by, now)
            print(f"seeded {args.market}/{args.set_name}, version {v}")
        elif args.cmd == "copy":
            v = copy_set(
                args.db, args.market, args.set_name, args.to_market, args.to_set, args.by, now, args.note
            )
            print(f"copied to {args.to_market}/{args.to_set}, version {v}")
        elif args.cmd == "set":
            pairs: dict[str, str] = {}
            for a in args.assignments:
                n, sep, text = a.partition("=")
                if not sep:
                    raise ConfigError(f"{a!r} is not name=value")
                if n in pairs:
                    raise ConfigError(f"{n!r} is given more than once; nothing written")
                pairs[n] = text
            before = _version(args.db, args.market, args.set_name)
            v = set_values(args.db, args.market, args.set_name, args.by, now, args.note, pairs)
            print(
                f"{args.market}/{args.set_name}: version {v}" + (" (no value changed)" if v == before else "")
            )
        elif args.cmd == "show":
            params, v = load_params(args.db, args.market, args.set_name)
            for n in FIELD_NAMES:
                print(f"{n}={param_to_text(n, getattr(params, n))}")
            print(f"version={v}")
        elif args.cmd == "list":
            for m, s, v in list_sets(args.db):
                print(f"{m}/{s}@v{v}")
        else:
            for r in history(args.db, args.market, args.set_name, args.name):
                print(f"{r[0]}\t{r[3]}\t{r[1]}\t{r[2]}\t{r[4]}\t{r[5]}")
    except ConfigError as e:
        print(f"zone_config: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
