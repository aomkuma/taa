"""The bot's parameters in a database (eye/BOT_RULES.md, "The parameters come from a database").

SQLite, ``data/bot_config.db`` by default. A *set* is a full set of every ``bot2e.Params`` field, named by
market and set name. The table ``config_change`` is append-only: one row per value written; a set's
current values are, per field, the row with the highest ``id``, and its version is the highest ``id``
among its rows.

    python eye/bot_config.py seed --market XAUUSD --set default --by me
    python eye/bot_config.py set --market XAUUSD --set default --by me --note "why" min_r=2.5
    python eye/bot_config.py copy --market XAUUSD --set default --to-market XAUUSD --to-set r3_off --by me
    python eye/bot_config.py show|list|history ...   (every command takes --db PATH)

Reading never creates the file. Every write is one transaction opened with ``BEGIN IMMEDIATE``; the set as it
would be after the write is checked through ``Params`` inside that transaction, so an invalid write writes
nothing. The time of a write is an argument (read once in ``main``).

``load_params`` lives here, not in ``bot2e`` (this module imports ``bot2e.Params``; the other way
round would be an import cycle).
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections.abc import Callable, Sequence
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from eye import bot2e  # noqa: E402

DEFAULT_DB = bot2e.CONFIG_DB
SEED_NOTE = "seeded from the code defaults"
_NAME = re.compile(r"[A-Za-z0-9_-]+")
SCHEMA = """
CREATE TABLE IF NOT EXISTS config_change (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    set_name TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    changed_at_utc TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS config_change_set ON config_change (market, set_name, name, id);
"""
_CURRENT = """
SELECT c.name, c.value, c.id FROM config_change c
WHERE c.market = ? AND c.set_name = ?
  AND c.id = (SELECT MAX(id) FROM config_change
              WHERE market = c.market AND set_name = c.set_name AND name = c.name)
"""
_INSERT = (
    "INSERT INTO config_change (market, set_name, name, value, changed_at_utc, changed_by, note)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)"
)


class ConfigError(ValueError):
    """A read or write the database refuses; the message says what to do."""


def check_name(kind: str, text: str) -> str:
    """A market or set name: letters, digits, ``_`` and ``-`` only (they name folders)."""
    if not _NAME.fullmatch(text):
        raise ConfigError(f"{kind} {text!r} must be letters, digits, '_' and '-' only")
    return text


def seed_command(db: Path, market: str, set_name: str) -> str:
    extra = "" if Path(db).resolve() == DEFAULT_DB.resolve() else f" --db {db}"
    return f"python eye/bot_config.py seed --market {market} --set {set_name} --by <who>{extra}"


def _missing(db: Path, market: str, set_name: str, what: str) -> ConfigError:
    return ConfigError(
        f"{what} for {market}/{set_name}: create it with  {seed_command(db, market, set_name)}"
    )


def _utc_text(at: datetime) -> str:
    if at.tzinfo is None:
        raise ValueError("changed_at_utc must be timezone-aware")
    return at.astimezone(UTC).isoformat(timespec="seconds")


def build_params(values: dict[str, str]) -> bot2e.Params:
    """The text values of one set as a ``Params``: every field present, no other name, each read by its
    type, the
    whole set checked by ``Params``. No value falls back to the code's default."""
    names = [f.name for f in fields(bot2e.Params)]
    missing = [n for n in names if n not in values]
    unknown = sorted(n for n in values if n not in names)
    if missing or unknown:
        raise ConfigError(f"the set is not a full set of Params: missing {missing}, unknown {unknown}")
    typed = {}
    for n in names:
        try:
            typed[n] = bot2e.param_from_text(n, values[n])
        except ValueError as e:
            raise ConfigError(str(e)) from None
    try:
        return bot2e.Params(**typed)
    except ValueError as e:
        raise ConfigError(f"the set is refused by Params: {e}") from None


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


def load_params(db: Path | str, market: str, set_name: str) -> tuple[bot2e.Params, int]:
    """The current ``Params`` of a set and its version. Never creates the file; a missing file or se stops
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
    """Run ``plan(con, stamp)`` (which inserts rows and returns the version) inside ``BEGIN IMMEDIATE``;
    commit,
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
        con.executescript(SCHEMA)
        con.execute("BEGIN IMMEDIATE")
        try:
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
        d = bot2e.Params()
        rows = {f.name: bot2e.param_to_text(f.name, getattr(d, f.name)) for f in fields(bot2e.Params)}
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
    """A new set with the values of an existing one; refused if the target exists. Returns the target's
    version."""
    for kind, text in (("market", market), ("set", set_name), ("market", to_market), ("set", to_set)):
        check_name(kind, text)

    def plan(con: sqlite3.Connection, stamp: str) -> int:
        src, _ = _read_current(con, market, set_name)
        if not src:
            raise _missing(Path(db), market, set_name, "no such set")
        if _read_current(con, to_market, to_set)[0]:
            raise ConfigError(f"{to_market}/{to_set} exists already; change it with  set")
        build_params(src)
        rows = {f.name: src[f.name] for f in fields(bot2e.Params)}
        return _insert_all(
            con, to_market, to_set, rows, stamp, by, note or f"copied from {market}/{set_name}"
        )

    return _write(db, by, at, plan, must_exist=(market, set_name))


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
    whole resulting set is checked through ``Params`` first. Returns the version after the write."""
    check_name("market", market)
    check_name("set", set_name)

    def plan(con: sqlite3.Connection, stamp: str) -> int:
        current, version = _read_current(con, market, set_name)
        if not current:
            raise _missing(Path(db), market, set_name, "no such set")
        known = {f.name for f in fields(bot2e.Params)}
        bad = sorted(n for n in assignments if n not in known)
        if bad:
            raise ConfigError(f"unknown parameter(s) {bad}")
        canonical: dict[str, str] = {}
        for n, text in assignments.items():
            try:
                canonical[n] = bot2e.param_to_text(n, bot2e.param_from_text(n, text))
            except ValueError as e:
                raise ConfigError(str(e)) from None
        build_params({**current, **canonical})
        changes = {n: t for n, t in canonical.items() if current.get(n) != t}
        return _insert_all(con, market, set_name, changes, stamp, by, note) or version

    return _write(db, by, at, plan, must_exist=(market, set_name))


# --- reading for the command line ---------------------------------------------------------------------------


def list_sets(db: Path | str) -> list[tuple[str, str, int]]:
    """Every (market, set name, version), in name order."""
    con = _open_ro(Path(db), "<market>", "<set>")
    try:
        try:
            rows = con.execute(
                "SELECT market, set_name, MAX(id) FROM config_change GROUP BY market, set_name ORDER BY 1, 2"
            ).fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e):
                raise
            rows = []
    finally:
        con.close()
    return [(m, s, v) for m, s, v in rows]


def history(db: Path | str, market: str, set_name: str, name: str = "") -> list[tuple[Any, ...]]:
    """The rows of a set (optionally one field), oldest first: (id, name, value, changed_at_utc, by, note)."""
    db = Path(db)
    check_name("market", market)
    check_name("set", set_name)
    con = _open_ro(db, market, set_name)
    try:
        sql = (
            "SELECT id, name, value, changed_at_utc, changed_by, note FROM config_change"
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
    now = datetime.now(UTC)  # read once; the write functions take it as an argument
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
                pairs[n] = text
            before = _version(args.db, args.market, args.set_name)
            v = set_values(args.db, args.market, args.set_name, args.by, now, args.note, pairs)
            print(
                f"{args.market}/{args.set_name}: version {v}" + (" (no value changed)" if v == before else "")
            )
        elif args.cmd == "show":
            params, v = load_params(args.db, args.market, args.set_name)
            print(f"{args.market}/{args.set_name}@v{v}")
            for n in bot2e.TEXT_ORDER:
                print(f"  {n}={bot2e.param_to_text(n, getattr(params, n))}")
        elif args.cmd == "list":
            for m, s, v in list_sets(args.db):
                print(f"{m}/{s}@v{v}")
        else:
            for r in history(args.db, args.market, args.set_name, args.name):
                print(f"{r[0]}\t{r[3]}\t{r[4]}\t{r[1]}={r[2]}\t{r[5]}")
    except ConfigError as e:
        print(f"bot_config: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
