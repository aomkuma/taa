"""Tests for eye/bot_config.py: the parameter database and its command line (BOT_RULES, "The parameters come from
a database"), on temporary databases and a fixed time."""

from __future__ import annotations

import importlib
import sqlite3
import sys
import threading
import time
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

cfg = importlib.import_module("eye.bot_config")
bot = importlib.import_module("eye.bot2e")

AT = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 31, 11, 30, tzinfo=UTC)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "sub" / "bot_config.db"


def rows(db: Path) -> list[tuple]:
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT * FROM config_change ORDER BY id").fetchall()
    finally:
        con.close()


def seeded(db: Path, market: str = "XAUUSD", name: str = "default") -> int:
    return cfg.seed(db, market, name, "tester", AT)


def test_seed_loads_back_equal_to_the_code_defaults(db: Path) -> None:
    v = seeded(db)
    p, version = cfg.load_params(db, "XAUUSD", "default")
    assert p == bot.Params() and version == v == len(fields(bot.Params))
    allrows = rows(db)
    assert len(allrows) == len(fields(bot.Params))
    assert {(r[1], r[2]) for r in allrows} == {("XAUUSD", "default")}
    assert {r[3] for r in allrows} == {f.name for f in fields(bot.Params)}
    assert all(r[5] == "2026-10-31T10:00:00+00:00" and r[6] == "tester" for r in allrows)
    assert all(r[7] == cfg.SEED_NOTE for r in allrows)
    assert dict((r[3], r[4]) for r in allrows)["min_r"] == "2.0"


def test_missing_field_and_unknown_name_stop_with_the_names(db: Path) -> None:
    seeded(db)
    con = sqlite3.connect(db)
    con.execute("DELETE FROM config_change WHERE name = 'min_r'")
    con.execute(
        "INSERT INTO config_change (market, set_name, name, value, changed_at_utc, changed_by, note)"
        " VALUES ('XAUUSD', 'default', 'band_frac', '0.1', 'x', 'y', '')"
    )
    con.commit()
    con.close()
    with pytest.raises(cfg.ConfigError) as e:
        cfg.load_params(db, "XAUUSD", "default")
    assert "min_r" in str(e.value) and "band_frac" in str(e.value)


def test_a_set_params_refuses_stops_the_read(db: Path) -> None:
    seeded(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO config_change SELECT NULL, market, set_name, 'fib_early', '0.1', 'x', 'y', '' FROM"
        " config_change LIMIT 1"
    )  # fib_early 0.1 needs line_tight: a combination Params refuses
    con.commit()
    con.close()
    with pytest.raises(cfg.ConfigError, match="fib_early"):
        cfg.load_params(db, "XAUUSD", "default")
    con = sqlite3.connect(db)
    con.execute("UPDATE config_change SET value = 'abc' WHERE name = 'min_r'")
    con.commit()
    con.close()
    with pytest.raises(cfg.ConfigError, match="min_r"):
        cfg.load_params(db, "XAUUSD", "default")


def test_missing_database_and_missing_set_name_the_seed_command(tmp_path: Path, db: Path) -> None:
    with pytest.raises(cfg.ConfigError) as e:
        cfg.load_params(db, "XAUUSD", "default")
    msg = str(e.value)
    assert "bot_config.py seed --market XAUUSD --set default" in msg and f"--db {db}" in msg
    assert not db.exists() and not db.parent.exists()  # reading creates nothing
    seeded(db)
    with pytest.raises(cfg.ConfigError, match="seed --market XAUUSD --set nope"):
        cfg.load_params(db, "XAUUSD", "nope")
    # the default path: no --db in the message
    assert "--db" not in cfg.seed_command(cfg.DEFAULT_DB, "XAUUSD", "default")
    # the other commands do not create a missing file either
    for call in (
        lambda: cfg.set_values(db.with_name("x.db"), "XAUUSD", "default", "t", AT, "n", {"min_r": "3"}),
        lambda: cfg.copy_set(db.with_name("x.db"), "XAUUSD", "default", "XAUUSD", "b", "t", AT),
        lambda: cfg.list_sets(db.with_name("x.db")),
        lambda: cfg.history(db.with_name("x.db"), "XAUUSD", "default"),
    ):
        with pytest.raises(cfg.ConfigError, match="seed"):
            call()
        assert not db.with_name("x.db").exists()


def test_invalid_value_or_combination_writes_nothing(db: Path) -> None:
    seeded(db)
    before = rows(db)
    for bad in (
        {"fib_entry": "0.5"},  # not an allowed value
        {"min_r": "abc"},  # not a float
        {"max_orders": "0"},
        {"fib_early": "0.1"},  # needs line_tight
        {"fib_stop": "line_tight"},  # line_tight needs fib_early
        {"min_r": "3", "fib_entry": "0.5"},  # one good, one bad: nothing is written
        {"nonsense": "1"},
    ):
        with pytest.raises(cfg.ConfigError):
            cfg.set_values(db, "XAUUSD", "default", "t", LATER, "why", bad)
        assert rows(db) == before, bad


def test_set_writes_the_combination_in_one_go_and_only_changed_values(db: Path) -> None:
    v0 = seeded(db)
    v1 = cfg.set_values(
        db, "XAUUSD", "default", "t", LATER, "r3", {"fib_early": "0.1", "fib_stop": "line_tight"}
    )
    assert v1 == v0 + 2
    p, version = cfg.load_params(db, "XAUUSD", "default")
    assert p.fib_early == 0.1 and p.fib_stop == "line_tight" and version == v1
    n = len(rows(db))
    # an unchanged value (and one written in another spelling of the same value) writes no row
    assert (
        cfg.set_values(db, "XAUUSD", "default", "t", LATER, "same", {"min_r": "2", "fib_early": "0.10"}) == v1
    )
    assert len(rows(db)) == n
    # a changed value: one row, with the time, who and the note
    v2 = cfg.set_values(db, "XAUUSD", "default", "me", LATER, "tighter", {"min_r": "2.5"})
    assert v2 == v1 + 1 and len(rows(db)) == n + 1
    last = rows(db)[-1]
    assert last[3:] == ("min_r", "2.5", "2026-10-31T11:30:00+00:00", "me", "tighter")
    assert cfg.load_params(db, "XAUUSD", "default")[0].min_r == 2.5


def test_set_on_a_missing_set_is_refused(db: Path) -> None:
    seeded(db)
    with pytest.raises(cfg.ConfigError, match="seed --market XAUUSD --set other"):
        cfg.set_values(db, "XAUUSD", "other", "t", AT, "n", {"min_r": "3"})
    assert len(rows(db)) == len(fields(bot.Params))


def test_version_rises_and_history_lists_every_row_oldest_first(db: Path) -> None:
    v0 = seeded(db)
    cfg.set_values(db, "XAUUSD", "default", "a", LATER, "one", {"min_r": "3"})
    cfg.set_values(db, "XAUUSD", "default", "b", LATER, "two", {"min_r": "4", "spread": "0.1"})
    assert cfg.load_params(db, "XAUUSD", "default")[1] == v0 + 3
    h = cfg.history(db, "XAUUSD", "default")
    assert len(h) == v0 + 3 and [r[0] for r in h] == sorted(r[0] for r in h)
    only = cfg.history(db, "XAUUSD", "default", "min_r")
    assert [r[2] for r in only] == ["2.0", "3.0", "4.0"] and [r[4] for r in only] == ["tester", "a", "b"]
    assert cfg.list_sets(db) == [("XAUUSD", "default", v0 + 3)]
    with pytest.raises(cfg.ConfigError):
        cfg.history(db, "XAUUSD", "nope")


def test_seed_and_copy_onto_an_existing_set_are_refused(db: Path) -> None:
    seeded(db)
    n = len(rows(db))
    with pytest.raises(cfg.ConfigError, match="exists"):
        seeded(db)
    cfg.set_values(db, "XAUUSD", "default", "t", AT, "n", {"min_r": "3"})
    v = cfg.copy_set(db, "XAUUSD", "default", "XAUUSD", "copy1", "t", LATER)
    assert cfg.load_params(db, "XAUUSD", "copy1") == (bot.Params(min_r=3.0), v)
    assert cfg.history(db, "XAUUSD", "copy1")[0][5] == "copied from XAUUSD/default"
    m = len(rows(db))
    with pytest.raises(cfg.ConfigError, match="exists"):
        cfg.copy_set(db, "XAUUSD", "default", "XAUUSD", "copy1", "t", LATER)
    with pytest.raises(cfg.ConfigError, match="exists"):
        cfg.copy_set(db, "XAUUSD", "copy1", "XAUUSD", "default", "t", LATER)
    with pytest.raises(cfg.ConfigError, match="seed --market XAUUSD --set none"):
        cfg.copy_set(db, "XAUUSD", "none", "XAUUSD", "new", "t", LATER)
    assert len(rows(db)) == m and m == n + 1 + len(fields(bot.Params))
    # another market's set is independent
    cfg.copy_set(db, "XAUUSD", "default", "EURUSD", "default", "t", LATER, "other market")
    assert cfg.load_params(db, "EURUSD", "default")[0].min_r == 3.0
    cfg.set_values(db, "EURUSD", "default", "t", LATER, "n", {"min_r": "5"})
    assert cfg.load_params(db, "XAUUSD", "default")[0].min_r == 3.0
    assert [(m_, s) for m_, s, _ in cfg.list_sets(db)] == [
        ("EURUSD", "default"), ("XAUUSD", "copy1"), ("XAUUSD", "default"),
    ]  # fmt: skip


def test_two_writes_from_two_connections_both_land(db: Path) -> None:
    seeded(db)
    holder = sqlite3.connect(db, timeout=30, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    t = threading.Thread(
        target=cfg.set_values, args=(db, "XAUUSD", "default", "b", LATER, "second", {"spread": "0.1"})
    )
    t.start()
    time.sleep(0.3)  # the second writer waits for the first one's transaction
    holder.execute(
        "INSERT INTO config_change (market, set_name, name, value, changed_at_utc, changed_by, note)"
        " VALUES ('XAUUSD', 'default', 'min_r', '3.0', 'x', 'a', 'first')"
    )
    holder.execute("COMMIT")
    holder.close()
    t.join(30)
    assert not t.is_alive()
    p, _ = cfg.load_params(db, "XAUUSD", "default")
    assert p.min_r == 3.0 and p.spread == 0.1


@pytest.mark.parametrize("bad", ["", "a/b", "a b", "..", "a.b", "x\n", "é", "a\\b", "a:b"])
def test_bad_names_are_refused_on_every_path(db: Path, bad: str) -> None:
    seeded(db)
    n = len(rows(db))
    for market, name in ((bad, "default"), ("XAUUSD", bad)):
        with pytest.raises(cfg.ConfigError, match="letters, digits"):
            cfg.load_params(db, market, name)
        with pytest.raises(cfg.ConfigError, match="letters, digits"):
            cfg.seed(db, market, name, "t", AT)
        with pytest.raises(cfg.ConfigError, match="letters, digits"):
            cfg.set_values(db, market, name, "t", AT, "n", {"min_r": "3"})
        with pytest.raises(cfg.ConfigError, match="letters, digits"):
            cfg.copy_set(db, market, name, "XAUUSD", "z", "t", AT)
        with pytest.raises(cfg.ConfigError, match="letters, digits"):
            cfg.copy_set(db, "XAUUSD", "default", market, name, "t", AT)
        with pytest.raises(cfg.ConfigError, match="letters, digits"):
            cfg.history(db, market, name)
    assert len(rows(db)) == n


def test_good_names_and_a_naive_time(db: Path) -> None:
    cfg.seed(db, "XAU-USD_2", "r3_off-1", "t", AT)
    assert cfg.load_params(db, "XAU-USD_2", "r3_off-1")[0] == bot.Params()
    with pytest.raises(ValueError, match="timezone"):
        cfg.set_values(db, "XAU-USD_2", "r3_off-1", "t", datetime(2026, 1, 1), "n", {"min_r": "3"})
    with pytest.raises(cfg.ConfigError, match="who"):
        cfg.set_values(db, "XAU-USD_2", "r3_off-1", " ", AT, "n", {"min_r": "3"})


def test_the_command_line(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = ["--db", str(db)]
    assert cfg.main(["show", "--market", "XAUUSD", "--set", "default", *d]) == 2
    err = capsys.readouterr().err
    assert "seed --market XAUUSD --set default" in err and f"--db {db}" in err
    assert cfg.main(["seed", "--market", "XAUUSD", "--set", "default", "--by", "me", *d]) == 0
    assert cfg.main(["seed", "--market", "XAUUSD", "--set", "default", "--by", "me", *d]) == 2
    assert (
        cfg.main(
            ["set", "--market", "XAUUSD", "--set", "default", "--by", "me", "--note", "n", *d, "min_r=2.5"]
        )
        == 0
    )
    assert (
        cfg.main(
            ["set", "--market", "XAUUSD", "--set", "default", "--by", "me", "--note", "n", *d, "min_r=2.5"]
        )
        == 0
    )
    assert "no value changed" in capsys.readouterr().out.splitlines()[-1]
    assert (
        cfg.main(["set", "--market", "XAUUSD", "--set", "default", "--by", "me", "--note", "n", *d, "min_r"])
        == 2
    )
    assert cfg.main(["show", "--market", "XAUUSD", "--set", "default", *d]) == 0
    out = capsys.readouterr().out
    assert "XAUUSD/default@v22" in out and "min_r=2.5" in out and "windows=off" in out
    assert cfg.main(["list", *d]) == 0 and "XAUUSD/default@v22" in capsys.readouterr().out
    assert cfg.main(["history", "--market", "XAUUSD", "--set", "default", "min_r", *d]) == 0
    assert capsys.readouterr().out.count("min_r=") == 2
    assert cfg.main(["copy", "--market", "XAUUSD", "--set", "default", "--to-market", "XAUUSD", "--to-set", "b",
                     "--by", "me", *d]) == 0  # fmt: skip
