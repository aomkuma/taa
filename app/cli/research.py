"""``python -m app.cli research``: the research harness (TAA-L707). Read-only on trading state.

* ``hypotheses``: the setup review's hypothesis set for one strategy over closed PLAN shadow trades (an engine
  database or scratch replay databases), as text or JSON.
* ``replay-family``: one-year ``advisory replay`` runs per symbol into ``data/research/fam_NAME_SYMBOL.db``,
  at idle priority, a few at a time, each started only while enough commit memory is free (four replays with
  the chart detectors once exhausted this machine's commit limit, and the DEMO engine shares it).
"""

from __future__ import annotations

import argparse
import ctypes
import glob
import json
import os

# Only this interpreter's own CLI is started (a fixed module, an argv list, no shell).
import subprocess  # nosec B404
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT

POLL_SECONDS = 30.0


def _databases(args: argparse.Namespace, settings_url: Callable[[], str]) -> list[str]:
    if not args.source_db:
        return [settings_url()]
    urls = []
    for pattern in args.source_db:
        matches = sorted(glob.glob(pattern)) or ([pattern] if "://" in pattern else [])
        if not matches:
            raise SystemExit(f"error: no database matches {pattern}")
        for path in matches:
            urls.append(path if "://" in path else f"sqlite:///{Path(path).resolve().as_posix()}")
    return urls


def _fmt(stat: dict[str, Any]) -> str:
    if not stat["n"]:
        return "n=0".ljust(26)
    if stat["low"] is None:
        return f"{stat['mean']:+.3f} n={stat['n']}".ljust(26)
    return f"{stat['mean']:+.3f} [{stat['low']:+.2f},{stat['high']:+.2f}] n={stat['n']}".ljust(26)


def _print_report(data: dict[str, Any]) -> None:
    print(
        f"{data['strategy']}  timeframes {','.join(data['timeframes'])}  signals {data['signals']}"
        f" (with a path {data['with_path']})  halves split at {data['split_at'][:10]}"
    )
    losers = data["losers"]
    print(
        f"  losers {losers['losers']}/{losers['trades']}; in favour before the stop: "
        + ", ".join(f"{k} R {100 * v:.0f}%" for k, v in losers["reached_before_stop"].items())
        + (
            f"; stopped trades that reached the target later {100 * losers['target_after_stop']:.0f}%"
            if losers["target_after_stop"] is not None
            else ""
        )
    )
    print(
        "  as traded by symbol: " + ", ".join(f"{k} {_fmt(v).strip()}" for k, v in data["by_symbol"].items())
    )
    group = None
    print(
        f"\n  {'hypothesis':44} {'all':26} {'first half':26} {'second half':26} paired: all / first / second"
    )
    for row in data["rows"]:
        if row["group"] != group:
            group = row["group"]
            print(f"  --- {group}")
        res, paired = row["result"], row["paired"]
        tail = ""
        if paired is not None:
            tail = " / ".join(
                f"{paired[h]['mean']:+.3f}" if paired[h]["mean"] is not None else "-"
                for h in ("all", "first", "second")
            )
        label = f"{row['label']} ({row['filled']}/{row['signals']})"
        print(f"  {label:44} {_fmt(res['all'])} {_fmt(res['first'])} {_fmt(res['second'])} {tail}")
    for title, key in (("own result", "walk_forward"), ("paired effect", "walk_forward_paired")):
        print(f"\n  walk-forward ({title}): best on one half, judged on the other")
        for wf in data[key]:
            print(
                f"    chosen on the {wf['chosen_on']} half among {wf['candidates']}: {wf['label']} "
                f"({wf['chosen_mean']:+.3f}) -> other half {_fmt(wf['judged']).strip()}"
            )
    print(
        f"\n  context rules chosen on one half ({data['context_candidates']} candidates), judged on the other"
    )
    for rule in data["context"]:
        print(
            f"    {rule['chosen_on']:6} {rule['feature']} {rule['op']} {rule['edge']:g}: "
            f"{rule['chosen_mean']:+.3f} (n={rule['chosen_n']}) -> {_fmt(rule['judged']).strip()}"
        )
    for note in data["notes"]:
        print(f"  ({note})")


def cmd_research_hypotheses(
    args: argparse.Namespace, settings_url: Callable[[], str], data_root: Path
) -> int:
    from app.learning.research import research
    from app.learning.research_data import load_inputs, load_signals
    from app.market_data.history_store import ParquetHistoryStore
    from app.storage.database import Database

    found = []
    for url in _databases(args, settings_url):
        db = Database(url)
        try:
            found += load_signals(db, strategy=args.strategy, source=args.source, timeframe=args.timeframe)
        finally:
            db.engine.dispose()
    inputs = load_inputs(found, ParquetHistoryStore(data_root))
    split = datetime.fromisoformat(args.split).replace(tzinfo=UTC) if args.split else None
    report = research(
        inputs.signals,
        inputs.paths,
        inputs.mirrors,
        inputs.frames,
        split_at=split,
        seed=args.seed,
        resamples=args.resamples,
    )
    data = report.to_dict()
    data["resolution"] = inputs.resolution
    data["skipped"] = inputs.skipped
    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        _print_report(data)
    return 0


# --- replay-family ------------------------------------------------------------------------------------------


class _MemoryStatus(ctypes.Structure):
    _fields_ = [  # ctypes needs a plain list
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def free_commit_gb() -> float | None:
    """Free commit memory (Windows: what the commit limit still allows); None where it cannot be read."""
    if sys.platform != "win32":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined,unused-ignore]
        return None
    return float(status.ullAvailPageFile) / 2**30


def _replay_command(args: argparse.Namespace, symbol: str) -> list[str]:
    cmd = [sys.executable, "-m", "app.cli", "--config", args.family_config, "advisory", "replay"]
    cmd += ["--server", args.server, "--symbols", symbol, "--start", args.start, "--end", args.end]
    cmd += ["--strategies", args.strategies, "--detectors", args.detectors, "--progress"]
    return cmd


def _popen_low_priority(cmd: list[str], env: dict[str, str], log_path: Path) -> subprocess.Popen[bytes]:
    with log_path.open("wb") as out:
        if sys.platform == "win32":
            return subprocess.Popen(  # noqa: S603  # nosec B603
                cmd,
                cwd=REPO_ROOT,
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.IDLE_PRIORITY_CLASS,
            )
        return subprocess.Popen(  # noqa: S603  # nosec B603
            cmd, cwd=REPO_ROOT, env=env, stdout=out, stderr=subprocess.STDOUT, preexec_fn=lambda: os.nice(19)
        )


def cmd_research_replay_family(
    args: argparse.Namespace,
    *,
    popen: Callable[[list[str], dict[str, str], Path], Any] = _popen_low_priority,
    free_gb: Callable[[], float | None] = free_commit_gb,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    out_dir = (REPO_ROOT / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    queue = [s for s in args.symbols.split(",") if s]
    running: list[tuple[str, Any]] = []
    failed: list[str] = []
    waited = False
    while queue or running:
        for symbol, proc in list(running):
            code = proc.poll()
            if code is not None:
                running.remove((symbol, proc))
                print(f"  {symbol} finished with exit code {code}", flush=True)
                if code != 0:
                    failed.append(symbol)
        if queue and len(running) < args.parallel:
            free = free_gb()
            if free is None or free >= args.min_free_gb:
                symbol = queue.pop(0)
                db_path = out_dir / f"fam_{args.name}_{symbol}.db"
                for stale in (
                    db_path,
                    db_path.with_name(db_path.name + "-wal"),
                    db_path.with_name(db_path.name + "-shm"),
                ):
                    stale.unlink(missing_ok=True)
                env = {
                    **os.environ,
                    "ENGINE_DB_URL": f"sqlite:///{db_path.as_posix()}",
                    "TRADING_MODE": "PAPER",
                }
                log_path = out_dir / f"fam_{args.name}_{symbol}.log"
                running.append((symbol, popen(_replay_command(args, symbol), env, log_path)))
                free_text = "unknown" if free is None else f"{free:.1f} GB"
                print(f"  {symbol} started (free commit {free_text}) -> {db_path.name}", flush=True)
                waited = False
                continue
            if not waited:
                print(f"  waiting: free commit {free:.1f} GB < {args.min_free_gb:g} GB", flush=True)
                waited = True
        sleep(args.poll)
    print(f"family {args.name} finished" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


Handler = Callable[[argparse.Namespace], int]


def add_parser(
    sub: argparse._SubParsersAction[argparse.ArgumentParser], *, hypotheses: Handler, replay_family: Handler
) -> argparse.ArgumentParser:
    res = sub.add_parser("research", help="research harness (hypothetical re-simulations; read-only)")
    res_sub = res.add_subparsers(dest="research_command", required=True)
    hyp = res_sub.add_parser("hypotheses", help="the setup review's hypothesis set for one strategy")
    hyp.add_argument("--strategy", required=True)
    hyp.add_argument(
        "--from",
        dest="source_db",
        action="append",
        default=None,
        help="engine-schema database: a path, a glob or a URL (repeatable; default: ENGINE_DB_URL)",
    )
    hyp.add_argument("--source", choices=["REPLAY", "LIVE"], default=None)
    hyp.add_argument("--timeframe", default=None, help="entry timeframe filter, e.g. M15 or H1")
    hyp.add_argument("--data", default="data/history")
    hyp.add_argument(
        "--split", default=None, help="ISO date of the walk-forward split (default: the midpoint)"
    )
    hyp.add_argument("--seed", type=int, default=0)
    hyp.add_argument("--resamples", type=int, default=1000)
    hyp.add_argument("--json", action="store_true")
    hyp.set_defaults(func=hypotheses)
    fam = res_sub.add_parser("replay-family", help="one-year advisory replay per symbol into data/research")
    fam.add_argument("name")
    fam.add_argument("--strategies", required=True)
    fam.add_argument("--detectors", required=True)
    fam.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY,XAUUSD")
    fam.add_argument("--server", default="FBS-Demo")
    fam.add_argument("--start", default="2025-10-15")
    fam.add_argument("--end", default="2026-10-05")
    fam.add_argument(
        "--family-config", default="config.yaml", help="config for the replays (e.g. an H1 copy)"
    )
    fam.add_argument("--out", default="data/research")
    fam.add_argument("--parallel", type=int, default=2)
    fam.add_argument(
        "--min-free-gb", type=float, default=3.0, help="start a replay only above this free commit"
    )
    fam.add_argument("--poll", type=float, default=POLL_SECONDS)
    fam.set_defaults(func=replay_family)
    return res
