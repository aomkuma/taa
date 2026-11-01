"""eye/zone_config.py: the run-zone setup's parameters in a database (eye/ZONE_RULES.md, rules 0 and 1; acceptance
cases 6 and 7). Temporary files only - never the real data/bot_config.db."""

from __future__ import annotations

import ast
import re
import sqlite3
import sys
import threading
from dataclasses import fields, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eye import zone_config as zc  # noqa: E402
from eye.zone_config import ConfigError, ZoneParams  # noqa: E402

AT = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
AT2 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)
NAMES = [f.name for f in fields(ZoneParams)]


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "cfg.db"


def _rows(db: Path, table: str = "zone_config_change") -> list[tuple[Any, ...]]:
    con = sqlite3.connect(db)
    try:
        return con.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()  # noqa: S608
    finally:
        con.close()


def _seeded(db: Path) -> int:
    return zc.seed(db, "XAUUSD", "default", "t", AT)


# --- the parameters -------------------------------------------------------------------------------------------


def test_defaults_are_the_table() -> None:
    p = ZoneParams()
    assert p.near_frac == 0.13157894736842105 == 10 / 76
    assert p.p1_frac == 0.13157894736842105
    assert p.p2_frac == 0.19736842105263158 == 15 / 76
    assert p.step_factor == 0.3333333333333333 == p.cancel_frac == 1 / 3
    assert p.grid_ks == (1, 2, 3)
    assert p.gate_w == (0.4, 0.3, 0.2, 0.1)
    assert NAMES == [
        "step_mode", "step_factor", "step_fixed", "grid_ks", "grid_tol", "shift_tol", "step_remake",
        "near_frac", "away_frac", "p1_frac", "p2_frac", "sl_frac", "tp_steps", "order_life_h", "cancel_frac",
        "mom_bars", "mom_med_bars", "run_bars", "gate_w", "gate_min", "abn_atr", "ema_len", "atr_len", "exec_tf",
    ]  # fmt: skip
    assert p.text().split(" ")[0] == "step_mode=watr"
    assert "gate_w=0.4,0.3,0.2,0.1" in p.text()


@pytest.mark.parametrize("name", NAMES)
def test_text_round_trip_every_field(name: str) -> None:
    value = getattr(ZoneParams(), name)
    text = zc.param_to_text(name, value)
    assert zc.param_from_text(name, text) == value
    assert type(zc.param_from_text(name, text)) is type(value)


def test_text_forms() -> None:
    assert zc.param_to_text("grid_ks", (1, 2, 3)) == "1,2,3"
    assert zc.param_to_text("gate_w", (0.4, 0.3, 0.2, 0.1)) == "0.4,0.3,0.2,0.1"
    assert zc.param_to_text("near_frac", 10 / 76) == "0.13157894736842105"
    assert zc.param_to_text("step_fixed", 76.0) == "76.0"
    assert zc.param_to_text("order_life_h", 48) == "48"
    assert zc.param_to_text("exec_tf", "M15") == "M15"
    with pytest.raises(ValueError, match="order_life_h"):
        zc.param_from_text("order_life_h", "4.5")
    with pytest.raises(ValueError, match="grid_ks"):
        zc.param_from_text("grid_ks", "1,x")


# Types and bounds: (field, value refused, value accepted just inside)
_BOUNDS: list[tuple[str, Any, Any]] = [
    ("step_mode", "weekly", "fixed"),
    ("exec_tf", "H1", "M5"),
    ("step_factor", 0.0, 1e-12),
    ("step_fixed", 0.0, 1e-12),
    ("near_frac", 0.0, 0.2),
    ("away_frac", 0.0, 0.2),
    ("p1_frac", 0.0, 1e-12),
    ("p2_frac", 0.0, 1e-12),
    ("sl_frac", 0.0, 0.2),
    ("cancel_frac", 0.0, 1e-12),
    ("abn_atr", 0.0, 1e-12),
    ("step_fixed", -1.0, 1.0),
    ("grid_tol", 0.0, 1e-12),
    ("grid_tol", 1.0, 0.999999),
    ("shift_tol", 0.0, 1e-12),
    ("shift_tol", 1.0, 0.999999),
    ("step_remake", 0.0, 1e-12),
    ("step_remake", 1.0, 0.999999),
    ("gate_min", -1e-12, 0.0),
    ("gate_min", 1.0, 0.999999),
    ("tp_steps", 0, 1),
    ("order_life_h", 0, 1),
    ("mom_bars", 0, 1),
    ("mom_med_bars", 0, 1),
    ("run_bars", 0, 1),
    ("ema_len", 0, 1),
    ("atr_len", 0, 1),
    ("grid_ks", (), (1,)),
    ("grid_ks", (0, 1), (1, 2)),
    ("grid_ks", (1, 1), (1, 2)),
    ("grid_ks", (2, 1), (1, 2)),
    ("grid_ks", [1, 2], (1, 2)),
    ("grid_ks", (1.0, 2), (1, 2)),
    ("gate_w", (0.4, 0.3, 0.2), (0.4, 0.3, 0.2, 0.1)),
    ("gate_w", (0.4, 0.3, 0.2, 0.2), (0.4, 0.3, 0.2, 0.1)),
    ("gate_w", (0.4, 0.3, 0.2, 0.1 + 2e-9), (0.4, 0.3, 0.2, 0.1 + 5e-10)),
    ("gate_w", (-0.1, 0.5, 0.3, 0.3), (0.0, 0.5, 0.3, 0.2)),
]


@pytest.mark.parametrize(("name", "bad", "good"), _BOUNDS)
def test_bounds_refused_at_the_edge_accepted_inside(name: str, bad: Any, good: Any) -> None:
    with pytest.raises(ValueError, match=name):
        ZoneParams(**{name: bad})
    ZoneParams(**{name: good})  # no raise


def test_p2_must_lie_before_the_sl() -> None:
    sl = 0.5
    with pytest.raises(ValueError, match="p2_frac"):
        ZoneParams(p2_frac=sl, sl_frac=sl)
    with pytest.raises(ValueError, match="p2_frac"):
        ZoneParams(p2_frac=0.6, sl_frac=sl)
    ZoneParams(p2_frac=0.4999999, sl_frac=sl)


def test_near_frac_below_away_frac() -> None:
    ZoneParams(near_frac=0.4999999, away_frac=0.5)
    with pytest.raises(ValueError, match="near_frac"):
        ZoneParams(near_frac=0.5, away_frac=0.5)
    with pytest.raises(ValueError, match="near_frac"):
        ZoneParams(near_frac=0.6, away_frac=0.5)


def test_p1_bounds() -> None:
    # p1_frac <= near_frac: equal accepted, just above refused
    ZoneParams(p1_frac=0.13, near_frac=0.13)
    with pytest.raises(ValueError, match="p1_frac"):
        ZoneParams(p1_frac=0.1300001, near_frac=0.13)
    # p1_frac < tp_steps: just below accepted, equal refused
    ZoneParams(p1_frac=0.999999, near_frac=1.0, away_frac=2.0, tp_steps=1, p2_frac=0.99999, sl_frac=1.0)
    with pytest.raises(ValueError, match="p1_frac"):
        ZoneParams(p1_frac=1.0, near_frac=1.0, away_frac=2.0, tp_steps=1, p2_frac=0.5, sl_frac=1.0)


def test_types_are_strict() -> None:
    with pytest.raises(ValueError, match="tp_steps"):
        ZoneParams(tp_steps=True)
    with pytest.raises(ValueError, match="order_life_h"):
        ZoneParams(order_life_h=48.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="abn_atr"):
        ZoneParams(abn_atr=float("nan"))
    with pytest.raises(ValueError, match="abn_atr"):
        ZoneParams(abn_atr=float("inf"))
    ZoneParams(abn_atr=1e9)  # switches 5c off in effect


# --- the database ---------------------------------------------------------------------------------------------


def test_seed_loads_back_equal(db: Path) -> None:
    v = _seeded(db)
    p, version = zc.load_params(db, "XAUUSD", "default")
    assert p == ZoneParams()
    assert version == v == len(NAMES)
    rows = _rows(db)
    assert [r[3] for r in rows] == NAMES
    assert {r[7] for r in rows} == {zc.SEED_NOTE}
    assert rows[0][5] == "2026-11-01T12:00:00+00:00"


def test_seed_and_copy_onto_existing_refused(db: Path) -> None:
    _seeded(db)
    n = len(_rows(db))
    with pytest.raises(ConfigError, match="exists already"):
        _seeded(db)
    zc.copy_set(db, "XAUUSD", "default", "XAUUSD", "alt", "t", AT)
    n2 = len(_rows(db))
    assert n2 == 2 * n
    with pytest.raises(ConfigError, match="exists already"):
        zc.copy_set(db, "XAUUSD", "default", "XAUUSD", "alt", "t", AT)
    with pytest.raises(ConfigError, match="no such set"):
        zc.copy_set(db, "XAUUSD", "nope", "XAUUSD", "alt2", "t", AT)
    assert len(_rows(db)) == n2
    assert zc.load_params(db, "XAUUSD", "alt")[0] == ZoneParams()


def test_copy_takes_current_values(db: Path) -> None:
    _seeded(db)
    zc.set_values(db, "XAUUSD", "default", "t", AT, "n", {"abn_atr": "2.5"})
    zc.copy_set(db, "XAUUSD", "default", "XAUUSD", "alt", "t", AT2)
    assert zc.load_params(db, "XAUUSD", "alt")[0].abn_atr == 2.5


def test_missing_database_and_set_name_the_seed_command(db: Path) -> None:
    with pytest.raises(ConfigError) as e:
        zc.load_params(db, "XAUUSD", "default")
    assert "seed" in str(e.value) and str(db) in str(e.value)
    assert not db.exists()  # reading never creates the file
    _seeded(db)
    with pytest.raises(ConfigError) as e2:
        zc.load_params(db, "XAUUSD", "other")
    assert "seed --market XAUUSD --set other" in str(e2.value) and str(db) in str(e2.value)
    with pytest.raises(ConfigError, match="seed"):
        zc.set_values(db, "XAUUSD", "other", "t", AT, "n", {"abn_atr": "2.0"})


def test_missing_database_stops_set_without_creating_it(db: Path) -> None:
    with pytest.raises(ConfigError, match="seed"):
        zc.set_values(db, "XAUUSD", "default", "t", AT, "n", {"abn_atr": "2.0"})
    assert not db.exists()


def test_missing_and_unknown_names_stop_naming_them(db: Path) -> None:
    _seeded(db)
    con = sqlite3.connect(db)
    con.execute("DELETE FROM zone_config_change WHERE name = 'abn_atr'")
    con.execute(
        "INSERT INTO zone_config_change (market, set_name, name, value, changed_at_utc, changed_by)"
        " VALUES ('XAUUSD', 'default', 'bogus_name', '1', 'x', 'x')"
    )
    con.commit()
    con.close()
    with pytest.raises(ConfigError) as e:
        zc.load_params(db, "XAUUSD", "default")
    assert "abn_atr" in str(e.value) and "bogus_name" in str(e.value)


def test_no_fallback_to_defaults_on_a_bad_stored_value(db: Path) -> None:
    _seeded(db)
    con = sqlite3.connect(db)
    con.execute("UPDATE zone_config_change SET value = 'x' WHERE name = 'tp_steps'")
    con.commit()
    con.close()
    with pytest.raises(ConfigError, match="tp_steps"):
        zc.load_params(db, "XAUUSD", "default")


@pytest.mark.parametrize("bad", ["", "a b", "a/b", "..", "a.b", "Ã©"])
def test_names_are_path_safe(db: Path, bad: str) -> None:
    with pytest.raises(ConfigError):
        zc.seed(db, bad, "default", "t", AT)
    with pytest.raises(ConfigError):
        zc.seed(db, "XAUUSD", bad, "t", AT)
    with pytest.raises(ConfigError):
        zc.load_params(db, bad, "default")
    assert not db.exists()
    zc.seed(db, "XAU_USD-1", "set-A_2", "t", AT)


def test_invalid_value_or_combination_writes_nothing(db: Path) -> None:
    _seeded(db)
    before = _rows(db)
    for assign in (
        {"tp_steps": "0"},  # out of bounds
        {"tp_steps": "x"},  # does not parse
        {"nonsense": "1"},  # unknown name
        {"p2_frac": "0.5"},  # combination: p2 == sl
        {"sl_frac": "0.1"},  # combination: sl < p2
        {"abn_atr": "2.0", "tp_steps": "0"},  # one good, one bad: nothing written
        {"gate_w": "0.5,0.5,0.5,0.5"},
        {"step_mode": "daily"},
    ):
        with pytest.raises(ConfigError):
            zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", assign)
        assert _rows(db) == before
    assert zc.load_params(db, "XAUUSD", "default")[0] == ZoneParams()


def test_set_of_an_unchanged_value_writes_no_row(db: Path) -> None:
    v = _seeded(db)
    assert zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"abn_atr": "3.0"}) == v
    assert zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"abn_atr": "3", "grid_ks": "1,2,3"}) == v
    assert len(_rows(db)) == len(NAMES)


def test_version_rises_and_history_lists_every_row(db: Path) -> None:
    v0 = _seeded(db)
    v1 = zc.set_values(db, "XAUUSD", "default", "alice", AT2, "tighter", {"abn_atr": "2.5"})
    assert v1 == v0 + 1
    v2 = zc.set_values(db, "XAUUSD", "default", "bob", AT2, "two", {"abn_atr": "2.0", "order_life_h": "24"})
    assert v2 == v1 + 2
    p, version = zc.load_params(db, "XAUUSD", "default")
    assert (p.abn_atr, p.order_life_h, version) == (2.0, 24, v2)
    assert p == replace(ZoneParams(), abn_atr=2.0, order_life_h=24)
    hist = zc.history(db, "XAUUSD", "default")
    assert len(hist) == len(NAMES) + 3
    assert [r[0] for r in hist] == sorted(r[0] for r in hist)
    h = zc.history(db, "XAUUSD", "default", "abn_atr")
    assert [(r[2], r[4], r[5]) for r in h] == [
        ("3.0", "t", zc.SEED_NOTE),
        ("2.5", "alice", "tighter"),
        ("2.0", "bob", "two"),
    ]
    assert h[1][3] == "2026-11-02T12:00:00+00:00"
    assert zc.list_sets(db) == [("XAUUSD", "default", v2)]


def test_two_writes_from_two_connections_both_land(db: Path) -> None:
    _seeded(db)
    errors: list[BaseException] = []

    def go(name: str, value: str) -> None:
        try:
            zc.set_values(db, "XAUUSD", "default", name, AT2, "n", {name: value})
        except BaseException as e:
            errors.append(e)

    ts = [threading.Thread(target=go, args=a) for a in (("abn_atr", "2.5"), ("order_life_h", "24"))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert errors == []
    p, version = zc.load_params(db, "XAUUSD", "default")
    assert (p.abn_atr, p.order_life_h) == (2.5, 24)
    assert version == len(NAMES) + 2


def test_by_must_say_who(db: Path) -> None:
    with pytest.raises(ConfigError, match="--by"):
        zc.seed(db, "XAUUSD", "default", " ", AT)
    assert not db.exists()


def test_fibonacci_bots_table_is_untouched(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE config_change (id INTEGER PRIMARY KEY AUTOINCREMENT, market TEXT, set_name TEXT,"
        " name TEXT, value TEXT, changed_at_utc TEXT, changed_by TEXT, note TEXT)"
    )
    con.execute(
        "INSERT INTO config_change (market, set_name, name, value) VALUES ('XAUUSD','default','min_r','2.0')"
    )
    con.commit()
    con.close()
    before = _rows(db, "config_change")
    schema_before = (
        sqlite3.connect(db).execute("SELECT sql FROM sqlite_master WHERE name='config_change'").fetchall()
    )

    _seeded(db)
    zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"abn_atr": "2.5"})
    zc.copy_set(db, "XAUUSD", "default", "XAUUSD", "alt", "t", AT2)
    with pytest.raises(ConfigError):
        zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"tp_steps": "0"})
    zc.load_params(db, "XAUUSD", "default")
    zc.list_sets(db)
    zc.history(db, "XAUUSD", "default")

    assert _rows(db, "config_change") == before
    schema_after = (
        sqlite3.connect(db).execute("SELECT sql FROM sqlite_master WHERE name='config_change'").fetchall()
    )
    assert schema_after == schema_before
    # and the zone sets never read the Fibonacci rows
    assert all(r[3] in NAMES for r in _rows(db))
    capsys.readouterr()


# --- the command line -----------------------------------------------------------------------------------------


def test_command_line(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--db", str(db)]
    assert zc.main(["show", "--market", "XAUUSD", "--set", "default", *base]) == 1
    err = capsys.readouterr().err
    assert "seed" in err and str(db) in err
    assert zc.main(["list", *base]) == 1
    capsys.readouterr()

    assert zc.main(["seed", "--market", "XAUUSD", "--set", "default", "--by", "me", *base]) == 0
    assert zc.main(["seed", "--market", "XAUUSD", "--set", "default", "--by", "me", *base]) == 1
    capsys.readouterr()

    assert zc.main(["show", "--market", "XAUUSD", "--set", "default", *base]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [ln.split("=")[0] for ln in lines] == [*NAMES, "version"]
    assert lines[-1] == f"version={len(NAMES)}"
    assert "near_frac=0.13157894736842105" in lines

    argv = ["set", "--market", "XAUUSD", "--set", "default", "--by", "me", "--note", "why", *base]
    assert zc.main([*argv, "abn_atr=2.5", "grid_ks=1,2"]) == 0
    capsys.readouterr()
    assert zc.main([*argv, "tp_steps=0"]) == 1
    assert "tp_steps" in capsys.readouterr().err
    assert zc.main([*argv, "tp_steps"]) == 1  # not name=value
    assert zc.load_params(db, "XAUUSD", "default")[0] == replace(ZoneParams(), abn_atr=2.5, grid_ks=(1, 2))

    assert (
        zc.main(
            [
                "copy",
                "--market",
                "XAUUSD",
                "--set",
                "default",
                "--to-market",
                "XAUUSD",
                "--to-set",
                "b",
                "--by",
                "me",
                *base,
            ]
        )
        == 0
    )
    assert zc.main(["list", *base]) == 0
    out = capsys.readouterr().out
    assert f"XAUUSD/b@v{len(NAMES) * 2 + 2}" in out
    assert zc.main(["history", "--market", "XAUUSD", "--set", "default", "abn_atr", *base]) == 0
    rows = capsys.readouterr().out.strip().splitlines()
    assert len(rows) == 2 and rows[1].split("\t")[2:4] == ["abn_atr", "2.5"]


def test_write_functions_take_the_time_from_the_caller(db: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        zc.seed(db, "XAUUSD", "default", "t", datetime(2026, 11, 1))
    assert _rows(db) == [] if db.exists() else True


# --- review fixes ---------------------------------------------------------------------------------------------

_SPEC_DEFAULTS: dict[str, Any] = {
    "step_mode": "watr",
    "step_factor": 0.3333333333333333,
    "step_fixed": 76.0,
    "grid_ks": (1, 2, 3),
    "grid_tol": 0.10,
    "shift_tol": 0.20,
    "step_remake": 0.20,
    "near_frac": 0.13157894736842105,
    "away_frac": 0.5,
    "p1_frac": 0.13157894736842105,
    "p2_frac": 0.19736842105263158,
    "sl_frac": 0.5,
    "tp_steps": 1,
    "order_life_h": 48,
    "cancel_frac": 0.3333333333333333,
    "mom_bars": 3,
    "mom_med_bars": 120,
    "run_bars": 6,
    "gate_w": (0.4, 0.3, 0.2, 0.1),
    "gate_min": 0.25,
    "abn_atr": 3.0,
    "ema_len": 50,
    "atr_len": 14,
    "exec_tf": "M15",
}


def test_every_default_against_the_spec_table() -> None:
    p = ZoneParams()
    assert len(_SPEC_DEFAULTS) == 24 == len(NAMES)
    for name, expected in _SPEC_DEFAULTS.items():
        assert getattr(p, name) == expected, name
        assert type(getattr(p, name)) is type(expected), name


def test_missing_name_alone_and_unknown_name_alone(db: Path) -> None:
    _seeded(db)
    con = sqlite3.connect(db)
    con.execute("DELETE FROM zone_config_change WHERE name = 'abn_atr'")
    con.commit()
    with pytest.raises(ConfigError) as e:
        zc.load_params(db, "XAUUSD", "default")
    assert "abn_atr" in str(e.value) and "unknown []" in str(e.value)
    con.execute(
        "INSERT INTO zone_config_change (market, set_name, name, value, changed_at_utc, changed_by)"
        " VALUES ('XAUUSD', 'default', 'abn_atr', '3.0', 'x', 'x'),"
        " ('XAUUSD', 'default', 'bogus_name', '1', 'x', 'x')"
    )
    con.commit()
    with pytest.raises(ConfigError) as e2:
        zc.load_params(db, "XAUUSD", "default")
    assert "bogus_name" in str(e2.value) and "missing []" in str(e2.value)
    con.close()


def test_signed_zero_writes_no_second_row(db: Path) -> None:
    _seeded(db)
    v1 = zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"gate_min": "0.5"})
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO zone_config_change (market, set_name, name, value, changed_at_utc, changed_by)"
        " VALUES ('XAUUSD', 'default', 'gate_min', '-0.0', 'x', 'x')"
    )
    con.commit()
    con.close()
    v1 += 1  # the stored current text is the signed zero "-0.0"
    n = len(_rows(db))
    assert zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"gate_min": "0.0"}) == v1
    assert len(_rows(db)) == n
    assert zc.param_to_text("gate_min", -0.0) == "0.0"
    assert zc.param_to_text("gate_w", (-0.0, 0.5, 0.3, 0.2)) == "0.0,0.5,0.3,0.2"


def test_a_failure_mid_write_rolls_everything_back(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seeded(db)
    before = _rows(db)
    real_execute_calls = {"n": 0}
    real_insert = zc._INSERT

    class Flaky:
        """A connection wrapper whose 2nd INSERT raises."""

        def __init__(self, con: sqlite3.Connection) -> None:
            self.con = con

        def execute(self, sql: str, *args: Any) -> Any:
            if sql == real_insert:
                real_execute_calls["n"] += 1
                if real_execute_calls["n"] == 2:
                    raise RuntimeError("boom")
            return self.con.execute(sql, *args)

        def close(self) -> None:
            self.con.close()

    real_connect = sqlite3.connect
    monkeypatch.setattr(zc.sqlite3, "connect", lambda *a, **k: Flaky(real_connect(*a, **k)))
    with pytest.raises(RuntimeError):
        zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"abn_atr": "2.5", "order_life_h": "24"})
    assert real_execute_calls["n"] == 2
    monkeypatch.undo()
    assert _rows(db) == before
    assert zc.load_params(db, "XAUUSD", "default")[0] == ZoneParams()


def test_overlapping_writers_and_a_coherent_read(db: Path) -> None:
    v0 = _seeded(db)
    a = sqlite3.connect(db, timeout=30, isolation_level=None)
    a.execute("BEGIN IMMEDIATE")
    a.execute(zc._INSERT, ("XAUUSD", "default", "abn_atr", "2.5", "2026-11-02T00:00:00+00:00", "A", "a"))
    landed: list[int] = []
    t = threading.Thread(
        target=lambda: landed.append(
            zc.set_values(db, "XAUUSD", "default", "B", AT2, "b", {"order_life_h": "24"})
        )
    )
    t.start()
    t.join(0.5)
    assert t.is_alive() and landed == []  # B waits on A's write lock
    # a read during A's open transaction sees the last commit: values and version together
    p, version = zc.load_params(db, "XAUUSD", "default")
    assert (p, version) == (ZoneParams(), v0)
    a.execute("COMMIT")
    a.close()
    t.join(30)
    assert not t.is_alive() and landed == [v0 + 2]
    p, version = zc.load_params(db, "XAUUSD", "default")
    assert (p.abn_atr, p.order_life_h, version) == (2.5, 24, v0 + 2)
    ids = [r[0] for r in zc.history(db, "XAUUSD", "default") if r[1] in ("abn_atr", "order_life_h")]
    assert ids[-2:] == [v0 + 1, v0 + 2]


def test_set_refuses_a_repeated_name_or_an_unparsable_value(db: Path) -> None:
    _seeded(db)
    before = _rows(db)
    argv = ["set", "--market", "XAUUSD", "--set", "default", "--by", "t", "--note", "n", "--db", str(db)]
    for pairs in (
        ["abn_atr=bad", "abn_atr=2.5"],
        ["abn_atr=2.5", "abn_atr=bad"],
        ["abn_atr=2.5", "abn_atr=2.5"],
        ["abn_atr=bad", "order_life_h=24"],
    ):
        assert zc.main([*argv, *pairs]) == 1
        assert _rows(db) == before


def test_set_on_a_set_with_a_missing_stored_field_stops_with_its_name(db: Path) -> None:
    _seeded(db)
    con = sqlite3.connect(db)
    con.execute("DELETE FROM zone_config_change WHERE name = 'abn_atr'")
    con.commit()
    con.close()
    before = _rows(db)
    for assign in ({"abn_atr": "2.5"}, {"order_life_h": "24"}):
        with pytest.raises(ConfigError, match="abn_atr") as e:
            zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", assign)
        assert not isinstance(e.value, KeyError)
        assert _rows(db) == before
    argv = ["set", "--market", "XAUUSD", "--set", "default", "--by", "t", "--note", "n", "--db", str(db)]
    assert zc.main([*argv, "abn_atr=2.5"]) == 1
    assert zc.main([*argv, "order_life_h=24"]) == 1
    assert _rows(db) == before


def test_load_params_reads_values_and_version_from_one_snapshot(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    v0 = _seeded(db)
    real_open = zc._open_ro
    fired: list[int] = []

    class Rows:
        def __init__(self, rows: list[Any]) -> None:
            self.rows = rows

        def fetchall(self) -> list[Any]:
            return self.rows

        def fetchone(self) -> Any:
            return self.rows[0] if self.rows else None

    class Hooked:
        """After the first SELECT is fully read, another connection commits a write."""

        def __init__(self, con: sqlite3.Connection) -> None:
            self.con = con

        def execute(self, sql: str, *args: Any) -> Any:
            rows = self.con.execute(sql, *args).fetchall()
            if not fired:
                fired.append(zc.set_values(db, "XAUUSD", "default", "w", AT2, "n", {"abn_atr": "2.5"}))
            return Rows(rows)

        def close(self) -> None:
            self.con.close()

    monkeypatch.setattr(zc, "_open_ro", lambda *a, **k: Hooked(real_open(*a, **k)))
    p, version = zc.load_params(db, "XAUUSD", "default")
    assert fired == [v0 + 1]  # the write really landed between the reader's statements
    # one coherent commit: either the old values with the old version, or the new with the new
    assert (p.abn_atr, version) in ((3.0, v0), (2.5, v0 + 1))


def test_set_repairs_a_broken_stored_value_and_stops_on_another_field(db: Path) -> None:
    _seeded(db)
    con = sqlite3.connect(db)
    con.execute("UPDATE zone_config_change SET value = 'broken' WHERE name = 'abn_atr'")
    con.commit()
    con.close()
    before = _rows(db)
    argv = ["set", "--market", "XAUUSD", "--set", "default", "--by", "t", "--note", "n", "--db", str(db)]
    # another field while abn_atr is broken: a clean stop naming the broken field, nothing written
    with pytest.raises(ConfigError, match="abn_atr"):
        zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"order_life_h": "24"})
    assert zc.main([*argv, "order_life_h=24"]) == 1
    assert _rows(db) == before
    # the repair itself: one row, exit 0, and the set loads again
    assert zc.main([*argv, "abn_atr=2.5"]) == 0
    rows = _rows(db)
    assert len(rows) == len(before) + 1 and rows[-1][3:5] == ("abn_atr", "2.5")
    assert zc.load_params(db, "XAUUSD", "default")[0].abn_atr == 2.5
    # repairing with the default's own text is also a write (the stored text did not parse)
    con = sqlite3.connect(db)
    con.execute("UPDATE zone_config_change SET value = 'broken' WHERE id = ?", (rows[-1][0],))
    con.commit()
    con.close()
    n = len(_rows(db))
    assert zc.main([*argv, "abn_atr=3.0"]) == 0
    assert len(_rows(db)) == n + 1


def test_only_main_reads_the_clock(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> datetime:
        raise AssertionError("the clock was read")

    monkeypatch.setattr(zc, "_now", boom)
    zc.seed(db, "XAUUSD", "default", "t", AT)
    zc.set_values(db, "XAUUSD", "default", "t", AT2, "n", {"abn_atr": "2.5"})
    zc.copy_set(db, "XAUUSD", "default", "XAUUSD", "alt", "t", AT2)
    zc.load_params(db, "XAUUSD", "default")
    zc.list_sets(db)
    zc.history(db, "XAUUSD", "default")
    with pytest.raises(AssertionError, match="clock"):
        zc.main(["seed", "--market", "XAUUSD", "--set", "x", "--by", "t", "--db", str(db)])
    src = (ROOT / "eye" / "zone_config.py").read_text(encoding="utf-8")
    assert src.count("datetime.now(") == 1  # only inside _now()


def test_refused_write_leaves_a_database_without_the_zone_table_as_it_was(db: Path) -> None:
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE other (x INTEGER)")
    con.commit()
    con.close()

    def objects() -> list[tuple[Any, ...]]:
        c = sqlite3.connect(db)
        try:
            return c.execute("SELECT type, name FROM sqlite_master").fetchall()
        finally:
            c.close()

    before = objects()
    with pytest.raises(ConfigError, match="no such set"):
        zc.set_values(db, "XAUUSD", "default", "t", AT, "n", {"abn_atr": "2.0"})
    with pytest.raises(ConfigError, match="no such set"):
        zc.copy_set(db, "XAUUSD", "default", "XAUUSD", "b", "t", AT)
    assert objects() == before
    with pytest.raises(ConfigError):
        zc.load_params(db, "XAUUSD", "default")
    assert objects() == before


def test_list_sets_validates_stored_names(db: Path) -> None:
    _seeded(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO zone_config_change (market, set_name, name, value, changed_at_utc, changed_by)"
        " VALUES ('XAUUSD', '..\\evil', 'abn_atr', '3.0', 'x', 'x')"
    )
    con.commit()
    con.close()
    with pytest.raises(ConfigError, match="evil"):
        zc.list_sets(db)


@pytest.mark.parametrize("bad", ["CON", "con", "Prn", "AUX", "nul", "COM1", "com9", "LPT1", "lpt9"])
def test_windows_reserved_names_refused(db: Path, bad: str) -> None:
    with pytest.raises(ConfigError, match="reserved"):
        zc.seed(db, bad, "default", "t", AT)
    with pytest.raises(ConfigError, match="reserved"):
        zc.seed(db, "XAUUSD", bad, "t", AT)
    assert not db.exists()
    zc.seed(db, "COM10", "console", "t", AT)  # not reserved


@pytest.mark.parametrize(
    ("name", "value"),
    [("tp_steps", "1"), ("tp_steps", None), ("near_frac", "0.1"), ("p1_frac", None), ("grid_ks", None),
     ("gate_w", None), ("grid_ks", ("a",)), ("step_mode", None), ("exec_tf", 5), ("abn_atr", 3)],
)  # fmt: skip
def test_wrong_types_give_a_value_error_naming_the_field(name: str, value: Any) -> None:
    with pytest.raises(ValueError, match=name) as e:
        ZoneParams(**{name: value})
    assert not isinstance(e.value, TypeError)


def test_fibonacci_table_untouched_by_every_cli_command(
    db: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE config_change (id INTEGER PRIMARY KEY AUTOINCREMENT, market TEXT, set_name TEXT,"
        " name TEXT, value TEXT, changed_at_utc TEXT, changed_by TEXT, note TEXT)"
    )
    con.execute(
        "INSERT INTO config_change (market, set_name, name, value) VALUES ('XAUUSD','default','min_r','2.0')"
    )
    con.commit()
    con.close()
    before = _rows(db, "config_change")

    statements: list[str] = []
    real_connect = sqlite3.connect

    def traced(*a: Any, **k: Any) -> sqlite3.Connection:
        c = real_connect(*a, **k)
        c.set_trace_callback(statements.append)
        return c

    monkeypatch.setattr(zc.sqlite3, "connect", traced)
    base = ["--db", str(db)]
    sm = ["--market", "XAUUSD", "--set", "default"]
    cmds = [
        ["seed", *sm, "--by", "t"],
        ["set", *sm, "--by", "t", "--note", "n", "abn_atr=2.5"],
        ["copy", *sm, "--to-market", "XAUUSD", "--to-set", "b", "--by", "t"],
        ["show", *sm],
        ["list"],
        ["history", *sm],
        ["history", *sm, "abn_atr"],
    ]
    for c in cmds:
        assert zc.main([*c, *base]) == 0
    monkeypatch.undo()
    capsys.readouterr()
    assert statements, "the trace saw nothing"
    # the table name as a whole word: zone_config_change contains it as a suffix only
    assert not [s for s in statements if re.search(r"(?<![A-Za-z_])config_change", s)]
    assert _rows(db, "config_change") == before


# --- independence (rule 0; acceptance case 7) -----------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.update(a.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            out.update((node.module or "").split("."))
            out.update(a.name for a in node.names)
    return out


def test_zone_config_imports_nothing_of_the_fibonacci_bot() -> None:
    assert _imports(ROOT / "eye" / "zone_config.py") & {"bot2e", "bot_config", "bot_research"} == set()


@pytest.mark.parametrize("name", ["bot2e.py", "bot_config.py", "bot_research.py"])
def test_the_fibonacci_bot_imports_nothing_of_the_zone_setup(name: str) -> None:
    assert _imports(ROOT / "eye" / name) & {"zone_config", "zone_bot"} == set()


def test_zone_bot_imports_nothing_of_the_fibonacci_bot_either() -> None:
    assert _imports(ROOT / "eye" / "zone_bot.py") & {"bot2e", "bot_config", "bot_research"} == set()
