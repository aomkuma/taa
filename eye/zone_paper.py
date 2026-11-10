"""Paper trading of the run-zone setup beside LIVE (the owner, 2026-11-10).

Every setup the simulation takes from ``--since`` on, at 0.01 lot a position, whatever the real account's
margin or risk allows - to compare, setup by setup, with what the LIVE runner could take. It is the
simulation itself (``eye/zone_bot.py`` / ``app.zone.core.run_zone``), unchanged, run on the LIVE server's
stored bars (``data/history/FBS-Real/XAUUSD``), cut at the last closed bar, from the arming epoch
(2023-10-01, as the runner arms); only the setups visited at or after ``--since`` are the paper's.

    python eye/zone_paper.py [--update] [--since "2026-11-10 12:00"] [--no-charts]

``--update`` first brings the stored bars up to date from the broker (read-only,
``scripts/download_history.py``; the broker's closed bars merged by open time). Outputs in
``eye/research/zone/XAUUSD/paper/``: ``positions.csv``, ``visits.csv``, ``summary.csv`` of the paper setups,
and a chart per traded one.
"""

from __future__ import annotations

import argparse
import dataclasses
import subprocess  # nosec B404 - runs this repository's own downloader
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.zone.core import TH, Bars, ZoneError, cut_bars, load_bars, run_zone  # noqa: E402
from app.zone.history_check import check_stored_history, required_frames  # noqa: E402
from app.zone.params import DEFAULT_DB, ConfigError, load_params  # noqa: E402
from eye.zone_bot import write_charts, write_outputs  # noqa: E402

SERVER = "FBS-Real"
EPOCH = "2023-10-01"


def update_bars(market: str) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "download_history.py"),
        "--symbols",
        market,
        "--timeframes",
        "D1,H4,H1,M15",
        "--days",
        "30",
    ]
    # read-only (the downloader sends no order); it connects with .env as it stands, so in LIVE mode it needs
    # the account's trading password and Algo Trading on, as the runner does
    subprocess.run(cmd, cwd=ROOT, check=True)  # noqa: S603  # nosec B603 - fixed arguments


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Paper trading of the run-zone setup (the simulation, forward).")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--market", default="XAUUSD")
    ap.add_argument("--set", dest="set_name", default="default")
    ap.add_argument("--since", default="2026-11-10 12:00", help="Thai time: the paper's first visit")
    ap.add_argument("--update", action="store_true", help="bring the stored bars up to date first")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-charts", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.update:
            update_bars(a.market)
        params, version = load_params(a.db, a.market, a.set_name)
        now = pd.Timestamp.now(tz="UTC")
        stored = load_bars(a.market, ROOT / "data" / "history" / SERVER / a.market)
        # as the runner starts (ZONE_LIVE L2): each frame cut to the simulation's first bar of that frame
        need = required_frames(params.exec_tf)
        check = check_stored_history(SERVER, {tf: stored.frame(tf) for tf in need}, params.exec_tf)
        if not check.ok:
            raise ZoneError("the stored history refuses the run: " + "; ".join(check.reasons))
        f = check.frames
        full = Bars(f["D1"], f["H4"], f["H1"], f["M15"], f.get("M5", stored.m5), stored.point)
        bars = cut_bars(full, now)
        start = pd.Timestamp(EPOCH, tz=TH)
        end = bars.h1["close_time"].iloc[-1]
        since = pd.Timestamp(a.since, tz=TH)
        res = run_zone(bars, params, start, end)
        paper = [o for o in res.outcomes if o.visit.time >= since]
        res = dataclasses.replace(res, outcomes=paper)
        zone = f"zone={a.market}/{a.set_name}@v{version} paper on {SERVER}"
        out_dir = Path(a.out) if a.out else ROOT / "eye" / "research" / "zone" / a.market / "paper"
        stats = write_outputs(out_dir, zone, params, since, end, res)
        n_charts = 0 if a.no_charts else len(write_charts(out_dir, res, bars, params))
    except (ConfigError, ZoneError, subprocess.CalledProcessError) as e:
        print(f"zone_paper: {e}", file=sys.stderr)
        return 1
    print(
        f"{zone}: since {since:%Y-%m-%d %H:%M} to {end.tz_convert(TH):%Y-%m-%d %H:%M} Thai; "
        f"setups {stats['setups']}, {stats['r_per_setup']:+.3f} R a setup, USD {stats['usd']:+.1f}, "
        f"open {stats['open']}, pending {stats['pending']}, charts {n_charts}; out {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
